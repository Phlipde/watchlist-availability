"""Store methods keep each profile's favorites, flags, scans, changes, history and jobs apart."""

import pytest

from watchlist_app import store as store_module
from watchlist_app.store import Store


@pytest.fixture
def store():
    database = Store(":memory:")
    yield database
    database.close()


def _movie(key: str) -> dict:
    return {"key": key, "title": key.title()}


class TestMarks:
    def test_favorites_are_per_profile(self, store):
        store.add_favorite(_movie("lb:heat"), profile_id=1)
        store.add_favorite(_movie("lb:alien"), profile_id=2)
        assert [f["key"] for f in store.list_favorites(profile_id=1)] == ["lb:heat"]
        assert [f["key"] for f in store.list_favorites(profile_id=2)] == ["lb:alien"]

    def test_same_film_in_two_profiles_is_updated_and_removed_apart(self, store):
        store.add_favorite(_movie("lb:heat"), profile_id=1)
        store.add_favorite(_movie("lb:heat"), profile_id=2)
        store.update_favorite("lb:heat", {"status": "watched"}, profile_id=2)
        assert store.list_favorites(profile_id=1)[0]["status"] == "plan"
        store.remove_favorite("lb:heat", profile_id=2)
        assert store.list_favorites(profile_id=2) == []
        assert [f["key"] for f in store.list_favorites(profile_id=1)] == ["lb:heat"]

    def test_flags_are_per_profile(self, store):
        store.set_flag("lb:heat", "watched", profile_id=1)
        store.set_flag("lb:alien", "not_now", until=4e9, profile_id=2)
        assert [f["key"] for f in store.list_flags(profile_id=1)] == ["lb:heat"]
        assert [f["key"] for f in store.list_flags(profile_id=2)] == ["lb:alien"]
        store.set_flag("lb:heat", "watched", profile_id=2)
        store.clear_flag("lb:heat", profile_id=2)
        assert [f["key"] for f in store.list_flags(profile_id=1)] == ["lb:heat"]

    def test_greyed_out_counts_and_reset_per_profile(self, store):
        store.set_flag("lb:heat", "watched", profile_id=1)
        store.add_favorite({**_movie("lb:alien"), "status": "watched"}, profile_id=1)
        store.set_flag("lb:heat", "watched", profile_id=2)
        assert store.greyed_out_counts(profile_id=1) == {"flags": 1, "favorites": 1}
        assert store.greyed_out_counts(profile_id=2) == {"flags": 1, "favorites": 0}
        assert store.reset_greyed_out(profile_id=2) == {"flags": 1, "favorites": 0}
        assert store.greyed_out_counts(profile_id=1) == {"flags": 1, "favorites": 1}


def _scan(store, created: float, profile_id: int = 1, source: str = "me") -> int:
    return store.save_scan("DE", source, "key", [], [], {}, created=created, profile_id=profile_id)


class TestScans:
    def test_scans_of_another_profile_do_not_push_out_max_scans(self, store, monkeypatch):
        monkeypatch.setattr(store_module, "MAX_SCANS", 2)
        _scan(store, 1)
        _scan(store, 2)
        for created in (3, 4, 5):
            _scan(store, created, profile_id=2)
        assert len(store.recent_scans("DE", "me", limit=10, profile_id=1)) == 2
        assert [s["created"] for s in store.recent_scans("DE", "me", limit=10, profile_id=2)] == [5, 4]

    def test_latest_scan_and_lookups_are_per_profile(self, store):
        first = _scan(store, 1)
        second = _scan(store, 2, profile_id=2)
        assert store.latest_scan(profile_id=1)["id"] == first
        assert store.latest_scan("DE", "me", profile_id=2)["id"] == second
        assert store.latest_scan(profile_id=3) is None
        assert store.latest_scan_created("DE", profile_id=1) == 1
        assert store.latest_scan_created("DE", profile_id=2) == 2
        assert store.find_scan("DE", "key", 1e12, profile_id=1)["id"] == first
        assert store.find_scan("DE", "key", 1e12, profile_id=3) is None

    def test_changes_are_per_profile(self, store):
        change = {"film_key": "lb:heat", "title": "Heat", "year": 1995, "provider": "Netflix"}
        change["change"] = "added"
        store.add_changes("DE", [change], created=10, profile_id=1)
        store.add_changes("DE", [{**change, "change": "removed"}], created=10, profile_id=2)
        assert [c["change"] for c in store.recent_changes("DE", 0, profile_id=1)] == ["added"]
        assert [c["change"] for c in store.recent_changes("DE", 0, profile_id=2)] == ["removed"]

    def test_service_history_is_per_profile(self, store):
        store.record_service_counts("DE", "2026-01-01", {"Netflix": (3, 1)}, profile_id=1)
        store.record_service_counts("DE", "2027-06-01", {"Disney+": (2, 0)}, profile_id=2)
        # profile 2's newer day must not prune profile 1's old row
        assert store.service_history("DE", profile_id=1) == {
            "Netflix": [{"day": "2026-01-01", "films": 3, "only_here": 1}]
        }
        assert list(store.service_history("DE", profile_id=2)) == ["Disney+"]

    def test_jobs_are_per_profile(self, store, monkeypatch):
        monkeypatch.setattr(store_module, "MAX_JOBS", 1)
        store.create_job("a", "DE", "manual", 1, profile_id=1)
        store.create_job("b", "DE", "manual", 2, profile_id=2)
        store.create_job("c", "DE", "manual", 3, profile_id=2)
        assert [j["id"] for j in store.list_jobs(profile_id=1)] == ["a"]
        assert [j["id"] for j in store.list_jobs(status="running", profile_id=2)] == ["c"]
        assert store.get_job("c") is not None


