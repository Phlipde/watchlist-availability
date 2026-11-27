"""Flask route registration for the web application."""

import gzip
import hashlib
import os
import time  # noqa: F401  (tests patch time, tmdb, matches, requests and notifications through here)
from urllib.parse import urlsplit

import requests  # noqa: F401
from flask import Flask, g, jsonify, request

from watchlist_app import matches, notifications, tmdb  # noqa: F401
from watchlist_app.scan_service import ScanService
from watchlist_app.settings import AppSettings
from watchlist_app.store import Store
from web import api_data, api_scan, feeds, pages
from web.common import PROFILE_COOKIE, SORTS, active_settings, page, status_overview  # noqa: F401

MAX_UPLOAD_BYTES = 50 * 1024 * 1024

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _trusted_hosts() -> set[str]:
    """Extra host names the app is reached under, e.g. behind a reverse proxy (comma-separated)."""
    return {
        host.strip().lower() for host in os.getenv("WATCHLIST_TRUSTED_HOSTS", "").split(",") if host.strip()
    }


def is_cross_site_write(method: str, headers, host: str) -> bool:
    """True for a changing request that another web site made the browser send.

    Without this, any page the user visits could post to the app in the home
    network (for example a prepared backup). Browsers mark the origin of a
    request; requests without these headers (command line, curl, Home Assistant)
    are allowed.
    """
    if method not in WRITE_METHODS:
        return False
    fetch_site = headers.get("Sec-Fetch-Site")
    if fetch_site is not None:
        return fetch_site not in {"same-origin", "none"}
    origin = headers.get("Origin")
    if not origin:
        return False
    origin_host = urlsplit(origin).netloc.lower()
    allowed = {host.lower(), *_trusted_hosts()}
    forwarded = headers.get("X-Forwarded-Host")
    if forwarded:
        allowed.update(part.strip().lower() for part in forwarded.split(","))
    return origin_host not in allowed


EMAIL_HEADER = "Cf-Access-Authenticated-User-Email"


def profile_for_request(profiles: list[dict]) -> int:
    """The profile this request is for: ?profile=<id> (GET only), the wl_profile cookie, the Cloudflare
    Access e-mail, else profile 1 (the lowest id when 1 is gone). Unknown values fall to the next step."""
    ids = {profile["id"] for profile in profiles}
    query = request.args.get("profile") if request.method == "GET" else None
    for raw in (query, request.cookies.get(PROFILE_COOKIE)):
        try:
            if int(raw or "") in ids:
                return int(raw or "")
        except ValueError:
            pass
    email = request.headers.get(EMAIL_HEADER, "").strip().lower()
    for profile in profiles:  # ordered by id: the lowest wins when two share an address
        if email and (profile["email"] or "").lower() == email:
            return profile["id"]
    return 1 if 1 in ids else min(ids)


def ago_text(seconds: float) -> str:
    """ "12 min ago", "3 h ago" or "4 days ago", the same words as ago() in static/js/ui.js."""
    minutes = int(seconds // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    return f"{minutes // 60} h ago" if minutes < 48 * 60 else f"{minutes // 1440} days ago"


# Scripts and styles from /static: packed like JSON and HTML, cached a year when the address has a version.
_STATIC_TYPES = {"text/javascript", "application/javascript", "text/css"}
_packed: dict[tuple[str, str], bytes] = {}  # (path, ETag) -> gzip body: the files only change with a deploy
_versions: dict[tuple[str, int], str] = {}  # (file, mtime) -> short content hash


def static_version(folder: str, filename: str) -> str:
    """A short hash of the file content: a new address whenever the file changes, so it can be cached long."""
    path = os.path.join(folder, filename)
    try:
        key = (path, os.stat(path).st_mtime_ns)
    except OSError:
        return ""
    if key not in _versions:
        with open(path, "rb") as file:
            _versions[key] = hashlib.sha256(file.read()).hexdigest()[:10]
    return _versions[key]


def register_routes(app: Flask, *, store: Store, settings: AppSettings, service: ScanService) -> None:
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    @app.url_defaults
    def version_static(endpoint, values):
        # Every url_for("static", ...) gets ?v=<content hash> instead of a hand-written v=: nothing to bump.
        # Our own modules stay without it: they import each other by bare name, and a preload or script tag
        # with ?v= would be a second address for the same module (fetched twice).
        filename = values.get("filename") or ""
        own_module = filename.endswith(".js") and not filename.endswith(".min.js")
        if endpoint == "static" and filename and app.static_folder and not own_module:
            values["v"] = static_version(app.static_folder, filename) or values.get("v")

    @app.after_request
    def keep_static(response):
        # A versioned address never changes its content; modules imported without ?v= keep asking (no-cache).
        if (
            request.path.startswith("/static/")
            and request.args.get("v")
            and response.status_code in {200, 304}
        ):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif request.path.startswith("/static/flags/"):  # flags never change: a month
            response.headers["Cache-Control"] = "public, max-age=2592000"
        return response

    @app.after_request
    def compress(response):
        # The film list is close to 1 MB of JSON and is fetched on every page; gzip makes it about a tenth.
        # Scripts and styles too (tabler.min.css alone is 1 MB); those are packed once per file version.
        static = response.mimetype in _STATIC_TYPES and request.path.startswith("/static/")
        if (
            response.status_code != 200
            or (response.is_streamed and not static)  # a sent file counts as streamed
            or (response.direct_passthrough and not static)
            or "Content-Encoding" in response.headers
            or (response.mimetype not in {"application/json", "text/html"} and not static)
            or "gzip" not in request.headers.get("Accept-Encoding", "")
            or request.range is not None
        ):
            return response
        response.direct_passthrough = False  # read the file so it can be packed
        key = (request.path, response.get_etag()[0] or "")
        if static and key in _packed:
            packed = _packed[key]
        else:
            data = response.get_data()
            if len(data) < 2048:
                return response
            packed = gzip.compress(data, compresslevel=5)
            if static:
                _packed[key] = packed
        response.set_data(packed)
        response.headers["Content-Encoding"] = "gzip"
        response.vary.add("Accept-Encoding")
        return response

    @app.errorhandler(413)
    def upload_too_large(error):
        return jsonify({"error": "The file is too large."}), 413

    @app.errorhandler(404)
    def not_found(error):
        """A page in the app's own look with the header; the API keeps answering in JSON."""
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found."}), 404
        return page("not-found.html", path=request.path), 404

    @app.before_request
    def reject_cross_site_writes():
        if is_cross_site_write(request.method, request.headers, request.host):
            return jsonify({"error": "Requests from other web sites are not allowed."}), 403
        return None

    @app.before_request
    def choose_profile():
        g.profiles = store.list_profiles()
        g.profile_id = profile_for_request(g.profiles)

    @app.context_processor
    def header_context():
        """The header is the same on every page: profile, country and the state of the data."""
        s = active_settings(settings)
        created = store.latest_scan_created(s.country, profile_id=s.profile_id)
        age = time.time() - created if created else None
        stale = age is None or age > 24 * 3600
        return {
            "header_country": s.country,
            "header_countries": s.country_choices(),
            "sync_state": "stale" if stale else "ok",
            "sync_text": "Not synced yet"
            if age is None
            else f"{'Out of date ·' if stale else 'Synced'} {ago_text(age)}",
            "profiles": g.profiles,
            "active_profile": next(p for p in g.profiles if p["id"] == g.profile_id),
        }

    for module in (pages, api_scan, api_data, feeds):
        module.register(app, store, settings, service)
