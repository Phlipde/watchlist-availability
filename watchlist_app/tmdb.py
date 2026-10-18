"""TMDB API access and movie metadata caches."""

import time

import pandas as pd
import requests

_TMDB_POSTER_PATHS: dict[int, str | None] = {}
_TMDB_MOVIE_DATA: dict[int, dict] = {}
_TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"


def clean_year(year: int | str | float | None) -> int | None:
    if year is None:
        return None
    if not isinstance(year, str) and pd.isna(year):
        return None
    try:
        return int(year)
    except (ValueError, TypeError):
        return None


def get_tmdb_id(
    title: str,
    year: int | str | float | None,
    api_key: str | None = None,
) -> int | None:
    key = api_key
    params: dict = {"api_key": key, "query": title}
    normalized_year = clean_year(year)
    if normalized_year is not None:
        params["year"] = normalized_year

    for attempt in range(2):
        try:
            response = requests.get(
                "https://api.themoviedb.org/3/search/movie",
                params=params,
                timeout=10,
            )
            if response.status_code == 429:
                if attempt == 0:
                    time.sleep(2)
                    continue
                return None
            response.raise_for_status()
            results = response.json().get("results", [])
            if not results:
                return None
            movie_id = results[0]["id"]
            _TMDB_POSTER_PATHS[movie_id] = results[0].get("poster_path")
            _TMDB_MOVIE_DATA[movie_id] = {
                "overview": results[0].get("overview", ""),
                "rating": results[0].get("vote_average"),
                "backdrop_path": results[0].get("backdrop_path"),
            }
            return movie_id
        except requests.RequestException:
            return None
    return None


def get_streaming_platforms(
    tmdb_id: int,
    country: str = "FR",
    api_key: str | None = None,
) -> dict[str, set[str]]:
    try:
        response = requests.get(
            f"https://api.themoviedb.org/3/movie/{tmdb_id}/watch/providers",
            params={"api_key": api_key},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return {}

    country_data = data.get("results", {}).get(country, {})
    result: dict[str, set[str]] = {}
    for category in ("free", "ads", "flatrate", "rent"):
        for provider in country_data.get(category, []):
            result.setdefault(provider["provider_name"], set()).add(category)
    return result


def get_tmdb_details(tmdb_id: int, api_key: str | None = None) -> dict:
    if tmdb_id in _TMDB_MOVIE_DATA and "runtime" in _TMDB_MOVIE_DATA[tmdb_id]:
        return _TMDB_MOVIE_DATA[tmdb_id]
    try:
        response = requests.get(
            f"https://api.themoviedb.org/3/movie/{tmdb_id}",
            params={"api_key": api_key, "append_to_response": "videos"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return {}

    videos = data.get("videos", {}).get("results", [])
    trailer = next(
        (
            video for video in videos
            if video.get("site") == "YouTube" and video.get("type") == "Trailer"
        ),
        None,
    )
    details = {
        "overview": data.get("overview", ""),
        "rating": data.get("vote_average"),
        "backdrop_path": data.get("backdrop_path"),
        "runtime": data.get("runtime"),
        "genres": [genre.get("name") for genre in data.get("genres", [])],
        "tmdb_url": f"https://www.themoviedb.org/movie/{tmdb_id}",
        "trailer_url": f"https://www.youtube.com/watch?v={trailer['key']}" if trailer else None,
    }
    _TMDB_MOVIE_DATA[tmdb_id] = details
    return details
