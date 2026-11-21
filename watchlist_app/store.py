"""One SQLite database for film data, offers, scans, favorites and settings."""

import json
import sqlite3
import threading
import time
from pathlib import Path

from . import validation
from .models import Film, legacy_key

MAX_SCANS = 30  # per country
MAX_JOBS = 100
BACKUP_VERSION = 1
# Time of the last match correction; a recent scan is not reused after it.
MATCHES_CHANGED_SETTING = "matches_changed_at"
# Settings the app keeps for itself; they are not part of a backup.
INTERNAL_SETTINGS = frozenset({"legacy_import_done", MATCHES_CHANGED_SETTING, "notify_token", "notify_state"})
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
    checked_at REAL
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

# Columns added after the first release; created on older databases at start.
_ADDED_COLUMNS = {
    "film_ids": (
        ("title", "TEXT"),
        ("year", "INTEGER"),
        ("last_seen", "REAL"),
        ("lb_rating", "REAL"),
        ("lb_checked_at", "REAL"),
    ),
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


class Store:
    """Thread-safe access to the application database."""

    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        with self._lock:
            self._db.executescript(_SCHEMA)
            for table, columns in _ADDED_COLUMNS.items():
                existing = {row[1] for row in self._db.execute(f"PRAGMA table_info({table})")}
                for name, kind in columns:
                    if name not in existing:
                        self._db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _write(self, sql: str, parameters=()) -> sqlite3.Cursor:
        with self._lock:
            cursor = self._db.execute(sql, parameters)
            self._db.commit()
            return cursor

    def _read(self, sql: str, parameters=()) -> list[tuple]:
        with self._lock:
            return self._db.execute(sql, parameters).fetchall()

    # ----- watchlist entry -> TMDB id -----

    def get_id(self, film_key: str) -> dict | None:
        rows = self._read(
            "SELECT tmdb_id, source, checked_at, lb_rating, lb_checked_at FROM film_ids WHERE film_key = ?",
            (film_key,),
        )
        if not rows:
            return None
        tmdb_id, source, checked_at, lb_rating, lb_checked_at = rows[0]
        return {
            "tmdb_id": tmdb_id,
            "source": source,
            "checked_at": checked_at,
            "lb_rating": lb_rating,
            "lb_checked_at": lb_checked_at,
        }

    def set_letterboxd_rating(self, film_key: str, rating: float | None, checked_at=None) -> None:
        """Remember the Letterboxd average of a watchlist entry (None: too few ratings)."""
        self._write(
            "UPDATE film_ids SET lb_rating = ?, lb_checked_at = ? WHERE film_key = ?",
            (rating, checked_at if checked_at is not None else time.time(), film_key),
        )

    def set_id(
        self,
        film_key: str,
        tmdb_id: int | None,
        source: str | None,
        checked_at=None,
        title: str | None = None,
        year: int | None = None,
    ) -> None:
        """Remember which TMDB id a watchlist entry maps to (None = not found).

        Sources: "letterboxd" (id from the film page), "search" (first TMDB title
        hit), "missing" (TMDB does not know the id) and "manual" (set by the user).
        """
        now = checked_at if checked_at is not None else time.time()
        self._write(
            "INSERT INTO film_ids (film_key, tmdb_id, source, checked_at, title, year, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(film_key) DO UPDATE SET tmdb_id = excluded.tmdb_id, "
            "source = excluded.source, checked_at = excluded.checked_at, "
            "title = coalesce(excluded.title, film_ids.title), year = coalesce(excluded.year, film_ids.year)",
            (film_key, tmdb_id, source, now, title, year, now),
        )

    def remove_id(self, film_key: str) -> None:
        self._write("DELETE FROM film_ids WHERE film_key = ?", (film_key,))

    def touch_ids(self, entries: list[tuple[str, str, int | None]], seen_at: float | None = None) -> None:
        """Mark watchlist entries (key, title, year) as seen in a scan; fills in missing titles."""
        moment = seen_at if seen_at is not None else time.time()
        with self._lock:
            self._db.executemany(
                "UPDATE film_ids SET last_seen = ?, title = coalesce(title, ?), year = coalesce(year, ?) "
                "WHERE film_key = ?",
                [(moment, title, year, key) for key, title, year in entries],
            )
            self._db.commit()

    def list_matches(self, seen_since: float = 0) -> list[dict]:
        """Watchlist entries and their TMDB id, with the stored TMDB data of the film."""
        rows = self._read(
            f"SELECT {', '.join('film_ids.' + name for name in MATCH_FIELDS)}, films.poster_path, "
            "films.details FROM film_ids LEFT JOIN films ON films.tmdb_id = film_ids.tmdb_id "
            "WHERE coalesce(film_ids.last_seen, film_ids.checked_at) >= ? ORDER BY film_ids.title",
            (seen_since,),
        )
        matches = []
        for row in rows:
            match = dict(zip(MATCH_FIELDS, row[: len(MATCH_FIELDS)], strict=True))
            match["poster_path"] = row[-2]
            match["details"] = json.loads(row[-1]) if row[-1] else None
            matches.append(match)
        return matches

    # ----- TMDB film data and offers -----

    def get_film(self, tmdb_id: int, country: str) -> dict | None:
        """Details and the offers for one country, or None if nothing is stored yet."""
        rows = self._read(
            "SELECT films.poster_path, films.details, films.fetched_at, offers.providers "
            "FROM films LEFT JOIN offers ON offers.tmdb_id = films.tmdb_id AND offers.country = ? "
            "WHERE films.tmdb_id = ?",
            (country, tmdb_id),
        )
        if not rows:
            return None
        poster_path, details, fetched_at, providers = rows[0]
        return {
            "poster_path": poster_path,
            "details": json.loads(details or "{}"),
            "providers": json.loads(providers) if providers else {},
            "fetched_at": fetched_at,
        }

    def offers_by_country(self, tmdb_id: int) -> dict[str, dict[str, list[str]]]:
        """The stored offers of every country: {country: {TMDB provider name: kinds}}."""
        rows = self._read("SELECT country, providers FROM offers WHERE tmdb_id = ?", (tmdb_id,))
        return {country: json.loads(providers) for country, providers in rows}

    def offers_for(self, tmdb_ids: list[int]) -> dict[str, dict[int, dict[str, list[str]]]]:
        """The stored offers of the given films in every country: {country: {tmdb_id: {provider: kinds}}}."""
        found: dict[str, dict[int, dict[str, list[str]]]] = {}
        for start in range(0, len(tmdb_ids), 500):  # SQLite limits the number of parameters
            chunk = tmdb_ids[start : start + 500]
            marks = ", ".join("?" for _ in chunk)
            for tmdb_id, country, providers in self._read(
                f"SELECT tmdb_id, country, providers FROM offers WHERE tmdb_id IN ({marks})", tuple(chunk)
            ):
                found.setdefault(country, {})[tmdb_id] = json.loads(providers)
        return found

    def save_bundle(self, tmdb_id: int, bundle: dict, fetched_at=None) -> None:
        """Store details and the offers of every country from one TMDB response."""
        with self._lock:
            self._db.execute(
                "INSERT INTO films (tmdb_id, poster_path, details, fetched_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(tmdb_id) DO UPDATE SET poster_path = excluded.poster_path, "
                "details = excluded.details, fetched_at = excluded.fetched_at",
                (
                    tmdb_id,
                    bundle.get("poster_path"),
                    json.dumps(bundle.get("details") or {}),
                    fetched_at if fetched_at is not None else time.time(),
                ),
            )
            self._db.execute("DELETE FROM offers WHERE tmdb_id = ?", (tmdb_id,))
            self._db.executemany(
                "INSERT INTO offers (tmdb_id, country, providers) VALUES (?, ?, ?)",
                [
                    (tmdb_id, country, json.dumps(providers))
                    for country, providers in (bundle.get("providers") or {}).items()
                ],
            )
            self._db.commit()

    # ----- providers TMDB knows per country -----

    def save_provider_catalog(self, country: str, items: list[dict], fetched_at=None) -> None:
        """Replace the providers of a country ({"name", "logo_path", "priority"} each)."""
        moment = fetched_at if fetched_at is not None else time.time()
        with self._lock:
            self._db.execute("DELETE FROM provider_catalog WHERE country = ?", (country,))
            self._db.executemany(
                "INSERT OR REPLACE INTO provider_catalog "
                "(country, tmdb_name, logo_path, priority, fetched_at) VALUES (?, ?, ?, ?, ?)",
                [
                    (country, item["name"], item.get("logo_path"), item.get("priority"), moment)
                    for item in items
                ],
            )
            self._db.commit()

    def provider_catalog(self, country: str | None = None) -> list[dict]:
        """Stored providers, by country and TMDB display priority."""
        where, parameters = ("WHERE country = ?", (country,)) if country else ("", ())
        rows = self._read(
            "SELECT country, tmdb_name, logo_path, priority, fetched_at FROM provider_catalog "
            f"{where} ORDER BY country, coalesce(priority, 9999), tmdb_name",
            parameters,
        )
        names = ("country", "name", "logo_path", "priority", "fetched_at")
        return [dict(zip(names, row, strict=True)) for row in rows]

    def provider_catalog_age(self, country: str) -> float | None:
        """When the providers of a country were last fetched, or None."""
        return self._read("SELECT max(fetched_at) FROM provider_catalog WHERE country = ?", (country,))[0][0]

    # ----- scans -----

    def save_scan(
        self,
        country: str,
        source_name: str,
        watchlist_key: str | None,
        results: list[dict],
        unavailable: list[dict],
        stats: dict,
        created: float | None = None,
    ) -> int:
        cursor = self._write(
            "INSERT INTO scans (created, country, source_name, watchlist_key, results, unavailable, stats) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                created if created is not None else time.time(),
                country,
                source_name,
                watchlist_key,
                json.dumps(results),
                json.dumps(unavailable),
                json.dumps(stats),
            ),
        )
        # Per country: a daily scan of one country must not push out the only scan of another.
        self._write(
            "DELETE FROM scans WHERE country = ? AND id NOT IN "
            "(SELECT id FROM scans WHERE country = ? ORDER BY created DESC LIMIT ?)",
            (country, country, MAX_SCANS),
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def _scan_from_row(self, row) -> dict:
        scan_id, created, country, source_name, watchlist_key, results, unavailable, stats = row
        return {
            "id": scan_id,
            "created": created,
            "country": country,
            "source_name": source_name,
            "watchlist_key": watchlist_key,
            "results": json.loads(results),
            "unavailable": json.loads(unavailable),
            "stats": json.loads(stats or "{}"),
        }

    _SCAN_COLUMNS = "id, created, country, source_name, watchlist_key, results, unavailable, stats"

    def latest_scan(self, country: str | None = None, source_name: str | None = None) -> dict | None:
        conditions, parameters = [], []
        if country is not None:
            conditions.append("country = ?")
            parameters.append(country)
        if source_name is not None:
            conditions.append("source_name = ?")
            parameters.append(source_name)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self._read(
            f"SELECT {self._SCAN_COLUMNS} FROM scans {where} ORDER BY created DESC LIMIT 1",
            parameters,
        )
        return self._scan_from_row(rows[0]) if rows else None

    def recent_scans(self, country: str, source_name: str, limit: int = 2) -> list[dict]:
        """The newest scans of one watchlist in a country, newest first."""
        rows = self._read(
            f"SELECT {self._SCAN_COLUMNS} FROM scans WHERE country = ? AND source_name = ? "
            "ORDER BY created DESC LIMIT ?",
            (country, source_name, limit),
        )
        return [self._scan_from_row(row) for row in rows]

    def find_scan(self, country: str, watchlist_key: str, max_age: float) -> dict | None:
        """A recent scan of exactly this watchlist, to skip scanning again."""
        rows = self._read(
            f"SELECT {self._SCAN_COLUMNS} FROM scans WHERE country = ? AND watchlist_key = ? "
            "AND created > ? ORDER BY created DESC LIMIT 1",
            (country, watchlist_key, time.time() - max_age),
        )
        return self._scan_from_row(rows[0]) if rows else None

    def get_scan(self, scan_id: int) -> dict | None:
        rows = self._read(f"SELECT {self._SCAN_COLUMNS} FROM scans WHERE id = ?", (scan_id,))
        return self._scan_from_row(rows[0]) if rows else None

    # ----- scan jobs (progress and history of scan runs) -----

    def create_job(self, job_id: str, country: str, trigger: str, started_at: float) -> None:
        self._write(
            "INSERT INTO jobs (id, status, trigger, country, phase, message, started_at, heartbeat_at) "
            "VALUES (?, 'running', ?, ?, 'Starting', 'Preparing scan...', ?, ?)",
            (job_id, trigger, country, started_at, started_at),
        )
        self._write(
            "DELETE FROM jobs WHERE id NOT IN (SELECT id FROM jobs ORDER BY started_at DESC LIMIT ?)",
            (MAX_JOBS,),
        )

    def update_job(self, job_id: str, **fields) -> None:
        unknown = set(fields) - set(JOB_FIELDS)
        if unknown:
            raise ValueError(f"Unknown job fields: {sorted(unknown)}")
        if "failed" in fields:
            fields["failed"] = json.dumps(fields["failed"])
        if "reused" in fields:
            fields["reused"] = int(bool(fields["reused"]))
        assignments = ", ".join(f"{name} = ?" for name in fields)
        self._write(f"UPDATE jobs SET {assignments} WHERE id = ?", (*fields.values(), job_id))

    def _job_from_row(self, row) -> dict:
        job = dict(zip(JOB_FIELDS, row, strict=True))
        job["failed"] = json.loads(job["failed"] or "[]")
        job["reused"] = bool(job["reused"])
        return job

    def get_job(self, job_id: str) -> dict | None:
        rows = self._read(f"SELECT {', '.join(JOB_FIELDS)} FROM jobs WHERE id = ?", (job_id,))
        return self._job_from_row(rows[0]) if rows else None

    def list_jobs(self, limit: int = 20, status: str | None = None) -> list[dict]:
        """Scan runs, newest first."""
        if status is None:
            rows = self._read(
                f"SELECT {', '.join(JOB_FIELDS)} FROM jobs ORDER BY started_at DESC LIMIT ?", (limit,)
            )
        else:
            rows = self._read(
                f"SELECT {', '.join(JOB_FIELDS)} FROM jobs WHERE status = ? ORDER BY started_at DESC LIMIT ?",
                (status, limit),
            )
        return [self._job_from_row(row) for row in rows]

    # ----- availability changes -----

    def add_changes(self, country: str, changes: list[dict], created: float | None = None) -> None:
        """Store changes found by watchlist_app.history.diff_scans."""
        moment = created if created is not None else time.time()
        with self._lock:
            self._db.executemany(
                "INSERT INTO changes (created, country, film_key, title, year, provider, change) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        moment,
                        country,
                        change["film_key"],
                        change["title"],
                        change["year"],
                        change["provider"],
                        change["change"],
                    )
                    for change in changes
                ],
            )
            self._db.commit()

    def recent_changes(self, country: str, since: float) -> list[dict]:
        """Changes for a country after `since`, newest first."""
        rows = self._read(
            "SELECT created, film_key, title, year, provider, change FROM changes "
            "WHERE country = ? AND created >= ? ORDER BY created DESC, id DESC",
            (country, since),
        )
        names = ("created", "film_key", "title", "year", "provider", "change")
        return [dict(zip(names, row, strict=True)) for row in rows]

    # ----- favorites -----

    def list_favorites(self) -> list[dict]:
        rows = self._read(
            "SELECT movie_key, title, year, poster_path, tmdb_url, trailer_url, rating, status, notes, "
            "added_at FROM favorites ORDER BY title"
        )
        return [dict(zip(FAVORITE_FIELDS, row, strict=True)) for row in rows]

    def add_favorite(self, movie: dict) -> None:
        self._write(
            "INSERT OR REPLACE INTO favorites "
            "(movie_key, title, year, poster_path, tmdb_url, trailer_url, rating, status, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                movie["key"],
                movie["title"],
                movie.get("year"),
                movie.get("poster_path"),
                movie.get("tmdb_url"),
                movie.get("trailer_url"),
                movie.get("rating"),
                movie.get("status", "plan"),
                movie.get("notes", ""),
            ),
        )

    def update_favorite(self, movie_key: str, changes: dict) -> None:
        allowed = {key: value for key, value in changes.items() if key in {"status", "notes"}}
        if not allowed:
            return
        assignments = ", ".join(f"{column} = ?" for column in allowed)
        self._write(
            f"UPDATE favorites SET {assignments} WHERE movie_key = ?",
            (*allowed.values(), movie_key),
        )

    def remove_favorite(self, movie_key: str) -> None:
        self._write("DELETE FROM favorites WHERE movie_key = ?", (movie_key,))

    # ----- service history: how many films each own service had, one row a day, kept for a year -----

    def record_service_counts(self, country: str, day: str, counts: dict[str, tuple[int, int]]) -> None:
        """Save {service: (films, only_here)} for a day (a second scan the same day replaces it)."""
        with self._lock:
            for service, (films, only_here) in counts.items():
                self._db.execute(
                    "INSERT OR REPLACE INTO service_history (country, day, service, films, only_here) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (country, day, service, films, only_here),
                )
            self._db.execute(
                "DELETE FROM service_history WHERE country = ? AND day < date(?, '-365 days')", (country, day)
            )
            self._db.commit()

    def service_history(self, country: str) -> dict[str, list[dict]]:
        """{service: [{day, films, only_here}]} oldest first."""
        rows = self._read(
            "SELECT service, day, films, only_here FROM service_history WHERE country = ? ORDER BY day",
            (country,),
        )
        history: dict[str, list[dict]] = {}
        for service, day, films, only_here in rows:
            history.setdefault(service, []).append({"day": day, "films": films, "only_here": only_here})
        return history

    # ----- flags: "watched" and "not now" (hidden until a date), kept apart from favorites -----

    def list_flags(self, now: float | None = None) -> list[dict]:
        """Flags that count: watched ones, and "not now" until its date."""
        now = now if now is not None else time.time()
        rows = self._read(
            "SELECT movie_key, flag, until FROM flags WHERE until IS NULL OR until > ? ORDER BY movie_key",
            (now,),
        )
        return [{"key": key, "flag": flag, "until": until} for key, flag, until in rows]

    def set_flag(self, movie_key: str, flag: str, until: float | None = None) -> None:
        self._write(
            "INSERT OR REPLACE INTO flags (movie_key, flag, until) VALUES (?, ?, ?)", (movie_key, flag, until)
        )

    def clear_flag(self, movie_key: str) -> None:
        self._write("DELETE FROM flags WHERE movie_key = ?", (movie_key,))

    def greyed_out_counts(self) -> dict[str, int]:
        """How many films are greyed out: by the flag, and by a favorite with the status "watched"."""
        flags = self._read("SELECT COUNT(*) FROM flags WHERE flag = 'watched'")[0][0]
        favorites = self._read("SELECT COUNT(*) FROM favorites WHERE status = 'watched'")[0][0]
        return {"flags": flags, "favorites": favorites}

    def reset_greyed_out(self) -> dict[str, int]:
        """Remove every grey-out; favorites stay, their status goes back to "plan". Returns the counts."""
        with self._lock:
            flags = self._db.execute("DELETE FROM flags WHERE flag = 'watched'").rowcount
            favorites = self._db.execute(
                "UPDATE favorites SET status = 'plan' WHERE status = 'watched'"
            ).rowcount
            self._db.commit()
        return {"flags": flags, "favorites": favorites}

    def rekey_favorites(self, films: list[Film]) -> int:
        """Move favorites saved under `Title|Year` to the TMDB id of the same film."""
        moved = 0
        with self._lock:
            existing = {row[0] for row in self._db.execute("SELECT movie_key FROM favorites")}
            for film in films:
                if film.tmdb_id is None:
                    continue
                old, new = legacy_key(film.title, film.year), film.key
                if old in existing and new not in existing:
                    self._db.execute("UPDATE favorites SET movie_key = ? WHERE movie_key = ?", (new, old))
                    existing.discard(old)
                    existing.add(new)
                    moved += 1
            self._db.commit()
        return moved

    # ----- backup -----

    def export_backup(self) -> dict:
        """Everything worth keeping: settings, favorites, change history and the last scan per country.

        Film data and offers are left out; the next scan fetches them again.
        """
        latest_ids = [row[0] for row in self._read("SELECT max(id) FROM scans GROUP BY country")]
        changes = self._read(
            "SELECT created, country, film_key, title, year, provider, change FROM changes ORDER BY id"
        )
        change_names = ("created", "country", "film_key", "title", "year", "provider", "change")
        return {
            "version": BACKUP_VERSION,
            "exported_at": time.time(),
            "settings": {
                key: value
                for key, value in self._read("SELECT key, value FROM settings")
                if key not in INTERNAL_SETTINGS
            },
            "favorites": self.list_favorites(),
            "flags": self.list_flags(),
            "changes": [dict(zip(change_names, row, strict=True)) for row in changes],
            "scans": [self.get_scan(scan_id) for scan_id in latest_ids],
            "matches": [
                {"film_key": key, "title": title, "year": year, "tmdb_id": tmdb_id}
                for key, title, year, tmdb_id in self._read(
                    "SELECT film_key, title, year, tmdb_id FROM film_ids WHERE source = 'manual'"
                )
            ],
        }

    def import_backup(self, backup: dict) -> dict[str, int]:
        """Restore favorites, changes, scans and match corrections from a backup.

        A backup file can come from anywhere: every entry is rebuilt with fixed
        types (watchlist_app.validation) and unusable entries are skipped and
        counted. Settings are restored by AppSettings.restore, with the same checks
        as the settings page. Changes, scans and matches are added only once.
        """
        if not isinstance(backup, dict) or backup.get("version") != BACKUP_VERSION:
            raise ValueError("This file is not a watchlist backup of a supported version.")
        favorites = backup.get("favorites") or []
        changes = backup.get("changes") or []
        scans = backup.get("scans") or []
        matches = backup.get("matches") or []  # missing in backups made before match corrections
        flags = backup.get("flags") or []  # missing in backups made before "watched" and "not now"
        if not all(isinstance(part, list) for part in (favorites, changes, scans, matches, flags)):
            raise ValueError("The backup file is damaged.")
        now = time.time()
        skipped = 0

        imported_favorites = 0
        for raw_favorite in favorites:
            favorite = validation.clean_favorite(raw_favorite)
            if favorite is None:
                skipped += 1
                continue
            self.add_favorite(favorite)
            imported_favorites += 1

        for raw_flag in flags:
            flag = validation.clean_flag(raw_flag, now)
            if flag is None:
                skipped += 1
                continue
            self.set_flag(flag["key"], flag["flag"], flag["until"])

        known = {
            tuple(row)
            for row in self._read("SELECT created, country, film_key, provider, change FROM changes")
        }
        new_changes: dict[tuple[float, str], list[dict]] = {}
        for raw_change in changes:
            change = validation.clean_change(raw_change, now)
            if change is None:
                skipped += 1
                continue
            identity = tuple(change[name] for name in CHANGE_IDENTITY)
            if identity not in known:
                known.add(identity)
                new_changes.setdefault((change["created"], change["country"]), []).append(change)
        for (created, country), group in new_changes.items():
            self.add_changes(country, group, created=created)

        existing_scans = {tuple(row) for row in self._read("SELECT created, country FROM scans")}
        imported_scans = 0
        for raw_scan in scans:
            scan, dropped_films = validation.clean_scan(raw_scan, now)
            skipped += dropped_films
            if scan is None:
                skipped += 1
                continue
            if (scan["created"], scan["country"]) in existing_scans:
                continue
            existing_scans.add((scan["created"], scan["country"]))
            self.save_scan(
                scan["country"],
                scan["source_name"],
                scan["watchlist_key"],
                scan["results"],
                scan["unavailable"],
                scan["stats"],
                created=scan["created"],
            )
            imported_scans += 1

        imported_matches = 0
        for raw_match in matches:
            match = validation.clean_match(raw_match)
            if match is None:
                skipped += 1
                continue
            stored = self.get_id(match["film_key"])
            if stored and (stored["tmdb_id"], stored["source"]) == (match["tmdb_id"], "manual"):
                continue
            self.set_id(
                match["film_key"], match["tmdb_id"], "manual", title=match["title"], year=match["year"]
            )
            imported_matches += 1
        if imported_matches:
            self.set_setting(MATCHES_CHANGED_SETTING, str(now))
        return {
            "favorites": imported_favorites,
            "changes": sum(len(group) for group in new_changes.values()),
            "scans": imported_scans,
            "matches": imported_matches,
            "skipped": skipped,
        }

    def counts(self) -> dict[str, int]:
        """Row counts for the status page."""
        tables = ("film_ids", "films", "offers", "scans", "changes", "favorites")
        return {table: self._read(f"SELECT count(*) FROM {table}")[0][0] for table in tables}

    # ----- settings -----

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        rows = self._read("SELECT value FROM settings WHERE key = ?", (key,))
        return rows[0][0] if rows else default

    def set_setting(self, key: str, value: str | None) -> None:
        self._write(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
