"""Backup version 2 with several profiles; version 1 files (one person) still restore."""

import copy
import json
import time

import pytest

from watchlist_app.config import Settings
from watchlist_app.settings import AppSettings
from watchlist_app.store import Store

HEAT = {"key": "949", "tmdb_id": 949, "title": "Heat", "year": 1995, "providers": {"Netflix": ["flatrate"]}}
V1_BACKUP = {
    "version": 1,
    "exported_at": 100.0,
    "settings": {
        "country": "DE",
        "letterboxd_username": "anna",
        "scan_interval_hours": "24",
        "subscriptions:DE": json.dumps(["Netflix"]),
    },
    "favorites": [{"key": "949", "title": "Heat", "status": "watching", "notes": "n"}],
    "flags": [{"key": "348", "flag": "watched", "until": None}],
    "changes": [
        {
            "created": 50.0,
            "country": "DE",
            "film_key": "949",
            "title": "Heat",
            "year": 1995,
            "provider": "Arte",
            "change": "added",
        }
    ],
    "scans": [{"created": 20.0, "country": "DE", "source_name": "src", "results": [HEAT], "unavailable": []}],
    "matches": [{"film_key": "lb:heat-1995", "title": "Heat", "year": 1995, "tmdb_id": 949}],
}


@pytest.fixture
def store():
    store = Store(":memory:")
    yield store
    store.close()


def _settings(store, tmp_path, profile_id=1):
    return AppSettings(store, Settings("key", None, "GB", tmp_path), profile_id)


def _restore(store, tmp_path, backup, target_profile=1):
    counts = store.import_backup(backup, target_profile=target_profile)
    counts["settings"] = _settings(store, tmp_path).restore_backup(backup, target_profile)[0]
    return counts


def _rows(store):
    tables = ("profiles", "profile_settings", "settings", "favorites", "flags", "changes", "scans")
    return {table: store._read(f"SELECT count(*) FROM {table}")[0][0] for table in tables}


def _personal(store, profile_id):
    return dict(store._read("SELECT key, value FROM profile_settings WHERE profile_id = ?", (profile_id,)))


def _add_profile(store, name, email=None):
    store._write("INSERT INTO profiles (name, email, created) VALUES (?, ?, 0)", (name, email))
    return store.find_profile(name)


def test_a_version_1_backup_restores_into_profile_1(store, tmp_path):
    counts = _restore(store, tmp_path, copy.deepcopy(V1_BACKUP))
    assert counts == {"favorites": 1, "changes": 1, "scans": 1, "matches": 1, "skipped": 0, "settings": 4}
    assert store.list_favorites()[0]["notes"] == "n"
    assert store.list_flags() == [{"key": "348", "flag": "watched", "until": None}]
    assert store.recent_changes("DE", 0)[0]["provider"] == "Arte"
    assert store.latest_scan("DE")["results"][0]["providers"] == {"Netflix": ["flatrate"]}
    assert store.get_id("lb:heat-1995")["source"] == "manual"
    assert _personal(store, 1) == {
        "country": "DE",
        "letterboxd_username": "anna",
        "subscriptions:DE": '["Netflix"]',
    }
    assert store.get_setting("scan_interval_hours") == "24"
    assert store._read("SELECT id, name FROM profiles") == [(1, "Me")]  # no profile is created for v1


def test_a_version_1_backup_with_target_profile_2_lands_in_profile_2_only(store, tmp_path):
    _restore(store, tmp_path, copy.deepcopy(V1_BACKUP))
    before = _rows(store)
    second = _add_profile(store, "ben")
    counts = _restore(store, tmp_path, copy.deepcopy(V1_BACKUP), target_profile=second)
    # Already in profile 1 is no reason to skip: profile 2 gets its own copy (matches are shared).
    assert counts == {"favorites": 1, "changes": 1, "scans": 1, "matches": 0, "skipped": 0, "settings": 4}
    assert store.list_favorites(profile_id=second)[0]["key"] == "949"
    assert store.list_flags(profile_id=second)[0]["key"] == "348"
    assert len(store.recent_changes("DE", 0, profile_id=second)) == 1
    assert store.latest_scan("DE", profile_id=second)["created"] == 20.0
    assert _personal(store, second)["letterboxd_username"] == "anna"
    after = _rows(store)
    assert after["favorites"] == before["favorites"] + 1 and after["scans"] == before["scans"] + 1
    assert len(store.recent_changes("DE", 0)) == 1 and len(store.list_favorites()) == 1


def _two_profiles(store, tmp_path):
    _restore(store, tmp_path, copy.deepcopy(V1_BACKUP))
    second = _add_profile(store, "ben", "ben@example.org")
    store.add_favorite({"key": "1", "title": "Up"}, profile_id=second)
    store.set_flag("2", "not_now", time.time() + 3600, profile_id=second)
    store.add_changes(
        "GB",
        [{"film_key": "1", "title": "Up", "year": 2009, "provider": "MUBI", "change": "removed"}],
        60.0,
        profile_id=second,
    )
    store.save_scan("GB", "src", "k", [], [], {}, created=30.0, profile_id=second)
    store.save_scan("GB", "src", "k", [], [], {}, created=40.0, profile_id=second)
    store.save_scan("DE", "src", "k", [HEAT], [], {}, created=20.0, profile_id=second)
    _settings(store, tmp_path, second).update({"country": "GB", "notify_token": "secret"})
    store.set_profile_setting("notify_state", "{}", profile_id=second)
    return second


