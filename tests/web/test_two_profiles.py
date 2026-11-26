"""Route tests with two profiles: each route reads and writes the active profile's data only."""

import io
import json

import pytest

from tests.web.conftest import FakeThread

HEAT = {"key": "949", "tmdb_id": 949, "title": "Heat", "year": 1995, "providers": {"MUBI": ["flatrate"]}}
ADDED = {"film_key": "949", "title": "Heat", "year": 1995, "provider": "MUBI", "change": "added"}


@pytest.fixture
def anna(store):
    return store.add_profile("Anna")


@pytest.fixture
def profile_1_data(store, settings):
    """Profile 1 has a favorite, a flag, a service, a scan and a change; profile 2 has nothing."""
    store.add_favorite({"key": "949", "title": "Heat"})
    store.set_flag("348", "watched")
    settings.update({"subscriptions": ["MUBI"], "costs": {"MUBI": {"price": 9, "remind_on": "2099-01-01"}}})
    store.save_scan("DE", "letterboxd", None, [HEAT], [], {})
    store.add_changes("DE", [ADDED])


@pytest.mark.usefixtures("profile_1_data")
class TestProfile2SeesNothingOfProfile1:
    def test_marks(self, client, anna):
        assert client.get(f"/api/favorites?profile={anna}").get_json() == []
        assert client.get(f"/api/flags?profile={anna}").get_json() == []
        assert client.get(f"/api/greyouts?profile={anna}").get_json()["flags"] == 0
        assert len(client.get("/api/favorites").get_json()) == 1  # profile 1 still has its own

    def test_settings(self, client, anna):
        assert "MUBI" not in client.get(f"/api/settings?profile={anna}").get_json()["subscriptions"]
        assert client.get("/api/settings").get_json()["subscriptions"] == ["MUBI"]

    def test_latest_scan_and_changes(self, client, store, anna):
        assert client.get(f"/api/latest?profile={anna}").get_json()["available"] is False
        store.save_scan("DE", "letterboxd", None, [HEAT], [], {}, profile_id=anna)
        answer = client.get(f"/api/latest?profile={anna}").get_json()
        assert answer["available"] is True and answer["changes"] == []
        assert "MUBI" not in answer["subscriptions"]
        assert len(client.get("/api/latest").get_json()["changes"]) == 1

    def test_status_and_header(self, client, store, anna):
        store.create_job("j1", "DE", "manual", 1.0)
        status = client.get(f"/api/status?profile={anna}").get_json()
        assert status["jobs"] == [] and status["last_scan_at"] is None
        assert len(client.get("/api/status").get_json()["jobs"]) == 1
        assert "Out of date" in client.get(f"/settings?profile={anna}").get_data(as_text=True)
        assert "Synced" in client.get("/settings").get_data(as_text=True)

    def test_pages(self, client, anna):
        pages = ("/", "/watchlist", "/stats", "/settings/services", "/settings/data", "/settings/matches")
        for path in pages:
            assert client.get(f"{path}?profile={anna}").status_code == 200, path
        assert "Heat" not in client.get(f"/subscriptions?profile={anna}").get_data(as_text=True)
        assert "Heat" in client.get("/subscriptions").get_data(as_text=True)

    def test_feeds(self, client, anna):
        assert client.get(f"/api/sensors?profile={anna}").get_json()["films_available"] == 0
        assert client.get("/api/sensors").get_json()["films_available"] == 1
        assert "Heat" not in client.get(f"/feed.xml?profile={anna}").get_data(as_text=True)
        assert "Heat" in client.get("/feed.xml").get_data(as_text=True)
        assert "MUBI" not in client.get(f"/calendar.ics?profile={anna}").get_data(as_text=True)
        assert "MUBI" in client.get("/calendar.ics").get_data(as_text=True)
        assert "Heat" not in client.get(f"/tile?profile={anna}").get_data(as_text=True)


