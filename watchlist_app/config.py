"""Runtime configuration for the watchlist application."""

import os
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TypeGuard

from dotenv import load_dotenv

load_dotenv()

PROJECT_DIR = Path(__file__).parent.parent
TMDB_API_KEY: str | None = os.getenv("TMDB_API_KEY")
LETTERBOXD_USERNAME: str | None = os.getenv("LETTERBOXD_USERNAME")
COUNTRY: str = os.getenv("COUNTRY", "FR")
DOWNLOADS_DIR = Path.home() / "Downloads"
PLATFORMS_TOML = PROJECT_DIR / "platforms.toml"
FLAGS_DIR = PROJECT_DIR / "static" / "flags"
# Flag files that are not countries.
_NOT_COUNTRIES = frozenset({"EU", "UN", "XX"})


@cache
def flag_countries() -> frozenset[str]:
    """Codes with a flag picture in static/flags (ISO 3166 two letters, upper case)."""
    codes = {path.stem.upper() for path in FLAGS_DIR.glob("*.svg")}
    return frozenset(code for code in codes if re.fullmatch(r"[A-Z]{2}", code)) - _NOT_COUNTRIES


def valid_country(code: object) -> TypeGuard[str]:
    """Any country the app can show: two upper-case letters with a flag file."""
    return isinstance(code, str) and code in flag_countries()


def data_dir() -> Path:
    return Path(os.getenv("WATCHLIST_DATA_DIR", PROJECT_DIR))


def database_path() -> Path:
    """The shared SQLite database (films, offers, scans, favorites, settings)."""
    return Path(os.getenv("WATCHLIST_DB", data_dir() / ".watchlist.sqlite3"))


@dataclass
class Settings:
    """Values the web app needs; tests build their own instance."""

    tmdb_api_key: str | None
    letterboxd_username: str | None
    country: str
    downloads_dir: Path


def load_settings() -> Settings:
    return Settings(
        tmdb_api_key=TMDB_API_KEY,
        letterboxd_username=LETTERBOXD_USERNAME,
        country=COUNTRY,
        downloads_dir=DOWNLOADS_DIR,
    )
