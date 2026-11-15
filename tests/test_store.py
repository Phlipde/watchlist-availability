import json
import sqlite3
import time

import pytest

from tests.helpers import BUNDLE
from watchlist_app import store as store_module
from watchlist_app.legacy_import import import_legacy_data
from watchlist_app.models import Film
from watchlist_app.store import Store


@pytest.fixture
def store():
    database = Store(":memory:")
    yield database
    database.close()


class TestFilmData:
    def test_ids_and_bundle_persist_between_instances(self, tmp_path):
        path = tmp_path / "data.sqlite3"
        first = Store(path)
        first.set_id("lb:heat", 949, "letterboxd")
        first.save_bundle(949, BUNDLE)
        first.close()
        second = Store(path)
        assert second.get_id("lb:heat")["tmdb_id"] == 949
        film = second.get_film(949, "DE")
        second.close()
        assert film["providers"] == {"Netflix": ["flatrate"]}
        assert film["details"]["runtime"] == 148
        assert film["fetched_at"] is not None

    def test_offers_are_per_country(self, store):
        store.save_bundle(949, BUNDLE)
        assert store.get_film(949, "US")["providers"] == {"Hulu": ["ads"]}
        assert store.get_film(949, "GB")["providers"] == {}

    def test_new_bundle_replaces_old_offers(self, store):
        store.save_bundle(949, BUNDLE)
        store.save_bundle(949, {**BUNDLE, "providers": {"GB": {"MUBI": ["flatrate"]}}})
        assert store.get_film(949, "DE")["providers"] == {}
        assert store.get_film(949, "GB")["providers"] == {"MUBI": ["flatrate"]}

    def test_unknown_entries(self, store):
        assert store.get_id("lb:missing") is None
        assert store.get_film(1, "DE") is None


class TestScans:
    def _save(self, store, country="DE", key="k", created=None, title="Heat"):
        results = [{"title": title, "providers": {"Netflix": ["rent"]}}]
        return store.save_scan(country, "src", key, results, [], {"total": 1}, created=created)

    def test_latest_scan_per_country(self, store):
        self._save(store, "DE", created=100, title="Old")
        self._save(store, "DE", created=200, title="New")
        self._save(store, "GB", created=300, title="British")
        assert store.latest_scan("DE")["results"][0]["title"] == "New"
        assert store.latest_scan()["country"] == "GB"
        assert store.latest_scan("US") is None

    def test_find_recent_scan_of_same_watchlist(self, store):
        self._save(store, key="list-a")
        assert store.find_scan("DE", "list-a", max_age=60)["source_name"] == "src"
        assert store.find_scan("DE", "list-b", max_age=60) is None
        assert store.find_scan("GB", "list-a", max_age=60) is None

    def test_old_scan_is_not_reused(self, store):
        self._save(store, key="list-a", created=time.time() - 3600)
        assert store.find_scan("DE", "list-a", max_age=60) is None

    def test_only_the_newest_scans_are_kept(self, store, monkeypatch):
        monkeypatch.setattr(store_module, "MAX_SCANS", 3)
        for created in range(5):
            self._save(store, created=created, title=str(created))
        rows = store._read("SELECT created FROM scans ORDER BY created")
        assert [row[0] for row in rows] == [2, 3, 4]


class TestFavorites:
    def test_add_update_remove(self, store):
        store.add_favorite({"key": "949", "title": "Heat", "year": 1995})
        store.update_favorite("949", {"status": "watched", "notes": "great", "title": "ignored"})
        favorite = store.list_favorites()[0]
        assert (favorite["key"], favorite["title"], favorite["status"], favorite["notes"]) == (
            "949",
            "Heat",
            "watched",
            "great",
        )
        store.remove_favorite("949")
        assert store.list_favorites() == []

    def test_rekey_moves_title_year_keys_to_tmdb_id(self, store):
        store.add_favorite({"key": "Heat|1995", "title": "Heat", "year": 1995, "notes": "keep me"})
        store.add_favorite({"key": "Ray Gunn|null", "title": "Ray Gunn"})
        moved = store.rekey_favorites(
            [Film(title="Heat", year=1995, tmdb_id=949), Film(title="Ray Gunn", year=None, tmdb_id=5)]
        )
        assert moved == 2
        favorites = {favorite["key"]: favorite for favorite in store.list_favorites()}
        assert set(favorites) == {"949", "5"}
        assert favorites["949"]["notes"] == "keep me"

    def test_rekey_keeps_existing_new_key(self, store):
        store.add_favorite({"key": "Heat|1995", "title": "Heat"})
        store.add_favorite({"key": "949", "title": "Heat"})
        assert store.rekey_favorites([Film(title="Heat", year=1995, tmdb_id=949)]) == 0
        assert {favorite["key"] for favorite in store.list_favorites()} == {"Heat|1995", "949"}


