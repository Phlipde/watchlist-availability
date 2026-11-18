"""Tests for the Flask routes."""

import datetime
import io
import json
import time

import pytest
from flask import Flask

from watchlist_app.config import Settings
from watchlist_app.models import WatchlistEntry
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
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    routes.register_routes(app, store=store, settings=settings, service=service)
    return app.test_client()


class TestUploadLimit:
    def test_too_large_upload_is_rejected(self, client, monkeypatch):
        client.application.config["MAX_CONTENT_LENGTH"] = 100
        upload = {"backup": (io.BytesIO(b"x" * 1000), "backup.json")}
        answer = client.post("/api/backup", data=upload, content_type="multipart/form-data")
        assert answer.status_code == 413 and "too large" in answer.get_json()["error"]


class TestScanStart:
    def test_same_country_reconnects_to_running_scan(self, client):
        first = client.post("/api/scan", data={"country": "DE"}).get_json()
        second = client.post("/api/scan", data={"country": "DE"}).get_json()
        assert second == {"job_id": first["job_id"], "reconnected": True}
        assert len(FakeThread.started) == 1

    def test_other_country_cancels_old_scan_and_starts_new_one(self, client, service):
        first = client.post("/api/scan", data={"country": "DE"}).get_json()
        second = client.post("/api/scan", data={"country": "GB"}).get_json()
        assert second["job_id"] != first["job_id"]
        assert "reconnected" not in second
        assert service._live[first["job_id"]]["cancel_requested"] is True
        assert service._live[second["job_id"]]["country"] == "GB"
        assert len(FakeThread.started) == 2

    def test_unsupported_country_rejected(self, client):
        assert client.post("/api/scan", data={"country": "XX"}).status_code == 400

    def test_missing_api_key_rejected(self, store, tmp_path):
        defaults = Settings(tmdb_api_key=None, letterboxd_username=None, country="DE", downloads_dir=tmp_path)
        app = Flask(__name__, template_folder="../templates")
        settings = AppSettings(store, defaults)
        routes.register_routes(
            app, store=store, settings=settings, service=ScanService(store, settings, FakeThread)
        )
        assert app.test_client().post("/api/scan", data={"country": "DE"}).status_code == 400

    def test_uploaded_csv_is_parsed(self, client, service):
        data = {"country": "DE", "watchlist": (io.BytesIO(b"Name,Year\nHeat,1995\n"), "list.csv")}
        job_id = client.post("/api/scan", data=data, content_type="multipart/form-data").get_json()["job_id"]
        assert service._live[job_id]["entries"] == [WatchlistEntry("Heat", 1995)]
        assert service._live[job_id]["source_name"] == "list.csv"
        assert "entries" not in client.get(f"/api/scan/{job_id}").get_json()

    def test_csv_without_required_columns_rejected(self, client):
        data = {"country": "DE", "watchlist": (io.BytesIO(b"Title\nHeat\n"), "list.csv")}
        answer = client.post("/api/scan", data=data, content_type="multipart/form-data")
        assert answer.status_code == 400
        assert "Name" in answer.get_json()["error"]

    def test_unknown_scan(self, client):
        assert client.get("/api/scan/nope").status_code == 404
        assert client.post("/api/scan/nope/cancel").status_code == 404


