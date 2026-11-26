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
        store.add_favorite(_movie("lb:heat"))
        store.add_favorite(_movie("lb:alien"), profile_id=2)
        assert [f["key"] for f in store.list_favorites()] == ["lb:heat"]
        assert [f["key"] for f in store.list_favorites(profile_id=2)] == ["lb:alien"]

    def test_same_film_in_two_profiles_is_updated_and_removed_apart(self, store):
        store.add_favorite(_movie("lb:heat"))
        store.add_favorite(_movie("lb:heat"), profile_id=2)
        store.update_favorite("lb:heat", {"status": "watched"}, profile_id=2)
        assert store.list_favorites()[0]["status"] == "plan"
        store.remove_favorite("lb:heat", profile_id=2)
        assert store.list_favorites(profile_id=2) == []
        assert [f["key"] for f in store.list_favorites()] == ["lb:heat"]

    def test_flags_are_per_profile(self, store):
        store.set_flag("lb:heat", "watched")
        store.set_flag("lb:alien", "not_now", until=4e9, profile_id=2)
        assert [f["key"] for f in store.list_flags()] == ["lb:heat"]
        assert [f["key"] for f in store.list_flags(profile_id=2)] == ["lb:alien"]
        store.set_flag("lb:heat", "watched", profile_id=2)
        store.clear_flag("lb:heat", profile_id=2)
        assert [f["key"] for f in store.list_flags()] == ["lb:heat"]

    def test_greyed_out_counts_and_reset_per_profile(self, store):
        store.set_flag("lb:heat", "watched")
        store.add_favorite({**_movie("lb:alien"), "status": "watched"})
        store.set_flag("lb:heat", "watched", profile_id=2)
        assert store.greyed_out_counts() == {"flags": 1, "favorites": 1}
        assert store.greyed_out_counts(profile_id=2) == {"flags": 1, "favorites": 0}
        assert store.reset_greyed_out(profile_id=2) == {"flags": 1, "favorites": 0}
        assert store.greyed_out_counts() == {"flags": 1, "favorites": 1}


def _scan(store, created: float, profile_id: int = 1, source: str = "me") -> int:
    return store.save_scan("DE", source, "key", [], [], {}, created=created, profile_id=profile_id)


class TestScans:
    def test_scans_of_another_profile_do_not_push_out_max_scans(self, store, monkeypatch):
        monkeypatch.setattr(store_module, "MAX_SCANS", 2)
        _scan(store, 1)
        _scan(store, 2)
        for created in (3, 4, 5):
            _scan(store, created, profile_id=2)
        assert len(store.recent_scans("DE", "me", limit=10)) == 2
        assert [s["created"] for s in store.recent_scans("DE", "me", limit=10, profile_id=2)] == [5, 4]

    def test_latest_scan_and_lookups_are_per_profile(self, store):
        first = _scan(store, 1)
        second = _scan(store, 2, profile_id=2)
        assert store.latest_scan()["id"] == first
        assert store.latest_scan("DE", "me", profile_id=2)["id"] == second
        assert store.latest_scan(profile_id=3) is None
        assert store.latest_scan_created("DE") == 1
        assert store.latest_scan_created("DE", profile_id=2) == 2
        assert store.find_scan("DE", "key", 1e12)["id"] == first
        assert store.find_scan("DE", "key", 1e12, profile_id=3) is None

    def test_changes_are_per_profile(self, store):
        change = {"film_key": "lb:heat", "title": "Heat", "year": 1995, "provider": "Netflix"}
        change["change"] = "added"
        store.add_changes("DE", [change], created=10)
        store.add_changes("DE", [{**change, "change": "removed"}], created=10, profile_id=2)
        assert [c["change"] for c in store.recent_changes("DE", 0)] == ["added"]
        assert [c["change"] for c in store.recent_changes("DE", 0, profile_id=2)] == ["removed"]

    def test_service_history_is_per_profile(self, store):
        store.record_service_counts("DE", "2026-01-01", {"Netflix": (3, 1)})
        store.record_service_counts("DE", "2027-06-01", {"Disney+": (2, 0)}, profile_id=2)
        # profile 2's newer day must not prune profile 1's old row
        assert store.service_history("DE") == {"Netflix": [{"day": "2026-01-01", "films": 3, "only_here": 1}]}
        assert list(store.service_history("DE", profile_id=2)) == ["Disney+"]

    def test_jobs_are_per_profile(self, store, monkeypatch):
        monkeypatch.setattr(store_module, "MAX_JOBS", 1)
        store.create_job("a", "DE", "manual", 1)
        store.create_job("b", "DE", "manual", 2, profile_id=2)
        store.create_job("c", "DE", "manual", 3, profile_id=2)
        assert [j["id"] for j in store.list_jobs()] == ["a"]
        assert [j["id"] for j in store.list_jobs(status="running", profile_id=2)] == ["c"]
        assert store.get_job("c") is not None