def _fill(store, profile_id: int) -> None:
    """One row of every kind for the profile."""
    store.add_favorite(_movie("lb:heat"), profile_id=profile_id)
    store.set_flag("lb:heat", "watched", profile_id=profile_id)
    _scan(store, 1, profile_id=profile_id)
    change = {"film_key": "lb:heat", "title": "Heat", "year": 1995, "provider": "Netflix", "change": "added"}
    store.add_changes("DE", [change], created=1, profile_id=profile_id)
    store.record_service_counts("DE", "2026-01-01", {"Netflix": (3, 1)}, profile_id=profile_id)
    store.create_job(f"job{profile_id}", "DE", "manual", 1, profile_id=profile_id)
    store.set_profile_setting("country", "GB", profile_id=profile_id)
    store.replace_watched(["lb:heat"], profile_id=profile_id)


def _owned_tables(store) -> list[str]:
    tables = [row[0] for row in store._read("SELECT name FROM sqlite_master WHERE type = 'table'")]
    return [t for t in tables if any(c[1] == "profile_id" for c in store._read(f"PRAGMA table_info({t})"))]


class TestProfiles:
    def test_add_list_and_rename(self, store):
        anna = store.add_profile("  Anna ", "Anna@Example.org")
        assert store.list_profiles() == [
            {"id": 1, "name": "Me", "email": None},
            {"id": anna, "name": "Anna", "email": "Anna@Example.org"},
        ]
        assert store.rename_profile(anna, "Anna", "anna@new.org")  # same name, new e-mail
        assert store.rename_profile(anna, "Annabel", None)
        assert store.list_profiles()[1] == {"id": anna, "name": "Annabel", "email": None}
        assert store.find_profile("Annabel") == anna
        assert not store.rename_profile(99, "Nobody")

    def test_duplicate_and_invalid_names_are_refused(self, store):
        anna = store.add_profile("Anna")
        with pytest.raises(ValueError, match="already exists"):
            store.add_profile("Anna")
        with pytest.raises(ValueError, match="already exists"):
            store.rename_profile(anna, "Me")
        for name in ("", "   ", "x" * 61, "a\nb", None):
            with pytest.raises(ValueError):
                store.add_profile(name)
        with pytest.raises(ValueError, match="e-mail"):
            store.add_profile("Ben", "not an address")
        assert [p["name"] for p in store.list_profiles()] == ["Me", "Anna"]

    def test_delete_leaves_no_rows_of_the_profile(self, store):
        anna = store.add_profile("Anna")
        _fill(store, 1)
        _fill(store, anna)
        tables = _owned_tables(store)
        assert len(tables) == 8
        assert store.delete_profile(anna)
        for table in tables:
            count = f"SELECT count(*) FROM {table} WHERE profile_id = ?"
            assert store._read(count, (anna,))[0][0] == 0, table
            assert store._read(count, (1,))[0][0] == 1, table
        assert [p["id"] for p in store.list_profiles()] == [1]
        assert not store.delete_profile(anna)

    def test_last_profile_cannot_be_deleted(self, store):
        anna = store.add_profile("Anna")
        assert store.delete_profile(1)
        with pytest.raises(ValueError, match="last profile"):
            store.delete_profile(anna)
        assert [p["id"] for p in store.list_profiles()] == [anna]

    def test_ids_of_deleted_profiles_are_not_reused(self, store):
        anna = store.add_profile("Anna")
        assert store.delete_profile(anna)
        ben = store.add_profile("Ben")
        assert ben == anna + 1
        assert "profile_last_id" not in store.export_backup()["settings"]


class TestWatched:
    def test_replace_keeps_profiles_apart_and_resolves_matched_ids(self, store):
        anna = store.add_profile("Anna")
        store.replace_watched(["lb:heat", "lb:alien", "lb:heat"], now=10.0, profile_id=1)
        store.replace_watched(["lb:up"], now=20.0, profile_id=anna)
        store.set_id("lb:heat", 949, "letterboxd")
        store.set_id("lb:alien", None, "search")  # not found on TMDB
        assert store.watched_keys(profile_id=1) == {"lb:heat", "lb:alien"}
        assert store.watched_tmdb_ids(profile_id=1) == {949}
        assert (store.watched_fetched_at(profile_id=1), store.watched_fetched_at(profile_id=anna)) == (
            10.0,
            20.0,
        )
        store.replace_watched([], now=30.0, profile_id=1)
        assert store.watched_keys(profile_id=1) == set() and store.watched_fetched_at(profile_id=1) == 30.0
        assert store.watched_keys(profile_id=anna) == {"lb:up"}
        assert store.watched_fetched_at(profile_id=99) is None