class TestLatestAndFavoritesApi:
    def test_latest_scan_per_country(self, client, store):
        assert client.get("/api/latest?country=DE").get_json() == {"available": False, "stale": True}
        store.save_scan("DE", "src", "k", [{"key": "1", "title": "Heat", "providers": {}}], [], {})
        answer = client.get("/api/latest?country=DE").get_json()
        assert answer["available"] is True
        assert answer["stale"] is False
        assert answer["results"][0]["title"] == "Heat"
        assert answer["changes"] == []
        assert client.get("/api/latest?country=GB").get_json() == {"available": False, "stale": True}

    def test_latest_scan_sends_free_services_of_its_country(self, client, store):
        # The page keeps its labels on a country switch, so each scan brings its own list.
        free = {"BBC iPlayer": ["free"]}
        store.save_scan("GB", "src", "k", [{"key": "1", "title": "Heat", "providers": free}], [], {})
        assert "BBC iPlayer" in client.get("/api/latest?country=GB").get_json()["free_services"]

    def test_latest_scan_reports_old_results_as_stale(self, client, store, settings, monkeypatch):
        store.save_scan("DE", "src", "k", [{"key": "1", "title": "Heat", "providers": {}}], [], {}, created=1)
        settings.update({"scan_interval_hours": 24})
        monkeypatch.setattr(routes.time, "time", lambda: 24 * 60 * 60 + 1)
        assert client.get("/api/latest?country=DE").get_json()["stale"] is True

    def test_old_results_are_stale_with_the_schedule_off(self, client, store, monkeypatch):
        store.save_scan("DE", "src", "k", [{"key": "1", "title": "Heat", "providers": {}}], [], {}, created=1)
        monkeypatch.setattr(routes.time, "time", lambda: 24 * 60 * 60 - 1)
        assert client.get("/api/latest?country=DE").get_json()["stale"] is False
        monkeypatch.setattr(routes.time, "time", lambda: 24 * 60 * 60 + 1)
        assert client.get("/api/latest?country=DE").get_json()["stale"] is True

    def test_favorite_lifecycle(self, client):
        assert client.post("/api/favorites", json={"title": "Heat"}).status_code == 400
        assert client.post("/api/favorites", json={"key": "949", "title": "Heat"}).status_code == 200
        assert client.patch("/api/favorites/949", json={"status": "nope"}).status_code == 400
        assert client.patch("/api/favorites/949", json={"other": 1}).status_code == 400
        assert (
            client.patch("/api/favorites/949", json={"status": "watched", "notes": "ok"}).status_code == 200
        )
        favorite = client.get("/api/favorites").get_json()[0]
        assert (favorite["key"], favorite["status"], favorite["notes"]) == ("949", "watched", "ok")
        client.delete("/api/favorites/949")
        assert client.get("/api/favorites").get_json() == []


class TestSettingsApi:
    def test_read_and_change_settings(self, client):
        assert client.get("/api/settings").get_json()["country"] == "DE"
        answer = client.put(
            "/api/settings",
            json={
                "letterboxd_username": "someone",
                "country": "GB",
                "scan_interval_hours": 24,
                "subscriptions": ["Netflix", "MUBI"],
            },
        )
        assert answer.status_code == 200
        saved = answer.get_json()
        assert (saved["letterboxd_username"], saved["country"], saved["scan_interval_hours"]) == (
            "someone",
            "GB",
            24,
        )
        assert saved["subscriptions"] == ["Netflix", "MUBI"]

    @pytest.mark.parametrize(
        "changes",
        [
            {"country": "XX"},
            {"scan_interval_hours": 5},
            {"subscriptions": ["Nope"]},
            {"letterboxd_username": "bad name!"},
        ],
    )
    def test_invalid_settings_rejected(self, client, changes):
        answer = client.put("/api/settings", json=changes)
        assert answer.status_code == 400
        assert answer.get_json()["error"]

    def test_body_must_be_an_object(self, client):
        assert client.put("/api/settings", json=[1, 2]).status_code == 400


class TestPages:
    def test_main_page_uses_saved_subscriptions(self, client, settings):
        settings.update({"subscriptions": ["MUBI"]})
        page = client.get("/").get_data(as_text=True)
        config = json.loads(page.split("window.WATCHLIST_CONFIG = ")[1].split(";</script>")[0])
        assert config["subscriptions"]["DE"] == ["MUBI"]
        assert "Apple TV Store" in config["rentalShops"]
        assert "Arte" in config["freeServices"]
        # The services menu is drawn in the browser from this config; the sidebar is gone.
        assert 'id="services-menu"' in page and 'id="provider-panel"' not in page

    def test_settings_page(self, client):
        page = client.get("/settings").get_data(as_text=True)
        assert 'id="letterboxd-username"' in page
        assert 'href="/subscriptions"' in page and 'name="subscriptions"' not in page
        assert "Once a day" in page
        # The services are chosen under Settings -> My services, not on the subscriptions page.
        services = client.get("/settings/services").get_data(as_text=True)
        assert 'type="checkbox" value="Netflix"' in services
        assert 'type="checkbox"' not in client.get("/subscriptions").get_data(as_text=True)

    def test_status_page_lists_scans(self, client, store):
        store.create_job("abc", "DE", "schedule", 100.0)
        store.update_job("abc", status="complete", finished_at=112.5, tmdb_requests=42, completed=3, total=3)
        page = client.get("/settings/data").get_data(as_text=True)
        assert "schedule" in page and "12.5 s" in page and ">42<" in page
        overview = client.get("/api/status").get_json()
        assert overview["jobs"][0]["tmdb_requests"] == 42
        assert overview["jobs"][0]["duration_seconds"] == 12.5


