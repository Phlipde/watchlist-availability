"""Automatic scans on a schedule."""

import logging
import threading
import time

from . import config
from .backups import write_daily_backup
from .notifications import run_notifications
from .scan_service import ScanService
from .settings import AppSettings
from .store import Store

CHECK_SECONDS = 60
RETRY_SECONDS = 60 * 60


def next_scan_at(store: Store, settings: AppSettings) -> float | None:
    """When the next automatic scan is due, or None if the schedule is off."""
    interval = settings.scan_interval_hours
    if interval <= 0:
        return None
    # Never more often than once a day.
    return (store.latest_scan_created(settings.country) or 0) + max(interval, 24) * 3600


def run_due_scan(store: Store, settings: AppSettings, service: ScanService, now: float | None = None) -> bool:
    """Start a scan of the configured country if one is due. Returns True if it started one."""
    now = now if now is not None else time.time()
    due = next_scan_at(store, settings)
    if due is None or now < due:
        return False
    if not settings.tmdb_api_key or service.is_running():
        return False
    # After a failed automatic scan, wait before trying again.
    if any(
        job["trigger"] == "schedule" and now - job["started_at"] < RETRY_SECONDS
        for job in store.list_jobs(limit=10)
    ):
        return False
    service.start(settings.country, trigger="schedule")
    return True


def start_scheduler(store: Store, settings: AppSettings, service: ScanService) -> threading.Thread:
    """Check once a minute in the background whether a scan is due."""

    def loop() -> None:
        while True:
            try:
                run_due_scan(store, settings, service)
            except Exception:  # the schedule must survive a failed check
                logging.exception("Scheduled scan check failed")
            try:
                run_notifications(store, settings)
            except Exception:  # a broken target must not stop the scans
                logging.exception("Notification check failed")
            try:
                write_daily_backup(store, config.data_dir() / "backups")
            except Exception:  # a full disk must not stop the scans
                logging.exception("Daily backup failed")
            time.sleep(CHECK_SECONDS)

    thread = threading.Thread(target=loop, name="watchlist-scheduler", daemon=True)
    thread.start()
    return thread
