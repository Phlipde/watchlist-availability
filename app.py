"""Flask entry point for the watchlist availability web application."""

from __future__ import annotations

import os

from flask import Flask

from watchlist_app import config
from watchlist_app.legacy_import import import_legacy_data
from watchlist_app.scan_service import ScanService
from watchlist_app.scheduler import start_scheduler
from watchlist_app.settings import AppSettings
from watchlist_app.store import Store
from web import routes as web_routes

app = Flask(__name__)
_STORE = Store(config.database_path())
import_legacy_data(_STORE, **config.legacy_paths())
_SETTINGS = AppSettings(_STORE)
_SERVICE = ScanService(_STORE, _SETTINGS)

web_routes.register_routes(app, store=_STORE, settings=_SETTINGS, service=_SERVICE)

# A scan that was running when the app stopped is closed and started again.
_SERVICE.recover_interrupted()
_SCHEDULER = None
if os.getenv("WATCHLIST_DISABLE_SCHEDULER", "").lower() not in {"1", "true", "yes"}:
    _SCHEDULER = start_scheduler(_STORE, _SETTINGS, _SERVICE)


@app.get("/health")
def health():
    """For the Docker healthcheck: the database answers and, if there is a schedule, its thread is alive."""
    try:
        _STORE.list_jobs(limit=1)
    except Exception:
        return {"status": "database unavailable"}, 503
    if _SCHEDULER is not None and not _SCHEDULER.is_alive():
        return {"status": "schedule stopped"}, 503
    return {"status": "ok"}, 200


if __name__ == "__main__":
    # No reloader: it would start a second process with its own schedule and scans.
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true", use_reloader=False)
