"""Background scan coordination for the Flask application."""

import time
from pathlib import Path
from threading import Lock
from typing import Any

from . import cache, serialization


def _save_latest_snapshot(
    path: Path,
    country: str,
    source_name: str,
    results: list[dict],
    unavailable: list[dict],
) -> None:
    cache.save_snapshot(
        path,
        {
            "created": time.time(),
            "country": country,
            "source_name": source_name,
            "results": results,
            "unavailable": unavailable,
            "stats": serialization.result_stats(results),
        },
    )


def run_scan(
    job_id: str,
    country: str,
    jobs: dict[str, dict],
    jobs_lock: Lock,
    result_cache: dict[str, dict],
    cache_path: Path,
    latest_result_path: Path,
    wa: Any,
) -> None:
    job = jobs[job_id]
    try:
        with jobs_lock:
            job["phase"] = "Loading watchlist"
            job["message"] = "Fetching your Letterboxd watchlist..."
            job["heartbeat_at"] = time.time()
        uploaded_dataframe = job.get("uploaded_dataframe")
        if uploaded_dataframe is not None:
            dataframe, source_name = uploaded_dataframe, job.get("uploaded_source", "Uploaded CSV")
        else:
            dataframe, source_name = _load_web_watchlist(wa)
        targets = dict(wa._ALL_PROVIDERS)
        cache_key = serialization.watchlist_key(dataframe, source_name, country)
        cached = result_cache.get(cache_key)
        with jobs_lock:
            job.update({
                "phase": "Scanning films",
                "message": "Checking films against TMDB...",
                "total": len(dataframe),
                "source_name": source_name,
                "country": country,
            })

        if cached and time.time() - cached.get("created", 0) < 86400:
            cached_results = list(cached["results"])
            cached_unavailable = list(cached.get("unavailable", []))
            with jobs_lock:
                job.update({
                    "completed": len(dataframe), "results": cached_results,
                    "unavailable": cached_unavailable,
                    "status": "complete", "phase": "Complete",
                    "message": "Loaded from cache.",
                    "last_updated": cached.get("created", time.time()),
                    "stats": serialization.result_stats(cached_results),
                })
            try:
                _save_latest_snapshot(
                    latest_result_path, country, source_name,
                    cached_results, cached_unavailable,
                )
            except OSError:
                pass
            return

        def on_progress(current, total, title):
            with jobs_lock:
                job.update({
                    "completed": current, "total": total,
                    "current_title": title, "heartbeat_at": time.time(),
                })

        def on_result(result):
            with jobs_lock:
                job["results"].append(serialization.public_result(result, targets))
                job["stats"] = serialization.result_stats(job["results"])

        def on_unavailable(result):
            with jobs_lock:
                job["unavailable"].append({"title": result["Title"], "year": result["Year"]})

        def on_failed(result, error):
            with jobs_lock:
                job["failed"].append({
                    "title": result["Title"], "year": result["Year"],
                    "message": str(error),
                })

        def is_cancelled():
            with jobs_lock:
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
            failed_callback=on_failed,
            include_details=True,
        )
        with jobs_lock:
            current_results = list(job["results"])
            cancelled = job["cancel_requested"]
        if not cancelled:
            with jobs_lock:
                job.update({
                    "phase": "Saving results",
                    "message": "Saving the completed scan...",
                })
            result_cache[cache_key] = {
                "created": time.time(),
                "results": current_results,
                "unavailable": list(job["unavailable"]),
            }
            try:
                cache.save_cache(cache_path, result_cache)
                _save_latest_snapshot(
                    latest_result_path, country, job.get("source_name", ""),
                    current_results, list(job["unavailable"]),
                )
            except OSError:
                pass
        with jobs_lock:
            job.update({
                "status": "cancelled" if cancelled else "complete",
                "phase": "Cancelled" if cancelled else "Complete",
                "message": "Scan cancelled." if cancelled else "All films loaded.",
                "last_updated": time.time() if not cancelled else job.get("last_updated"),
            })
    except (FileNotFoundError, ValueError, wa.LetterboxdError) as exc:
        with jobs_lock:
            job.update({"status": "error", "phase": "Error", "message": str(exc)})
    except Exception:
        with jobs_lock:
            job.update({
                "status": "error",
                "phase": "Error",
                "message": "The scan failed unexpectedly.",
            })


def _load_web_watchlist(wa):
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
