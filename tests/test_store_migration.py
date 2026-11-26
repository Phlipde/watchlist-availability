"""Migration of the database layout from version 1 (no profiles) to 2 (data owned by profile 1) and 3
(the settings of one person in profile_settings)."""

import json
import sqlite3

from watchlist_app import store_base
from watchlist_app.config import Settings
from watchlist_app.settings import AppSettings
from watchlist_app.store import INTERNAL_SETTINGS, SCHEMA_VERSION, Store

# Settings of one person: version 3 moves them to profile_settings of profile 1.
PERSONAL_SETTINGS = [
    ("country", "DE"),
    ("weekly_hours", "7.5"),
    ("notify_kind", "ntfy"),
    ("notify_url", "https://ntfy.example/t"),
    ("notify_token", "secret"),
    ("notify_events", '{"weekly": false}'),
    ("notify_state", '{"checked": 5}'),
    ("subscriptions:DE", '["Netflix"]'),
    ("subscriptions:FR", "[]"),
    ("subscription_costs:DE", '{"Netflix": {"price": 9.99, "remind_on": ""}}'),
]
# Settings of the whole app; they stay in settings.
GLOBAL_SETTINGS = [
    ("scan_interval_hours", "24"),
    ("tmdb_regions", '{"codes": ["DE"], "fetched_at": 1}'),
    ("matches_changed_at", "12.5"),
    ("subscriptionXcosts:DE", "{}"),  # not the prefix: `_` is no wildcard
    ("old_unknown_key", "x"),
]

# The layout of version 1, as it was in store_schema._SCHEMA; old databases look like this.
V1_SCHEMA = """
CREATE TABLE IF NOT EXISTS film_ids (
    film_key TEXT PRIMARY KEY,
    tmdb_id INTEGER,
    source TEXT,
    checked_at REAL,
    title TEXT,
    year INTEGER,
    last_seen REAL,
    lb_rating REAL,
    lb_checked_at REAL
);
CREATE TABLE IF NOT EXISTS films (
    tmdb_id INTEGER PRIMARY KEY,
    poster_path TEXT,
    details TEXT NOT NULL DEFAULT '{}',
    fetched_at REAL
);
CREATE TABLE IF NOT EXISTS offers (
    tmdb_id INTEGER NOT NULL,
    country TEXT NOT NULL,
    providers TEXT NOT NULL,
    PRIMARY KEY (tmdb_id, country)
);
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created REAL NOT NULL,
    country TEXT NOT NULL,
    source_name TEXT NOT NULL DEFAULT '',
    watchlist_key TEXT,
    results TEXT NOT NULL,
    unavailable TEXT NOT NULL,
    stats TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created REAL NOT NULL,
    country TEXT NOT NULL,
    film_key TEXT NOT NULL,
    title TEXT NOT NULL,
    year INTEGER,
    provider TEXT NOT NULL,
    change TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS changes_by_country ON changes (country, created);
CREATE TABLE IF NOT EXISTS favorites (
    movie_key TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    year INTEGER,
    poster_path TEXT,
    tmdb_url TEXT,
    trailer_url TEXT,
    rating REAL,
    status TEXT NOT NULL DEFAULT 'plan',
    notes TEXT NOT NULL DEFAULT '',
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS service_history (
    country TEXT NOT NULL,
    day TEXT NOT NULL,
    service TEXT NOT NULL,
    films INTEGER NOT NULL,
    only_here INTEGER NOT NULL,
    PRIMARY KEY (country, day, service)
);
CREATE TABLE IF NOT EXISTS flags (
    movie_key TEXT PRIMARY KEY,
    flag TEXT NOT NULL,
    until REAL
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    trigger TEXT NOT NULL DEFAULT 'manual',
    country TEXT NOT NULL,
    source_name TEXT,
    phase TEXT,
    message TEXT,
    completed INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    available INTEGER NOT NULL DEFAULT 0,
    unavailable INTEGER NOT NULL DEFAULT 0,
    failed TEXT NOT NULL DEFAULT '[]',
    tmdb_requests INTEGER NOT NULL DEFAULT 0,
    reused INTEGER NOT NULL DEFAULT 0,
    started_at REAL NOT NULL,
    heartbeat_at REAL,
    finished_at REAL,
    scan_id INTEGER
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS provider_catalog (
    country TEXT NOT NULL,
    tmdb_name TEXT NOT NULL,
    logo_path TEXT,
    priority INTEGER,
    fetched_at REAL NOT NULL,
    PRIMARY KEY (country, tmdb_name)
);
"""


