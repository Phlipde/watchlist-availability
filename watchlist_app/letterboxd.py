"""Letterboxd scraping and exported watchlist loading."""

import re
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from .config import DOWNLOADS_DIR

FILMS_PER_PAGE = 28
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_TITLE_YEAR_RE = re.compile(r"^(.*?)\s*\((\d{4})\)\s*$")


class LetterboxdError(Exception):
    """Raised when the watchlist cannot be fetched from Letterboxd."""


def parse_watchlist_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("div.poster-grid") or soup
    rows: list[dict] = []
    for poster in container.select("[data-item-slug]"):
        raw = poster.get("data-item-name") or poster.get("data-item-full-display-name") or ""
        title: str = raw
        year: int | None = None
        match = _TITLE_YEAR_RE.match(raw)
        if match:
            title, year = match.group(1), int(match.group(2))
        if not title:
            image = poster.find("img")
            if image and image.get("alt"):
                title = image.get("alt")
        if title:
            rows.append({"Name": title, "Year": year})
    return rows


def extract_num_entries(html: str) -> int | None:
    element = BeautifulSoup(html, "html.parser").select_one("[data-num-entries]")
    if element is None:
        return None
    try:
        return int(element["data-num-entries"])
    except (ValueError, TypeError, KeyError):
        return None


def fetch_watchlist_from_letterboxd(
    username: str,
    max_pages: int = 100,
    session: requests.Session | None = None,
    show_progress: bool = True,
) -> pd.DataFrame:
    sess = session or requests.Session()
    rows: list[dict] = []
    progress: tqdm | None = None
    try:
        for page in range(1, max_pages + 1):
            url = f"https://letterboxd.com/{username}/watchlist/page/{page}/"
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
                raise LetterboxdError(
                    f'Watchlist not found for "{username}" '
                    "(wrong username or private watchlist)."
                )
            if not response.ok:
                raise LetterboxdError(f"Letterboxd returned {response.status_code} for {url}.")
            if progress is None:
                progress = tqdm(
                    total=extract_num_entries(response.text),
                    desc="Fetching Letterboxd watchlist",
                    unit="film",
                    disable=not show_progress,
                )
            page_rows = parse_watchlist_page(response.text)
            if not page_rows:
                break
            rows.extend(page_rows)
            progress.update(len(page_rows))
            if len(page_rows) < FILMS_PER_PAGE:
                break
    finally:
        if progress is not None:
            progress.close()
    return pd.DataFrame(rows, columns=["Name", "Year"])


def find_watchlist_csv(downloads_dir: Path | None = None) -> Path:
    directory = downloads_dir or DOWNLOADS_DIR
    candidates = list(directory.glob("watchlist*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"No 'watchlist*.csv' file found in {directory}.\n"
            "Export your watchlist from letterboxd.com > Settings > Import & Export."
        )
    return max(candidates, key=lambda file: file.stat().st_mtime)


def load_watchlist(csv_path: Path) -> pd.DataFrame:
    dataframe = pd.read_csv(csv_path)
    missing = [column for column in ("Name", "Year") if column not in dataframe.columns]
    if missing:
        raise ValueError(
            f"Missing columns in the CSV: {missing}. "
            "Make sure the file comes from Letterboxd."
        )
    return dataframe


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
