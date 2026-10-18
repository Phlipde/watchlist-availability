"""Local web application for selecting streaming providers and checking a watchlist."""

from __future__ import annotations

import os
import hashlib
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

import watchlist_availability as wa

app = Flask(__name__)
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()
_CACHE_PATH = Path(__file__).parent / ".watchlist_cache.json"
_FAVORITES_DB = Path(__file__).parent / ".watchlist_favorites.sqlite3"
try:
    _RESULT_CACHE: dict[str, dict] = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
except (FileNotFoundError, json.JSONDecodeError):
    _RESULT_CACHE = {}


def _favorites_db() -> sqlite3.Connection:
    connection = sqlite3.connect(_FAVORITES_DB)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS favorites ("
        "movie_key TEXT PRIMARY KEY, title TEXT NOT NULL, year INTEGER, "
        "poster_path TEXT, tmdb_url TEXT, trailer_url TEXT, rating REAL)"
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(favorites)")}
    for name, definition in {
        "status": "TEXT NOT NULL DEFAULT 'plan'",
        "notes": "TEXT NOT NULL DEFAULT ''",
        "added_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    }.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE favorites ADD COLUMN {name} {definition}")
    connection.commit()
    return connection


def _provider_groups() -> list[tuple[str, list[tuple[str, list[str]]]]]:
    """Return all providers grouped by type and country for the selection form."""
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
        ("International", [
            ("Free and ad-supported", ["Arte", "Molotov", "Pluto TV", "Plex"]),
            ("Subscriptions", [
                "Netflix", "Canal+", "TF1+", "M6+", "Prime Video", "Disney+",
                "Apple TV+", "Paramount+", "HBO Max", "Crunchyroll", "MUBI",
            ]),
        ]),
        ("Germany", [
            ("German and specialty services", germany),
            ("Amazon Channels", amazon_channels),
        ]),
    ]


def _all_targets() -> dict[str, str]:
    return dict(wa._ALL_PROVIDERS)


def _default_selection() -> list[str]:
    return list(wa.load_platforms_config(wa.COUNTRY).keys())


def _load_web_watchlist():
    """Load a watchlist without blocking a web request on input()."""
    if wa.LETTERBOXD_USERNAME:
        try:
            dataframe = wa.fetch_watchlist_from_letterboxd(
                wa.LETTERBOXD_USERNAME, show_progress=False
            )
            if len(dataframe):
                return dataframe, f"Letterboxd @{wa.LETTERBOXD_USERNAME}"
        except wa.LetterboxdError:
            pass

    csv_path = wa.find_watchlist_csv()
    return wa.load_watchlist(csv_path), csv_path.name


def _public_result(result: dict) -> dict:
    return {
        "title": result["Title"],
        "year": result["Year"],
        "poster_path": result.get("PosterPath"),
        "overview": result.get("overview", ""),
        "rating": result.get("rating"),
        "backdrop_path": result.get("backdrop_path"),
        "runtime": result.get("runtime"),
        "genres": result.get("genres", []),
        "tmdb_url": result.get("tmdb_url"),
        "trailer_url": result.get("trailer_url"),
        "providers": {
            provider: sorted(result.get(provider, set()))
            for provider in wa._ALL_PROVIDERS
            if result.get(provider)
        },
    }


def _watchlist_key(dataframe, source_name: str, country: str) -> str:
    rows = "|".join(f"{row['Name']}:{row['Year']}" for _, row in dataframe.iterrows())
    return hashlib.sha256(f"{country}|{source_name}|{rows}".encode()).hexdigest()


def _result_stats(results: list[dict]) -> dict:
    provider_counts: dict[str, int] = {}
    for result in results:
        for provider in result["providers"]:
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
    top = max(provider_counts.items(), key=lambda item: item[1], default=("-", 0))
    return {
        "total": len(results),
        "free": sum(
            any(kind in {"free", "ads"} for kinds in result["providers"].values() for kind in kinds)
            for result in results
        ),
        "paid": sum(
            any(kind in {"flatrate", "rent"} for kinds in result["providers"].values() for kind in kinds)
            for result in results
        ),
        "top_provider": top[0],
        "top_provider_count": top[1],
    }


