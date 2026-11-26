"""Shared test setup."""

import pytest

from watchlist_app import letterboxd, tmdb


@pytest.fixture(autouse=True)
def no_provider_catalog_request(request, monkeypatch):
    """Scans load the provider list from TMDB; tests must never send that request.

    Tests marked `provider_catalog` use the real function (with their own mocks).
    """
    if request.node.get_closest_marker("provider_catalog") is None:
        monkeypatch.setattr(tmdb, "get_region_providers", lambda country, api_key=None: [])


@pytest.fixture(autouse=True)
def no_regions_request(request, monkeypatch):
    """Scans load TMDB's country list; tests never send that request (marked tests mock HTTP instead)."""
    if request.node.get_closest_marker("regions_request") is None:
        monkeypatch.setattr(tmdb, "get_regions", lambda api_key=None: [])


@pytest.fixture(autouse=True)
def no_letterboxd_rating_request(request, monkeypatch):
    """Scans refresh the Letterboxd rating from the film page; tests must never load it.

    Tests marked `letterboxd_rating` use the real function (with their own mocks).
    """
    if request.node.get_closest_marker("letterboxd_rating") is None:
        monkeypatch.setattr(letterboxd, "fetch_rating", lambda slug, session=None: None)


@pytest.fixture(autouse=True)
def no_letterboxd_watched_request(monkeypatch):
    """A finished scan loads the watched films from Letterboxd; tests get an empty list instead.

    A test that passes its own (mocked) session uses the real function.
    """
    real = letterboxd.fetch_watched_slugs

    def fake(username, max_pages=500, session=None):
        return real(username, max_pages, session) if session is not None else []

    monkeypatch.setattr(letterboxd, "fetch_watched_slugs", fake)
