"""
watchlist_availability.py

Checks which films from your Letterboxd watchlist are available to stream
via the TMDB API, grouped into two sections: Free and Paid.

The watchlist is fetched automatically from your public Letterboxd page
(via LETTERBOXD_USERNAME in .env). Otherwise, an exported ZIP or CSV is used
as a fallback.

Usage: python watchlist_availability.py
"""

import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from tabulate import tabulate
from tqdm import tqdm

# =========================
# CONFIGURATION
# =========================

from watchlist_app.config import (
    COUNTRY,
    DOWNLOADS_DIR,
    LETTERBOXD_USERNAME,
    PLATFORMS_TOML,
    TMDB_API_KEY,
)
from watchlist_app.providers import (
    _ALL_PROVIDERS,
    _DEFAULT_ENABLED,
    _SECTION_ORDER,
    load_platforms_config,
)
from watchlist_app import cli as _cli
from watchlist_app import letterboxd as _letterboxd
from watchlist_app import results as _results
from watchlist_app import rendering as _rendering
from watchlist_app import tmdb as _tmdb

_TMDB_IMAGE_BASE_URL = _tmdb._TMDB_IMAGE_BASE_URL
_TMDB_POSTER_PATHS = _tmdb._TMDB_POSTER_PATHS
_TMDB_MOVIE_DATA = _tmdb._TMDB_MOVIE_DATA
FILMS_PER_PAGE = _letterboxd.FILMS_PER_PAGE
_USER_AGENT = _letterboxd._USER_AGENT
_TITLE_YEAR_RE = _letterboxd._TITLE_YEAR_RE

# =========================
# FUNCTIONS
# =========================


LetterboxdError = _letterboxd.LetterboxdError

def _date_en(value: date) -> str:
    return _rendering._date_en(value)



def _parse_watchlist_page(html: str) -> list[dict]:
    return _letterboxd.parse_watchlist_page(html)


def _extract_num_entries(html: str) -> int | None:
    return _letterboxd.extract_num_entries(html)


def fetch_watchlist_from_letterboxd(
    username: str,
    max_pages: int = 100,
    session: requests.Session | None = None,
    show_progress: bool = True,
) -> pd.DataFrame:
    original_tqdm = _letterboxd.tqdm
    _letterboxd.tqdm = tqdm
    try:
        return _letterboxd.fetch_watchlist_from_letterboxd(
            username,
            max_pages=max_pages,
            session=session,
            show_progress=show_progress,
        )
    finally:
        _letterboxd.tqdm = original_tqdm


def find_watchlist_csv(downloads_dir: Path | None = None) -> Path:
    return _letterboxd.find_watchlist_csv(downloads_dir)


def load_watchlist(csv_path: Path) -> pd.DataFrame:
    return _letterboxd.load_watchlist(csv_path)


def _clean_year(year: int | str | float | None) -> int | None:
    return _tmdb.clean_year(year)


def get_tmdb_id(
    title: str, year: int | str | float | None, api_key: str | None = None
) -> int | None:
    original_requests, original_time = _tmdb.requests, _tmdb.time
    _tmdb.requests, _tmdb.time = requests, time
    try:
        return _tmdb.get_tmdb_id(title, year, api_key or TMDB_API_KEY)
    finally:
        _tmdb.requests, _tmdb.time = original_requests, original_time


def get_streaming_platforms(
    tmdb_id: int, country: str = "FR", api_key: str | None = None
) -> dict[str, set[str]]:
    original_requests = _tmdb.requests
    _tmdb.requests = requests
    try:
        return _tmdb.get_streaming_platforms(tmdb_id, country, api_key or TMDB_API_KEY)
    finally:
        _tmdb.requests = original_requests


def get_tmdb_details(tmdb_id: int, api_key: str | None = None) -> dict:
    original_requests = _tmdb.requests
    _tmdb.requests = requests
    try:
        return _tmdb.get_tmdb_details(tmdb_id, api_key or TMDB_API_KEY)
    finally:
        _tmdb.requests = original_requests

def build_results(
    df: pd.DataFrame,
    targets: dict[str, str],
    country: str = "FR",
    api_key: str | None = None,
    progress_callback=None,
    result_callback=None,
    cancel_callback=None,
    unavailable_callback=None,
    failed_callback=None,
    include_details: bool = False,
) -> list[dict]:
    original = (_results.get_tmdb_id, _results.get_streaming_platforms, _results.get_tmdb_details)
    original_tqdm, original_time = _results.tqdm, _results.time
    _results.get_tmdb_id = get_tmdb_id
    _results.get_streaming_platforms = get_streaming_platforms
    _results.get_tmdb_details = get_tmdb_details
    _results.tqdm, _results.time = tqdm, time
    try:
        return _results.build_results(
            df, targets, country=country, api_key=api_key,
            progress_callback=progress_callback, result_callback=result_callback,
            cancel_callback=cancel_callback, unavailable_callback=unavailable_callback,
            failed_callback=failed_callback,
            include_details=include_details,
        )
    finally:
        (_results.get_tmdb_id, _results.get_streaming_platforms, _results.get_tmdb_details) = original
        _results.tqdm, _results.time = original_tqdm, original_time

def _split_by_section(results: list[dict], targets: dict[str, str]):
    return _rendering._split_by_section(results, targets)


def _sort_results(results: list[dict], targets: dict[str, str]) -> pd.DataFrame:
    return _rendering._sort_results(results, targets)


def _summary_line(results: list[dict], targets: dict[str, str]) -> str:
    return _rendering._summary_line(results, targets)


def _render_section(title: str, results: list[dict], targets: dict[str, str]) -> str:
    original_tabulate = _rendering.tabulate
    _rendering.tabulate = tabulate
    try:
        return _rendering._render_section(title, results, targets)
    finally:
        _rendering.tabulate = original_tabulate


def display_results(results: list[dict], targets: dict[str, str] | None = None) -> None:
    return _rendering.display_results(results, targets)


def save_results(
    results: list[dict],
    source_name: str,
    targets: dict[str, str],
    output_dir: Path | None = None,
) -> Path:
    return _rendering.save_results(results, source_name, targets, output_dir)


def _render_html_section(title: str, results: list[dict], targets: dict[str, str]) -> str:
    return _rendering._render_html_section(title, results, targets)


def _find_letterboxd_zip(downloads_dir: Path) -> Path | None:
    return _letterboxd.find_letterboxd_zip(downloads_dir)


def _extract_watchlist_from_zip(zip_path: Path, downloads_dir: Path) -> Path:
    return _letterboxd.extract_watchlist_from_zip(zip_path, downloads_dir)


def _prompt_for_csv(downloads_dir: Path | None = None, username: str | None = None) -> Path:
    return _cli.prompt_for_csv(
        sys.modules[__name__], downloads_dir=downloads_dir, username=username
    )


def load_watchlist_source() -> tuple[pd.DataFrame, str, Path]:
    original_prompt = _cli.prompt_for_csv
    _cli.prompt_for_csv = lambda wa, downloads_dir=None, username=None: _prompt_for_csv(
        downloads_dir=downloads_dir, username=username
    )
    try:
        return _cli.load_watchlist_source(sys.modules[__name__])
    finally:
        _cli.prompt_for_csv = original_prompt


def test_unknown_providers(
    df: pd.DataFrame, country: str = "DE", api_key: str | None = None
) -> None:
    return _cli.test_unknown_providers(sys.modules[__name__], df, country, api_key)


def main() -> None:
    return _cli.main(sys.modules[__name__])


if __name__ == "__main__":
    main()
