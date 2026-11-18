"""The scan service: one way to scan for the button, the schedule and the CLI.

`perform_scan` does the work (lookup, saving, change history). `ScanService`
runs it in the background and keeps the progress: live results in memory, the
state of every run in the database so it is still known after a restart.
"""

import hashlib
import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial

from . import costs, history, letterboxd, matches, providers, tmdb
from .lookup import film_key, lookup_film
from .models import Film, WatchlistEntry
from .results import build_results
from .settings import AppSettings
from .store import Store
from .tmdb import clean_year

RESULT_REUSE_SECONDS = 24 * 60 * 60
STALE_SCAN_SECONDS = 30 * 60
LIVE_JOB_TTL_SECONDS = 60 * 60
DB_UPDATE_SECONDS = 1.0
PROVIDER_CATALOG_TTL_SECONDS = 7 * 24 * 60 * 60
# Marks scans that keep every provider TMDB reports (stats["providers"]).
ALL_PROVIDERS = "all"
# Raise when films get new fields: a saved scan in an older format is not reused, so the new
# fields arrive with the next scan instead of a day later.
FILM_FORMAT = 3


def refresh_provider_catalog(
    store: Store, country: str, api_key: str | None, max_age: float = PROVIDER_CATALOG_TTL_SECONDS
) -> bool:
    """Load the providers TMDB knows in a country, at most once a week. Returns True if loaded.

    A failure is not fatal: the scan goes on and the next one tries again.
    """
    fetched_at = store.provider_catalog_age(country)
    if not api_key or (fetched_at is not None and time.time() - fetched_at < max_age):
        return False
    try:
        items = tmdb.get_region_providers(country, api_key)
    except tmdb.TmdbError:
        return False
    if not items:
        return False
    store.save_provider_catalog(country, items)
    return True


def watchlist_key(entries: list[WatchlistEntry], source_name: str, country: str) -> str:
    """Fingerprint of a watchlist, used to reuse a recent scan of the same list."""
    rows = "|".join(f"{entry.title}:{entry.year}" for entry in entries)
    return hashlib.sha256(f"{country}|{source_name}|{rows}".encode()).hexdigest()


def result_stats(results: list[dict]) -> dict:
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


def with_changes(store: Store, country: str, results: list[dict], unavailable: list[dict]) -> dict:
    """Attach the stored availability changes of the last two weeks to a scan's films."""
    changes = store.recent_changes(country, time.time() - history.CHANGE_WINDOW_SECONDS)
    return {
        "results": history.apply_changes(results, changes),
        "unavailable": history.apply_changes(unavailable, changes),
        "changes": changes,
        # The page does not reload on a country switch, so the free list travels with the films.
        "free_services": sorted(providers.mostly_free_from_scan(results, unavailable)),
    }


def load_watchlist(settings: AppSettings) -> tuple[list[WatchlistEntry], str]:
    """The watchlist from Letterboxd, or from an exported CSV in the downloads folder."""
    username = settings.letterboxd_username
    error = None
    if username:
        try:
            entries = letterboxd.fetch_watchlist_from_letterboxd(username, show_progress=False)
            if entries:
                return entries, f"Letterboxd @{username}"
        except letterboxd.LetterboxdError as exc:
            error = exc
    try:
        csv_path = letterboxd.find_watchlist_csv(settings.downloads_dir)
    except FileNotFoundError:
        if error:  # the Letterboxd problem is the real one, not the missing export
            raise error from None
        raise
    return letterboxd.load_watchlist(csv_path), csv_path.name


@dataclass
class ScanOutcome:
    """A finished scan. `results` and `unavailable` are Film dicts with their recent changes."""

    films: list[Film]
    results: list[dict]
    unavailable: list[dict]
    changes: list[dict]
    source_name: str
    created: float
    reused: bool = False
    scan_id: int | None = None
    failed: list[dict] = field(default_factory=list)
    free_services: list[str] = field(default_factory=list)