def _v1_database(path, username="anna", version=1):
    connection = sqlite3.connect(path)
    connection.executescript(V1_SCHEMA)
    rows = {
        "favorites": [
            ("lb:heat", "Heat", 1995, None, None, None, 4.5, "plan", "note", "2026-01-01 10:00:00")
        ],
        "flags": [("lb:alien", "watched", None), ("lb:jaws", "not_now", 9e9)],
        "service_history": [("DE", "2026-11-20", "Netflix", 60, 12)],
        "scans": [(1, 100.0, "DE", "csv", "key", "[]", "[]", "{}")],
        "changes": [(1, 100.0, "DE", "lb:heat", "Heat", 1995, "Netflix", "added")],
        "jobs": [
            ("job1", "done", "manual", "DE", None, None, None, 0, 0, 0, 0, "[]", 0, 0, 1.0, None, 2.0, 1)
        ],
        "settings": PERSONAL_SETTINGS
        + GLOBAL_SETTINGS
        + ([("letterboxd_username", username)] if username is not None else []),
    }
    for table, values in rows.items():
        for row in values:
            connection.execute(f"INSERT INTO {table} VALUES ({', '.join('?' * len(row))})", row)
    connection.execute(f"PRAGMA user_version = {version}")
    connection.commit()
    connection.close()
    return rows


def _dump(path):
    connection = sqlite3.connect(path)
    tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    dump = {table: sorted(connection.execute(f"SELECT * FROM {table}").fetchall()) for table in tables}
    connection.close()
    return dump


def _layout(path):
    connection = sqlite3.connect(path)
    names = connection.execute(
        "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    columns = {
        name: connection.execute(f"PRAGMA table_info({name})").fetchall()
        for kind, name in names
        if kind == "table"
    }
    indexes = {
        name: connection.execute(f"PRAGMA index_info({name})").fetchall()
        for kind, name in names
        if kind == "index"
    }
    connection.close()
    return names, columns, indexes


