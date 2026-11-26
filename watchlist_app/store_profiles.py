"""Store methods for the profiles: list, add, rename and delete."""

import sqlite3
import time

from . import validation
from .store_base import StoreBase

# Every table with rows owned by one profile; deleting the profile empties them for it.
_OWNED_TABLES = ("favorites", "flags", "service_history", "scans", "changes", "jobs", "profile_settings")


def _clean(name, email) -> dict:
    """The profile as validation.clean_profile keeps it; ValueError for a bad name or e-mail."""
    profile = validation.clean_profile({"name": name, "email": email})
    if profile is None:
        raise ValueError(f"A name of 1 to {validation.MAX_PROFILE_NAME} printable characters is required.")
    if isinstance(email, str) and email.strip() and profile["email"] is None:
        raise ValueError("That does not look like an e-mail address.")
    return profile


class ProfileStore(StoreBase):
    def list_profiles(self) -> list[dict]:
        rows = self._read("SELECT id, name, email FROM profiles ORDER BY id")
        return [{"id": profile_id, "name": name, "email": email} for profile_id, name, email in rows]

    def find_profile(self, name: str) -> int | None:
        rows = self._read("SELECT id FROM profiles WHERE name = ?", (name,))
        return rows[0][0] if rows else None

    def add_profile(self, name: str | None, email: str | None = None) -> int:
        """A new profile; ValueError for an invalid or already used name."""
        return self._new_profile(_clean(name, email), time.time())

    def _new_profile(self, profile: dict, now: float) -> int:
        try:
            cursor = self._write(
                "INSERT INTO profiles (name, email, created) VALUES (?, ?, ?)",
                (profile["name"], profile["email"], now),
            )
        except sqlite3.IntegrityError:
            raise ValueError("A profile with that name already exists.") from None
        return int(cursor.lastrowid or 0)

    def rename_profile(self, profile_id: int, name: str | None, email: str | None = None) -> bool:
        """Set name and e-mail; False for an unknown id, ValueError for an invalid or used name."""
        profile = _clean(name, email)
        try:
            cursor = self._write(
                "UPDATE profiles SET name = ?, email = ? WHERE id = ?",
                (profile["name"], profile["email"], profile_id),
            )
        except sqlite3.IntegrityError:
            raise ValueError("A profile with that name already exists.") from None
        return cursor.rowcount > 0

    def delete_profile(self, profile_id: int) -> bool:
        """Remove the profile and all its rows in one transaction; False for an unknown id.

        ValueError for the last profile: the app always needs one.
        """
        with self._lock, self._db:
            if not self._db.execute("SELECT 1 FROM profiles WHERE id = ?", (profile_id,)).fetchone():
                return False
            if self._db.execute("SELECT count(*) FROM profiles").fetchone()[0] <= 1:
                raise ValueError("The last profile cannot be deleted.")
            for table in _OWNED_TABLES:
                self._db.execute(f"DELETE FROM {table} WHERE profile_id = ?", (profile_id,))
            self._db.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        return True
