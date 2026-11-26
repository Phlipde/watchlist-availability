"""One SQLite database for film data, offers, scans, favorites and settings."""

from .store_backup import BackupStore
from .store_schema import (
    CHANGE_IDENTITY,
    FAVORITE_FIELDS,
    INTERNAL_SETTINGS,
    JOB_FIELDS,
    MATCH_FIELDS,
    MATCHES_CHANGED_SETTING,
    REGIONS_SETTING,
    SCHEMA_VERSION,
)

__all__ = [
    "BACKUP_VERSION",
    "CHANGE_IDENTITY",
    "FAVORITE_FIELDS",
    "INTERNAL_SETTINGS",
    "JOB_FIELDS",
    "MATCH_FIELDS",
    "MATCHES_CHANGED_SETTING",
    "MAX_JOBS",
    "MAX_SCANS",
    "REGIONS_SETTING",
    "SCHEMA_VERSION",
    "Store",
]

# The mixins read these through this module at call time (tests change them).
MAX_SCANS = 30  # per country
MAX_JOBS = 100
BACKUP_VERSION = 2  # 2: several profiles; import_backup still reads version 1


class Store(BackupStore):
    """Thread-safe access to the application database."""

    def counts(self) -> dict[str, int]:
        """Row counts for the status page."""
        tables = ("film_ids", "films", "offers", "scans", "changes", "favorites")
        return {table: self._read(f"SELECT count(*) FROM {table}")[0][0] for table in tables}

    def profile_counts(self, *, profile_id: int) -> dict[str, int]:
        """Row counts of one profile for the status page."""
        tables = ("changes", "favorites")
        return {
            table: self._read(f"SELECT count(*) FROM {table} WHERE profile_id = ?", (profile_id,))[0][0]
            for table in tables
        }
