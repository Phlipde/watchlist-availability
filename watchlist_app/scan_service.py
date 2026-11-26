"""The scan service: one way to scan for the button, the schedule and the CLI.

`perform_scan` does the work (lookup, saving, change history). `ScanService`
runs it in the background and keeps the progress: live results in memory, the
state of every run in the database so it is still known after a restart.
"""

import logging
import threading
import time
import uuid

from . import costs, letterboxd, tmdb
from .models import Film, WatchlistEntry
from .scan_run import (  # re-exported: importers and tests use them from here
    ALL_PROVIDERS,
    FILM_FORMAT,
    PROVIDER_CATALOG_TTL_SECONDS,
    RESULT_REUSE_SECONDS,
    ScanOutcome,
    load_watchlist,
    perform_scan,
    refresh_provider_catalog,
    refresh_watched,
    result_stats,
    watchlist_key,
    with_changes,
)
from .settings import AppSettings
from .store import Store

__all__ = [
    "ALL_PROVIDERS",
    "FILM_FORMAT",
    "PROVIDER_CATALOG_TTL_SECONDS",
    "RESULT_REUSE_SECONDS",
    "ScanOutcome",
    "ScanService",
    "load_watchlist",
    "perform_scan",
    "refresh_provider_catalog",
    "result_stats",
    "watchlist_key",
    "with_changes",
]

STALE_SCAN_SECONDS = 30 * 60
LIVE_JOB_TTL_SECONDS = 60 * 60
DB_UPDATE_SECONDS = 1.0