def test_settings(store):
    assert store.get_setting("missing", "default") == "default"
    store.set_setting("country", "DE")
    store.set_setting("country", "GB")
    assert store.get_setting("country") == "GB"


class TestLegacyImport:
    def _legacy_files(self, tmp_path):
        favorites = tmp_path / "favorites.sqlite3"
        connection = sqlite3.connect(favorites)
        connection.execute(
            "CREATE TABLE favorites (movie_key TEXT PRIMARY KEY, title TEXT NOT NULL, year INTEGER, "
            "poster_path TEXT, tmdb_url TEXT, trailer_url TEXT, rating REAL, status TEXT, "
            "notes TEXT, added_at TEXT)"
        )
        connection.execute(
            "INSERT INTO favorites VALUES "
            "('Heat|1995', 'Heat', 1995, NULL, NULL, NULL, 8.3, 'watching', 'n', 'x')"
        )
        connection.commit()
        connection.close()

        latest = tmp_path / "latest.json"
        latest.write_text(
            json.dumps(
                {
                    "created": 123.0,
                    "country": "DE",
                    "source_name": "Letterboxd @someone",
                    "results": [{"title": "Heat", "year": 1995, "providers": {"Netflix": ["rent"]}}],
                    "unavailable": [{"title": "Nope", "year": 2000}],
                    "stats": {"total": 1},
                }
            ),
            encoding="utf-8",
        )

        films = tmp_path / "films.sqlite3"
        connection = sqlite3.connect(films)
        connection.execute(
            "CREATE TABLE films (film_key TEXT PRIMARY KEY, tmdb_id INTEGER, id_source TEXT, "
            "id_checked_at REAL, poster_path TEXT, details TEXT, providers TEXT, fetched_at REAL)"
        )
        connection.execute(
            "INSERT INTO films VALUES ('lb:heat', 949, 'letterboxd', 1.0, '/p.jpg', ?, ?, 2.0)",
            (json.dumps(BUNDLE["details"]), json.dumps(BUNDLE["providers"])),
        )
        connection.execute(
            "INSERT INTO films VALUES ('title:nope|2000', NULL, 'search', 3.0, NULL, NULL, NULL, NULL)"
        )
        connection.commit()
        connection.close()
        return {"favorites_db": favorites, "latest_json": latest, "film_cache_db": films}

    def test_imports_everything_once(self, store, tmp_path):
        paths = self._legacy_files(tmp_path)
        counts = import_legacy_data(store, **paths)
        assert counts == {"favorites": 1, "scans": 1, "films": 2}

        favorite = store.list_favorites()[0]
        assert (favorite["key"], favorite["status"], favorite["rating"]) == ("Heat|1995", "watching", 8.3)
        scan = store.latest_scan("DE")
        assert scan["created"] == 123.0 and scan["unavailable"] == [{"title": "Nope", "year": 2000}]
        assert store.get_id("lb:heat")["tmdb_id"] == 949
        assert store.get_film(949, "DE")["fetched_at"] == 2.0
        assert store.get_id("title:nope|2000")["tmdb_id"] is None

        assert import_legacy_data(store, **paths) is None
        assert len(store.list_favorites()) == 1

    def test_missing_files_are_fine(self, store, tmp_path):
        counts = import_legacy_data(
            store,
            favorites_db=tmp_path / "a.sqlite3",
            latest_json=tmp_path / "b.json",
            film_cache_db=tmp_path / "c.sqlite3",
        )
        assert counts == {"favorites": 0, "scans": 0, "films": 0}
        assert not (tmp_path / "a.sqlite3").exists()


