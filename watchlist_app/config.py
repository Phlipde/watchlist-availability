"""Runtime configuration for the watchlist application."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY: str | None = os.getenv("TMDB_API_KEY")
LETTERBOXD_USERNAME: str | None = os.getenv("LETTERBOXD_USERNAME")
COUNTRY: str = os.getenv("COUNTRY", "FR")
DOWNLOADS_DIR = Path.home() / "Downloads"
PLATFORMS_TOML = Path(__file__).parent.parent / "platforms.toml"
