"""The connection of the Store: opening and migrating the database, locked reads and writes."""

import sqlite3
import threading
from pathlib import Path

from .store_schema import _MIGRATIONS, _SCHEMA, SCHEMA_VERSION


class StoreBase:
    """One SQLite connection, used under a lock by all Store methods."""

    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self._lock = threading.Lock()
        self.offers_version = 0  # counts the saved offers, so answers built from them can be cached safely
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        with self._lock:
            version = self._db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError(f"The database is from a newer version of the app (layout {version}).")
            if not self._db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table'").fetchone():
                # An empty database gets the current layout at once; _SCHEMA would not fit an older one.
                self._db.executescript(_SCHEMA)
            else:
                version = max(version, 1)  # tables without a version: the baseline layout 1
                if version < SCHEMA_VERSION and self.path != ":memory:":
                    # A migration cannot be undone: keep a copy of the old layout next to the database first.
                    with sqlite3.connect(f"{self.path}.pre-v{SCHEMA_VERSION}") as copy:
                        self._db.backup(copy)
                    copy.close()
                for step in range(version + 1, SCHEMA_VERSION + 1):
                    if step in _MIGRATIONS:
                        self._db.executescript(_MIGRATIONS[step])
            self._db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
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