def _summary(backup):
    """What a backup holds per profile; scans are rebuilt on import (new ids, filled-in film fields)."""
    return [
        (
            profile["name"],
            profile["email"],
            profile["settings"],
            [(f["key"], f["status"], f["notes"]) for f in profile["favorites"]],
            profile["flags"],
            profile["changes"],
            sorted((scan["country"], scan["created"], len(scan["results"])) for scan in profile["scans"]),
        )
        for profile in backup["profiles"]
    ] + [backup["settings"], backup["matches"]]


def test_two_profiles_survive_a_round_trip(store, tmp_path):
    _two_profiles(store, tmp_path)
    backup = json.loads(json.dumps(store.export_backup()))
    assert backup["version"] == 2 and backup["settings"] == {"scan_interval_hours": "24"}
    assert [(p["name"], p["email"]) for p in backup["profiles"]] == [("Me", None), ("ben", "ben@example.org")]
    assert sorted((s["country"], s["created"]) for s in backup["profiles"][1]["scans"]) == [
        ("DE", 20.0),
        ("GB", 40.0),
    ]
    fresh = Store(":memory:")
    counts = _restore(fresh, tmp_path, backup)
    assert counts == {"favorites": 2, "changes": 2, "scans": 3, "matches": 1, "skipped": 0, "settings": 5}
    assert fresh._read("SELECT id, name, email FROM profiles ORDER BY id") == [
        (1, "Me", None),
        (2, "ben", "ben@example.org"),
    ]
    assert _personal(fresh, 1) == _personal(store, 1)
    assert _personal(fresh, 2) == {"country": "GB"}  # the token and the notification state stay out
    assert _summary(json.loads(json.dumps(fresh.export_backup()))) == _summary(backup)
    fresh.close()


def test_importing_twice_adds_nothing(store, tmp_path):
    _two_profiles(store, tmp_path)
    backup = json.loads(json.dumps(store.export_backup()))
    fresh = Store(":memory:")
    _restore(fresh, tmp_path, backup)
    rows = _rows(fresh)
    counts = _restore(fresh, tmp_path, backup)
    assert (counts["changes"], counts["scans"], counts["matches"], counts["skipped"]) == (0, 0, 0, 0)
    assert _rows(fresh) == rows
    fresh.close()


def test_secrets_never_appear_in_an_export(store, tmp_path):
    _two_profiles(store, tmp_path)
    _settings(store, tmp_path).update({"notify_token": "hidden"})
    text = json.dumps(store.export_backup())
    assert "notify_token" not in text and "notify_state" not in text
    assert "secret" not in text and "hidden" not in text


@pytest.mark.parametrize("name", ["", "   ", "x" * 61, 5, None, "a\nb"])
def test_a_profile_with_an_invalid_name_is_skipped_and_counted(store, tmp_path, name):
    good = {"name": " carla ", "email": "carla@example.org", "favorites": [{"key": "1", "title": "Up"}]}
    bad = {"name": name, "favorites": [{"key": "2", "title": "Jaws"}]}
    broken = {"name": "dora", "favorites": "not a list"}
    backup = {"version": 2, "settings": {}, "matches": [], "profiles": [bad, good, broken, "x"]}
    counts = store.import_backup(backup)
    assert (counts["favorites"], counts["skipped"]) == (1, 3)
    carla = store.find_profile("carla")
    assert [f["key"] for f in store.list_favorites(profile_id=carla)] == ["1"]
    # A fresh install: carla takes over the empty "Me" as profile 1; dora is not created.
    assert store._read("SELECT id, name FROM profiles") == [(1, "carla")]


def test_a_new_profile_is_created_with_its_email_and_settings(store, tmp_path):
    backup = {
        "version": 2,
        # A per-person key at the top is ignored; a global key inside a profile too.
        "settings": {"scan_interval_hours": "48", "country": "FR"},
        "matches": [],
        "profiles": [
            {
                "name": "eva",
                "email": "eva@example.org",
                "settings": {"country": "IT", "scan_interval_hours": "168", "notify_token": "x"},
            },
            {"name": "finn", "email": "not an address"},
        ],
    }
    counts = _restore(store, tmp_path, backup)
    assert counts["settings"] == 2
    # A fresh install: the first person takes over the empty profile 1, the next one is new.
    assert store._read("SELECT id, name, email FROM profiles ORDER BY id") == [
        (1, "eva", "eva@example.org"),
        (2, "finn", None),
    ]
    assert _personal(store, 1) == {"country": "IT"}
    assert store.get_setting("scan_interval_hours") == "48"


@pytest.mark.parametrize("backup", [{"version": 2, "profiles": "x"}, {"version": 2, "matches": {"a": 1}}])
def test_a_damaged_version_2_backup_is_refused(store, backup):
    with pytest.raises(ValueError):
        store.import_backup(backup)