class TestCosts:
    def test_save_prices_and_show_costs(self, client, store, settings):
        settings.update({"subscriptions": ["Netflix", "MUBI"]})
        films = [
            {"key": "1", "title": "Heat", "providers": {"Netflix": ["flatrate"], "MUBI": ["flatrate"]}},
            {"key": "2", "title": "Alien", "providers": {"Netflix": ["flatrate"]}},
        ]
        store.save_scan("DE", "letterboxd", None, films, [], {})
        answer = client.put(
            "/api/settings", json={"costs": {"Netflix": {"price": "10", "remind_on": "2026-12-01"}}}
        )
        assert answer.status_code == 200
        page = client.get("/subscriptions").get_data(as_text=True)
        # Heat is also on MUBI, so Netflix has one film only here (Alien): 10.00 per film, total 10.00.
        assert ">10.00<" in page and "Alien" in page and 'value="10.0"' in page
        status = client.get("/settings/data").get_data(as_text=True)
        assert "2026-12-01" in status and "Netflix (DE)" in status

    def test_costs_only_for_own_services(self, client, settings):
        settings.update({"subscriptions": ["Netflix"]})
        answer = client.put("/api/settings", json={"costs": {"MUBI": {"price": 5}}})
        assert answer.status_code == 400

    def test_subscriptions_page_without_scan_or_subscriptions(self, client, settings):
        settings.update({"subscriptions": []})
        page = client.get("/subscriptions").get_data(as_text=True)
        assert "No services chosen" in page and 'href="/settings/services"' in page

    def test_old_costs_address_moves_to_subscriptions(self, client):
        answer = client.get("/costs")
        assert answer.status_code == 301 and answer.headers["Location"].endswith("/subscriptions")

    def test_another_country_is_edited_without_switching_the_app(self, client, settings):
        settings.update({"subscriptions": ["Netflix"]})
        answer = client.put(
            "/api/settings",
            json={
                "subscriptions_country": "GB",
                "subscriptions": ["MUBI"],
                "costs": {"MUBI": {"price": 7}},
            },
        )
        assert answer.status_code == 200
        assert settings.country == "DE"
        assert settings.subscriptions("DE") == ["Netflix"]
        assert settings.subscriptions("GB") == ["MUBI"]
        assert settings.costs("GB")["MUBI"]["price"] == 7.0
        settings.update({"country": "GB"})
        page = client.get("/subscriptions").get_data(as_text=True)
        assert 'data-service="MUBI"' in page and 'data-service="Netflix"' not in page

    def test_film_time_per_week_is_checked_and_saved(self, client, settings):
        assert settings.weekly_hours == 5.0
        assert client.put("/api/settings", json={"weekly_hours": 7.5}).status_code == 200
        assert settings.weekly_hours == 7.5
        for bad in (0, 100, "lots"):
            assert client.put("/api/settings", json={"weekly_hours": bad}).status_code == 400
        assert settings.weekly_hours == 7.5

    def test_unknown_country_is_refused(self, client):
        answer = client.put("/api/settings", json={"subscriptions_country": "XX", "subscriptions": []})
        assert answer.status_code == 400

    def test_free_services_have_no_price_field(self, client, store, settings):
        settings.update({"subscriptions": ["Arte", "Netflix"]})
        films = [{"key": "1", "title": "Heat", "providers": {"Arte": ["free"], "Netflix": ["flatrate"]}}]
        store.save_scan("DE", "letterboxd", None, films, [], {})
        page = client.get("/subscriptions").get_data(as_text=True)
        assert "Price per month for Netflix" in page and "Price per month for Arte" not in page
        assert "Free services" in page and "Arte" in page  # the free service is a chip, not a row

    def test_costs_survive_a_backup(self, client, settings):
        settings.update({"subscriptions": ["Netflix"], "costs": {"Netflix": {"price": 9}}})
        backup = client.get("/api/backup").get_json()
        settings.update({"costs": {}})
        upload = {"backup": (io.BytesIO(json.dumps(backup).encode()), "backup.json")}
        client.post("/api/backup", data=upload, content_type="multipart/form-data")
        assert settings.costs() == {"Netflix": {"price": 9.0, "remind_on": None}}


