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
    """When the next automatic scan of the settings' profile is due, or None if it is never scanned.

    The interval is global; a profile other than the first needs a Letterboxd name (no CSV fallback).
    """
    interval = settings.scan_interval_hours
    if interval <= 0 or (settings.profile_id != 1 and not settings.letterboxd_username):
        return None
    # Never more often than once a day.
    created = store.latest_scan_created(settings.country, profile_id=settings.profile_id)
    return (created or 0) + max(interval, 24) * 3600


def run_due_scan(store: Store, settings: AppSettings, service: ScanService, now: float | None = None) -> bool:
    """Start the scan of the first profile that is due, one scan at a time. Returns True if it started one."""
    now = now if now is not None else time.time()
    if not settings.tmdb_api_key or service.is_running():
        return False
    for profile in store.list_profiles():
        profile_settings = settings.for_profile(profile["id"])
        due = next_scan_at(store, profile_settings)
        if due is None or now < due:
            continue
        # After a failed automatic scan, wait before trying this profile again.
        if any(
            job["trigger"] == "schedule" and now - job["started_at"] < RETRY_SECONDS
            for job in store.list_jobs(limit=10, profile_id=profile["id"])
        ):
            continue
        service.start(profile_settings.country, trigger="schedule", profile_id=profile["id"])
        return True
    return False


def start_scheduler(store: Store, settings: AppSettings, service: ScanService) -> threading.Thread:
    """Check once a minute in the background whether a scan is due."""

    def loop() -> None:
        while True:
            try:
                run_due_scan(store, settings, service)
            except Exception:  # the schedule must survive a failed check
                logging.exception("Scheduled scan check failed")
            for profile in store.list_profiles():
                try:
                    run_notifications(store, settings.for_profile(profile["id"]))
                except Exception:  # a broken target must not stop the scans or the other profiles
                    logging.exception("Notification check failed for profile %s", profile["id"])
            try:
                write_daily_backup(store, config.data_dir() / "backups")
            except Exception:  # a full disk must not stop the scans
                logging.exception("Daily backup failed")
            time.sleep(CHECK_SECONDS)

    thread = threading.Thread(target=loop, name="watchlist-scheduler", daemon=True)
    thread.start()
    return thread
