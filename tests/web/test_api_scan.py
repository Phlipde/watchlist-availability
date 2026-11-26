"""Route tests: starting scans and the latest-scan, favorites and abroad APIs."""

import io

from flask import Flask

from tests.web.conftest import FakeThread
from watchlist_app.config import Settings
from watchlist_app.models import WatchlistEntry
from watchlist_app.scan_service import ScanService
from watchlist_app.settings import AppSettings
from web import routes


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
        assert client.post("/api/scan", data={"country": "PLX"}).status_code == 400

    def test_any_country_with_a_flag_can_be_scanned(self, client, service):
        job_id = client.post("/api/scan", data={"country": "PL"}).get_json()["job_id"]
        assert service._live[job_id]["country"] == "PL"

    def test_missing_api_key_rejected(self, store, tmp_path):
        defaults = Settings(tmdb_api_key=None, letterboxd_username=None, country="DE", downloads_dir=tmp_path)
        app = Flask(__name__, template_folder="../../templates")
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
    def test_latest_scan_per_country(self, client, store, settings):
        first = client.get("/api/latest?country=DE").get_json()
        assert (first["available"], first["stale"]) == (False, True)
        assert first["subscriptions"] == settings.subscriptions("DE")
        store.save_scan("DE", "src", "k", [{"key": "1", "title": "Heat", "providers": {}}], [], {})
        answer = client.get("/api/latest?country=DE").get_json()
        assert answer["available"] is True
        assert answer["stale"] is False
        assert answer["results"][0]["title"] == "Heat"
        assert answer["changes"] == []
        assert client.get("/api/latest?country=GB").get_json()["available"] is False
        # Any country with a flag; a made-up code is refused.
        assert client.get("/api/latest?country=PL").get_json() == {
            "available": False,
            "stale": True,
            "subscriptions": [],
        }
        assert client.get("/api/latest?country=<b>").status_code == 400

    def test_big_answers_are_gzipped_when_the_browser_accepts_it(self, client, store):
        import gzip
        import json

        films = [{"key": str(n), "title": f"Film {n}", "providers": {}} for n in range(200)]
        store.save_scan("DE", "src", "k", films, [], {})
        plain = client.get("/api/latest?country=DE")
        assert "Content-Encoding" not in plain.headers
        packed = client.get("/api/latest?country=DE", headers={"Accept-Encoding": "gzip, br"})
        assert packed.headers["Content-Encoding"] == "gzip"
        assert "Accept-Encoding" in packed.headers["Vary"]
        assert len(packed.data) < len(plain.data) / 3
        assert json.loads(gzip.decompress(packed.data)) == plain.get_json()

    def test_latest_scan_sends_free_services_of_its_country(self, client, store):
        # The page keeps its labels on a country switch, so each scan brings its own list.
        offers = {"BBC iPlayer": ["free"], "Sky Store": ["rent", "buy"]}
        store.save_scan("GB", "src", "k", [{"key": "1", "title": "Heat", "providers": offers}], [], {})
        latest = client.get("/api/latest?country=GB").get_json()
        assert (latest["free_services"], latest["rental_shops"]) == (["BBC iPlayer"], ["Sky Store"])

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


class TestAbroad:
    def test_films_your_services_have_abroad(self, client, store, settings):
        settings.update({"subscriptions": ["Netflix"]})
        store.save_scan(
            "DE",
            "letterboxd",
            None,
            [{"key": "7", "tmdb_id": 7, "title": "Heat", "providers": {}}],
            [],
            {},
        )
        store.save_bundle(7, {"details": {}, "providers": {"AT": {"Netflix": ["flatrate"]}}})
        data = client.get("/api/abroad?country=DE&services=Netflix").get_json()
        assert data == {"7": {"Netflix": {"AT": "flatrate"}}}
        assert client.get("/api/abroad?country=DE&services=MUBI").get_json() == {}
        assert client.get("/api/abroad?country=ZZ&services=Netflix").status_code == 400
