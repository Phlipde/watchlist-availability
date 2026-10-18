"""Movie result construction and scan callbacks."""

import time
from collections.abc import Callable

import pandas as pd
from tqdm import tqdm

from .tmdb import _TMDB_MOVIE_DATA, _TMDB_POSTER_PATHS


def clean_year(year: int | str | float | None) -> int | None:
    if year is None:
        return None
    if not isinstance(year, str) and pd.isna(year):
        return None
    try:
        return int(year)
    except (ValueError, TypeError):
        return None


def build_results(
    df: pd.DataFrame,
    targets: dict[str, str],
    country: str = "FR",
    api_key: str | None = None,
    progress_callback=None,
    result_callback=None,
    cancel_callback=None,
    unavailable_callback=None,
    failed_callback: Callable | None = None,
    include_details: bool = False,
) -> list[dict]:
    """Walk the DataFrame and return one result dict per available film.

    Makes a single TMDB API call per film. Each platform column holds the SET of
    TMDB monetization types the film is available under on that provider (a subset
    of free / ads / flatrate / rent), or an empty set. Sectioning (Free / Paid)
    is derived from these sets later.

    Returns:
        List of dicts with keys 'Title', 'Year', and one set per platform.
        Only films available on at least one target are included.
    """
    results: list[dict] = []

    for current, (_, row) in enumerate(tqdm(
        df.iterrows(),
        total=len(df),
        desc="Checking streaming availability on TMDB",
        unit="film",
    ), start=1):
        if cancel_callback and cancel_callback():
            break
        title = row["Name"]
        year = clean_year(row["Year"])

        try:
            tmdb_id = get_tmdb_id(title, year, api_key=api_key)
        except (KeyError, TypeError, ValueError) as exc:
            if failed_callback:
                failed_callback({"Title": title, "Year": year}, exc)
            if progress_callback:
                progress_callback(current, len(df), title)
            continue
        if tmdb_id is None:
            if unavailable_callback:
                unavailable_callback({"Title": title, "Year": year})
            if progress_callback:
                progress_callback(current, len(df), title)
            time.sleep(0.15)
            continue

        try:
            providers = get_streaming_platforms(tmdb_id, country=country, api_key=api_key)
            details = get_tmdb_details(tmdb_id, api_key=api_key) if include_details else _TMDB_MOVIE_DATA.get(tmdb_id, {})
        except (KeyError, TypeError, ValueError) as exc:
            if failed_callback:
                failed_callback({"Title": title, "Year": year}, exc)
            if progress_callback:
                progress_callback(current, len(df), title)
            continue

        row_data: dict = {
            "Title": title,
            "Year": year,
            "PosterPath": _TMDB_POSTER_PATHS.get(tmdb_id),
            **details,
        }
        for display, tmdb_name in targets.items():
            row_data[display] = providers.get(tmdb_name, set())

        if any(row_data[display] for display in targets):
            results.append(row_data)
            if result_callback:
                result_callback(row_data)
        elif unavailable_callback:
            unavailable_callback({"Title": title, "Year": year})

        if progress_callback:
            progress_callback(current, len(df), title)

        time.sleep(0.15)

    return results



# Assigned by the compatibility facade before each call.
get_tmdb_id = None
get_streaming_platforms = None
get_tmdb_details = None