class TestBackupApi:
    def test_download_and_restore(self, client, store):
        store.add_favorite({"key": "949", "title": "Heat", "status": "watched"})
        answer = client.get("/api/backup")
        assert "attachment" in answer.headers["Content-Disposition"]
        backup = answer.get_json()
        store.remove_favorite("949")
        upload = {"backup": (io.BytesIO(json.dumps(backup).encode()), "backup.json")}
        restored = client.post("/api/backup", data=upload, content_type="multipart/form-data").get_json()
        assert restored["imported"]["favorites"] == 1
        assert store.list_favorites()[0]["status"] == "watched"

    @pytest.mark.parametrize("content", [b"not json", b'{"version": 99}', b"[]"])
    def test_invalid_file_rejected(self, client, content):
        upload = {"backup": (io.BytesIO(content), "backup.json")}
        answer = client.post("/api/backup", data=upload, content_type="multipart/form-data")
        assert answer.status_code == 400
        assert answer.get_json()["error"]

    def test_missing_file(self, client):
        assert client.post("/api/backup").status_code == 400

    def test_settings_are_checked_like_the_settings_page(self, client, settings):
        backup = {
            "version": 1,
            "settings": {
                "country": "GB",
                "scan_interval_hours": "24",
                "letterboxd_username": "<script>",
                "subscriptions:GB": json.dumps(["MUBI", 5, "Brand New Stream"]),
                "subscriptions:XX": "[]",
                "legacy_import_done": "x",
                "anything": "else",
            },
        }
        upload = {"backup": (io.BytesIO(json.dumps(backup).encode()), "backup.json")}
        counts = client.post("/api/backup", data=upload, content_type="multipart/form-data").get_json()[
            "imported"
        ]
        assert (counts["settings"], counts["skipped"]) == (3, 2)
        assert (settings.country, settings.scan_interval_hours, settings.letterboxd_username) == (
            "GB",
            24,
            None,
        )
        assert settings.subscriptions("GB") == ["MUBI"]  # "Brand New Stream" shows up once TMDB lists it


class TestCrossSiteWrites:
    def _backup(self):
        return {"backup": (io.BytesIO(b'{"version": 1}'), "backup.json")}

    def test_other_site_cannot_post(self, client, store):
        for headers in (
            {"Origin": "https://evil.example"},
            {"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"},
            {"Sec-Fetch-Site": "same-site", "Origin": "http://localhost:8080"},
        ):
            answer = client.post("/api/backup", data=self._backup(), headers=headers)
            assert answer.status_code == 403, headers
        assert (
            client.put("/api/settings", json={"country": "GB"}, headers={"Origin": "null"}).status_code == 403
        )
        assert (
            client.delete("/api/favorites/1", headers={"Origin": "https://evil.example"}).status_code == 403
        )

    def test_own_page_and_tools_without_browser_headers_may_post(self, client):
        own = {"Origin": "http://localhost", "Sec-Fetch-Site": "same-origin"}
        assert client.post("/api/backup", data=self._backup(), headers=own).status_code == 200
        assert (
            client.post(
                "/api/backup", data=self._backup(), headers={"Origin": "http://localhost"}
            ).status_code
            == 200
        )
        assert client.post("/api/backup", data=self._backup()).status_code == 200  # curl, CLI, Home Assistant
        # Reading stays possible from anywhere; the browser keeps the answer from other sites.
        assert client.get("/api/settings", headers={"Origin": "https://evil.example"}).status_code == 200

    def test_reverse_proxy_host(self, client, monkeypatch):
        proxied = {"Origin": "https://watch.example.org"}
        assert client.post("/api/backup", data=self._backup(), headers=proxied).status_code == 403
        forwarded = {**proxied, "X-Forwarded-Host": "watch.example.org"}
        assert client.post("/api/backup", data=self._backup(), headers=forwarded).status_code == 200
        monkeypatch.setenv("WATCHLIST_TRUSTED_HOSTS", "other.example, watch.example.org")
        assert client.post("/api/backup", data=self._backup(), headers=proxied).status_code == 200


