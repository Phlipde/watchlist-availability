"""Runtime configuration for the watchlist application."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_DIR = Path(__file__).parent.parent
TMDB_API_KEY: str | None = os.getenv("TMDB_API_KEY")
LETTERBOXD_USERNAME: str | None = os.getenv("LETTERBOXD_USERNAME")
COUNTRY: str = os.getenv("COUNTRY", "FR")
DOWNLOADS_DIR = Path.home() / "Downloads"
PLATFORMS_TOML = PROJECT_DIR / "platforms.toml"
COUNTRIES = ("FR", "DE", "US", "GB")


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
