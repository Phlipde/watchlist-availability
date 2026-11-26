"""The scan API, title matches and the stored offers of a film per country."""

import time

from flask import Flask, jsonify, request

from watchlist_app import costs, letterboxd, matches, providers, tmdb
from watchlist_app.config import valid_country
from watchlist_app.scan_service import ScanService, with_changes
from watchlist_app.settings import AppSettings
from watchlist_app.store import Store
from web.common import active_profile_id, active_settings


def register(app: Flask, store: Store, settings: AppSettings, service: ScanService) -> None:
    # ----- scans -----

    @app.get("/api/latest")
    def latest_result():
        s, pid = active_settings(settings), active_profile_id()
        country = request.args.get("country") or s.country
        if not valid_country(country):
            return jsonify({"error": "Unknown country."}), 400
        scan = store.latest_scan(country, profile_id=pid)
        # The country's own services come along, so a country switch needs no reload.
        own = s.subscriptions(country)
        if not scan:
            return jsonify({"available": False, "stale": True, "subscriptions": own})
        annotated = with_changes(store, scan["country"], scan["results"], scan["unavailable"], profile_id=pid)
        annotated["results"] = costs.mark_only_on_my_services(annotated["results"], own)
        # Older than a day (or the schedule interval) counts as stale, also with the schedule off.
        stale = time.time() >= scan["created"] + max(s.scan_interval_hours, 24) * 3600
        return jsonify({"available": True, "stale": stale, **scan, **annotated, "subscriptions": own})

    @app.route("/api/scan", methods=["GET", "POST"])
    def start_scan():
        if request.method == "GET":
            return jsonify(
                {
                    "message": "Use POST /api/scan to start a scan.",
                    "status_endpoint": "/api/scan/<job_id>",
                }
            )
        # shortcut: ScanService scans for profile 1 only; per-profile scans come with M2.
        if active_profile_id() != 1:
            return jsonify({"error": "Scans for other profiles come in a later update."}), 409
        if not settings.tmdb_api_key:
            return jsonify({"error": "TMDB_API_KEY is missing."}), 400
        source = (request.get_json(silent=True) or {}) if request.is_json else request.form
        country = source.get("country", settings.country)
        if not valid_country(country):
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

    @app.get("/api/films/<int:tmdb_id>/countries")
    def film_countries(tmdb_id: int):
        # From the stored scan data only, never a TMDB request: {country: {service: kinds}}.
        stored = store.offers_by_country(tmdb_id)
        return jsonify({country: providers.display_providers(offers) for country, offers in stored.items()})
