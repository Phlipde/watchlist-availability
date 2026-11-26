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
    store.add_favorite({"key": "949", "title": "Heat"}, profile_id=1)
    store.set_flag("348", "watched", profile_id=1)
    settings.update({"subscriptions": ["MUBI"], "costs": {"MUBI": {"price": 9, "remind_on": "2099-01-01"}}})
    store.save_scan("DE", "letterboxd", None, [HEAT], [], {}, profile_id=1)
    store.add_changes("DE", [ADDED], profile_id=1)


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
        store.create_job("j1", "DE", "manual", 1.0, profile_id=1)
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
        assert store.list_favorites(profile_id=1) == [] and store.list_flags(profile_id=1) == []
        assert "MUBI" not in settings.subscriptions()
        client.delete("/api/favorites/949")
        client.delete("/api/flags/348")
        assert store.list_favorites(profile_id=anna) == [] and store.list_flags(profile_id=anna) == []

    def test_greyout_reset_only_touches_profile_2(self, client, store, anna):
        store.set_flag("1", "watched", profile_id=1)
        store.set_flag("2", "watched", profile_id=anna)
        client.set_cookie("wl_profile", str(anna))
        client.post("/api/greyouts/reset")
        assert store.list_flags(profile_id=anna) == [] and len(store.list_flags(profile_id=1)) == 1

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
        assert store.list_favorites(profile_id=1) == [] and store.list_flags(profile_id=1) == []
        assert "MUBI" not in settings.subscriptions()


def _netflix(key: str) -> dict:
    return {"key": key, "tmdb_id": int(key), "title": f"Film {key}", "providers": {"Netflix": ["flatrate"]}}


@pytest.fixture
def anna_data(store, settings, anna):
    """Anna has Netflix at 13 a month and two films on it; profile 1 keeps MUBI at 9 and one film."""
    settings.for_profile(anna).update({"subscriptions": ["Netflix"], "costs": {"Netflix": {"price": 13}}})
    store.save_scan("DE", "letterboxd", None, [_netflix("1"), _netflix("2")], [], {}, profile_id=anna)
    store.record_service_counts("DE", "2026-11-20", {"Netflix": (2, 2)}, profile_id=anna)
    store.record_service_counts("DE", "2026-11-20", {"MUBI": (1, 1)}, profile_id=1)
    store.add_favorite({"key": "1", "title": "Film 1"}, profile_id=anna)
    store.add_favorite({"key": "2", "title": "Film 2"}, profile_id=anna)
    return anna


@pytest.mark.usefixtures("profile_1_data")
class TestStatsAndDataPerProfile:
    def test_subscriptions_page_shows_the_profiles_services_and_numbers(self, client, anna_data):
        mine = client.get("/subscriptions").get_data(as_text=True)
        theirs = client.get(f"/subscriptions?profile={anna_data}").get_data(as_text=True)
        assert 'data-service="MUBI"' in mine and 'data-films="1"' in mine and "9.00" in mine
        assert 'data-service="Netflix"' not in mine and "13.00" not in mine
        assert 'data-service="Netflix"' in theirs and 'data-films="2"' in theirs and "13.00" in theirs
        assert 'data-service="MUBI"' not in theirs
        assert "&#34;films&#34;: 2" in theirs and "&#34;films&#34;: 2" not in mine  # detail and history

    def test_stats_page_gets_the_profiles_services_and_prices(self, client, anna_data):
        def config(path: str) -> dict:
            html = client.get(path).get_data(as_text=True)
            return json.loads(html.split("window.STATS_PAGE = ", 1)[1].split(";</script>", 1)[0])

        mine, theirs = config("/stats"), config(f"/stats?profile={anna_data}")
        assert (mine["subscriptions"], mine["prices"]) == (["MUBI"], {"MUBI": 9})
        assert (theirs["subscriptions"], theirs["prices"]) == (["Netflix"], {"Netflix": 13})

    def test_data_page_counts_the_active_profile_and_labels_the_shared_part(self, client, store, anna_data):
        store.create_job("j1", "DE", "manual", 1.0, profile_id=1)
        mine = client.get("/api/status").get_json()
        theirs = client.get(f"/api/status?profile={anna_data}").get_json()
        assert (mine["profile_counts"]["favorites"], mine["profile_counts"]["changes"]) == (1, 1)
        assert (theirs["profile_counts"]["favorites"], theirs["profile_counts"]["changes"]) == (2, 0)
        assert (mine["base"]["watchlist"], theirs["base"]["watchlist"]) == (1, 2)
        assert mine["counts"] == theirs["counts"]  # films, offers: shared by all profiles
        assert theirs["jobs"] == [] and len(mine["jobs"]) == 1
        html = client.get(f"/settings/data?profile={anna_data}").get_data(as_text=True)
        assert "This profile (Anna)" in html and "Shared by all profiles" in html
        assert "Favorites: <strong>2</strong>" in html and "Recent scans of Anna" in html

    def test_settings_page_says_where_a_backup_goes(self, client, anna):
        html = client.get(f"/settings?profile={anna}").get_data(as_text=True)
        assert "An old backup (one person) is restored into the active profile, Anna." in html
        assert "restores every profile in it by name" in html
