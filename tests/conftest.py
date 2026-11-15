"""Shared test setup."""

import pytest

from watchlist_app import tmdb


@pytest.fixture(autouse=True)
def no_provider_catalog_request(request, monkeypatch):
    """Scans load the provider list from TMDB; tests must never send that request.

    Tests marked `provider_catalog` use the real function (with their own mocks).
    """
    if request.node.get_closest_marker("provider_catalog") is None:
        monkeypatch.setattr(tmdb, "get_region_providers", lambda country, api_key=None: [])
