"""The API of the user's own marks: favorites, flags, services abroad and greyed-out films."""

import time

from flask import Flask, jsonify, request

from watchlist_app import costs, providers, validation
from watchlist_app.config import valid_country
from watchlist_app.scan_service import ScanService
from watchlist_app.settings import AppSettings
from watchlist_app.store import Store


def register(app: Flask, store: Store, settings: AppSettings, service: ScanService) -> None:
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

    # ----- flags: watched and not now -----

    @app.get("/api/flags")
    def list_flags():
        return jsonify(store.list_flags())

    @app.put("/api/flags/<path:movie_key>")
    def set_flag(movie_key: str):
        body = request.get_json(silent=True) or {}
        now = time.time()
        # "Not now" lasts 30 days from now; the client does not choose the date.
        flag = validation.clean_flag(
            {"key": movie_key, "flag": body.get("flag"), "until": now + validation.NOT_NOW_SECONDS}, now
        )
        if flag is None:
            return jsonify({"error": "The flag must be watched or not_now."}), 400
        store.set_flag(flag["key"], flag["flag"], flag["until"])
        return jsonify({"ok": True, **flag})

    @app.delete("/api/flags/<path:movie_key>")
    def clear_flag(movie_key: str):
        store.clear_flag(movie_key)
        return jsonify({"ok": True})

    abroad_cache: dict[tuple, dict] = {}

    @app.get("/api/abroad")
    def abroad():
        """Films your services have abroad but not at home: {film key: {service: {country: kind}}}.

        `services` are the ticked services (comma separated); the data is stored, there is no TMDB request.
        """
        country = request.args.get("country") or settings.country
        if not valid_country(country):
            return jsonify({"error": "Unknown country."}), 400
        own = {name for name in request.args.get("services", "").split(",") if name and len(name) < 80}
        scan = store.latest_scan(country)
        if not scan or not own:
            return jsonify({})
        # The same answer for the same scan and the same services: keep the last few (it reads every country).
        cache_key = (country, scan["created"], store.offers_version, ",".join(sorted(own)))
        if cache_key in abroad_cache:
            return jsonify(abroad_cache[cache_key])
        films = [*scan["results"], *scan["unavailable"]]
        ids = [film["tmdb_id"] for film in films if isinstance(film.get("tmdb_id"), int)]
        raw = store.offers_for(ids)
        shown = {
            code: {tmdb_id: providers.display_providers(offers) for tmdb_id, offers in by_film.items()}
            for code, by_film in raw.items()
        }
        found = costs.abroad_map(shown, own, country)
        key_of = {
            film["tmdb_id"]: film.get("key") or str(film["tmdb_id"]) for film in films if film.get("tmdb_id")
        }
        answer = {key_of[tmdb_id]: services for tmdb_id, services in found.items() if tmdb_id in key_of}
        if len(abroad_cache) >= 8:
            abroad_cache.pop(next(iter(abroad_cache)))
        abroad_cache[cache_key] = answer
        return jsonify(answer)

    @app.get("/api/greyouts")
    def greyed_out():
        return jsonify(store.greyed_out_counts())

    @app.post("/api/greyouts/reset")
    def reset_greyed_out():
        return jsonify({"ok": True, **store.reset_greyed_out()})
