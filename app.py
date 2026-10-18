"""Flask entry point for the watchlist availability web application."""

from __future__ import annotations

import os
import threading
from pathlib import Path

from flask import Flask

import watchlist_availability as wa
from web import cache as web_cache
from web import routes as web_routes

app = Flask(__name__)
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()
_DATA_DIR = Path(os.getenv("WATCHLIST_DATA_DIR", Path(__file__).parent))
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_CACHE_PATH = Path(os.getenv("WATCHLIST_CACHE_PATH", _DATA_DIR / ".watchlist_cache.json"))
_LATEST_RESULT_PATH = Path(os.getenv("WATCHLIST_LATEST_PATH", _DATA_DIR / ".watchlist_latest.json"))
_FAVORITES_DB = Path(os.getenv("WATCHLIST_FAVORITES_DB", _DATA_DIR / ".watchlist_favorites.sqlite3"))
_RESULT_CACHE: dict[str, dict] = web_cache.load_cache(_CACHE_PATH)

web_routes.register_routes(
    app,
    jobs=_JOBS,
    jobs_lock=_JOBS_LOCK,
    result_cache=_RESULT_CACHE,
    cache_path=_CACHE_PATH,
    latest_result_path=_LATEST_RESULT_PATH,
    favorites_path=_FAVORITES_DB,
    wa=wa,
)


@app.get("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
