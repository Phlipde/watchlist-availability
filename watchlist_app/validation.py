"""Checks for data from outside the app, above all a restored backup.

A backup file can come from anywhere. Every value is rebuilt with a fixed type
and a size limit before it is stored, so the page never receives text where it
expects a number, a link to another site, or an unknown offer type.
"""

import math
import re
import time

from .config import COUNTRIES
from .models import OFFER_KINDS, Film

MAX_TEXT = 500
MAX_OVERVIEW = 5000
MAX_PEOPLE = 5
MAX_KEYWORDS = 50
MAX_NOTES = 2000
MAX_FILMS_PER_SCAN = 20000
FAVORITE_STATUSES = ("plan", "watching", "watched")
CHANGE_KINDS = ("added", "removed")
# A restored time may be a little ahead (clock differences), not in the future.
FUTURE_TOLERANCE_SECONDS = 24 * 60 * 60

_IMAGE_PATH_RE = re.compile(r"^/[A-Za-z0-9._-]{1,200}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TMDB_URL_RE = re.compile(r"^https://www\.themoviedb\.org/movie/\d+$")
_TRAILER_URL_RE = re.compile(r"^https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{1,40}$")


def text(value, limit: int = MAX_TEXT) -> str | None:
    """A string, cut to the limit; anything else is None."""
    if not isinstance(value, str):
        return None
    return value[:limit]


def integer(value, low: int, high: int) -> int | None:
    """A whole number in a range (digits in a string are accepted); anything else is None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return value if isinstance(value, int) and low <= value <= high else None


def number(value, low: float, high: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    value = float(value)
    return value if math.isfinite(value) and low <= value <= high else None


def timestamp(value, now: float | None = None) -> float | None:
    """A Unix time that is not in the future."""
    limit = (now if now is not None else time.time()) + FUTURE_TOLERANCE_SECONDS
    return number(value, 0, limit)


def _matching(value, pattern: re.Pattern) -> str | None:
    return value if isinstance(value, str) and pattern.fullmatch(value) else None


def image_path(value) -> str | None:
    """A TMDB image path such as "/abc.png", or None."""
    return _matching(value, _IMAGE_PATH_RE)


def year(value) -> int | None:
    return integer(value, 1870, 2200)


def clean_film(data) -> dict | None:
    """A film dict as the page expects it, or None if it has no usable title."""
    if not isinstance(data, dict):
        return None
    title = text(data.get("title"))
    if not title or not title.strip():
        return None
    providers = {}
    raw_providers = data.get("providers")
    if isinstance(raw_providers, dict):
        for name, kinds in list(raw_providers.items())[:300]:
            name = text(name, 200)
            if name and isinstance(kinds, list):
                allowed = [kind for kind in kinds if kind in OFFER_KINDS]
                if allowed:
                    providers[name] = allowed
    genres = data.get("genres")
    cast = data.get("cast")
    keywords = data.get("keywords")
    similar = data.get("similar_ids")
    film = Film(
        title=title,
        year=year(data.get("year")),
        tmdb_id=integer(data.get("tmdb_id"), 1, 10**9),
        poster_path=_matching(data.get("poster_path"), _IMAGE_PATH_RE),
        overview=text(data.get("overview"), MAX_OVERVIEW) or "",
        rating=number(data.get("rating"), 0, 10),
        popularity=number(data.get("popularity"), 0, 10**9),
        vote_count=integer(data.get("vote_count"), 0, 10**9),
        director=text(data.get("director"), 200),
        cast=[person[:200] for person in cast[:MAX_PEOPLE] if isinstance(person, str)]
        if isinstance(cast, list)
        else [],
        keywords=[keyword[:100] for keyword in keywords[:MAX_KEYWORDS] if isinstance(keyword, str)]
        if isinstance(keywords, list)
        else [],
        backdrop_path=_matching(data.get("backdrop_path"), _IMAGE_PATH_RE),
        runtime=integer(data.get("runtime"), 0, 2000),  # TMDB reports 0 for films not yet released
        genres=[genre[:100] for genre in genres[:30] if isinstance(genre, str)]
        if isinstance(genres, list)
        else [],
        release_date=_matching(data.get("release_date"), _DATE_RE),
        tmdb_url=_matching(data.get("tmdb_url"), _TMDB_URL_RE),
        trailer_url=_matching(data.get("trailer_url"), _TRAILER_URL_RE),
        collection=text(data.get("collection"), 200),
        watchlist_position=integer(data.get("watchlist_position"), 0, 10**6),
        similar_ids=[n for n in similar[:40] if type(n) is int and 0 < n < 10**9]
        if isinstance(similar, list)
        else [],
        certification=text(data.get("certification"), 20),
        cinema_date=_matching(data.get("cinema_date"), _DATE_RE),
        home_date=_matching(data.get("home_date"), _DATE_RE),
    )
    film.providers = {name: kinds for name, kinds in providers.items()}
    return film.to_dict()


def clean_films(items) -> tuple[list[dict], int]:
    """Clean a list of films: (usable films, number of dropped entries)."""
    if not isinstance(items, list):
        return [], 0
    films = [film for film in (clean_film(item) for item in items[:MAX_FILMS_PER_SCAN]) if film]
    return films, len(items) - len(films)


def clean_scan(data, now: float | None = None) -> tuple[dict | None, int]:
    """A restored scan: (scan or None, number of dropped films)."""
    if not isinstance(data, dict) or data.get("country") not in COUNTRIES:
        return None, 0
    created = timestamp(data.get("created"), now)
    if created is None:
        return None, 0
    results, dropped_results = clean_films(data.get("results"))
    unavailable, dropped_unavailable = clean_films(data.get("unavailable"))
    stored_stats = data.get("stats")
    raw_stats: dict = stored_stats if isinstance(stored_stats, dict) else {}
    stats: dict = {
        name: integer(raw_stats.get(name), 0, MAX_FILMS_PER_SCAN) or 0
        for name in ("total", "free", "paid", "top_provider_count")
    }
    stats["top_provider"] = text(raw_stats.get("top_provider"), 200) or "-"
    if raw_stats.get("providers") == "all":
        stats["providers"] = "all"
    scan = {
        "created": created,
        "country": data["country"],
        "source_name": text(data.get("source_name"), 200) or "",
        "watchlist_key": text(data.get("watchlist_key"), 100),
        "results": results,
        "unavailable": unavailable,
        "stats": stats,
    }
    return scan, dropped_results + dropped_unavailable


def clean_favorite(data) -> dict | None:
    if not isinstance(data, dict):
        return None
    key, title = text(data.get("key"), 300), text(data.get("title"))
    if not key or not title:
        return None
    return {
        "key": key,
        "title": title,
        "year": year(data.get("year")),
        "poster_path": _matching(data.get("poster_path"), _IMAGE_PATH_RE),
        "tmdb_url": _matching(data.get("tmdb_url"), _TMDB_URL_RE),
        "trailer_url": _matching(data.get("trailer_url"), _TRAILER_URL_RE),
        "rating": number(data.get("rating"), 0, 10),
        "status": data.get("status") if data.get("status") in FAVORITE_STATUSES else "plan",
        "notes": text(data.get("notes"), MAX_NOTES) or "",
    }


def clean_change(data, now: float | None = None) -> dict | None:
    if not isinstance(data, dict) or data.get("country") not in COUNTRIES:
        return None
    if data.get("change") not in CHANGE_KINDS:
        return None
    created = timestamp(data.get("created"), now)
    film_key, title, provider = (
        text(data.get("film_key"), 300),
        text(data.get("title")),
        text(data.get("provider"), 200),
    )
    if created is None or not film_key or not title or not provider:
        return None
    return {
        "created": created,
        "country": data["country"],
        "film_key": film_key,
        "title": title,
        "year": year(data.get("year")),
        "provider": provider,
        "change": data["change"],
    }


def clean_match(data) -> dict | None:
    if not isinstance(data, dict):
        return None
    film_key, tmdb_id = text(data.get("film_key"), 300), integer(data.get("tmdb_id"), 1, 10**9)
    if not film_key or tmdb_id is None:
        return None
    return {
        "film_key": film_key,
        "tmdb_id": tmdb_id,
        "title": text(data.get("title")),
        "year": year(data.get("year")),
    }
