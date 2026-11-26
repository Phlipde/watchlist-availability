"""Store methods for scans, scan jobs, availability changes and the service history."""

import json
import time

from .store_base import StoreBase
from .store_schema import JOB_FIELDS


class ScanStore(StoreBase):
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
        *,
        profile_id: int = 1,
    ) -> int:
        from . import store as store_module  # read at call time, so tests can change the limit

        cursor = self._write(
            "INSERT INTO scans "
            "(profile_id, created, country, source_name, watchlist_key, results, unavailable, stats) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                profile_id,
                created if created is not None else time.time(),
                country,
                source_name,
                watchlist_key,
                json.dumps(results),
                json.dumps(unavailable),
                json.dumps(stats),
            ),
        )
        # Per profile and country: a daily scan of one must not push out the only scan of another.
        self._write(
            "DELETE FROM scans WHERE profile_id = ? AND country = ? AND id NOT IN "
            "(SELECT id FROM scans WHERE profile_id = ? AND country = ? ORDER BY created DESC LIMIT ?)",
            (profile_id, country, profile_id, country, store_module.MAX_SCANS),
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

    def latest_scan(
        self, country: str | None = None, source_name: str | None = None, *, profile_id: int = 1
    ) -> dict | None:
        conditions = ["profile_id = ?"]
        parameters: list[object] = [profile_id]
        if country is not None:
            conditions.append("country = ?")
            parameters.append(country)
        if source_name is not None:
            conditions.append("source_name = ?")
            parameters.append(source_name)
        rows = self._read(
            f"SELECT {self._SCAN_COLUMNS} FROM scans WHERE {' AND '.join(conditions)} "
            "ORDER BY created DESC LIMIT 1",
            parameters,
        )
        return self._scan_from_row(rows[0]) if rows else None

    def latest_scan_created(self, country: str, *, profile_id: int = 1) -> float | None:
        """When the newest scan of a country was made, without loading its films (asked on every page)."""
        rows = self._read(
            "SELECT max(created) FROM scans WHERE profile_id = ? AND country = ?", (profile_id, country)
        )
        return rows[0][0] if rows else None

    def recent_scans(
        self, country: str, source_name: str, limit: int = 2, *, profile_id: int = 1
    ) -> list[dict]:
        """The newest scans of one watchlist in a country, newest first."""
        rows = self._read(
            f"SELECT {self._SCAN_COLUMNS} FROM scans WHERE profile_id = ? AND country = ? "
            "AND source_name = ? ORDER BY created DESC LIMIT ?",
            (profile_id, country, source_name, limit),
        )
        return [self._scan_from_row(row) for row in rows]

    def find_scan(
        self, country: str, watchlist_key: str, max_age: float, *, profile_id: int = 1
    ) -> dict | None:
        """A recent scan of exactly this watchlist, to skip scanning again."""
        rows = self._read(
            f"SELECT {self._SCAN_COLUMNS} FROM scans WHERE profile_id = ? AND country = ? "
            "AND watchlist_key = ? AND created > ? ORDER BY created DESC LIMIT 1",
            (profile_id, country, watchlist_key, time.time() - max_age),
        )
        return self._scan_from_row(rows[0]) if rows else None

    def get_scan(self, scan_id: int) -> dict | None:
        rows = self._read(f"SELECT {self._SCAN_COLUMNS} FROM scans WHERE id = ?", (scan_id,))
        return self._scan_from_row(rows[0]) if rows else None

    # ----- scan jobs (progress and history of scan runs) -----

    def create_job(
        self, job_id: str, country: str, trigger: str, started_at: float, *, profile_id: int = 1
    ) -> None:
        from . import store as store_module  # read at call time, so tests can change the limit

        self._write(
            "INSERT INTO jobs "
            "(id, profile_id, status, trigger, country, phase, message, started_at, heartbeat_at) "
            "VALUES (?, ?, 'running', ?, ?, 'Starting', 'Preparing scan...', ?, ?)",
            (job_id, profile_id, trigger, country, started_at, started_at),
        )
        self._write(
            "DELETE FROM jobs WHERE profile_id = ? AND id NOT IN "
            "(SELECT id FROM jobs WHERE profile_id = ? ORDER BY started_at DESC LIMIT ?)",
            (profile_id, profile_id, store_module.MAX_JOBS),
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

    def list_jobs(self, limit: int = 20, status: str | None = None, *, profile_id: int = 1) -> list[dict]:
        """Scan runs, newest first."""
        if status is None:
            rows = self._read(
                f"SELECT {', '.join(JOB_FIELDS)} FROM jobs WHERE profile_id = ? "
                "ORDER BY started_at DESC LIMIT ?",
                (profile_id, limit),
            )
        else:
            rows = self._read(
                f"SELECT {', '.join(JOB_FIELDS)} FROM jobs WHERE profile_id = ? AND status = ? "
                "ORDER BY started_at DESC LIMIT ?",
                (profile_id, status, limit),
            )
        return [self._job_from_row(row) for row in rows]

    # ----- availability changes -----

    def add_changes(
        self, country: str, changes: list[dict], created: float | None = None, *, profile_id: int = 1
    ) -> None:
        """Store changes found by watchlist_app.history.diff_scans."""
        moment = created if created is not None else time.time()
        with self._lock:
            self._db.executemany(
                "INSERT INTO changes (profile_id, created, country, film_key, title, year, provider, change) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        profile_id,
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

    def recent_changes(self, country: str, since: float, *, profile_id: int = 1) -> list[dict]:
        """Changes for a country after `since`, newest first."""
        rows = self._read(
            "SELECT created, film_key, title, year, provider, change FROM changes "
            "WHERE profile_id = ? AND country = ? AND created >= ? ORDER BY created DESC, id DESC",
            (profile_id, country, since),
        )
        names = ("created", "film_key", "title", "year", "provider", "change")
        return [dict(zip(names, row, strict=True)) for row in rows]

    # ----- service history: how many films each own service had, one row a day, kept for a year -----

    def record_service_counts(
        self, country: str, day: str, counts: dict[str, tuple[int, int]], *, profile_id: int = 1
    ) -> None:
        """Save {service: (films, only_here)} for a day (a second scan the same day replaces it)."""
        with self._lock:
            for service, (films, only_here) in counts.items():
                self._db.execute(
                    "INSERT OR REPLACE INTO service_history "
                    "(profile_id, country, day, service, films, only_here) VALUES (?, ?, ?, ?, ?, ?)",
                    (profile_id, country, day, service, films, only_here),
                )
            self._db.execute(
                "DELETE FROM service_history WHERE profile_id = ? AND country = ? "
                "AND day < date(?, '-365 days')",
                (profile_id, country, day),
            )
            self._db.commit()

    def service_history(self, country: str, *, profile_id: int = 1) -> dict[str, list[dict]]:
        """{service: [{day, films, only_here}]} oldest first."""
        rows = self._read(
            "SELECT service, day, films, only_here FROM service_history WHERE profile_id = ? AND country = ? "
            "ORDER BY day",
            (profile_id, country),
        )
        history: dict[str, list[dict]] = {}
        for service, day, films, only_here in rows:
            history.setdefault(service, []).append({"day": day, "films": films, "only_here": only_here})
        return history