class TestJobs:
    def test_create_update_and_list(self, store):
        store.create_job("a", "DE", "manual", 10.0)
        store.create_job("b", "GB", "schedule", 20.0)
        store.update_job("a", status="complete", failed=[{"title": "Heat"}], reused=True, tmdb_requests=7)
        job = store.get_job("a")
        assert (job["status"], job["failed"], job["reused"], job["tmdb_requests"]) == (
            "complete",
            [{"title": "Heat"}],
            True,
            7,
        )
        assert [job["id"] for job in store.list_jobs()] == ["b", "a"]
        assert [job["id"] for job in store.list_jobs(status="running")] == ["b"]
        assert store.get_job("missing") is None

    def test_unknown_field_rejected(self, store):
        store.create_job("a", "DE", "manual", 10.0)
        with pytest.raises(ValueError):
            store.update_job("a", api_key="x")

    def test_only_the_newest_jobs_are_kept(self, store, monkeypatch):
        monkeypatch.setattr(store_module, "MAX_JOBS", 2)
        for number in range(4):
            store.create_job(str(number), "DE", "manual", float(number))
        assert [job["id"] for job in store.list_jobs()] == ["3", "2"]


class TestBackup:
    def _fill(self, store):
        store.set_setting("country", "GB")
        store.set_setting("legacy_import_done", "{}")
        store.add_favorite({"key": "949", "title": "Heat", "status": "watching", "notes": "n"})
        store.add_changes(
            "DE",
            [{"film_key": "949", "title": "Heat", "year": 1995, "provider": "Arte", "change": "added"}],
            50.0,
        )
        heat = {
            "key": "949",
            "tmdb_id": 949,
            "title": "Heat",
            "year": 1995,
            "providers": {"Netflix": ["flatrate"]},
        }
        store.save_scan("DE", "src", "k", [heat], [], {}, created=10.0)
        store.save_scan("DE", "src", "k", [heat], [], {}, created=20.0)
        store.save_scan("GB", "src", "k", [], [], {}, created=30.0)
        store.save_bundle(949, BUNDLE)
        store.set_id("lb:heat-1995", 949, "manual", title="Heat", year=1995)
        store.set_id("lb:alien", 348, "letterboxd", title="Alien", year=1979)

    def test_export_contents(self, store):
        self._fill(store)
        backup = store.export_backup()
        assert backup["version"] == store_module.BACKUP_VERSION
        assert backup["settings"] == {"country": "GB"}
        assert backup["favorites"][0]["notes"] == "n"
        assert backup["changes"][0]["provider"] == "Arte"
        assert sorted((scan["country"], scan["created"]) for scan in backup["scans"]) == [
            ("DE", 20.0),
            ("GB", 30.0),
        ]
        assert "offers" not in backup and "films" not in backup
        # Only corrections made by hand are kept; the other matches are found again.
        assert backup["matches"] == [
            {"film_key": "lb:heat-1995", "title": "Heat", "year": 1995, "tmdb_id": 949}
        ]

    def test_restore_into_empty_database_and_again(self, store):
        self._fill(store)
        backup = json.loads(json.dumps(store.export_backup()))
        fresh = Store(":memory:")
        assert fresh.import_backup(backup) == {
            "favorites": 1,
            "changes": 1,
            "scans": 2,
            "matches": 1,
            "skipped": 0,
        }
        # Settings are restored by AppSettings.restore, with the checks of the settings page.
        assert fresh.get_setting("country") is None
        assert fresh.list_favorites()[0]["status"] == "watching"
        assert fresh.recent_changes("DE", 0)[0]["created"] == 50.0
        restored = fresh.latest_scan("DE")
        assert restored["created"] == 20.0
        assert restored["results"][0] == {
            **Film(title="Heat", year=1995, tmdb_id=949).to_dict(),
            "providers": {"Netflix": ["flatrate"]},
        }
        assert fresh.get_id("lb:heat-1995")["source"] == "manual"
        # Restoring the same file twice adds nothing.
        assert fresh.import_backup(backup) == {
            "favorites": 1,
            "changes": 0,
            "scans": 0,
            "matches": 0,
            "skipped": 0,
        }
        fresh.close()

    def test_hostile_backup_is_cleaned(self, store):
        attack = '<img src=x onerror="alert(1)">'
        backup = {
            "version": 1,
            "favorites": [
                {"key": "1", "title": "Ok", "year": attack, "rating": attack, "status": attack},
                {"key": "2"},
            ],
            "changes": [
                {
                    "created": 5.0,
                    "country": "DE",
                    "film_key": "1",
                    "title": "Ok",
                    "provider": "X",
                    "change": attack,
                },
                {
                    "created": 5.0,
                    "country": "DE",
                    "film_key": "1",
                    "title": "Ok",
                    "provider": "X",
                    "change": "added",
                },
            ],
            "scans": [
                {
                    "created": 99999999999,  # far in the future, would always be the newest scan
                    "country": "DE",
                    "results": [],
                    "unavailable": [{"title": "Evil", "key": "x", "year": attack}],
                },
                {
                    "created": 40.0,
                    "country": "DE",
                    "source_name": attack,
                    "stats": {"total": attack, "providers": "all"},
                    "results": [
                        {
                            "title": "Evil",
                            "tmdb_id": 7,
                            "year": attack,
                            "runtime": attack,
                            "rating": 99,
                            "poster_path": 'x" onerror="alert(1)',
                            "tmdb_url": "javascript:alert(1)",
                            "trailer_url": "https://evil.example/watch?v=x",
                            "genres": [attack, 3],
                            "providers": {
                                "Netflix": ["flatrate", attack],
                                "Bad": [attack],
                                "Odd": "flatrate",
                            },
                        },
                        {"year": 2000},
                    ],
                    "unavailable": [{"title": "Fine", "year": "1999", "runtime": 90.0}],
                },
                {"created": 41.0, "country": "XX", "results": []},
            ],
            "matches": [{"film_key": "lb:x", "tmdb_id": "7"}, {"film_key": "lb:y", "tmdb_id": attack}],
        }
        counts = store.import_backup(backup)
        assert counts == {"favorites": 1, "changes": 1, "scans": 1, "matches": 1, "skipped": 6}
        favorite = store.list_favorites()[0]
        assert (favorite["year"], favorite["rating"], favorite["status"]) == (None, None, "plan")
        scan = store.latest_scan("DE")
        assert scan["created"] == 40.0
        film = scan["results"][0]
        assert (film["year"], film["runtime"], film["rating"], film["poster_path"]) == (
            None,
            None,
            None,
            None,
        )
        assert (film["tmdb_url"], film["trailer_url"]) == (None, None)
        assert film["providers"] == {"Netflix": ["flatrate"]}
        assert film["genres"] == [attack]  # text the page escapes
        assert scan["unavailable"][0]["year"] == 1999 and scan["unavailable"][0]["runtime"] == 90
        assert scan["stats"]["total"] == 0 and scan["stats"]["providers"] == "all"
        assert store.get_id("lb:x")["tmdb_id"] == 7 and store.get_id("lb:y") is None

    def test_backup_without_matches_still_restores(self, store):
        self._fill(store)
        backup = store.export_backup()
        del backup["matches"]
        assert Store(":memory:").import_backup(backup)["matches"] == 0

    @pytest.mark.parametrize("backup", [[], {"version": 99}, {"version": 1, "favorites": "x"}])
    def test_invalid_backup(self, store, backup):
        with pytest.raises(ValueError):
            store.import_backup(backup)

    def test_old_database_gets_the_new_columns(self, tmp_path):
        path = tmp_path / "old.sqlite3"
        old = sqlite3.connect(path)
        old.execute(
            "CREATE TABLE film_ids (film_key TEXT PRIMARY KEY, tmdb_id INTEGER, source TEXT, checked_at REAL)"
        )
        old.execute("INSERT INTO film_ids VALUES ('lb:heat', 949, 'letterboxd', 5.0)")
        old.commit()
        old.close()
        store = Store(path)
        store.touch_ids([("lb:heat", "Heat", 1995)], seen_at=100.0)
        match = store.list_matches()[0]
        assert (match["title"], match["year"], match["last_seen"], match["tmdb_id"]) == (
            "Heat",
            1995,
            100.0,
            949,
        )
        store.close()

    def test_counts(self, store):
        self._fill(store)
        counts = store.counts()
        assert (counts["favorites"], counts["scans"], counts["offers"]) == (1, 3, 2)
