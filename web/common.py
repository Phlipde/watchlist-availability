"""Helpers the route modules share: the sorts, the status overview, page responses and logos."""

from pathlib import Path

from flask import g, make_response, render_template

from watchlist_app import base, costs, matches, providers, scheduler, validation
from watchlist_app.scan_service import ScanService
from watchlist_app.settings import AppSettings
from watchlist_app.store import Store

# The sorts of the filter bar, default first; static/js/filtering.js sortFilms implements them.
SORTS = [
    ("priority", "Priority", "Best rated", "Favorites first, then the Letterboxd rating."),
    ("letterboxd", "Letterboxd rating", "Best rated", "Highest average rating on Letterboxd first."),
    ("rating", "TMDB rating", "Best rated", "Highest TMDB score first."),
    ("runtime", "Shortest first", "By film", "Shortest runtime first."),
    ("year-desc", "Newest first", "By film", "Latest release year first."),
    ("recent", "Recently added", "By availability", "Last added to your Letterboxd watchlist first."),
    ("oldest", "Longest on the list", "By availability", "First added to your Letterboxd watchlist first."),
    ("new", "Newly available", "By availability", "Most recently added by a service first."),
    ("random", "Random", "Other", "Shuffled; the order stays while you browse."),
]


def status_overview(store: Store, settings: AppSettings, service: ScanService) -> dict:
    """What the status page shows: recent scan runs, the schedule and the size of the data.

    `settings` is bound to the profile shown (common.active_settings)."""
    pid = settings.profile_id
    jobs = []
    for job in store.list_jobs(limit=20, profile_id=pid):
        end = job["finished_at"] or job["heartbeat_at"] or job["started_at"]
        jobs.append(
            {
                "id": job["id"],
                "status": job["status"],
                "trigger": job["trigger"],
                "country": job["country"],
                "source_name": job["source_name"],
                "message": job["message"],
                "started_at": job["started_at"],
                "duration_seconds": round(end - job["started_at"], 1),
                "completed": job["completed"],
                "total": job["total"],
                "available": job["available"],
                "unavailable": job["unavailable"],
                "failed": job["failed"],
                "tmdb_requests": job["tmdb_requests"],
                "reused": job["reused"],
            }
        )
    latest = store.latest_scan(settings.country, profile_id=pid)
    database = Path(store.path) if store.path != ":memory:" else None
    catalog = store.provider_catalog(settings.country)
    return {
        "uncertain_matches": len(matches.list_matches(store)),
        "base": base.base_counts(latest, len(matches.list_matches(store))),
        "provider_catalog": {
            "count": len(catalog),
            "fetched_at": max((item["fetched_at"] for item in catalog), default=None),
        },
        "country": settings.country,
        "running": service.is_running(pid),
        "last_scan_at": latest["created"] if latest else None,
        "scan_interval_hours": settings.scan_interval_hours,
        "next_scan_at": scheduler.next_scan_at(store, settings),
        "jobs": jobs,
        "counts": store.counts(),  # shared by all profiles
        "profile_counts": store.profile_counts(profile_id=pid),
        "database_bytes": database.stat().st_size if database and database.exists() else None,
        "tmdb_api_key_set": bool(settings.tmdb_api_key),
        "reminders": costs.reminders(
            {country: settings.costs(country) for country in settings.countries_in_use()}
        ),
    }


PROFILE_COOKIE = "wl_profile"  # the profile chosen on this device


def active_profile_id() -> int:
    """The profile of this request, set by routes.choose_profile; only valid inside a request."""
    return g.profile_id


def active_settings(settings: AppSettings) -> AppSettings:
    """The settings of this request's profile."""
    return settings.for_profile(active_profile_id())


def page(template: str, **context):
    response = make_response(render_template(template, **context))
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


def provider_logos(store: Store) -> dict[str, str]:
    """Logos of the providers loaded from TMDB: {display name: checked image path}."""
    return {
        providers.display_name(item["name"]): path
        for item in store.provider_catalog()
        if (path := validation.image_path(item["logo_path"]))
    }
