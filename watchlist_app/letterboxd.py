"""Letterboxd scraping and exported watchlist loading."""

import csv
import io
import re
import threading
import time
import zipfile
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from .config import DOWNLOADS_DIR
from .models import WatchlistEntry
from .tmdb import clean_year

FILMS_PER_PAGE = 28
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_TITLE_YEAR_RE = re.compile(r"^(.*?)\s*\((\d{4})\)\s*$")
_TMDB_ID_RE = re.compile(r'data-tmdb-id="(\d+)"')
_TMDB_TYPE_RE = re.compile(r'data-tmdb-type="([a-z]+)"')
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_LOCAL = threading.local()


class LetterboxdError(Exception):
    """Raised when the watchlist cannot be fetched from Letterboxd."""


def _attribute(tag, name: str) -> str:
    """An HTML attribute as text ("" when missing); BeautifulSoup may return a list."""
    value = tag.get(name)
    if isinstance(value, list):
        return " ".join(value)
    return value or ""


def parse_watchlist_page(html: str) -> list[WatchlistEntry]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("div.poster-grid") or soup
    rows: list[WatchlistEntry] = []
    for poster in container.select("[data-item-slug]"):
        raw = _attribute(poster, "data-item-name") or _attribute(poster, "data-item-full-display-name")
        title = raw
        year: int | None = None
        match = _TITLE_YEAR_RE.match(raw)
        if match:
            title, year = match.group(1), int(match.group(2))
        if not title:
            image = poster.select_one("img")
            if image is not None:
                title = _attribute(image, "alt")
        if title:
            slug = _attribute(poster, "data-item-slug") or None
            rows.append(WatchlistEntry(title=title, year=year, slug=slug))
    return rows


def parse_tmdb_id(html: str) -> int | None:
    """Return the TMDB movie id a Letterboxd film page links to, if any."""
    kind = _TMDB_TYPE_RE.search(html)
    match = _TMDB_ID_RE.search(html)
    if match is None or (kind is not None and kind.group(1) != "movie"):
        return None
    return int(match.group(1))


_RATING_RE = re.compile(r'"ratingValue":\s*([0-9]+(?:\.[0-9]+)?)')


def parse_rating(html: str) -> float | None:
    """The Letterboxd average (0-5) from a film page, or None when the film has too few ratings."""
    match = _RATING_RE.search(html)
    if match is None:
        return None
    value = float(match.group(1))
    return value if 0 <= value <= 5 else None


def fetch_tmdb_id(slug: str, session: requests.Session | None = None) -> int | None:
    """Look up the TMDB movie id of a Letterboxd film.

    Returns None if the page has no TMDB link or points to a TV entry, so callers
    can fall back to a title search. Raises LetterboxdError when the page could not
    be loaded right now (network, rate limit, server error), so that a guess from
    the title search is not stored for good.
    """
    html = _film_page(slug, session)
    return parse_tmdb_id(html) if html is not None else None


def fetch_rating(slug: str, session: requests.Session | None = None) -> float | None:
    """The Letterboxd average rating of a film; raises LetterboxdError like fetch_tmdb_id."""
    html = _film_page(slug, session)
    return parse_rating(html) if html is not None else None


