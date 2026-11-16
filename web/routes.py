"""Flask route registration for the web application."""

import json
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, Response, jsonify, make_response, render_template, request, send_file

from watchlist_app import costs, letterboxd, matches, providers, scheduler, tmdb, validation
from watchlist_app.config import COUNTRIES
from watchlist_app.scan_service import ScanService, with_changes
from watchlist_app.settings import SCAN_INTERVALS_HOURS, AppSettings
from watchlist_app.store import Store
from watchlist_app.tmdb import _TMDB_IMAGE_BASE_URL, _TMDB_LOGO_BASE_URL

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def status_overview(store: Store, settings: AppSettings, service: ScanService) -> dict:
    """What the status page shows: recent scan runs, the schedule and the size of the data."""
    jobs = []
    for job in store.list_jobs(limit=20):
        end = job["finished_at"] or job["heartbeat_at"] or job["started_at"]
        jobs.append(
            {
                "id": job["id"],
                "status": job["status"],
                "trigger": job["trigger"],
                "country": job["country"],
                "source_name": job["source_name"],
                "message": job["message"],
                "started_at": job["started_at"],
                "duration_seconds": round(end - job["started_at"], 1),
                "completed": job["completed"],
                "total": job["total"],
                "available": job["available"],
                "unavailable": job["unavailable"],
                "failed": job["failed"],
                "tmdb_requests": job["tmdb_requests"],
                "reused": job["reused"],
            }
        )
    latest = store.latest_scan(settings.country)
    database = Path(store.path) if store.path != ":memory:" else None
    catalog = store.provider_catalog(settings.country)
    return {
        "uncertain_matches": len(matches.list_matches(store)),
        "provider_catalog": {
            "count": len(catalog),
            "fetched_at": max((item["fetched_at"] for item in catalog), default=None),
        },
        "country": settings.country,
        "running": service.is_running(),
        "last_scan_at": latest["created"] if latest else None,
        "scan_interval_hours": settings.scan_interval_hours,
        "next_scan_at": scheduler.next_scan_at(store, settings),
        "jobs": jobs,
        "counts": store.counts(),
        "database_bytes": database.stat().st_size if database and database.exists() else None,
        "tmdb_api_key_set": bool(settings.tmdb_api_key),
        "reminders": costs.reminders({country: settings.costs(country) for country in COUNTRIES}),
    }


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

    @app.errorhandler(413)
    def upload_too_large(error):
        return jsonify({"error": "The file is too large."}), 413

    @app.before_request
    def reject_cross_site_writes():
        if is_cross_site_write(request.method, request.headers, request.host):
            return jsonify({"error": "Requests from other web sites are not allowed."}), 403
        return None

    def page(template: str, **context):
        response = make_response(render_template(template, **context))
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @app.route("/")
    def index():
        latest = store.latest_scan(settings.country)
        free_services = (
            providers.mostly_free_from_scan(latest["results"], latest["unavailable"])
            if latest
            else providers.MOSTLY_FREE
        )
        initial_filters = {
            "query": request.args.get("q", ""),
            "availability": request.args.get("availability", "all"),
            "kind": request.args.get("kind", "all"),
            "min_rating": request.args.get("rating", "0"),
            "sort": request.args.get("sort", "title"),
        }
        return page(
            "index.html",
            provider_groups=providers.provider_groups(settings.loaded_providers()),
            mostly_free_providers=free_services,
            selected=settings.subscriptions(),
            country=settings.country,
            countries=list(COUNTRIES),
            initial_filters=initial_filters,
            client_config={
                "imageBaseUrl": _TMDB_IMAGE_BASE_URL,
                "initialFilters": initial_filters,
                "subscriptions": {country: settings.subscriptions(country) for country in COUNTRIES},
                "rentalShops": sorted(providers.RENTAL_SHOPS),
                "freeServices": sorted(free_services),
                "logoBaseUrl": _TMDB_LOGO_BASE_URL,
                # Logos of the providers loaded from TMDB, for the availability in the details.
                "providerLogos": {
                    providers.display_name(item["name"]): path
                    for item in store.provider_catalog()
                    if (path := validation.image_path(item["logo_path"]))
                },
            },
        )

    @app.get("/settings")
    def settings_page():
        return page(
            "settings.html",
            settings=settings.as_dict(),
            countries=list(COUNTRIES),
            intervals=SCAN_INTERVALS_HOURS,
            provider_groups=providers.provider_groups(settings.loaded_providers()),
            subscriptions={country: settings.subscriptions(country) for country in COUNTRIES},
        )

    @app.get("/status")
    def status_page():
        return page("status.html", status=status_overview(store, settings, service))

    @app.get("/costs")
    def costs_page():
        scan = store.latest_scan(settings.country)
        return page(
            "costs.html",
            country=settings.country,
            last_scan_at=scan["created"] if scan else None,
            costs=costs.overview(scan["results"] if scan else [], settings.subscriptions(), settings.costs()),
        )

    @app.get("/matches")
    def matches_page():
        return page(
            "matches.html",
            client_config={"imageBaseUrl": _TMDB_IMAGE_BASE_URL, "country": settings.country},
            tmdb_api_key_set=bool(settings.tmdb_api_key),
        )

    @app.get("/manifest.webmanifest")
    def manifest():
        return send_file(
            Path(__file__).parent.parent / "manifest.webmanifest",
            mimetype="application/manifest+json",
        )

    # ----- scans -----

    @app.get("/api/latest")
    def latest_result():
        country = request.args.get("country") or None
        scan = store.latest_scan(country)
        if not scan:
            return jsonify({"available": False, "stale": True})
        annotated = with_changes(store, scan["country"], scan["results"], scan["unavailable"])
        annotated["results"] = costs.mark_only_on_my_services(
            annotated["results"], settings.subscriptions(scan["country"])
        )
        # Older than a day (or the schedule interval) counts as stale, also with the schedule off.
        stale = time.time() >= scan["created"] + max(settings.scan_interval_hours, 24) * 3600
        return jsonify({"available": True, "stale": stale, **scan, **annotated})

    @app.route("/api/scan", methods=["GET", "POST"])
    def start_scan():
        if request.method == "GET":
            return jsonify(
                {
                    "message": "Use POST /api/scan to start a scan.",
                    "status_endpoint": "/api/scan/<job_id>",
                }
            )
        if not settings.tmdb_api_key:
            return jsonify({"error": "TMDB_API_KEY is missing."}), 400
        source = (request.get_json(silent=True) or {}) if request.is_json else request.form
        country = source.get("country", settings.country)
        if country not in COUNTRIES:
            return jsonify({"error": "Unsupported country."}), 400
        entries = None
        source_name = None
        uploaded_file = request.files.get("watchlist")
        if uploaded_file and uploaded_file.filename:
            try:
                entries = letterboxd.parse_watchlist_csv(uploaded_file.read().decode("utf-8"))
                source_name = uploaded_file.filename
            except (UnicodeDecodeError, ValueError) as exc:
                return jsonify({"error": f"Could not read CSV: {exc}"}), 400
        job_id, reconnected = service.start(country, entries=entries, source_name=source_name)
        return jsonify({"job_id": job_id, "reconnected": True} if reconnected else {"job_id": job_id})

    @app.get("/api/scan/<job_id>")
    def scan_status(job_id: str):
        status = service.status(job_id, start=request.args.get("from", 0, type=int))
        if status is None:
            return jsonify({"error": "Scan not found."}), 404
        return jsonify(status)

    @app.post("/api/scan/<job_id>/cancel")
    def cancel_scan(job_id: str):
        if not service.cancel(job_id):
            return jsonify({"error": "Scan not found."}), 404
        return jsonify({"ok": True})

    # ----- title matches -----

    @app.get("/api/matches")
    def list_matches():
        include_certain = request.args.get("all") in {"1", "true"}
        return jsonify(matches.list_matches(store, include_certain=include_certain))

    @app.get("/api/matches/search")
    def search_matches():
        query = (request.args.get("q") or "").strip()
        if not query:
            return jsonify({"error": "Enter a title to search for."}), 400
        if not settings.tmdb_api_key:
            return jsonify({"error": "TMDB_API_KEY is missing."}), 400
        try:
            found = tmdb.search_movies(query, request.args.get("year") or None, settings.tmdb_api_key)
        except tmdb.TmdbError as exc:
            return jsonify({"error": str(exc)}), 502
        return jsonify(found)

    @app.put("/api/matches/<path:film_key>")
    def correct_match(film_key: str):
        body = request.get_json(silent=True) or {}
        tmdb_id = matches.parse_tmdb_reference(body.get("tmdb_id"))
        if tmdb_id is None:
            return jsonify({"error": "Enter a TMDB id or a themoviedb.org film link."}), 400
        if not settings.tmdb_api_key:
            return jsonify({"error": "TMDB_API_KEY is missing."}), 400
        try:
            corrected = matches.correct_match(store, film_key, tmdb_id, settings.tmdb_api_key)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except tmdb.TmdbError as exc:
            return jsonify({"error": str(exc)}), 502
        return jsonify({"ok": True, **corrected})

    @app.delete("/api/matches/<path:film_key>")
    def reset_match(film_key: str):
        if store.get_id(film_key) is None:
            return jsonify({"error": "This watchlist entry is unknown."}), 404
        matches.reset_match(store, film_key)
        return jsonify({"ok": True})

    # ----- favorites -----

    @app.get("/api/favorites")
    def list_favorites():
        return jsonify(store.list_favorites())

    @app.post("/api/favorites")
    def add_favorite():
        favorite = validation.clean_favorite(request.get_json(silent=True) or {})
        if favorite is None:
            return jsonify({"error": "A movie key and title are required."}), 400
        store.add_favorite(favorite)
        return jsonify({"ok": True})

    @app.patch("/api/favorites/<path:movie_key>")
    def update_favorite(movie_key: str):
        changes = request.get_json(silent=True) or {}
        updates = {key: value for key, value in changes.items() if key in {"status", "notes"}}
        if not updates:
            return jsonify({"error": "No favorite fields supplied."}), 400
        if "status" in updates and updates["status"] not in validation.FAVORITE_STATUSES:
            return jsonify({"error": "Invalid favorite status."}), 400
        if "notes" in updates:
            updates["notes"] = validation.text(updates["notes"], validation.MAX_NOTES) or ""
        store.update_favorite(movie_key, updates)
        return jsonify({"ok": True})

    @app.delete("/api/favorites/<path:movie_key>")
    def remove_favorite(movie_key: str):
        store.remove_favorite(movie_key)
        return jsonify({"ok": True})

    # ----- settings, status, backup -----

    @app.get("/api/settings")
    def get_settings():
        return jsonify(settings.as_dict())

    @app.put("/api/settings")
    def put_settings():
        changes = request.get_json(silent=True)
        if not isinstance(changes, dict):
            return jsonify({"error": "Send the settings as a JSON object."}), 400
        try:
            settings.update(changes)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(settings.as_dict())

    @app.get("/api/status")
    def get_status():
        return jsonify(status_overview(store, settings, service))

    @app.get("/api/backup")
    def download_backup():
        name = f"watchlist-backup-{time.strftime('%Y-%m-%d')}.json"
        return Response(
            json.dumps(store.export_backup()),
            mimetype="application/json",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @app.post("/api/backup")
    def restore_backup():
        uploaded = request.files.get("backup")
        if uploaded is None:
            return jsonify({"error": "Choose a backup file."}), 400
        try:
            backup = json.loads(uploaded.read().decode("utf-8"))
            counts = store.import_backup(backup)
        except (UnicodeDecodeError, ValueError) as exc:
            message = str(exc) if "backup" in str(exc) else "The file is not valid JSON."
            return jsonify({"error": message}), 400
        restored, skipped = settings.restore(backup.get("settings"))
        counts["settings"] = restored
        counts["skipped"] += skipped
        return jsonify({"ok": True, "imported": counts})
