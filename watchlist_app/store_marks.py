"""Store methods for favorites, flags and settings."""

import time

from .store_base import StoreBase
from .store_schema import FAVORITE_FIELDS


class MarkStore(StoreBase):
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

    # ----- settings -----

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        rows = self._read("SELECT value FROM settings WHERE key = ?", (key,))
        return rows[0][0] if rows else default

    def setting_keys(self, prefix: str) -> list[str]:
        """Stored setting keys that start with `prefix` (no LIKE: `_` would be a wildcard)."""
        rows = self._read("SELECT key FROM settings WHERE substr(key, 1, ?) = ?", (len(prefix), prefix))
        return [row[0] for row in rows]

    def set_setting(self, key: str, value: str | None) -> None:
        self._write(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