class TestMatches:
    def _fill(self, store):
        store.save_bundle(949, {"poster_path": "/p.jpg", "details": {"tmdb_title": "Heat"}, "providers": {}})
        store.set_id("title:heat|1995", 949, "search", title="Heat", year=1995)

    def test_page_and_list(self, client, store):
        self._fill(store)
        assert b"Title matches" in client.get("/settings/matches").data
        assert b"stats-page.js" in client.get("/stats").data
        # Old addresses from before the move under Settings redirect for good.
        assert client.get("/matches").headers["Location"].endswith("/settings/matches")
        assert client.get("/status").status_code == 301
        rows = client.get("/api/matches").get_json()
        assert [(row["film_key"], row["reason"], row["tmdb_title"]) for row in rows] == [
            ("title:heat|1995", "search", "Heat")
        ]
        assert client.get("/api/status").get_json()["uncertain_matches"] == 1

    def test_search(self, client, monkeypatch):
        found = [{"tmdb_id": 949, "title": "Heat", "year": 1995}]
        monkeypatch.setattr(routes.tmdb, "search_movies", lambda query, year, api_key: found)
        assert client.get("/api/matches/search?q=Heat&year=1995").get_json() == found
        assert client.get("/api/matches/search?q=").status_code == 400

    def test_correct_with_a_link_and_undo(self, client, store, monkeypatch):
        self._fill(store)
        bundle = {"poster_path": None, "details": {"tmdb_title": "Heat", "release_date": "1995-12-15"}}
        monkeypatch.setattr(routes.matches.tmdb, "get_movie_bundle", lambda tmdb_id, api_key: bundle)
        key = "title%3Aheat%7C1995"
        answer = client.put(
            f"/api/matches/{key}", json={"tmdb_id": "https://www.themoviedb.org/movie/950-heat"}
        )
        assert answer.get_json() == {"ok": True, "tmdb_id": 950, "tmdb_title": "Heat", "tmdb_year": 1995}
        assert store.get_id("title:heat|1995")["source"] == "manual"
        assert client.get("/api/matches").get_json() == []
        assert client.delete(f"/api/matches/{key}").get_json() == {"ok": True}
        assert store.get_id("title:heat|1995") is None
        assert client.delete(f"/api/matches/{key}").status_code == 404

    def test_correction_errors(self, client, store, monkeypatch):
        self._fill(store)
        assert client.put("/api/matches/title:heat|1995", json={"tmdb_id": "heat"}).status_code == 400
        monkeypatch.setattr(routes.matches.tmdb, "get_movie_bundle", lambda tmdb_id, api_key: None)
        answer = client.put("/api/matches/title:heat|1995", json={"tmdb_id": 5})
        assert answer.status_code == 400 and "no film" in answer.get_json()["error"]


def test_loaded_providers_appear_on_the_pages(client, store, settings):
    store.save_provider_catalog("DE", [{"name": "Brand New Stream"}, {"name": "Amazon Prime Video"}])
    assert b"Brand New Stream" in client.get("/settings/services").data
    # A loaded provider can be saved as a subscription; the built-in name is kept for known ones.
    saved = client.put("/api/settings", json={"subscriptions": ["Brand New Stream", "Prime Video"]})
    assert saved.status_code == 200
    assert settings.subscriptions() == ["Brand New Stream", "Prime Video"]
    assert client.get("/api/status").get_json()["provider_catalog"]["count"] == 2


def test_latest_marks_films_only_on_one_own_service(client, store, settings):
    settings.update({"subscriptions": ["Netflix", "MUBI"]})
    films = [
        {"key": "1", "title": "Alien", "providers": {"Netflix": ["flatrate"]}},
        {"key": "2", "title": "Heat", "providers": {"Netflix": ["flatrate"], "MUBI": ["flatrate"]}},
    ]
    store.save_scan("DE", "src", "k", films, [], {})
    results = client.get("/api/latest?country=DE").get_json()["results"]
    marks = [film["only_on_my_services"] for film in results]
    assert marks == [True, False]