class ScanService:
    """Runs scans in the background and reports their progress."""

    def __init__(self, store: Store, settings: AppSettings, thread_factory=threading.Thread):
        self._store = store
        self._settings = settings
        self._thread_factory = thread_factory
        self._lock = threading.Lock()
        self._live: dict[str, dict] = {}

    # ----- starting and stopping -----

    def start(
        self,
        country: str,
        entries: list[WatchlistEntry] | None = None,
        source_name: str | None = None,
        trigger: str = "manual",
        *,
        profile_id: int,
    ) -> tuple[str, bool]:
        """Start a scan for a profile. Returns (job id, True if an already running scan was joined).

        Scans of different profiles run side by side; only the same profile's scans join or stop.
        """
        now = time.time()
        with self._lock:
            self._expire_stale(now)
            self._forget_old(now)
            for job_id, job in self._live.items():
                if job["status"] != "running" or job["cancel_requested"] or job["profile_id"] != profile_id:
                    continue
                if job["country"] == country and entries is None:
                    return job_id, True
                # Another country or an uploaded list was requested: stop the old scan,
                # unless it runs in the background (schedule, after a restart).
                if job["trigger"] == "manual":
                    job["cancel_requested"] = True
            job_id = uuid.uuid4().hex
            self._live[job_id] = {
                "job_id": job_id,
                "profile_id": profile_id,
                "status": "running",
                "trigger": trigger,
                "phase": "Starting",
                "message": "Preparing scan...",
                "completed": 0,
                "total": 0,
                "current_title": "",
                "results": [],
                "stats": result_stats([]),
                "unavailable": [],
                "changes": [],
                "failed": [],
                "last_updated": None,
                "started_at": now,
                "heartbeat_at": now,
                "cancel_requested": False,
                "country": country,
                "entries": entries,
                "source_name": source_name,
            }
        self._store.create_job(job_id, country, trigger, now, profile_id=profile_id)
        self._thread_factory(target=self.run, args=(job_id,), daemon=True).start()
        return job_id, False

    def cancel(self, job_id: str, *, profile_id: int) -> bool:
        with self._lock:
            job = self._live.get(job_id)
            if job is None or job["profile_id"] != profile_id:
                return False
            job["cancel_requested"] = True
            return True

    def is_running(self, profile_id: int | None = None) -> bool:
        """True while a scan runs: of the given profile, or of any profile."""
        with self._lock:
            return any(
                job["status"] == "running" and profile_id in (None, job["profile_id"])
                for job in self._live.values()
            )

    def recover_interrupted(self, restart: bool = True) -> list[str]:
        """After a restart: close scans the old process left unfinished, and scan again (once per profile)."""
        interrupted = [
            job
            for profile in self._store.list_profiles()
            for job in self._store.list_jobs(limit=20, status="running", profile_id=profile["id"])
            if job["id"] not in self._live
        ]
        for job in interrupted:
            self._store.update_job(
                job["id"],
                status="interrupted",
                phase="Interrupted",
                message="The app was restarted during this scan.",
                finished_at=time.time(),
            )
        if restart and self._settings.tmdb_api_key:
            newest: dict[int, dict] = {}
            for job in interrupted:  # newest first within each profile
                newest.setdefault(job["profile_id"], job)
            for profile_id, job in newest.items():
                self.start(job["country"], trigger="resume", profile_id=profile_id)
        return [job["id"] for job in interrupted]

    def _expire_stale(self, now: float) -> None:
        for job_id, job in self._live.items():
            if job["status"] == "running" and now - job["heartbeat_at"] > STALE_SCAN_SECONDS:
                job.update(
                    status="error",
                    phase="Error",
                    message="The scan expired and was stopped.",
                    cancel_requested=True,
                    finished_at=now,
                )
                self._store.update_job(
                    job_id, status="error", phase="Error", message=job["message"], finished_at=now
                )

    def _forget_old(self, now: float) -> None:
        """Drop live results of scans that ended a while ago; the database keeps the rest."""
        for job_id in [
            job_id
            for job_id, job in self._live.items()
            if job["status"] != "running" and now - job.get("finished_at", now) > LIVE_JOB_TTL_SECONDS
        ]:
            del self._live[job_id]

    # ----- progress -----

    def status(self, job_id: str, start: int = 0, *, profile_id: int) -> dict | None:
        """The state of a scan for the browser, from memory or, after a restart, the database.

        While a scan runs, only the films found after the first `start` are sent; the
        page already has those. A finished scan always sends every film. A scan of another
        profile is None.
        """
        with self._lock:
            job = self._live.get(job_id)
            if job is not None and job["profile_id"] != profile_id:
                return None
            if job is not None:
                live = {key: value for key, value in job.items() if key != "entries"}
                if live["status"] == "running":
                    live["results"] = live["results"][max(start, 0) :]
        if job is not None:
            return self._mark_own_services(live)
        stored = self._store.get_job(job_id)
        if stored is None or stored["profile_id"] != profile_id:
            return None
        scan = self._store.get_scan(stored["scan_id"]) if stored["scan_id"] else None
        films = (
            with_changes(
                self._store, scan["country"], scan["results"], scan["unavailable"], profile_id=profile_id
            )
            if scan
            else {"results": [], "unavailable": [], "changes": []}
        )
        return self._mark_own_services(
            {
                "job_id": stored["id"],
                "profile_id": profile_id,
                "status": stored["status"],
                "trigger": stored["trigger"],
                "phase": stored["phase"],
                "message": stored["message"],
                "completed": stored["completed"],
                "total": stored["total"],
                "current_title": "",
                **films,
                "stats": result_stats(films["results"]),
                "failed": stored["failed"],
                "last_updated": scan["created"] if scan else None,
                "country": stored["country"],
                "source_name": stored["source_name"],
            }
        )

    def _mark_own_services(self, status: dict) -> dict:
        own = self._settings.for_profile(status["profile_id"]).subscriptions(status["country"])
        return {**status, "results": costs.mark_only_on_my_services(status["results"], own)}

    # ----- the scan itself -----

    def run(self, job_id: str) -> None:
        """Run a started scan to the end. Called on a background thread."""
        job = self._live[job_id]
        store = self._store
        settings = self._settings.for_profile(job["profile_id"])  # threads have no request context
        requests_before = tmdb.request_count()
        last_write = 0.0

        def change(**fields) -> None:
            with self._lock:
                job.update(fields)

        def write_progress(force: bool = False) -> None:
            nonlocal last_write
            now = time.time()
            if not force and now - last_write < DB_UPDATE_SECONDS:
                return
            last_write = now
            with self._lock:
                snapshot = {
                    "phase": job["phase"],
                    "message": job["message"],
                    "completed": job["completed"],
                    "total": job["total"],
                    "available": len(job["results"]),
                    "unavailable": len(job["unavailable"]),
                    "failed": list(job["failed"]),
                    "heartbeat_at": job["heartbeat_at"],
                    "source_name": job["source_name"],
                }
            store.update_job(job_id, tmdb_requests=tmdb.request_count() - requests_before, **snapshot)

        def finish(status: str, phase: str, message: str, **fields) -> None:
            now = time.time()
            change(status=status, phase=phase, message=message, finished_at=now, heartbeat_at=now, **fields)
            write_progress(force=True)
            store.update_job(job_id, status=status, finished_at=now)

        try:
            change(phase="Loading watchlist", message="Fetching your Letterboxd watchlist...")
            entries, source_name = job["entries"], job["source_name"]
            if entries is None:
                entries, source_name = load_watchlist(settings)
            change(
                phase="Scanning films",
                message="Checking films against TMDB...",
                total=len(entries),
                source_name=source_name or "Uploaded CSV",
            )
            write_progress(force=True)

            def on_progress(current, total, title):
                change(completed=current, total=total, current_title=title, heartbeat_at=time.time())
                write_progress()

            def on_result(film: Film):
                with self._lock:
                    job["results"].append(film.to_dict())
                    job["stats"] = result_stats(job["results"])

            def on_unavailable(film: Film):
                with self._lock:
                    job["unavailable"].append(film.to_dict())

            def on_failed(failure: dict):
                with self._lock:
                    job["failed"].append(failure)

            def is_cancelled():
                with self._lock:
                    return job["cancel_requested"]

            outcome = perform_scan(
                store,
                entries,
                job["source_name"],
                job["country"],
                settings.tmdb_api_key,
                on_progress=on_progress,
                on_result=on_result,
                on_unavailable=on_unavailable,
                on_failed=on_failed,
                is_cancelled=is_cancelled,
                profile_id=settings.profile_id,
            )
            if outcome is None:
                finish("cancelled", "Cancelled", "Scan cancelled.")
                return
            if outcome.scan_id is None:
                finish("error", "Error", f"No film could be checked: {outcome.failed[0]['message']}")
                return
            change(
                results=outcome.results,
                unavailable=outcome.unavailable,
                changes=outcome.changes,
                free_services=outcome.free_services,
                rental_shops=outcome.rental_shops,
                stats=result_stats(outcome.results),
                completed=len(entries),
                last_updated=outcome.created,
            )
            store.update_job(job_id, scan_id=outcome.scan_id, reused=outcome.reused)
            try:  # the history is a bonus; a problem there must not fail a good scan
                store.record_service_counts(
                    job["country"],
                    time.strftime("%Y-%m-%d", time.localtime(outcome.created)),
                    costs.service_counts(outcome.results, settings.subscriptions(job["country"])),
                    profile_id=settings.profile_id,
                )
            except Exception:
                logging.exception("Could not save the service history")
            finish("complete", "Complete", "Loaded from cache." if outcome.reused else "All films loaded.")
        except (FileNotFoundError, ValueError, letterboxd.LetterboxdError) as exc:
            finish("error", "Error", str(exc))
            return
        except Exception:
            logging.exception("Scan %s failed", job_id)
            finish("error", "Error", "The scan failed unexpectedly.")
            return
        try:  # after the scan is complete: Together needs the watched films, the scan does not
            refresh_watched(store, settings)
        except Exception:
            logging.exception("Could not refresh the watched films")