class TestWritesOfProfile2:
    def test_favorite_flag_and_settings_land_in_profile_2(self, client, store, settings, anna):
        client.set_cookie("wl_profile", str(anna))
        client.post("/api/favorites", json={"key": "949", "title": "Heat"})
        client.patch("/api/favorites/949", json={"status": "watching"})
        client.put("/api/flags/348", json={"flag": "watched"})
        assert client.put("/api/settings", json={"subscriptions": ["MUBI"]}).get_json()["subscriptions"] == [
            "MUBI"
        ]
        favorites = store.list_favorites(profile_id=anna)
        assert [(f["key"], f["status"]) for f in favorites] == [("949", "watching")]
        assert [f["key"] for f in store.list_flags(profile_id=anna)] == ["348"]
        assert settings.for_profile(anna).subscriptions() == ["MUBI"]
        assert store.list_favorites() == [] and store.list_flags() == []
        assert "MUBI" not in settings.subscriptions()
        client.delete("/api/favorites/949")
        client.delete("/api/flags/348")
        assert store.list_favorites(profile_id=anna) == [] and store.list_flags(profile_id=anna) == []

    def test_greyout_reset_only_touches_profile_2(self, client, store, anna):
        store.set_flag("1", "watched")
        store.set_flag("2", "watched", profile_id=anna)
        client.set_cookie("wl_profile", str(anna))
        client.post("/api/greyouts/reset")
        assert store.list_flags(profile_id=anna) == [] and len(store.list_flags()) == 1

    def test_scan_of_profile_2_runs_beside_profile_1_and_stays_its_own(self, client, store, service, anna):
        first = client.post("/api/scan", json={"country": "DE"}).get_json()["job_id"]
        client.set_cookie("wl_profile", str(anna))
        answer = client.post("/api/scan", json={"country": "DE"}).get_json()
        assert "reconnected" not in answer and answer["job_id"] != first
        assert service._live[answer["job_id"]]["profile_id"] == anna
        assert service._live[first]["cancel_requested"] is False
        assert store.list_jobs(profile_id=anna)[0]["id"] == answer["job_id"]
        # Profile 2 can neither see nor stop the scan of profile 1.
        assert client.get(f"/api/scan/{first}").status_code == 404
        assert client.post(f"/api/scan/{first}/cancel").status_code == 404
        assert client.get(f"/api/scan/{answer['job_id']}").get_json()["profile_id"] == anna
        assert client.post(f"/api/scan/{answer['job_id']}/cancel").status_code == 200
        assert service._live[first]["cancel_requested"] is False

    def test_a_new_letterboxd_name_starts_the_first_scan(self, client, store, service, anna):
        client.set_cookie("wl_profile", str(anna))
        client.put("/api/settings", json={"weekly_hours": 6})
        assert FakeThread.started == []  # no name, no scan
        client.put("/api/settings", json={"letterboxd_username": "anna"})
        [job_id] = FakeThread.started
        assert service._live[job_id]["profile_id"] == anna
        assert service._live[job_id]["trigger"] == "schedule"
        service._live[job_id]["status"] = "complete"
        store.save_scan("DE", "letterboxd", None, [HEAT], [], {}, profile_id=anna)
        client.put("/api/settings", json={"letterboxd_username": "anna2"})
        assert len(FakeThread.started) == 1  # it has a scan now

    def test_a_new_name_waits_while_another_scan_runs(self, client, service, anna):
        client.post("/api/scan", json={"country": "DE"})
        client.set_cookie("wl_profile", str(anna))
        client.put("/api/settings", json={"letterboxd_username": "anna"})
        assert len(FakeThread.started) == 1 and not service.is_running(anna)

    def test_backup_import_goes_into_the_active_profile(self, client, store, settings, anna):
        backup = {
            "version": 1,
            "settings": {"subscriptions:DE": json.dumps(["MUBI"])},
            "favorites": [{"key": "949", "title": "Heat"}],
            "flags": [{"key": "348", "flag": "watched", "until": None}],
            "changes": [],
            "scans": [],
        }
        client.set_cookie("wl_profile", str(anna))
        upload = {"backup": (io.BytesIO(json.dumps(backup).encode()), "backup.json")}
        assert client.post("/api/backup", data=upload, content_type="multipart/form-data").status_code == 200
        assert [f["key"] for f in store.list_favorites(profile_id=anna)] == ["949"]
        assert [f["key"] for f in store.list_flags(profile_id=anna)] == ["348"]
        assert settings.for_profile(anna).subscriptions() == ["MUBI"]
        assert store.list_favorites() == [] and store.list_flags() == []
        assert "MUBI" not in settings.subscriptions()
