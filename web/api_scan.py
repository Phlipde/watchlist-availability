"""The scan API, title matches and the stored offers of a film per country."""

import time

from flask import Flask, jsonify, request

from watchlist_app import costs, letterboxd, matches, providers, tmdb, together
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

    @app.get("/api/together")
    def together_result():
        """The active profile's list merged with those in ?with=2,3, in the active profile's country."""
        s, pid = active_settings(settings), active_profile_id()
        names = {profile["id"]: profile["name"] for profile in store.list_profiles()}
        try:
            asked = [int(part) for part in (request.args.get("with") or "").split(",") if part.strip()]
        except ValueError:
            return jsonify({"error": "Name the other profiles by id, e.g. ?with=2,3."}), 400
        partners = [member for member in dict.fromkeys(asked) if member != pid]
        if not partners or any(member not in names for member in partners):
            return jsonify({"error": "Choose one or more other profiles."}), 400
        country = s.country
        fresh_seconds = max(s.scan_interval_hours, 24) * 3600
        now = time.time()
        members, missing, own_scan = [], [], None
        for member in [pid, *partners]:
            scan = store.latest_scan(country, profile_id=member)
            if member == pid:
                own_scan = scan
            elif scan is None or now >= scan["created"] + fresh_seconds:
                missing.append(member)  # an old scan still counts; the page may offer a new one
            films = (
                with_changes(store, country, scan["results"], scan["unavailable"], profile_id=member)
                if scan
                else {"results": None, "unavailable": []}
            )
            hidden = {flag["key"] for flag in store.list_flags(profile_id=member)} | {
                favorite["key"]
                for favorite in store.list_favorites(profile_id=member)
                if favorite["status"] == "watched"  # the grid hides these too
            }
            watched = store.watched_keys(profile_id=member)
            members.append(
                {
                    "id": member,
                    "name": names[member],
                    "results": films["results"],
                    "unavailable": films["unavailable"],
                    "watched": watched
                    | {str(tmdb_id) for tmdb_id in store.watched_tmdb_ids(profile_id=member)},
                    "hidden": hidden,
                    "subscriptions": settings.for_profile(member).subscriptions(country),
                    "changes": films.get("changes", []),
                }
            )
        merged = together.merge(members)
        info = {
            "together": {
                "members": merged["members"],
                "groups": merged["groups"],
                "service_owners": merged["service_owners"],
            },
            "missing": missing,
            "subscriptions": merged["subscriptions"],
        }
        if own_scan is None:
            return jsonify({"available": False, "stale": True, **info})
        results = costs.mark_only_on_my_services(merged["results"], merged["subscriptions"])
        return jsonify(
            {
                "available": True,
                "stale": now >= own_scan["created"] + fresh_seconds,
                **own_scan,
                "results": results,
                "unavailable": merged["unavailable"],
                "changes": members[0]["changes"],
                "free_services": sorted(providers.mostly_free_from_scan(results, merged["unavailable"])),
                "rental_shops": sorted(providers.rental_from_scan(results, merged["unavailable"])),
                **info,
            }
        )

    @app.route("/api/scan", methods=["GET", "POST"])
    def start_scan():
        if request.method == "GET":
            return jsonify(
                {
                    "message": "Use POST /api/scan to start a scan.",
                    "status_endpoint": "/api/scan/<job_id>",
                }
            )
        s, pid = active_settings(settings), active_profile_id()
        if not s.tmdb_api_key:
            return jsonify({"error": "TMDB_API_KEY is missing."}), 400
        source = (request.get_json(silent=True) or {}) if request.is_json else request.form
        country = source.get("country", s.country)
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
        job_id, reconnected = service.start(country, entries=entries, source_name=source_name, profile_id=pid)
        return jsonify({"job_id": job_id, "reconnected": True} if reconnected else {"job_id": job_id})

    @app.get("/api/scan/<job_id>")
    def scan_status(job_id: str):
        status = service.status(
            job_id, start=request.args.get("from", 0, type=int), profile_id=active_profile_id()
        )
        if status is None:
            return jsonify({"error": "Scan not found."}), 404
        return jsonify(status)

    @app.post("/api/scan/<job_id>/cancel")
    def cancel_scan(job_id: str):
        if not service.cancel(job_id, profile_id=active_profile_id()):
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
