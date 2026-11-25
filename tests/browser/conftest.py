"""Shared setup for the browser tests (Playwright).

The app runs on a local port with its own empty database; Letterboxd and TMDB
are replaced by fixed answers, so no request leaves the computer.

Run with `pytest -m browser`. Needs `pip install -r requirements-dev.txt` and a
browser: `playwright install chromium`, or an installed Chrome or Edge.
"""

import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from flask import Flask
from werkzeug.serving import make_server

from tests.helpers import know_services
from watchlist_app.config import Settings
from watchlist_app.models import WatchlistEntry
from watchlist_app.scan_service import ScanService
from watchlist_app.settings import AppSettings
from watchlist_app.store import Store
from web import routes

PROJECT = Path(__file__).resolve().parents[2]


ENTRIES = [WatchlistEntry("Heat", 1995), WatchlistEntry("Alien", 1979), WatchlistEntry("Nope Film", 2001)]


IDS = {"Heat": 949, "Alien": 348}


BUNDLES = {
    949: {
        "poster_path": None,
        "details": {
            "tmdb_title": "Heat",
            "release_date": "1995-12-15",
            "overview": "A thief.",
            "rating": 8.0,
            "runtime": 120,
            "genres": ["Action", "Thriller", "Sci-Fi"],
            "trailer_url": "https://www.youtube.com/watch?v=abc",
            "release_dates": {"DE": {"certification": "16", "home": "2099-03-01"}},
        },
        "providers": {"DE": {"Netflix": ["flatrate"]}, "GB": {"BBC iPlayer": ["free"]}},
    },
    348: {
        "poster_path": None,
        "details": {
            "tmdb_title": "Alien",
            "release_date": "1979-05-25",
            "overview": "In space.",
            "rating": 8.1,
            "genres": ["Thriller", "Sci-Fi"],
            "similar_ids": [949, 111],
        },
        "providers": {"DE": {"Arte": ["free"]}, "GB": {"Arte": ["flatrate"]}},
    },
    111: {
        "poster_path": None,
        "details": {
            "tmdb_title": "Heat 2",
            "release_date": "2026-01-01",
            "overview": "Sequel.",
            "rating": 6.0,
        },
        "providers": {},
    },
}


CANDIDATES = [
    {
        "tmdb_id": 949,
        "title": "Heat",
        "original_title": "Heat",
        "year": 1995,
        "poster_path": None,
        "overview": "",
    },
    {
        "tmdb_id": 111,
        "title": "Heat 2",
        "original_title": "Heat 2",
        "year": 2026,
        "poster_path": None,
        "overview": "",
    },
]


CATALOG = {
    country: [{"name": name, "logo_path": None, "priority": rank} for rank, name in enumerate(names)]
    for country, names in {"DE": ["Netflix", "Arte", "MUBI"], "GB": ["BBC iPlayer", "Arte", "MUBI"]}.items()
}


@pytest.fixture
def app_server(tmp_path):
    """The web app with fixed answers for Letterboxd and TMDB, on a free local port."""
    store = Store(tmp_path / "test.sqlite3")
    know_services(store)
    defaults = Settings(
        tmdb_api_key="test-key", letterboxd_username="tester", country="DE", downloads_dir=tmp_path
    )
    settings = AppSettings(store, defaults)
    settings.update({"subscriptions": ["Netflix"]})
    service = ScanService(store, settings)
    app = Flask(
        "watchlist", template_folder=str(PROJECT / "templates"), static_folder=str(PROJECT / "static")
    )
    routes.register_routes(app, store=store, settings=settings, service=service)
    fakes = [
        patch("watchlist_app.scan_service.load_watchlist", return_value=(ENTRIES, "Letterboxd @tester")),
        patch("watchlist_app.tmdb.search_movie_id", side_effect=lambda title, year, key=None: IDS.get(title)),
        patch(
            "watchlist_app.tmdb.get_movie_bundle", side_effect=lambda tmdb_id, key=None: BUNDLES.get(tmdb_id)
        ),
        patch("watchlist_app.tmdb.search_movies", return_value=CANDIDATES),
        # The services TMDB lists per country; the services page and "Add a service" offer only these.
        patch(
            "watchlist_app.tmdb.get_region_providers",
            side_effect=lambda country, key=None: CATALOG.get(country, []),
        ),
    ]
    for fake in fakes:
        fake.start()
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {"url": f"http://127.0.0.1:{server.server_port}", "store": store, "settings": settings}
    server.shutdown()
    for fake in fakes:
        fake.stop()
    store.close()


@pytest.fixture(scope="session")
def browser():
    playwright_api = pytest.importorskip("playwright.sync_api")
    with playwright_api.sync_playwright() as playwright:
        launched = None
        for options in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
            try:
                launched = playwright.chromium.launch(**options)
                break
            except playwright_api.Error:
                continue
        if launched is None:
            pytest.skip("No browser for Playwright: run `playwright install chromium`.")
        yield launched
        launched.close()


@pytest.fixture
def page(browser):
    # Wide, so Year, Runtime and Rating stay in the bar; one test narrows the window on purpose.
    context = browser.new_context(service_workers="block", viewport={"width": 2400, "height": 1000})
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield page
    context.close()
    assert errors == [], f"JavaScript errors: {errors}"