def test_provider_logos_reach_the_page_under_their_display_name(client, store):
    store.save_provider_catalog(
        "DE",
        [
            {"name": "Amazon Prime Video", "logo_path": "/prime.png"},
            {"name": "Odd", "logo_path": '"><script>x()</script>'},
            {"name": "No Logo"},
        ],
    )
    page = client.get("/").get_data(as_text=True)
    config = json.loads(page.split("window.WATCHLIST_CONFIG = ", 1)[1].split(";</script>", 1)[0])
    assert config["providerLogos"] == {"Prime Video": "/prime.png"}


def test_other_countries_come_from_stored_offers(client, store):
    store.save_bundle(
        949,
        {
            "poster_path": None,
            "details": {},
            "providers": {"DE": {"Netflix": ["flatrate"]}, "GB": {"Netflix": ["flatrate"], "MUBI": ["rent"]}},
        },
    )
    countries = client.get("/api/films/949/countries").get_json()
    assert countries == {"DE": {"Netflix": ["flatrate"]}, "GB": {"Netflix": ["flatrate"], "MUBI": ["rent"]}}
    assert client.get("/api/films/1/countries").get_json() == {}


class TestHeader:
    PAGES = [
        "/",
        "/watchlist",
        "/subscriptions",
        "/stats",
        "/settings",
        "/settings/data",
        "/settings/matches",
    ]

    def test_every_page_has_the_same_header(self, client):
        headers = set()
        for path in self.PAGES:
            html = client.get(path).get_data(as_text=True)
            start = html.index('<header class="app-header"')
            head = html[start : html.index("</header>", start)]
            assert 'id="country-select"' in head, path
            assert 'class="page-nav"' in head, path
            assert 'id="sync-toggle"' in head, path
            headers.add(head.count("<a ") >= 5)
        assert headers == {True}

    def test_sort_menu_groups_the_sorts_with_a_line_each(self, client):
        html = client.get("/watchlist").get_data(as_text=True)
        assert html.count('class="sort-option"') == 8
        assert "Favorites first, then the Letterboxd rating." in html
        assert 'id="sort-order" value="priority"' in html


class TestFlags:
    def test_watched_and_not_now_are_saved_and_cleared(self, client):
        assert client.put("/api/flags/949", json={"flag": "watched"}).status_code == 200
        answer = client.put("/api/flags/950", json={"flag": "not_now"}).get_json()
        assert answer["flag"] == "not_now" and answer["until"] > time.time() + 29 * 24 * 3600
        flags = {item["key"]: item["flag"] for item in client.get("/api/flags").get_json()}
        assert flags == {"949": "watched", "950": "not_now"}
        client.delete("/api/flags/949")
        assert [item["key"] for item in client.get("/api/flags").get_json()] == ["950"]

    def test_unknown_flag_is_refused(self, client):
        assert client.put("/api/flags/949", json={"flag": "loved"}).status_code == 400

    def test_flags_survive_a_backup_and_an_expired_one_is_dropped(self, client, store):
        store.set_flag("1", "watched")
        store.set_flag("2", "not_now", time.time() + 3600)
        store.set_flag("3", "not_now", time.time() - 10)  # over: no longer listed
        backup = client.get("/api/backup").get_json()
        assert sorted(item["key"] for item in backup["flags"]) == ["1", "2"]
        store.clear_flag("1")
        store.clear_flag("2")
        upload = {"backup": (io.BytesIO(json.dumps(backup).encode()), "backup.json")}
        client.post("/api/backup", data=upload, content_type="multipart/form-data")
        assert sorted(item["key"] for item in store.list_flags()) == ["1", "2"]

    def test_a_backup_cannot_hide_a_film_for_ever(self, client, store):
        hostile = {"version": 1, "flags": [{"key": "9", "flag": "not_now", "until": time.time() + 10**9}]}
        upload = {"backup": (io.BytesIO(json.dumps(hostile).encode()), "backup.json")}
        answer = client.post("/api/backup", data=upload, content_type="multipart/form-data").get_json()
        assert answer["imported"]["skipped"] == 1 and store.list_flags() == []


