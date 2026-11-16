"""TMDB API access.

Errors are raised as TmdbError instead of being reported as "not found", and
details, trailer and providers of a film come from a single request.
"""

import math
import threading
import time

import requests

_TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
_TMDB_LOGO_BASE_URL = "https://image.tmdb.org/t/p/w92"
_API_BASE_URL = "https://api.themoviedb.org/3"
_MONETIZATION_TYPES = ("free", "ads", "flatrate", "rent")
_MAX_ATTEMPTS = 3
_LOCAL = threading.local()
_COUNT_LOCK = threading.Lock()
_request_count = 0


class TmdbError(Exception):
    """Raised when TMDB cannot be reached or keeps rejecting a request."""


def _http_get(url: str, params: dict | None = None, timeout: float = 10):
    """GET through a per-thread session so connections are reused."""
    session = getattr(_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        _LOCAL.session = session
    return session.get(url, params=params, timeout=timeout)


def request_count() -> int:
    """Number of TMDB requests sent by this process so far."""
    with _COUNT_LOCK:
        return _request_count


def clean_year(year: int | str | float | None) -> int | None:
    if year is None or (isinstance(year, float) and math.isnan(year)):
        return None
    try:
        return int(float(year)) if isinstance(year, str) else int(year)
    except (ValueError, TypeError, OverflowError):
        return None


def _details_from_movie(data: dict, tmdb_id: int) -> dict:
    videos = data.get("videos", {}).get("results", [])
    trailer = next(
        (video for video in videos if video.get("site") == "YouTube" and video.get("type") == "Trailer"),
        None,
    )
    credits = data.get("credits", {})
    directors = [
        p.get("name") for p in credits.get("crew", []) if p.get("job") == "Director" and p.get("name")
    ]
    cast = [p.get("name") for p in credits.get("cast", []) if p.get("name")][:5]
    keywords = [
        keyword.get("name") for keyword in data.get("keywords", {}).get("keywords", []) if keyword.get("name")
    ]
    return {
        "tmdb_title": data.get("title") or "",
        "overview": data.get("overview", ""),
        "rating": data.get("vote_average"),
        "popularity": data.get("popularity"),
        "vote_count": data.get("vote_count"),
        "director": directors[0] if directors else None,
        "cast": cast,
        "keywords": keywords,
        "backdrop_path": data.get("backdrop_path"),
        "runtime": data.get("runtime"),
        "genres": [genre.get("name") for genre in data.get("genres", [])],
        "release_date": data.get("release_date") or None,
        "tmdb_url": f"https://www.themoviedb.org/movie/{tmdb_id}",
        "trailer_url": f"https://www.youtube.com/watch?v={trailer['key']}" if trailer else None,
    }


def _request_json(path: str, params: dict) -> dict | None:
    """GET a TMDB resource. Returns None on 404, raises TmdbError otherwise."""
    global _request_count
    for attempt in range(_MAX_ATTEMPTS):
        last_attempt = attempt == _MAX_ATTEMPTS - 1
        with _COUNT_LOCK:
            _request_count += 1
        try:
            response = _http_get(f"{_API_BASE_URL}{path}", params=params, timeout=10)
        except requests.RequestException as exc:
            if last_attempt:
                # The exception text contains the request URL with the API key.
                raise TmdbError(f"TMDB request failed ({type(exc).__name__}).") from None
            time.sleep(0.5 * (attempt + 1))
            continue
        if response.status_code == 429:
            if last_attempt:
                break
            try:
                delay = float(response.headers.get("Retry-After", ""))
            except (TypeError, ValueError):
                delay = 1.0 + attempt
            time.sleep(min(max(delay, 0.5), 10.0))
            continue
        if response.status_code == 404:
            return None
        if response.status_code >= 500 and not last_attempt:
            time.sleep(0.5 * (attempt + 1))
            continue
        if response.status_code >= 400:
            raise TmdbError(f"TMDB returned {response.status_code}.")
        try:
            return response.json()
        except ValueError:
            raise TmdbError("TMDB returned an unreadable response.") from None
    raise TmdbError("TMDB rate limit reached.")


def search_movies(
    title: str,
    year: int | str | float | None = None,
    api_key: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """TMDB title search: [{"tmdb_id", "title", "original_title", "year", "poster_path", "overview"}]."""
    params: dict = {"api_key": api_key, "query": title}
    normalized_year = clean_year(year)
    if normalized_year is not None:
        params["year"] = normalized_year
    data = _request_json("/search/movie", params) or {}
    return [
        {
            "tmdb_id": result["id"],
            "title": result.get("title") or "",
            "original_title": result.get("original_title") or "",
            "year": clean_year((result.get("release_date") or "")[:4] or None),
            "poster_path": result.get("poster_path"),
            "overview": result.get("overview") or "",
        }
        for result in data.get("results", [])[:limit]
        if result.get("id") is not None
    ]


def search_movie_id(
    title: str,
    year: int | str | float | None,
    api_key: str | None = None,
) -> int | None:
    """Best TMDB search hit for a title: an exact title with the same year, else the first hit."""
    candidates = search_movies(title, year, api_key)
    if not candidates:
        return None
    wanted, wanted_year = title.strip().casefold(), clean_year(year)
    for candidate in candidates:
        names = {candidate["title"].casefold(), candidate["original_title"].casefold()}
        if wanted in names and (wanted_year is None or candidate["year"] == wanted_year):
            return candidate["tmdb_id"]
    return candidates[0]["tmdb_id"]


def get_region_providers(country: str, api_key: str | None = None) -> list[dict]:
    """Every film provider TMDB knows in a country: [{"name", "logo_path", "priority"}]."""
    data = _request_json("/watch/providers/movie", {"api_key": api_key, "watch_region": country}) or {}
    providers = []
    for item in data.get("results", []):
        name = (item.get("provider_name") or "").strip()
        if name:
            priority = (item.get("display_priorities") or {}).get(country, item.get("display_priority"))
            providers.append({"name": name, "logo_path": item.get("logo_path"), "priority": priority})
    return providers


def get_movie_bundle(tmdb_id: int, api_key: str | None = None) -> dict | None:
    """Fetch details, trailer and providers for every country in one request.

    Returns None if TMDB does not know the id. The result has the keys
    'poster_path', 'details' and 'providers' ({country: {provider: [kinds]}}).
    """
    data = _request_json(
        f"/movie/{tmdb_id}",
        {"api_key": api_key, "append_to_response": "videos,watch/providers,credits,keywords"},
    )
    if data is None:
        return None
    providers: dict[str, dict[str, list[str]]] = {}
    for country, offers in data.get("watch/providers", {}).get("results", {}).items():
        by_provider: dict[str, list[str]] = {}
        for category in _MONETIZATION_TYPES:
            for provider in offers.get(category, []):
                by_provider.setdefault(provider["provider_name"].strip(), []).append(category)
        if by_provider:
            providers[country] = by_provider
    return {
        "poster_path": data.get("poster_path"),
        "details": _details_from_movie(data, tmdb_id),
        "providers": providers,
    }