def _film_page(slug: str, session: requests.Session | None) -> str | None:
    """HTML of a Letterboxd film page; None for an unknown film or an invalid slug."""
    if not slug or not _SLUG_RE.match(slug):
        return None
    sess = session
    if sess is None:
        sess = getattr(_LOCAL, "session", None)
        if sess is None:
            sess = requests.Session()
            _LOCAL.session = sess
    try:
        response = sess.get(
            f"https://letterboxd.com/film/{slug}/",
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise LetterboxdError(f"Letterboxd could not be reached ({type(exc).__name__}).") from None
    if response.status_code == 429 or response.status_code >= 500:
        raise LetterboxdError(f"Letterboxd returned {response.status_code}.")
    if not response.ok:
        return None
    return response.text


def extract_num_entries(html: str) -> int | None:
    element = BeautifulSoup(html, "html.parser").select_one("[data-num-entries]")
    if element is None:
        return None
    try:
        return int(_attribute(element, "data-num-entries"))
    except ValueError:
        return None


def _get_list_page(sess: requests.Session, url: str, not_found: str) -> str:
    """HTML of one page of a user's list, with one retry after a rate limit; LetterboxdError otherwise."""
    for attempt in range(2):
        try:
            response = sess.get(url, headers={"User-Agent": _USER_AGENT}, timeout=10)
        except requests.RequestException as exc:
            raise LetterboxdError(f"Network error reaching Letterboxd: {exc}") from exc
        if response.status_code == 429 and attempt == 0:
            time.sleep(2)
            continue
        break
    if response.status_code == 404:
        raise LetterboxdError(not_found)
    if not response.ok:
        raise LetterboxdError(f"Letterboxd returned {response.status_code} for {url}.")
    return response.text


def fetch_watchlist_from_letterboxd(
    username: str,
    max_pages: int = 100,
    session: requests.Session | None = None,
    show_progress: bool = True,
) -> list[WatchlistEntry]:
    sess = session or requests.Session()
    rows: list[WatchlistEntry] = []
    progress: tqdm | None = None
    try:
        for page in range(1, max_pages + 1):
            url = f"https://letterboxd.com/{username}/watchlist/page/{page}/"
            html = _get_list_page(
                sess, url, f"Watchlist not found for “{username}” (wrong username or private watchlist)."
            )
            if progress is None:
                progress = tqdm(
                    total=extract_num_entries(html),
                    desc="Fetching Letterboxd watchlist",
                    unit="film",
                    disable=not show_progress,
                )
            page_rows = parse_watchlist_page(html)
            if not page_rows:
                break
            rows.extend(page_rows)
            progress.update(len(page_rows))
            if len(page_rows) < FILMS_PER_PAGE:
                break
        else:
            raise LetterboxdError(f"The watchlist has more than {max_pages * FILMS_PER_PAGE} films.")
    finally:
        if progress is not None:
            progress.close()
    return rows


def parse_watched_page(html: str) -> tuple[list[str], bool]:
    """The film slugs on one page of /{user}/films/ and whether an older page follows.

    The page has the watchlist's poster grid (72 films, checked 2026-11-26); the pager links
    the next page as `.pagination a.next`.
    """
    slugs = [entry.slug for entry in parse_watchlist_page(html) if entry.slug]
    more = BeautifulSoup(html, "html.parser").select_one(".pagination a.next") is not None
    return slugs, more


def fetch_watched_slugs(
    username: str, max_pages: int = 500, session: requests.Session | None = None
) -> list[str]:
    """Slugs of every film a user has marked as watched, newest first, from the public /films/ pages."""
    sess = session or requests.Session()
    slugs: list[str] = []
    for page in range(1, max_pages + 1):
        suffix = f"page/{page}/" if page > 1 else ""
        html = _get_list_page(
            sess,
            f"https://letterboxd.com/{username}/films/{suffix}",
            f"Watched films not found for “{username}” (wrong username or private profile).",
        )
        page_slugs, more = parse_watched_page(html)
        slugs.extend(page_slugs)
        if not page_slugs or not more:
            break
    else:
        raise LetterboxdError(f"More than {max_pages} pages of watched films.")
    return list(dict.fromkeys(slugs))  # a film logged while paging can show up twice


def find_watchlist_csv(downloads_dir: Path | None = None) -> Path:
    directory = downloads_dir or DOWNLOADS_DIR
    candidates = list(directory.glob("watchlist*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"No 'watchlist*.csv' file found in {directory}.\n"
            "Export your watchlist from letterboxd.com > Settings > Import & Export."
        )
    return max(candidates, key=lambda file: file.stat().st_mtime)


def parse_watchlist_csv(text: str) -> list[WatchlistEntry]:
    """Read a Letterboxd watchlist export (columns Name and Year are required)."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    columns = reader.fieldnames or []
    missing = [column for column in ("Name", "Year") if column not in columns]
    if missing:
        raise ValueError(f"Missing columns in the CSV: {missing}. Make sure the file comes from Letterboxd.")
    rows = [row for row in reader if (row.get("Name") or "").strip()]
    # The website lists the most recently added film first; sort the export the same way so that
    # the position on the watchlist means the same for both sources.
    if "Date" in columns:
        rows.sort(key=lambda row: row.get("Date") or "", reverse=True)
    return [WatchlistEntry(title=row["Name"].strip(), year=clean_year(row["Year"] or None)) for row in rows]


def load_watchlist(csv_path: Path) -> list[WatchlistEntry]:
    return parse_watchlist_csv(csv_path.read_text(encoding="utf-8"))


def find_letterboxd_zip(downloads_dir: Path) -> Path | None:
    for zip_path in sorted(
        downloads_dir.glob("*.zip"),
        key=lambda file: file.stat().st_mtime,
        reverse=True,
    ):
        try:
            with zipfile.ZipFile(zip_path) as archive:
                if any(name.endswith("watchlist.csv") for name in archive.namelist()):
                    return zip_path
        except zipfile.BadZipFile:
            continue
    return None


def extract_watchlist_from_zip(zip_path: Path, downloads_dir: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        entry = next(name for name in archive.namelist() if name.endswith("watchlist.csv"))
        archive.extract(entry, downloads_dir)
        extracted = downloads_dir / entry
    zip_path.unlink()
    destination = downloads_dir / "watchlist.csv"
    if extracted != destination:
        extracted.replace(destination)
        try:
            extracted.parent.rmdir()
        except OSError:
            pass
    return destination