class TestMigrationToProfiles:
    def test_every_row_is_kept_and_owned_by_profile_1(self, tmp_path):
        path = tmp_path / "old.sqlite3"
        rows = _v1_database(path)
        Store(path).close()
        connection = sqlite3.connect(path)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 4
        for table in ("favorites", "flags", "service_history"):
            stored = connection.execute(f"SELECT * FROM {table}").fetchall()
            assert sorted(stored) == sorted((1, *row) for row in rows[table])  # profile_id comes first
        for table in ("scans", "changes", "jobs"):
            stored = connection.execute(f"SELECT * FROM {table}").fetchall()
            assert sorted(stored) == sorted((*row, 1) for row in rows[table])  # profile_id comes last
        assert connection.execute("SELECT id, name, email FROM profiles").fetchall() == [(1, "anna", None)]
        connection.close()
        copy = sqlite3.connect(tmp_path / "old.sqlite3.pre-v4")
        assert copy.execute("PRAGMA user_version").fetchone()[0] == 1
        assert copy.execute("SELECT movie_key FROM favorites").fetchall() == [("lb:heat",)]
        copy.close()

    def test_opening_again_changes_nothing(self, tmp_path):
        path = tmp_path / "old.sqlite3"
        _v1_database(path)
        Store(path).close()
        before = _dump(path)
        Store(path).close()
        assert _dump(path) == before

    def test_without_a_username_the_profile_is_me(self, tmp_path):
        path = tmp_path / "old.sqlite3"
        _v1_database(path, username=None)
        assert Store(path)._read("SELECT id, name FROM profiles") == [(1, "Me")]
        blank = tmp_path / "blank.sqlite3"
        _v1_database(blank, username="")
        assert Store(blank)._read("SELECT id, name FROM profiles") == [(1, "Me")]

    def test_a_new_database_has_profile_1_and_the_same_layout(self, tmp_path):
        new = tmp_path / "new.sqlite3"
        old = tmp_path / "old.sqlite3"
        Store(new).close()
        _v1_database(old)
        Store(old).close()
        assert _dump(new)["profiles"][0][:3] == (1, "Me", None)
        assert _layout(new) == _layout(old)

    def test_favorites_and_flags_still_work(self, tmp_path):
        path = tmp_path / "old.sqlite3"
        _v1_database(path)
        store = Store(path)
        store.add_favorite(
            {"key": "lb:heat", "title": "Heat", "year": 1995, "status": "seen"}, profile_id=1
        )  # replaces
        store.add_favorite({"key": "lb:up", "title": "Up"}, profile_id=1)
        store.update_favorite("lb:up", {"notes": "later"}, profile_id=1)
        assert [(f["key"], f["status"], f["notes"]) for f in store.list_favorites(profile_id=1)] == [
            ("lb:heat", "seen", ""),
            ("lb:up", "plan", "later"),
        ]
        store.remove_favorite("lb:heat", profile_id=1)
        assert [f["key"] for f in store.list_favorites(profile_id=1)] == ["lb:up"]
        store.set_flag("lb:alien", "not_now", 9e9, profile_id=1)  # replaces the "watched" flag
        store.clear_flag("lb:jaws", profile_id=1)
        assert store.list_flags(now=0, profile_id=1) == [{"key": "lb:alien", "flag": "not_now", "until": 9e9}]
        store.record_service_counts(
            "DE", "2026-11-20", {"Netflix": (61, 13)}, profile_id=1
        )  # the same day: replaced
        assert store.service_history("DE", profile_id=1)["Netflix"] == [
            {"day": "2026-11-20", "films": 61, "only_here": 13}
        ]
        assert store._read("SELECT DISTINCT profile_id FROM favorites") == [(1,)]
        assert store._read("SELECT DISTINCT profile_id FROM flags") == [(1,)]
        assert "profile_id" not in json.dumps(store.export_backup())  # the backup format is unchanged


def _settings_rows(path):
    connection = sqlite3.connect(path)
    personal = sorted(connection.execute("SELECT profile_id, key, value FROM profile_settings").fetchall())
    shared = sorted(connection.execute("SELECT key, value FROM settings").fetchall())
    connection.close()
    return personal, shared


class TestMigrationOfProfileSettings:
    def test_from_version_1_the_personal_settings_move_to_profile_1(self, tmp_path):
        path = tmp_path / "old.sqlite3"
        _v1_database(path)
        Store(path).close()
        personal, shared = _settings_rows(path)
        moved = PERSONAL_SETTINGS + [("letterboxd_username", "anna")]
        assert personal == sorted((1, key, value) for key, value in moved)
        assert shared == sorted(GLOBAL_SETTINGS)

    def test_from_version_2_the_personal_settings_move_to_profile_1(self, tmp_path, monkeypatch):
        path = tmp_path / "old.sqlite3"
        _v1_database(path)
        with monkeypatch.context() as patch:
            patch.setattr(store_base, "SCHEMA_VERSION", 2)
            Store(path).close()
        connection = sqlite3.connect(path)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert connection.execute("SELECT name FROM profiles").fetchall() == [("anna",)]
        v2_settings = sorted(connection.execute("SELECT key, value FROM settings").fetchall())
        connection.close()
        Store(path).close()
        personal, shared = _settings_rows(path)
        assert [
            (1, key, value) for key, value in v2_settings if (key, value) not in GLOBAL_SETTINGS
        ] == personal
        assert shared == sorted(GLOBAL_SETTINGS)
        copy = sqlite3.connect(tmp_path / "old.sqlite3.pre-v4")
        assert copy.execute("PRAGMA user_version").fetchone()[0] == 2
        copy.close()

    def test_the_backup_holds_the_same_settings_as_before(self, tmp_path):
        path = tmp_path / "old.sqlite3"
        rows = _v1_database(path)
        store = Store(path)
        expected = {key: value for key, value in rows["settings"] if key not in INTERNAL_SETTINGS}
        backup = store.export_backup()
        assert {**backup["settings"], **backup["profiles"][0]["settings"]} == expected
        assert "notify_token" not in expected and "notify_state" not in expected

    def test_a_used_profile_1_is_not_taken_over_by_a_backup(self, tmp_path):
        path = tmp_path / "old.sqlite3"
        _v1_database(path)
        backup = json.loads(json.dumps(Store(path).export_backup()))
        fresh = Store(tmp_path / "fresh.sqlite3")
        fresh.add_favorite({"key": "x|2000", "title": "X", "year": 2000}, profile_id=1)
        fresh.import_backup(backup)
        assert fresh.find_profile("Me") == 1 and fresh.find_profile("anna") == 2

    def test_a_migrated_database_backup_restores_by_profile_name(self, tmp_path):
        path = tmp_path / "old.sqlite3"
        _v1_database(path)
        backup = json.loads(json.dumps(Store(path).export_backup()))
        fresh = Store(tmp_path / "fresh.sqlite3")
        fresh.import_backup(backup)
        AppSettings(fresh, Settings("key", None, "GB", tmp_path)).restore_backup(backup)
        # A fresh install has only an empty "Me": the backup's person takes over profile 1.
        assert fresh.find_profile("anna") == 1 and fresh.find_profile("Me") is None
        assert len(fresh.list_favorites(profile_id=1)) == len(Store(path).list_favorites(profile_id=1))
        personal = dict(fresh._read("SELECT key, value FROM profile_settings WHERE profile_id = 1"))
        assert personal["country"] == "DE" and personal["letterboxd_username"] == "anna"
        assert json.loads(personal["subscriptions:DE"]) == ["Netflix"]
        assert json.loads(personal["subscription_costs:DE"])["Netflix"]["price"] == 9.99
        assert "notify_token" not in personal and "notify_state" not in personal
        assert dict(fresh._read("SELECT key, value FROM settings")) == {"scan_interval_hours": "24"}