class TestRecommendationsAndDeadlines:
    def _scan(self, store, settings):
        settings.update({"subscriptions": ["Netflix", "MUBI"]})
        films = [
            {
                "key": "1",
                "title": "Heat",
                "runtime": 120,
                "providers": {"Netflix": ["flatrate"], "MUBI": ["flatrate"]},
            },
            {"key": "2", "title": "Alien", "runtime": 90, "providers": {"Netflix": ["flatrate"]}},
            {"key": "3", "title": "Ran", "runtime": 150, "providers": {"Disney+": ["flatrate"]}},
        ]
        store.save_scan("DE", "letterboxd", None, films, [], {})

    def test_cards_name_the_service_the_numbers_and_the_actions(self, client, store, settings):
        self._scan(store, settings)
        page = client.get("/subscriptions").get_data(as_text=True)
        assert "Cancel MUBI" in page and "You lose no watchlist film" in page
        assert "Subscribe to Disney+ for a month" in page and "Based on the film count only" in page
        assert 'href="/watchlist?providers=Disney%2B&cost=subscription"' in page
        assert "Not interested" in page

    def test_a_date_within_a_week_makes_the_banner_data(self, client, store, settings):
        self._scan(store, settings)
        soon = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
        later = (datetime.date.today() + datetime.timedelta(days=40)).isoformat()
        settings.update(
            {"costs": {"Netflix": {"price": 10, "remind_on": soon}, "MUBI": {"price": 8, "remind_on": later}}}
        )
        page = client.get("/subscriptions").get_data(as_text=True)
        assert (
            "Netflix" in page.split('id="deadline-banner"')[1].split(">")[0]
            and "MUBI" not in page.split('id="deadline-banner"')[1].split(">")[0]
        )
        config = json.loads(
            client.get("/")
            .get_data(as_text=True)
            .split("window.WATCHLIST_CONFIG = ")[1]
            .split(";</script>")[0]
        )
        assert [item["name"] for item in config["deadlines"]] == ["Netflix"]


class TestNotificationsAndSensors:
    def test_settings_page_has_the_notification_form(self, client):
        page = client.get("/settings").get_data(as_text=True)
        assert 'id="notify-kind"' in page and 'name="notify_event" value="weekly"' in page

    def test_test_message_needs_a_target_and_reports_a_refusal(self, client, settings, monkeypatch):
        assert client.post("/api/notify/test").status_code == 400
        settings.update({"notify_kind": "webhook", "notify_url": "https://hook.example/x"})

        def refuse(*args, **kwargs):
            raise routes.requests.ConnectionError("down")

        monkeypatch.setattr(routes.notifications.requests, "post", refuse)
        answer = client.post("/api/notify/test")
        assert answer.status_code == 502 and "did not accept" in answer.get_json()["error"]

    def test_sensors_for_home_assistant(self, client, store, settings):
        settings.update({"subscriptions": ["Netflix"]})
        store.save_scan(
            "DE",
            "letterboxd",
            None,
            [{"key": "1", "title": "Heat", "providers": {"Netflix": ["flatrate"]}}],
            [],
            {},
        )
        data = client.get("/api/sensors").get_json()
        assert data["watchlist_coverage"] == 100 and data["films_available"] == 1
        assert data["new_on_my_services"] == 0 and data["next_subscription_deadline"] is None


class TestCalendar:
    def test_feed_has_one_event_per_date_and_one_for_the_last_day_to_cancel(self, client, settings):
        settings.update({"subscriptions": ["Netflix", "MUBI"]})
        settings.update(
            {
                "costs": {
                    "Netflix": {"price": 10, "remind_on": "2026-12-01", "notice_days": 14},
                    "MUBI": {"price": 8},
                }
            }
        )
        answer = client.get("/calendar.ics")
        assert answer.mimetype == "text/calendar"
        body = answer.get_data(as_text=True)
        assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
        assert body.count("BEGIN:VEVENT") == 2  # MUBI has no date
        assert "DTSTART;VALUE=DATE:20261201" in body and "DTSTART;VALUE=DATE:20261117" in body
        assert "SUMMARY:Netflix: last day to cancel" in body

    def test_long_lines_are_folded_without_cutting_a_character(self):
        from watchlist_app.calendar import _fold

        folded = _fold("SUMMARY:" + "ä" * 60)
        assert all(len(part.encode("utf-8")) <= 76 for part in folded)
        assert (
            "".join(part.lstrip(" ") if index else part for index, part in enumerate(folded))
            == "SUMMARY:" + "ä" * 60
        )


