"""Any country with a flag: the check, the list for the picker and the countries in use."""

import json
from unittest.mock import patch

import pytest

from tests.test_tmdb import API_KEY, response
from watchlist_app import config, scan_run, tmdb
from watchlist_app.config import Settings
from watchlist_app.settings import AppSettings
from watchlist_app.store import REGIONS_SETTING, Store


@pytest.fixture
def settings(tmp_path):
    store = Store(":memory:")
    yield AppSettings(store, Settings("key", None, "DE", tmp_path))
    store.close()


def test_valid_country_needs_two_capitals_and_a_flag():
    assert config.valid_country("PL") and config.valid_country("FR")
    for code in ("xx", "pl", "PLX", "<b>", "PL\n", "", None, 3, ["PL"], "XX", "EU", "QQ"):
        assert not config.valid_country(code), code


def test_settings_accept_any_country(settings):
    settings.update({"country": "PL"})
    assert settings.country == "PL"
    with pytest.raises(ValueError):
        settings.update({"country": "QQ"})
    # A new country starts with no own services.
    assert settings.subscriptions("PL") == []


def test_countries_in_use_are_the_country_and_those_with_saved_services(settings):
    settings._store.set_profile_setting("subscriptions:FR", "[]")
    settings._store.set_profile_setting("subscription_costs:PL", "{}")
    settings._store.set_profile_setting("subscriptionsXIT", "[]")  # not the prefix
    settings._store.set_profile_setting("subscriptions:GB", "[]", profile_id=2)  # another profile
    assert settings.countries_in_use() == ["DE", "FR", "PL"]


def test_backup_restore_keeps_a_scan_of_any_country():
    store = Store(":memory:")
    backup = {"version": 1, "scans": [{"created": 40.0, "country": "PL", "results": [{"title": "Ida"}]}]}
    assert store.import_backup(backup)["scans"] == 1
    assert store.latest_scan("PL")["results"][0]["title"] == "Ida"


def test_country_choices_fall_back_to_the_flags(settings):
    assert settings.country_choices() == sorted(config.flag_countries())
    settings._store.set_setting(REGIONS_SETTING, json.dumps({"codes": ["PL", "FR", "QQ"], "fetched_at": 1}))
    assert settings.country_choices() == ["DE", "FR", "PL"]  # the app's own country stays


def test_regions_refresh_keeps_the_fallback_when_tmdb_fails(settings, monkeypatch):
    store = settings._store

    def broken(api_key=None):
        raise tmdb.TmdbError("down")

    monkeypatch.setattr(tmdb, "get_regions", broken)
    assert not scan_run.refresh_regions(store, "key")
    assert settings.country_choices() == sorted(config.flag_countries())
    monkeypatch.setattr(tmdb, "get_regions", lambda api_key=None: ["PL", "GB", "QQ"])
    assert not scan_run.refresh_regions(store, None)  # no key, no request
    assert scan_run.refresh_regions(store, "key")
    assert not scan_run.refresh_regions(store, "key")  # fresh for a week
    assert settings.country_choices() == ["DE", "GB", "PL"]


@pytest.mark.regions_request
def test_get_regions_reads_the_codes():
    data = {"results": [{"iso_3166_1": "PL", "english_name": "Poland"}, {"english_name": "?"}]}
    with patch("watchlist_app.tmdb._http_get", return_value=response(data)) as get:
        assert tmdb.get_regions(API_KEY) == ["PL"]
    assert get.call_args[0][0].endswith("/watch/providers/regions")
