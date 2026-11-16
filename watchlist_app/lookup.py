"""Film lookup with a persistent cache, used by the CLI and the web scan."""

import time

from . import letterboxd, tmdb
from .store import Store

PROVIDERS_TTL_SECONDS = 24 * 60 * 60
NOT_FOUND_TTL_SECONDS = 7 * 24 * 60 * 60


def film_key(title: str, year: int | None, slug: str | None) -> str:
    """Key of a watchlist entry before its TMDB id is known."""
    if slug:
        return f"lb:{slug}"
    return f"title:{str(title).strip().lower()}|{year if year is not None else ''}"


def _resolve_tmdb_id(
    title: str, year: int | None, slug: str | None, api_key: str | None
) -> tuple[int | None, str]:
    """Prefer the id Letterboxd links to; fall back to a TMDB title search."""
    if slug:
        tmdb_id = letterboxd.fetch_tmdb_id(slug)
        if tmdb_id is not None:
            return tmdb_id, "letterboxd"
    return tmdb.search_movie_id(title, year, api_key), "search"


def lookup_film(
    title: str,
    year: int | None,
    slug: str | None,
    country: str,
    api_key: str | None,
    cache: Store | None = None,
    providers_ttl: float = PROVIDERS_TTL_SECONDS,
) -> dict | None:
    """Return TMDB id, poster, details and providers ({TMDB name: set(kinds)}) for one country.

    Returns None when the film cannot be found on TMDB. Raises tmdb.TmdbError
    when TMDB cannot be reached, so a failure is never cached as "not found".
    """
    now = time.time()
    key = film_key(title, year, slug)
    known = cache.get_id(key) if cache else None
    if known is not None and known["tmdb_id"] is None:
        if now - (known["checked_at"] or 0) < NOT_FOUND_TTL_SECONDS:
            return None
        known = None

    if known is None:
        tmdb_id, source = _resolve_tmdb_id(title, year, slug, api_key)
        if cache:
            cache.set_id(key, tmdb_id, source, title=title, year=year)
        if tmdb_id is None:
            return None
    else:
        tmdb_id = known["tmdb_id"]

    stored = cache.get_film(tmdb_id, country) if cache else None
    if stored is not None and now - (stored["fetched_at"] or 0) < providers_ttl:
        poster_path, details, providers = stored["poster_path"], stored["details"], stored["providers"]
    else:
        bundle = tmdb.get_movie_bundle(tmdb_id, api_key)
        if bundle is None:
            if cache:
                cache.set_id(key, None, "missing", title=title, year=year)
            return None
        if cache:
            cache.save_bundle(tmdb_id, bundle)
        poster_path, details = bundle.get("poster_path"), bundle.get("details") or {}
        providers = (bundle.get("providers") or {}).get(country, {})

    return {
        "tmdb_id": tmdb_id,
        "poster_path": poster_path,
        "details": details or {},
        "release": ((details or {}).get("release_dates") or {}).get(country) or {},
        "providers": {provider: set(kinds) for provider, kinds in providers.items()},
    }
