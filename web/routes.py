"""Flask route registration for the web application."""

import threading
import time
import uuid
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, make_response, render_template, request, send_file

from . import cache, favorites, scans, serialization

STALE_SCAN_SECONDS = 30 * 60


def register_routes(
    app: Flask,
    *,
    jobs: dict[str, dict],
    jobs_lock: threading.Lock,
    result_cache: dict[str, dict],
    cache_path: Path,
    latest_result_path: Path,
    favorites_path: Path,
    wa,
) -> None:
    def favorites_db():
        return favorites.connect(favorites_path)

    def provider_groups() -> list[tuple[str, list[tuple[str, list[str]]]]]:
        standard = {
            "Arte", "Molotov", "Pluto TV", "Plex", "Netflix", "Canal+", "TF1+",
            "M6+", "Prime Video", "Disney+", "Apple TV+", "Paramount+", "HBO Max",
            "Crunchyroll", "MUBI",
        }
        germany = [
            name for name in wa._ALL_PROVIDERS
            if name not in standard and "Amazon Channel" not in name and "Amazon Channels" not in name
        ]
        amazon_channels = [
            name for name in wa._ALL_PROVIDERS
            if "Amazon Channel" in name or "Amazon Channels" in name
        ]
        return [
            ("Services", [
                ("Free and ad-supported", ["Arte", "Molotov", "Pluto TV", "Plex"]),
                ("Subscriptions", [
                    "Netflix", "Canal+", "TF1+", "M6+", "Prime Video", "Disney+",
                    "Apple TV+", "Paramount+", "HBO Max", "Crunchyroll", "MUBI",
                ]),
                ("German and specialty services", germany),
            ]),
            ("Amazon Channels", [("Amazon Channels", amazon_channels)]),
        ]

    def mostly_free_providers() -> set[str]:
        return {
            "Arte", "Molotov", "Pluto TV", "Plex", "ARD Mediathek",
            "filmfriend", "Netzkino", "YouTube Free", "ZDF", "Alleskino",
            "Joyn", "Amazon MX Player", "Amazon Prime Video Free with Ads",
            "Amazon Prime Video with Ads", "Plex Channel",
        }

    def all_targets() -> dict[str, str]:
        return dict(wa._ALL_PROVIDERS)

    def default_selection() -> list[str]:
        return list(wa.load_platforms_config(wa.COUNTRY).keys())

    @app.route("/")
    def index():
        response = make_response(render_template(
            "index.html",
            provider_groups=provider_groups(),
            mostly_free_providers=mostly_free_providers(),
            selected=default_selection(),
            targets=all_targets(),
            country=wa.COUNTRY,
            countries=["FR", "DE", "US", "GB"],
            initial_filters={
                "query": request.args.get("q", ""),
                "availability": request.args.get("availability", "all"),
                "kind": request.args.get("kind", "all"),
                "min_rating": request.args.get("rating", "0"),
                "sort": request.args.get("sort", "title"),
            },
            image_base_url=wa._TMDB_IMAGE_BASE_URL,
        ))
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @app.get("/sw.js")
    def service_worker():
        return send_file(Path(__file__).parent.parent / "sw.js", mimetype="application/javascript")

    @app.get("/manifest.webmanifest")
    def manifest():
        return send_file(
            Path(__file__).parent.parent / "manifest.webmanifest",
            mimetype="application/manifest+json",
        )

    @app.get("/api/latest")
    def latest_result():
        snapshot = cache.load_snapshot(latest_result_path)
        requested_country = request.args.get("country")
        if requested_country and snapshot.get("country") not in {None, requested_country}:
            return jsonify({"available": False})
        if not snapshot:
            return jsonify({"available": False})
        return jsonify({"available": True, **snapshot})

    @app.route("/api/scan", methods=["GET", "POST"])
    def start_scan():
        if request.method == "GET":
            return jsonify({
                "message": "Use POST /api/scan to start a scan.",
                "status_endpoint": "/api/scan/<job_id>",
            })
        if not wa.TMDB_API_KEY:
            return jsonify({"error": "TMDB_API_KEY is missing."}), 400
        payload = request.get_json(silent=True) or {}
        country = (
            payload.get("country", wa.COUNTRY)
            if request.is_json
            else request.form.get("country", wa.COUNTRY)
        )
        if country not in {"FR", "DE", "US", "GB"}:
            return jsonify({"error": "Unsupported country."}), 400
        with jobs_lock:
            now = time.time()
            for stale_job in jobs.values():
                if (
                    stale_job.get("status") == "running"
                    and now - stale_job.get("heartbeat_at", now) > STALE_SCAN_SECONDS
                ):
                    stale_job.update({
                        "status": "error",
                        "phase": "Error",
                        "message": "The scan expired and was stopped.",
                        "cancel_requested": True,
                    })
            active_job = next(
                (
                    (job_id, job)
                    for job_id, job in jobs.items()
                    if job.get("status") == "running"
                ),
                None,
            )
            if active_job is not None:
                return jsonify({
                    "job_id": active_job[0],
                    "reconnected": True,
                })
        uploaded_dataframe = None
        uploaded_source = None
        uploaded_file = request.files.get("watchlist")
        if uploaded_file and uploaded_file.filename:
            try:
                uploaded_dataframe = pd.read_csv(uploaded_file)
                missing = [
                    column for column in ("Name", "Year")
                    if column not in uploaded_dataframe.columns
                ]
                if missing:
                    return jsonify({
                        "error": f"CSV is missing columns: {', '.join(missing)}."
                    }), 400
                uploaded_source = uploaded_file.filename
            except (UnicodeDecodeError, ValueError) as exc:
                return jsonify({"error": f"Could not read CSV: {exc}"}), 400
        job_id = uuid.uuid4().hex
        with jobs_lock:
            jobs[job_id] = {
                "job_id": job_id,
                "status": "running", "phase": "Starting",
                "message": "Preparing scan...", "completed": 0, "total": 0,
                "current_title": "", "results": [],
                "stats": serialization.result_stats([]), "unavailable": [],
                "last_updated": None,
                "started_at": time.time(),
                "heartbeat_at": time.time(),
                "failed": [],
                "uploaded_dataframe": uploaded_dataframe,
                "uploaded_source": uploaded_source,
                "cancel_requested": False, "country": country,
            }
        threading.Thread(
            target=scans.run_scan,
            args=(
                job_id, country, jobs, jobs_lock, result_cache, cache_path,
                latest_result_path, wa,
            ),
            daemon=True,
        ).start()
        return jsonify({"job_id": job_id})

    @app.get("/api/scan/<job_id>")
    def scan_status(job_id: str):
        with jobs_lock:
            job = jobs.get(job_id)
            if job is None:
                return jsonify({"error": "Scan not found."}), 404
            return jsonify({
                key: value for key, value in job.items()
                if key != "uploaded_dataframe"
            })

    @app.get("/api/favorites")
    def list_favorites():
        rows = favorites.rows(favorites_path)
        return jsonify([
            {
                "key": row[0], "title": row[1], "year": row[2],
                "poster_path": row[3], "tmdb_url": row[4],
                "trailer_url": row[5], "rating": row[6], "status": row[7],
                "notes": row[8], "added_at": row[9],
            }
            for row in rows
        ])

    @app.post("/api/favorites")
    def add_favorite():
        movie = request.get_json(silent=True) or {}
        if not movie.get("key") or not movie.get("title"):
            return jsonify({"error": "A movie key and title are required."}), 400
        with favorites_db() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO favorites "
                "(movie_key, title, year, poster_path, tmdb_url, trailer_url, rating, status, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    movie["key"], movie["title"], movie.get("year"),
                    movie.get("poster_path"), movie.get("tmdb_url"),
                    movie.get("trailer_url"), movie.get("rating"),
                    movie.get("status", "plan"), movie.get("notes", ""),
                ),
            )
        return jsonify({"ok": True})

    @app.patch("/api/favorites/<path:movie_key>")
    def update_favorite(movie_key: str):
        changes = request.get_json(silent=True) or {}
        allowed = {"status", "notes"}
        updates = {key: value for key, value in changes.items() if key in allowed}
        if not updates:
            return jsonify({"error": "No favorite fields supplied."}), 400
        if "status" in updates and updates["status"] not in {"plan", "watching", "watched"}:
            return jsonify({"error": "Invalid favorite status."}), 400
        assignments = ", ".join(f"{key} = ?" for key in updates)
        with favorites_db() as connection:
            connection.execute(
                f"UPDATE favorites SET {assignments} WHERE movie_key = ?",
                (*updates.values(), movie_key),
            )
        return jsonify({"ok": True})

    @app.delete("/api/favorites/<path:movie_key>")
    def remove_favorite(movie_key: str):
        with favorites_db() as connection:
            connection.execute("DELETE FROM favorites WHERE movie_key = ?", (movie_key,))
        return jsonify({"ok": True})

    @app.post("/api/scan/<job_id>/cancel")
    def cancel_scan(job_id: str):
        with jobs_lock:
            job = jobs.get(job_id)
            if job is None:
                return jsonify({"error": "Scan not found."}), 404
            job["cancel_requested"] = True
        return jsonify({"ok": True})