def test_a_second_profile_does_not_see_the_services_of_profile_1(tmp_path):
    store = Store(":memory:")
    store.save_provider_catalog("ZZ", [{"name": name} for name in ("Netflix", "MUBI", "Arte")])
    defaults = Settings("key", None, "DE", tmp_path)
    first = AppSettings(store, defaults)
    second = AppSettings(store, defaults, profile_id=2)
    untouched = second.subscriptions("DE")
    first.update({"subscriptions": ["MUBI", "Arte"], "costs": {"MUBI": {"price": 12}}})
    assert first.subscriptions("DE") == ["MUBI", "Arte"]
    assert second.subscriptions("DE") == untouched != first.subscriptions("DE")
    assert second.costs("DE") == {} and second.countries_in_use() == ["DE"]
    second.update({"country": "FR", "subscriptions_country": "DE", "subscriptions": ["Netflix"]})
    assert (first.country, second.country) == ("DE", "FR")
    assert first.subscriptions("DE") == ["MUBI", "Arte"] and second.subscriptions("DE") == ["Netflix"]


class TestMigrationOfWatched:
    def test_from_version_3_profiles_get_an_empty_watched_list(self, tmp_path, monkeypatch):
        path = tmp_path / "old.sqlite3"
        _v1_database(path)
        with monkeypatch.context() as patch:
            patch.setattr(store_base, "SCHEMA_VERSION", 3)
            Store(path).close()
        before = _dump(path)
        assert "watched" not in before
        store = Store(path)
        assert store._read("PRAGMA user_version") == [(4,)]
        assert store.watched_keys(profile_id=1) == set() and store.watched_fetched_at(profile_id=1) is None
        after = _dump(path)
        assert after["watched"] == []
        for table, rows in before.items():  # every row is kept; profiles get the empty fetched-at column
            assert after[table] == ([(*row, None) for row in rows] if table == "profiles" else rows), table
        store.replace_watched(["lb:seen-only"], now=5.0, profile_id=1)
        assert store.watched_keys(profile_id=1) == {"lb:seen-only"}
        assert store.watched_fetched_at(profile_id=1) == 5.0
        backup = json.dumps(store.export_backup())  # a cache: not backed up
        assert "lb:seen-only" not in backup and "watched_fetched_at" not in backup
        store.close()
        copy = sqlite3.connect(tmp_path / "old.sqlite3.pre-v4")
        assert copy.execute("PRAGMA user_version").fetchone()[0] == 3
        copy.close()
