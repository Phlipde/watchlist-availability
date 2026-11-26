"""One scan of a watchlist: lookup, saving, change history (`perform_scan`), and its helpers."""

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial

from . import history, letterboxd, matches, providers, tmdb
from .config import valid_country
from .lookup import film_key, lookup_film
from .models import Film, WatchlistEntry
from .results import build_results
from .settings import AppSettings
from .store import REGIONS_SETTING, Store
from .tmdb import clean_year

RESULT_REUSE_SECONDS = 24 * 60 * 60
PROVIDER_CATALOG_TTL_SECONDS = 7 * 24 * 60 * 60
# Marks scans that keep every provider TMDB reports (stats["providers"]).
ALL_PROVIDERS = "all"
# Raise when films get new fields: a saved scan in an older format is not reused, so the new
# fields arrive with the next scan instead of a day later.
FILM_FORMAT = 4


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


def refresh_regions(store: Store, api_key: str | None, max_age: float = PROVIDER_CATALOG_TTL_SECONDS) -> bool:
    """Store the countries TMDB has offers for, at most once a week; a failure keeps the old list."""
    try:
        stored = json.loads(store.get_setting(REGIONS_SETTING) or "{}")
    except ValueError:
        stored = {}
    fetched_at = stored.get("fetched_at") if isinstance(stored, dict) else None
    if not api_key or (isinstance(fetched_at, int | float) and time.time() - fetched_at < max_age):
        return False
    try:
        codes = [code for code in tmdb.get_regions(api_key) if valid_country(code)]
    except tmdb.TmdbError:
        return False
    if not codes:
        return False
    store.set_setting(REGIONS_SETTING, json.dumps({"codes": sorted(set(codes)), "fetched_at": time.time()}))
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


def with_changes(
    store: Store, country: str, results: list[dict], unavailable: list[dict], *, profile_id: int = 1
) -> dict:
    """Attach the stored availability changes of the last two weeks to a scan's films."""
    since = time.time() - history.CHANGE_WINDOW_SECONDS
    changes = store.recent_changes(country, since, profile_id=profile_id)
    return {
        "results": history.apply_changes(results, changes),
        "unavailable": history.apply_changes(unavailable, changes),
        "changes": changes,
        # The page does not reload on a country switch, so these lists travel with the films.
        "free_services": sorted(providers.mostly_free_from_scan(results, unavailable)),
        "rental_shops": sorted(providers.rental_from_scan(results, unavailable)),
    }


def load_watchlist(settings: AppSettings) -> tuple[list[WatchlistEntry], str]:
    """The watchlist from Letterboxd, or (first profile only) from an exported CSV in the downloads folder."""
    username = settings.letterboxd_username
    error = None
    if username:
        try:
            entries = letterboxd.fetch_watchlist_from_letterboxd(username, show_progress=False)
            if entries:
                return entries, f"Letterboxd @{username}"
        except letterboxd.LetterboxdError as exc:
            error = exc
    if settings.profile_id != 1:  # the downloads folder belongs to the first profile
        if error:
            raise error
        if username:
            raise ValueError(f"The Letterboxd watchlist of @{username} is empty.")
        raise ValueError("Add your Letterboxd username in Settings or upload a watchlist CSV.")
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
    rental_shops: list[str] = field(default_factory=list)


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
    profile_id: int = 1,
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
    recent = store.find_scan(country, key, RESULT_REUSE_SECONDS, profile_id=profile_id)
    reusable = (
        recent is not None
        and recent["stats"].get("providers") == ALL_PROVIDERS
        and recent["stats"].get("film_format") == FILM_FORMAT
        and not matches.changed_since(store, recent["created"])
    )
    if recent is not None and reusable:
        store.touch_ids(seen)
        films = [Film.from_dict(result) for result in recent["results"]]
        return ScanOutcome(
            films=films,
            **with_changes(store, country, recent["results"], recent["unavailable"], profile_id=profile_id),
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
    refresh_regions(store, api_key)
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
    earlier = store.recent_scans(country, source_name, profile_id=profile_id)
    previous = earlier[0] if earlier else None
    older = earlier[1] if len(earlier) > 1 else None
    created = time.time()
    stats = {**result_stats(results), "providers": ALL_PROVIDERS, "film_format": FILM_FORMAT}
    scan_id = None
    # Nothing could be checked (TMDB down, wrong key): keep the previous scan on the page.
    if results or unavailable or not failed:
        # A scan with failed lookups is incomplete and must not be reused.
        saved_key = None if failed else key
        scan_id = store.save_scan(
            country,
            source_name,
            saved_key,
            results,
            unavailable,
            stats,
            created=created,
            profile_id=profile_id,
        )
        store.add_changes(
            country,
            history.diff_scans(previous, results, unavailable, older=older),
            created=created,
            profile_id=profile_id,
        )
    store.touch_ids(seen, seen_at=created)
    return ScanOutcome(
        films=films,
        **with_changes(store, country, results, unavailable, profile_id=profile_id),
        source_name=source_name,
        created=created,
        scan_id=scan_id,
        failed=failed,
    )