class TestInstallable:
    def test_manifest_icons_exist_and_the_worker_is_served_from_the_root(self, client):
        manifest = client.get("/manifest.webmanifest").get_json()
        assert {"192x192", "512x512"} <= {icon["sizes"] for icon in manifest["icons"]}
        assert any(icon.get("purpose") == "maskable" for icon in manifest["icons"])
        for icon in manifest["icons"]:
            answer = client.get(icon["src"])
            assert answer.status_code == 200 and answer.data[1:4] == b"PNG"
        worker = client.get("/sw.js")
        assert worker.status_code == 200 and "javascript" in worker.mimetype
        assert worker.headers["Cache-Control"] == "no-cache"
        assert b"addEventListener('fetch'" in worker.data

    def test_no_script_removes_the_service_worker_again(self, client):
        # An old clean-up line in app.js once unregistered the worker on every visit.
        for name in ("app.js", "header.js", "register-sw.js"):
            assert "unregister" not in client.get(f"/static/js/{name}").get_data(as_text=True), name

    def test_every_page_links_the_manifest_and_an_icon(self, client):
        for path in ("/", "/watchlist", "/subscriptions", "/stats", "/settings"):
            page = client.get(path).get_data(as_text=True)
            assert 'rel="manifest"' in page and 'rel="icon"' in page, path


class TestTmdbKeyCheck:
    def test_the_button_reports_the_result(self, client, monkeypatch):
        monkeypatch.setattr(routes.tmdb, "check_key", lambda key: None)
        assert client.post("/api/tmdb/test").get_json() == {"ok": True}

        def refused(key):
            raise routes.tmdb.TmdbError("TMDB does not accept this key.")

        monkeypatch.setattr(routes.tmdb, "check_key", refused)
        answer = client.post("/api/tmdb/test")
        assert answer.status_code == 400 and "does not accept" in answer.get_json()["error"]


class TestFirstStart:
    def test_tonight_says_what_to_do_until_there_is_a_user_name_or_a_scan(self, client, store, settings):
        page = client.get("/").get_data(as_text=True)
        assert "Set up in a minute" in page and "Letterboxd user name" in page
        settings.update({"letterboxd_username": "someone"})
        assert "Set up in a minute" not in client.get("/").get_data(as_text=True)


class TestFeedAndTile:
    def _scan(self, store, settings):
        settings.update({"subscriptions": ["Netflix"]})
        store.save_scan(
            "DE",
            "letterboxd",
            None,
            [
                {
                    "key": "1",
                    "title": "Heat & Co",
                    "year": 1995,
                    "rating": 8.0,
                    "providers": {"Netflix": ["flatrate"]},
                },
                {
                    "key": "2",
                    "title": "Alien",
                    "year": 1979,
                    "rating": 8.4,
                    "providers": {"MUBI": ["flatrate"]},
                },
            ],
            [],
            {},
        )
        store.add_changes(
            "DE",
            [{"film_key": "1", "title": "Heat & Co", "year": 1995, "provider": "Netflix", "change": "added"}],
        )

    def test_rss_lists_new_films_on_own_services_and_escapes_text(self, client, store, settings):
        self._scan(store, settings)
        response = client.get("/feed.xml")
        assert response.mimetype == "application/rss+xml"
        assert "Heat &amp; Co (1995) is now on Netflix" in response.get_data(as_text=True)

    def test_tile_shows_the_new_film_and_a_pick_on_own_services(self, client, store, settings):
        self._scan(store, settings)
        html = client.get("/tile").get_data(as_text=True)
        assert "Heat &amp; Co" in html and "Alien" not in html  # Alien is not on an own service

    def test_tile_without_a_scan_is_still_a_page(self, client):
        assert "No film to suggest yet." in client.get("/tile").get_data(as_text=True)
