"""Migration of the database layout from version 1 (no profiles) to 2 (data owned by profile 1)."""

import json
import sqlite3

from watchlist_app.store import SCHEMA_VERSION, Store

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
        "settings": [("country", "DE")]
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
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 2
        for table in ("favorites", "flags", "service_history"):
            stored = connection.execute(f"SELECT * FROM {table}").fetchall()
            assert sorted(stored) == sorted((1, *row) for row in rows[table])  # profile_id comes first
        for table in ("scans", "changes", "jobs"):
            stored = connection.execute(f"SELECT * FROM {table}").fetchall()
            assert sorted(stored) == sorted((*row, 1) for row in rows[table])  # profile_id comes last
        assert sorted(connection.execute("SELECT * FROM settings").fetchall()) == sorted(rows["settings"])
        assert connection.execute("SELECT id, name, email FROM profiles").fetchall() == [(1, "anna", None)]
        connection.close()
        copy = sqlite3.connect(tmp_path / "old.sqlite3.pre-v2")
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
        store.add_favorite({"key": "lb:heat", "title": "Heat", "year": 1995, "status": "seen"})  # replaces
        store.add_favorite({"key": "lb:up", "title": "Up"})
        store.update_favorite("lb:up", {"notes": "later"})
        assert [(f["key"], f["status"], f["notes"]) for f in store.list_favorites()] == [
            ("lb:heat", "seen", ""),
            ("lb:up", "plan", "later"),
        ]
        store.remove_favorite("lb:heat")
        assert [f["key"] for f in store.list_favorites()] == ["lb:up"]
        store.set_flag("lb:alien", "not_now", 9e9)  # replaces the "watched" flag
        store.clear_flag("lb:jaws")
        assert store.list_flags(now=0) == [{"key": "lb:alien", "flag": "not_now", "until": 9e9}]
        store.record_service_counts("DE", "2026-11-20", {"Netflix": (61, 13)})  # the same day: replaced
        assert store.service_history("DE")["Netflix"] == [{"day": "2026-11-20", "films": 61, "only_here": 13}]
        assert store._read("SELECT DISTINCT profile_id FROM favorites") == [(1,)]
        assert store._read("SELECT DISTINCT profile_id FROM flags") == [(1,)]
        assert "profile_id" not in json.dumps(store.export_backup())  # the backup format is unchanged
