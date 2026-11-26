"""Database layout of the Store: schema SQL, migrations, setting names and column lists."""

# Time of the last match correction; a recent scan is not reused after it.
MATCHES_CHANGED_SETTING = "matches_changed_at"
# Settings the app keeps for itself; they are not part of a backup.
REGIONS_SETTING = "tmdb_regions"  # the countries TMDB has offers for, as JSON with the fetch time
INTERNAL_SETTINGS = frozenset({MATCHES_CHANGED_SETTING, "notify_token", "notify_state", REGIONS_SETTING})
# Settings of one person, kept in profile_settings; every other key stays global in settings.
PROFILE_SETTING_KEYS = frozenset(
    {
        "letterboxd_username",
        "country",
        "weekly_hours",
        "notify_kind",
        "notify_url",
        "notify_token",
        "notify_events",
        "notify_state",
    }
)
PROFILE_SETTING_PREFIXES = ("subscriptions:", "subscription_costs:")


def is_profile_setting(key: str) -> bool:
    return key in PROFILE_SETTING_KEYS or key.startswith(PROFILE_SETTING_PREFIXES)


# The same test in SQL, for the migration (substr, not LIKE: `_` would be a wildcard).
_PROFILE_KEYS_SQL = (
    "key IN ({}) OR substr(key, 1, 14) = 'subscriptions:' OR substr(key, 1, 19) = 'subscription_costs:'"
).format(", ".join(f"'{key}'" for key in sorted(PROFILE_SETTING_KEYS)))
# Fields that identify a stored change, used to skip duplicates when restoring a backup.
CHANGE_IDENTITY = ("created", "country", "film_key", "provider", "change")

JOB_FIELDS = (
    "id",
    "profile_id",
    "status",
    "trigger",
    "country",
    "source_name",
    "phase",
    "message",
    "completed",
    "total",
    "available",
    "unavailable",
    "failed",
    "tmdb_requests",
    "reused",
    "started_at",
    "heartbeat_at",
    "finished_at",
    "scan_id",
)

_SCHEMA = """
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
    stats TEXT NOT NULL DEFAULT '{}',
    profile_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created REAL NOT NULL,
    country TEXT NOT NULL,
    film_key TEXT NOT NULL,
    title TEXT NOT NULL,
    year INTEGER,
    provider TEXT NOT NULL,
    change TEXT NOT NULL,
    profile_id INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS changes_by_country ON changes (country, created);
CREATE INDEX IF NOT EXISTS changes_by_owner ON changes (profile_id, country, created);
CREATE INDEX IF NOT EXISTS scans_by_owner ON scans (profile_id, country, created);
CREATE TABLE IF NOT EXISTS favorites (
    profile_id INTEGER NOT NULL DEFAULT 1,
    movie_key TEXT NOT NULL,
    title TEXT NOT NULL,
    year INTEGER,
    poster_path TEXT,
    tmdb_url TEXT,
    trailer_url TEXT,
    rating REAL,
    status TEXT NOT NULL DEFAULT 'plan',
    notes TEXT NOT NULL DEFAULT '',
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profile_id, movie_key)
);
CREATE TABLE IF NOT EXISTS service_history (
    profile_id INTEGER NOT NULL DEFAULT 1,
    country TEXT NOT NULL,
    day TEXT NOT NULL,
    service TEXT NOT NULL,
    films INTEGER NOT NULL,
    only_here INTEGER NOT NULL,
    PRIMARY KEY (profile_id, country, day, service)
);
CREATE TABLE IF NOT EXISTS flags (
    profile_id INTEGER NOT NULL DEFAULT 1,
    movie_key TEXT NOT NULL,
    flag TEXT NOT NULL,
    until REAL,
    PRIMARY KEY (profile_id, movie_key)
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
    scan_id INTEGER,
    profile_id INTEGER NOT NULL DEFAULT 1
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
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    email TEXT,
    created REAL NOT NULL
);
INSERT OR IGNORE INTO profiles (id, name, created) VALUES (1, 'Me', (julianday('now') - 2440587.5) * 86400.0);
CREATE TABLE IF NOT EXISTS profile_settings (
    profile_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (profile_id, key)
);
"""

