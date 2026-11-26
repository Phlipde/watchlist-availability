"""Database layout of the Store: schema SQL, migrations, setting names and column lists."""

# Time of the last match correction; a recent scan is not reused after it.
MATCHES_CHANGED_SETTING = "matches_changed_at"
# Settings the app keeps for itself; they are not part of a backup.
REGIONS_SETTING = "tmdb_regions"  # the countries TMDB has offers for, as JSON with the fetch time
INTERNAL_SETTINGS = frozenset({MATCHES_CHANGED_SETTING, "notify_token", "notify_state", REGIONS_SETTING})
# Fields that identify a stored change, used to skip duplicates when restoring a backup.
CHANGE_IDENTITY = ("created", "country", "film_key", "provider", "change")

JOB_FIELDS = (
    "id",
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

# The database layout is versioned with SQLite's `user_version`. Version 1 is the layout of _SCHEMA above, the
# baseline of 2026-11-22 (the production database already had it); layouts before it are not migrated.
# A later change: put the SQL from version N-1 to N into _MIGRATIONS[N], raise SCHEMA_VERSION to N and put the
# same change into _SCHEMA for new databases.
SCHEMA_VERSION = 1
_MIGRATIONS: dict[int, str] = {}

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
