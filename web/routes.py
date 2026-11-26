"""Flask route registration for the web application."""

import os
import time  # noqa: F401  (tests patch time, tmdb, matches, requests and notifications through here)
from urllib.parse import urlsplit

import requests  # noqa: F401
from flask import Flask, jsonify, request

from watchlist_app import matches, notifications, tmdb  # noqa: F401
from watchlist_app.scan_service import ScanService
from watchlist_app.settings import AppSettings
from watchlist_app.store import Store
from web import api_data, api_scan, feeds, pages
from web.common import SORTS, status_overview  # noqa: F401

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


def register_routes(app: Flask, *, store: Store, settings: AppSettings, service: ScanService) -> None:
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    @app.after_request
    def keep_flags(response):
        # The flag pictures never change: the browser keeps them for a month instead of asking again.
        if request.path.startswith("/static/flags/"):
            response.headers["Cache-Control"] = "public, max-age=2592000"
        return response

    @app.errorhandler(413)
    def upload_too_large(error):
        return jsonify({"error": "The file is too large."}), 413

    @app.before_request
    def reject_cross_site_writes():
        if is_cross_site_write(request.method, request.headers, request.host):
            return jsonify({"error": "Requests from other web sites are not allowed."}), 403
        return None

    @app.context_processor
    def header_context():
        """The header is the same on every page: country and the state of the data."""
        created = store.latest_scan_created(settings.country)
        age = time.time() - created if created else None
        stale = age is None or age > 24 * 3600
        return {
            "header_country": settings.country,
            "header_countries": settings.country_choices(),
            "sync_state": "stale" if stale else "ok",
            "sync_text": "Out of date" if stale else "Synced",
        }

    for module in (pages, api_scan, api_data, feeds):
        module.register(app, store, settings, service)