# The database layout is versioned with SQLite's `user_version`. Version 1 is the baseline of 2026-11-22 (the
# production database already had it); layouts before it are not migrated. _SCHEMA above is the current layout
# and only runs on an empty database; an older one goes through the migrations.
# A later change: put the SQL from version N-1 to N into _MIGRATIONS[N] (in BEGIN; ... COMMIT; with its
# user_version, so a crash leaves the old layout), raise SCHEMA_VERSION to N and change _SCHEMA the same way.
SCHEMA_VERSION = 3
_MIGRATIONS: dict[int, str] = {
    # 2: profiles; favorites, flags and service_history get profile_id in their key, scans, changes and jobs
    # an owner column. Everything that exists belongs to profile 1.
    2: """
BEGIN;
CREATE TABLE profiles (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    email TEXT,
    created REAL NOT NULL
);
INSERT INTO profiles (id, name, created) VALUES (
    1,
    COALESCE(NULLIF((SELECT trim(value) FROM settings WHERE key = 'letterboxd_username'), ''), 'Me'),
    (julianday('now') - 2440587.5) * 86400.0
);
CREATE TABLE favorites_new (
    profile_id INTEGER NOT NULL DEFAULT 1,
    movie_key TEXT NOT NULL,
    title TEXT NOT NULL,
    year INTEGER,
    poster_path TEXT,
    tmdb_url TEXT,
    trailer_url TEXT,
    rating REAL,
    status TEXT NOT NULL DEFAULT 'plan',
    notes TEXT NOT NULL DEFAULT '',
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profile_id, movie_key)
);
INSERT INTO favorites_new (
    profile_id, movie_key, title, year, poster_path, tmdb_url, trailer_url, rating, status, notes, added_at
)
SELECT 1, movie_key, title, year, poster_path, tmdb_url, trailer_url, rating, status, notes, added_at
FROM favorites;
DROP TABLE favorites;
ALTER TABLE favorites_new RENAME TO favorites;
CREATE TABLE service_history_new (
    profile_id INTEGER NOT NULL DEFAULT 1,
    country TEXT NOT NULL,
    day TEXT NOT NULL,
    service TEXT NOT NULL,
    films INTEGER NOT NULL,
    only_here INTEGER NOT NULL,
    PRIMARY KEY (profile_id, country, day, service)
);
INSERT INTO service_history_new (profile_id, country, day, service, films, only_here)
SELECT 1, country, day, service, films, only_here FROM service_history;
DROP TABLE service_history;
ALTER TABLE service_history_new RENAME TO service_history;
CREATE TABLE flags_new (
    profile_id INTEGER NOT NULL DEFAULT 1,
    movie_key TEXT NOT NULL,
    flag TEXT NOT NULL,
    until REAL,
    PRIMARY KEY (profile_id, movie_key)
);
INSERT INTO flags_new (profile_id, movie_key, flag, until) SELECT 1, movie_key, flag, until FROM flags;
DROP TABLE flags;
ALTER TABLE flags_new RENAME TO flags;
ALTER TABLE scans ADD COLUMN profile_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE changes ADD COLUMN profile_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE jobs ADD COLUMN profile_id INTEGER NOT NULL DEFAULT 1;
CREATE INDEX changes_by_owner ON changes (profile_id, country, created);
CREATE INDEX scans_by_owner ON scans (profile_id, country, created);
PRAGMA user_version = 2;
COMMIT;
""",
    # 3: the settings of one person move from settings to profile_settings, owned by profile 1. Version 2
    # has already named profile 1 after the stored letterboxd_username.
    3: f"""
BEGIN;
CREATE TABLE profile_settings (
    profile_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (profile_id, key)
);
INSERT INTO profile_settings (profile_id, key, value)
SELECT 1, key, value FROM settings WHERE {_PROFILE_KEYS_SQL};
DELETE FROM settings WHERE {_PROFILE_KEYS_SQL};
PRAGMA user_version = 3;
COMMIT;
""",
}

MATCH_FIELDS = ("film_key", "title", "year", "tmdb_id", "source", "checked_at", "last_seen")

FAVORITE_FIELDS = (
    "key",
    "title",
    "year",
    "poster_path",
    "tmdb_url",
    "trailer_url",
    "rating",
    "status",
    "notes",
    "added_at",
)
