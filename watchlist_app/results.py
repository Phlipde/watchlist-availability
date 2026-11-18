"""Check a watchlist against TMDB and build Film results."""

import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from typing import Any

from tqdm import tqdm

from .lookup import lookup_film
from .models import Film, WatchlistEntry, sort_kinds
from .providers import display_providers
from .tmdb import clean_year

DEFAULT_SCAN_WORKERS = 6

# lookup(title, year, slug, country, api_key) -> dict | None, see watchlist_app.lookup.
Lookup = Callable[[str, int | None, str | None, str, str | None], dict | None]


def scan_workers() -> int:
    """Number of films looked up at the same time."""
    try:
        return max(1, int(os.getenv("WATCHLIST_SCAN_WORKERS", DEFAULT_SCAN_WORKERS)))
    except ValueError:
        return DEFAULT_SCAN_WORKERS


def make_film(entry: WatchlistEntry, found: dict, targets: dict[str, str] | None) -> Film:
    """Combine a watchlist entry with lookup data.

    Providers are reduced to the targets ({display name: TMDB name}); with
    targets=None every provider TMDB reports is kept, under its display name.
    """
    available = found.get("providers") or {}
    details = found.get("details") or {}
    release = found.get("release") or {}
    if targets is None:
        offered = {name: sort_kinds(kinds) for name, kinds in display_providers(available).items() if kinds}
    else:
        offered = {
            display: sort_kinds(available[tmdb_name])
            for display, tmdb_name in targets.items()
            if available.get(tmdb_name)
        }
    return Film(
        title=entry.title,
        year=clean_year(entry.year),
        tmdb_id=found.get("tmdb_id"),
        poster_path=found.get("poster_path"),
        overview=details.get("overview") or "",
        rating=details.get("rating"),
        popularity=details.get("popularity"),
        vote_count=details.get("vote_count"),
        director=details.get("director"),
        original_title=details.get("original_title"),
        cast=list(details.get("cast") or []),
        keywords=list(details.get("keywords") or []),
        backdrop_path=details.get("backdrop_path"),
        runtime=details.get("runtime"),
        genres=list(details.get("genres") or []),
        release_date=details.get("release_date"),
        tmdb_url=details.get("tmdb_url"),
        trailer_url=details.get("trailer_url"),
        collection=details.get("collection"),
        similar_ids=details.get("similar_ids") or [],
        letterboxd_rating=found.get("letterboxd_rating"),
        certification=release.get("certification"),
        original_language=details.get("original_language"),
        origin_countries=list(details.get("origin_countries") or []),
        cinema_date=release.get("cinema"),
        home_date=release.get("home"),
        providers=offered,
    )


def build_results(
    entries: list[WatchlistEntry],
    targets: dict[str, str] | None,
    country: str = "FR",
    api_key: str | None = None,
    progress_callback: Callable | None = None,
    result_callback: Callable[[Film], None] | None = None,
    cancel_callback: Callable[[], bool] | None = None,
    unavailable_callback: Callable[[Film], None] | None = None,
    failed_callback: Callable[[WatchlistEntry, Exception], None] | None = None,
    lookup: Lookup | None = None,
    workers: int | None = None,
) -> list[Film]:
    """Look up every entry and return the films available on at least one target, in watchlist order.

    Several films are checked at the same time; callbacks run on the calling
    thread, in the order films finish. Films that are not on TMDB or only on
    other providers go to `unavailable_callback`; lookup errors to `failed_callback`.
    """
    lookup = lookup or partial(lookup_film, cache=None)
    total = len(entries)

    # (status, payload): a Film for "available"/"unavailable", the exception for "failed".
    def process(index: int) -> tuple[str, Any]:
        if cancel_callback and cancel_callback():
            return "cancelled", None
        entry = entries[index]
        try:
            found = lookup(entry.title, clean_year(entry.year), entry.slug, country, api_key)
        except Exception as exc:  # one broken film must not stop the scan
            return "failed", exc
        if found is None:
            return "unavailable", Film(
                title=entry.title, year=clean_year(entry.year), watchlist_position=index
            )
        film = make_film(entry, found, targets)
        film.watchlist_position = index
        return ("available" if film.providers else "unavailable"), film

    available: dict[int, Film] = {}
    progress = tqdm(
        total=total,
        desc="Checking streaming availability on TMDB",
        unit="film",
        disable=progress_callback is not None,  # the web app reports progress itself
    )

    def report(index: int, outcome: tuple[str, Any], completed: int) -> None:
        status, payload = outcome
        if status == "cancelled":
            return
        entry = entries[index]
        if status == "available":
            available[index] = payload
            if result_callback:
                result_callback(payload)
        elif status == "unavailable":
            if unavailable_callback:
                unavailable_callback(payload)
        elif failed_callback:
            failed_callback(entry, payload)
        progress.update(1)
        if progress_callback:
            progress_callback(completed, total, entry.title)

    try:
        worker_count = max(1, workers if workers is not None else scan_workers())
        if worker_count == 1:
            for index in range(total):
                outcome = process(index)
                if outcome[0] == "cancelled":
                    break
                report(index, outcome, index + 1)
        else:
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = {executor.submit(process, index): index for index in range(total)}
                for completed, future in enumerate(as_completed(futures), start=1):
                    report(futures[future], future.result(), completed)
    finally:
        progress.close()

    return [available[index] for index in sorted(available)]
