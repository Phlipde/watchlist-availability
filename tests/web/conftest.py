"""Shared setup for the tests of the Flask routes."""

import pytest
from flask import Flask

from tests.helpers import know_services
from watchlist_app.config import Settings
from watchlist_app.scan_service import ScanService
from watchlist_app.settings import AppSettings
from watchlist_app.store import Store
from web import routes


class FakeThread:
    """Records started scans instead of running them."""

    started: list = []

    def __init__(self, target, args, daemon):
        self.args = args

    def start(self):
        FakeThread.started.append(self.args[0])


@pytest.fixture
def store():
    database = Store(":memory:")
    know_services(database)
    yield database
    database.close()


@pytest.fixture
def settings(store, tmp_path):
    defaults = Settings(
        tmdb_api_key="test-key", letterboxd_username=None, country="DE", downloads_dir=tmp_path
    )
    return AppSettings(store, defaults)


@pytest.fixture
def service(store, settings):
    FakeThread.started = []
    return ScanService(store, settings, thread_factory=FakeThread)


@pytest.fixture
def client(store, settings, service):
    app = Flask(__name__, template_folder="../../templates", static_folder="../../static")
    routes.register_routes(app, store=store, settings=settings, service=service)
    return app.test_client()