def perform_scan(
    store: Store,
    entries: list[WatchlistEntry],
    source_name: str,
    country: str,
    api_key: str | None,
    *,
    on_progress: Callable | None = None,
    on_result: Callable[[Film], None] | None = None,
    on_unavailable: Callable[[Film], None] | None = None,
    on_failed: Callable[[dict], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> ScanOutcome | None:
    """Check a watchlist against every known provider and store the result.

    A scan of the same watchlist from the last 24 hours is reused. Otherwise
    the films are looked up, the scan and the changes since the previous one are
    saved, and favorites are moved to their TMDB id. Returns None when cancelled.
    """
    key = watchlist_key(entries, source_name, country)
    seen = [
        (film_key(entry.title, clean_year(entry.year), entry.slug), entry.title, clean_year(entry.year))
        for entry in entries
    ]
    recent = store.find_scan(country, key, RESULT_REUSE_SECONDS)
    reusable = (
        recent is not None
        and recent["stats"].get("providers") == ALL_PROVIDERS
        and recent["stats"].get("film_format") == FILM_FORMAT
        and not matches.changed_since(store, recent["created"])
    )
    if recent is not None and reusable:
        store.touch_ids(seen)
        films = [Film.from_dict(result) for result in recent["results"]]
        store.rekey_favorites(films)
        return ScanOutcome(
            films=films,
            **with_changes(store, country, recent["results"], recent["unavailable"]),
            source_name=source_name,
            created=recent["created"],
            reused=True,
            scan_id=recent["id"],
        )

    unavailable: list[dict] = []
    failed: list[dict] = []

    def record_unavailable(film: Film) -> None:
        unavailable.append(film.to_dict())
        if on_unavailable:
            on_unavailable(film)

    def record_failed(entry: WatchlistEntry, error: Exception) -> None:
        failure = {
            "title": entry.title,
            "year": entry.year,
            "message": str(error)
            if isinstance(error, tmdb.TmdbError | letterboxd.LetterboxdError)
            else type(error).__name__,
        }
        failed.append(failure)
        if on_failed:
            on_failed(failure)

    refresh_provider_catalog(store, country, api_key)
    films = build_results(
        entries,
        None,  # keep every provider TMDB reports; the page chooses which ones to show
        country=country,
        api_key=api_key,
        progress_callback=on_progress,
        result_callback=on_result,
        cancel_callback=is_cancelled,
        unavailable_callback=record_unavailable,
        failed_callback=record_failed,
        lookup=partial(lookup_film, cache=store),
    )
    if is_cancelled and is_cancelled():
        return None
    results = [film.to_dict() for film in films]
    earlier = store.recent_scans(country, source_name)
    previous = earlier[0] if earlier else None
    older = earlier[1] if len(earlier) > 1 else None
    # Scans before the provider list came from TMDB only knew the built-in providers;
    # comparing against them would report every newly known provider as "new on ...".
    compare_only = None
    if previous is not None and previous["stats"].get("providers") != ALL_PROVIDERS:
        compare_only = set(providers._ALL_PROVIDERS) - providers.MATCHING_CHANGED
    created = time.time()
    stats = {**result_stats(results), "providers": ALL_PROVIDERS, "film_format": FILM_FORMAT}
    scan_id = None
    # Nothing could be checked (TMDB down, wrong key): keep the previous scan on the page.
    if results or unavailable or not failed:
        # A scan with failed lookups is incomplete and must not be reused.
        saved_key = None if failed else key
        scan_id = store.save_scan(
            country, source_name, saved_key, results, unavailable, stats, created=created
        )
        store.add_changes(
            country,
            history.diff_scans(previous, results, unavailable, compare_only, older=older),
            created=created,
        )
    store.touch_ids(seen, seen_at=created)
    store.rekey_favorites(films)
    return ScanOutcome(
        films=films,
        **with_changes(store, country, results, unavailable),
        source_name=source_name,
        created=created,
        scan_id=scan_id,
        failed=failed,
    )


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
    ) -> tuple[str, bool]:
        """Start a scan. Returns (job id, True if an already running scan was joined)."""
        now = time.time()
        with self._lock:
            self._expire_stale(now)
            self._forget_old(now)
            for job_id, job in self._live.items():
                if job["status"] != "running" or job["cancel_requested"]:
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
        self._store.create_job(job_id, country, trigger, now)
        self._thread_factory(target=self.run, args=(job_id,), daemon=True).start()
        return job_id, False

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._live.get(job_id)
            if job is None:
                return False
            job["cancel_requested"] = True
            return True

    def is_running(self) -> bool:
        with self._lock:
            return any(job["status"] == "running" for job in self._live.values())

    def recover_interrupted(self, restart: bool = True) -> list[str]:
        """After a restart: close scans the old process left unfinished, and scan again."""
        interrupted = [
            job for job in self._store.list_jobs(limit=20, status="running") if job["id"] not in self._live
        ]
        for job in interrupted:
            self._store.update_job(
                job["id"],
                status="interrupted",
                phase="Interrupted",
                message="The app was restarted during this scan.",
                finished_at=time.time(),
            )
        if interrupted and restart and self._settings.tmdb_api_key:
            self.start(interrupted[0]["country"], trigger="resume")
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

    def status(self, job_id: str, start: int = 0) -> dict | None:
        """The state of a scan for the browser, from memory or, after a restart, the database.

        While a scan runs, only the films found after the first `start` are sent; the
        page already has those. A finished scan always sends every film.
        """
        with self._lock:
            job = self._live.get(job_id)
            if job is not None:
                live = {key: value for key, value in job.items() if key != "entries"}
                if live["status"] == "running":
                    live["results"] = live["results"][max(start, 0) :]
        if job is not None:
            return self._mark_own_services(live)
        stored = self._store.get_job(job_id)
        if stored is None:
            return None
        scan = self._store.get_scan(stored["scan_id"]) if stored["scan_id"] else None
        films = (
            with_changes(self._store, scan["country"], scan["results"], scan["unavailable"])
            if scan
            else {"results": [], "unavailable": [], "changes": []}
        )
        return self._mark_own_services(
            {
                "job_id": stored["id"],
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
        own = self._settings.subscriptions(status["country"])
        return {**status, "results": costs.mark_only_on_my_services(status["results"], own)}

    # ----- the scan itself -----

    def run(self, job_id: str) -> None:
        """Run a started scan to the end. Called on a background thread."""
        job = self._live[job_id]
        store = self._store
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
                entries, source_name = load_watchlist(self._settings)
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
                self._settings.tmdb_api_key,
                on_progress=on_progress,
                on_result=on_result,
                on_unavailable=on_unavailable,
                on_failed=on_failed,
                is_cancelled=is_cancelled,
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
                stats=result_stats(outcome.results),
                completed=len(entries),
                last_updated=outcome.created,
            )
            store.update_job(job_id, scan_id=outcome.scan_id, reused=outcome.reused)
            try:  # the history is a bonus; a problem there must not fail a good scan
                store.record_service_counts(
                    job["country"],
                    time.strftime("%Y-%m-%d", time.localtime(outcome.created)),
                    costs.service_counts(outcome.results, self._settings.subscriptions(job["country"])),
                )
            except Exception:
                logging.exception("Could not save the service history")
            finish("complete", "Complete", "Loaded from cache." if outcome.reused else "All films loaded.")
        except (FileNotFoundError, ValueError, letterboxd.LetterboxdError) as exc:
            finish("error", "Error", str(exc))
        except Exception:
            logging.exception("Scan %s failed", job_id)
            finish("error", "Error", "The scan failed unexpectedly.")
