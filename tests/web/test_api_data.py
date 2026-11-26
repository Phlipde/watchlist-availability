"""Route tests: settings, costs, backups, title matches, flags and grey-outs."""

import datetime
import io
import json
import time

import pytest

from web import routes


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
                "notify_state": "x",  # an internal value is never restored
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


class TestMatches:
    def _fill(self, store):
        store.save_bundle(949, {"poster_path": "/p.jpg", "details": {"tmdb_title": "Heat"}, "providers": {}})
        store.set_id("title:heat|1995", 949, "search", title="Heat", year=1995)

    def test_page_and_list(self, client, store):
        self._fill(store)
        assert b"Title matches" in client.get("/settings/matches").data
        assert b"stats-page.js" in client.get("/stats").data
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
        assert sorted(item["key"] for item in backup["profiles"][0]["flags"]) == ["1", "2"]
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


class TestTmdbKeyCheck:
    def test_the_button_reports_the_result(self, client, monkeypatch):
        monkeypatch.setattr(routes.tmdb, "check_key", lambda key: None)
        assert client.post("/api/tmdb/test").get_json() == {"ok": True}

        def refused(key):
            raise routes.tmdb.TmdbError("TMDB does not accept this key.")

        monkeypatch.setattr(routes.tmdb, "check_key", refused)
        answer = client.post("/api/tmdb/test")
        assert answer.status_code == 400 and "does not accept" in answer.get_json()["error"]


class TestGreyOuts:
    def test_reset_removes_every_grey_out_and_keeps_the_favorites(self, client, store):
        client.put("/api/flags/949", json={"flag": "watched"})
        client.put("/api/flags/950", json={"flag": "not_now"})
        client.post("/api/favorites", json={"title": "Heat", "key": "949", "status": "watched"})
        assert client.get("/api/greyouts").get_json() == {"flags": 1, "favorites": 1}
        done = client.post("/api/greyouts/reset").get_json()
        assert (done["flags"], done["favorites"]) == (1, 1)
        assert client.get("/api/greyouts").get_json() == {"flags": 0, "favorites": 0}
        assert [flag["key"] for flag in client.get("/api/flags").get_json()] == [
            "950"
        ]  # "not now" is not a grey-out
        assert client.get("/api/favorites").get_json()[0]["status"] == "plan"


def test_a_service_cancelled_to_a_past_date_is_no_longer_yours(settings):
    future = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
    past = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    settings.update(
        {
            "subscriptions": ["Netflix", "MUBI", "Disney+"],
            "costs": {"Netflix": {"ends_on": future}, "MUBI": {"ends_on": past}},
        }
    )
    assert settings.subscriptions() == ["Netflix", "Disney+"]  # Netflix runs to the end date, MUBI is over