def _run_scan(job_id: str, country: str) -> None:
    job = _JOBS[job_id]
    try:
        with _JOBS_LOCK:
            job["phase"] = "Loading watchlist"
            job["message"] = "Fetching your Letterboxd watchlist..."
        uploaded_dataframe = job.get("uploaded_dataframe")
        if uploaded_dataframe is not None:
            dataframe, source_name = uploaded_dataframe, job.get("uploaded_source", "Uploaded CSV")
        else:
            dataframe, source_name = _load_web_watchlist()
        targets = _all_targets()
        cache_key = _watchlist_key(dataframe, source_name, country)
        cached = _RESULT_CACHE.get(cache_key)
        with _JOBS_LOCK:
            job.update({
                "phase": "Scanning films",
                "message": "Checking films against TMDB...",
                "total": len(dataframe),
                "source_name": source_name,
                "country": country,
            })

        if cached and time.time() - cached.get("created", 0) < 86400:
            with _JOBS_LOCK:
                job.update({
                    "completed": len(dataframe), "results": list(cached["results"]),
                    "unavailable": list(cached.get("unavailable", [])),
                    "status": "complete", "phase": "Complete",
                    "message": "Loaded from cache.",
                    "stats": _result_stats(cached["results"]),
                })
            return

        def on_progress(current, total, title):
            with _JOBS_LOCK:
                job.update({"completed": current, "total": total, "current_title": title})

        def on_result(result):
            with _JOBS_LOCK:
                job["results"].append(_public_result(result))
                job["stats"] = _result_stats(job["results"])

        def on_unavailable(result):
            with _JOBS_LOCK:
                job["unavailable"].append({"title": result["Title"], "year": result["Year"]})

        def is_cancelled():
            with _JOBS_LOCK:
                return job["cancel_requested"]

        wa.build_results(
            dataframe,
            targets,
            country=country,
            api_key=wa.TMDB_API_KEY,
            progress_callback=on_progress,
            result_callback=on_result,
            cancel_callback=is_cancelled,
            unavailable_callback=on_unavailable,
            include_details=True,
        )
        with _JOBS_LOCK:
            current_results = list(job["results"])
            cancelled = job["cancel_requested"]
        if not cancelled:
            _RESULT_CACHE[cache_key] = {
                "created": time.time(),
                "results": current_results,
                "unavailable": list(job["unavailable"]),
            }
            try:
                _CACHE_PATH.write_text(json.dumps(_RESULT_CACHE), encoding="utf-8")
            except OSError:
                pass
        with _JOBS_LOCK:
            job.update({
                "status": "cancelled" if cancelled else "complete",
                "phase": "Cancelled" if cancelled else "Complete",
                "message": "Scan cancelled." if cancelled else "All films loaded.",
            })
    except (FileNotFoundError, ValueError, wa.LetterboxdError) as exc:
        with _JOBS_LOCK:
            job.update({"status": "error", "phase": "Error", "message": str(exc)})
    except Exception:
        with _JOBS_LOCK:
            job.update({"status": "error", "phase": "Error", "message": "The scan failed unexpectedly."})


@app.route("/")
def index():
    """Render the shell immediately; the scan starts in the browser."""
    targets = _all_targets()
    return render_template(
        "index.html",
        provider_groups=_provider_groups(),
        selected=_default_selection(),
        targets=targets,
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
    )


@app.get("/sw.js")
def service_worker():
    return send_file(Path(__file__).parent / "sw.js", mimetype="application/javascript")


@app.get("/manifest.webmanifest")
def manifest():
    return send_file(Path(__file__).parent / "manifest.webmanifest", mimetype="application/manifest+json")


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
    country = payload.get("country", wa.COUNTRY) if request.is_json else request.form.get("country", wa.COUNTRY)
    if country not in {"FR", "DE", "US", "GB"}:
        return jsonify({"error": "Unsupported country."}), 400
    uploaded_dataframe = None
    uploaded_source = None
    uploaded_file = request.files.get("watchlist")
    if uploaded_file and uploaded_file.filename:
        try:
            uploaded_dataframe = wa.pd.read_csv(uploaded_file)
            missing = [column for column in ("Name", "Year") if column not in uploaded_dataframe.columns]
            if missing:
                return jsonify({"error": f"CSV is missing columns: {', '.join(missing)}."}), 400
            uploaded_source = uploaded_file.filename
        except (UnicodeDecodeError, ValueError) as exc:
            return jsonify({"error": f"Could not read CSV: {exc}"}), 400
    job_id = uuid.uuid4().hex
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "status": "running", "phase": "Starting", "message": "Preparing scan...",
            "completed": 0, "total": 0, "current_title": "", "results": [],
            "stats": _result_stats([]),
            "unavailable": [],
            "uploaded_dataframe": uploaded_dataframe, "uploaded_source": uploaded_source,
            "cancel_requested": False, "country": country,
        }
    threading.Thread(target=_run_scan, args=(job_id, country), daemon=True).start()
    return jsonify({"job_id": job_id})


@app.get("/api/scan/<job_id>")
def scan_status(job_id: str):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return jsonify({"error": "Scan not found."}), 404
        public_job = {key: value for key, value in job.items() if key != "uploaded_dataframe"}
        return jsonify(public_job)


@app.get("/api/favorites")
def list_favorites():
    with _favorites_db() as connection:
        rows = connection.execute(
            "SELECT movie_key, title, year, poster_path, tmdb_url, trailer_url, "
            "rating, status, notes, added_at "
            "FROM favorites ORDER BY title"
        ).fetchall()
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
    with _favorites_db() as connection:
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
    with _favorites_db() as connection:
        connection.execute(
            f"UPDATE favorites SET {assignments} WHERE movie_key = ?",
            (*updates.values(), movie_key),
        )
    return jsonify({"ok": True})


@app.delete("/api/favorites/<path:movie_key>")
def remove_favorite(movie_key: str):
    with _favorites_db() as connection:
        connection.execute("DELETE FROM favorites WHERE movie_key = ?", (movie_key,))
    return jsonify({"ok": True})


@app.post("/api/scan/<job_id>/cancel")
def cancel_scan(job_id: str):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return jsonify({"error": "Scan not found."}), 404
        job["cancel_requested"] = True
        job["message"] = "Stopping after the current film..."
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")