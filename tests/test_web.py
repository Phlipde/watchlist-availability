"""Tests for the Flask routes."""

import io
import json

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
        assert client.get("/api/latest?country=DE").get_json() == {"available": False}
        store.save_scan("DE", "src", "k", [{"key": "1", "title": "Heat", "providers": {}}], [], {})
        answer = client.get("/api/latest?country=DE").get_json()
        assert answer["available"] is True
        assert answer["results"][0]["title"] == "Heat"
        assert answer["changes"] == []
        assert client.get("/api/latest?country=GB").get_json() == {"available": False}

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
        assert 'value="MUBI" checked' in page
        assert 'id="rental-providers"' in page

    def test_settings_page(self, client):
        page = client.get("/settings").get_data(as_text=True)
        assert 'id="letterboxd-username"' in page
        assert 'name="subscriptions" value="Netflix"' in page
        assert "Once a day" in page

    def test_status_page_lists_scans(self, client, store):
        store.create_job("abc", "DE", "schedule", 100.0)
        store.update_job("abc", status="complete", finished_at=112.5, tmdb_requests=42, completed=3, total=3)
        page = client.get("/status").get_data(as_text=True)
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
        page = client.get("/costs").get_data(as_text=True)
        assert ">5.00<" in page and "10.00" in page and "Alien" in page
        status = client.get("/status").get_data(as_text=True)
        assert "2026-12-01" in status and "Netflix (DE)" in status

    def test_costs_only_for_own_services(self, client, settings):
        settings.update({"subscriptions": ["Netflix"]})
        answer = client.put("/api/settings", json={"costs": {"MUBI": {"price": 5}}})
        assert answer.status_code == 400

    def test_costs_page_without_scan_or_subscriptions(self, client, settings):
        settings.update({"subscriptions": []})
        assert "No subscriptions saved" in client.get("/costs").get_data(as_text=True)

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
        assert b"Title matches" in client.get("/matches").data
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
    assert b"Brand New Stream" in client.get("/").data
    assert b"Brand New Stream" in client.get("/settings").data
    # A loaded provider can be saved as a subscription; the built-in name is kept for known ones.
    saved = client.put("/api/settings", json={"subscriptions": ["Brand New Stream", "Prime Video"]})
    assert saved.status_code == 200
    assert settings.subscriptions() == ["Brand New Stream", "Prime Video"]
    assert client.get("/api/status").get_json()["provider_catalog"]["count"] == 2
