"""Store methods for the backup file: export and import."""

import time

from . import validation
from .store_films import FilmStore
from .store_marks import MarkStore
from .store_scans import ScanStore
from .store_schema import CHANGE_IDENTITY, INTERNAL_SETTINGS, MATCHES_CHANGED_SETTING

_CHANGE_NAMES = ("created", "country", "film_key", "title", "year", "provider", "change")
# The lists one person owns in a backup: v1 has them at the top, v2 in each entry of "profiles".
_PERSONAL_PARTS = ("favorites", "flags", "changes", "scans")


def _personal_parts(entry) -> list[list] | None:
    """The four lists of one person (a missing one is empty); None when one is not a list."""
    if not isinstance(entry, dict):
        return None
    parts = [entry.get(name) or [] for name in _PERSONAL_PARTS]
    return parts if all(isinstance(part, list) for part in parts) else None


class BackupStore(FilmStore, ScanStore, MarkStore):
    # ----- backup -----

    def _public_settings(self, sql: str, parameters=()) -> dict[str, str]:
        return {key: value for key, value in self._read(sql, parameters) if key not in INTERNAL_SETTINGS}

    def export_backup(self) -> dict:
        """Everything worth keeping: global settings, match corrections and per profile its settings,
        favorites, flags, change history and the last scan per country.

        Film data and offers are left out; the next scan fetches them again.
        """
        from . import store as store_module  # read at call time, so tests can change the version

        profiles = []
        for profile_id, name, email in self._read("SELECT id, name, email FROM profiles ORDER BY id"):
            latest_ids = [
                row[0]
                for row in self._read(
                    "SELECT max(id) FROM scans WHERE profile_id = ? GROUP BY country", (profile_id,)
                )
            ]
            changes = self._read(
                f"SELECT {', '.join(_CHANGE_NAMES)} FROM changes WHERE profile_id = ? ORDER BY id",
                (profile_id,),
            )
            profiles.append(
                {
                    "name": name,
                    "email": email,
                    "settings": self._public_settings(
                        "SELECT key, value FROM profile_settings WHERE profile_id = ?", (profile_id,)
                    ),
                    "favorites": self.list_favorites(profile_id=profile_id),
                    "flags": self.list_flags(profile_id=profile_id),
                    "changes": [dict(zip(_CHANGE_NAMES, row, strict=True)) for row in changes],
                    "scans": [self.get_scan(scan_id) for scan_id in latest_ids],
                }
            )
        return {
            "version": store_module.BACKUP_VERSION,
            "exported_at": time.time(),
            "settings": self._public_settings("SELECT key, value FROM settings"),
            "matches": [
                {"film_key": key, "title": title, "year": year, "tmdb_id": tmdb_id}
                for key, title, year, tmdb_id in self._read(
                    "SELECT film_key, title, year, tmdb_id FROM film_ids WHERE source = 'manual'"
                )
            ],
            "profiles": profiles,
        }

    def find_profile(self, name: str) -> int | None:
        rows = self._read("SELECT id FROM profiles WHERE name = ?", (name,))
        return rows[0][0] if rows else None

    def import_backup(self, backup: dict, target_profile: int = 1) -> dict[str, int]:
        """Restore favorites, flags, changes, scans and match corrections from a backup.

        Version 1 holds one person and goes into target_profile. Version 2 holds several profiles,
        matched by name; a missing one is created. A backup file can come from anywhere: every entry
        is rebuilt with fixed types (watchlist_app.validation) and unusable entries, a broken profile
        included, are skipped and counted. Settings are restored by AppSettings.restore_backup, with
        the same checks as the settings page. Changes, scans and matches are added only once.
        """
        from . import store as store_module  # read at call time, so tests can change the version

        version = backup.get("version") if isinstance(backup, dict) else None
        if version not in (1, store_module.BACKUP_VERSION):
            raise ValueError("This file is not a watchlist backup of a supported version.")
        matches = backup.get("matches") or []  # missing in backups made before match corrections
        entries = [backup] if version == 1 else backup.get("profiles") or []
        if not isinstance(matches, list) or not isinstance(entries, list):
            raise ValueError("The backup file is damaged.")
        now = time.time()
        people: list[tuple[int, list[list]]] = []
        skipped = 0
        # Into a new install: the first person of the backup becomes profile 1, the one the app shows.
        take_over = version != 1 and self._fresh_install()
        for entry in entries:
            parts = _personal_parts(entry)
            if version == 1:
                if parts is None:
                    raise ValueError("The backup file is damaged.")
                people.append((target_profile, parts))
                continue
            profile = validation.clean_profile(entry)
            if profile is None or parts is None:
                skipped += 1
                continue
            profile_id = self.find_profile(profile["name"])
            if profile_id is None and take_over:
                self._write(
                    "UPDATE profiles SET name = ?, email = ? WHERE id = 1",
                    (profile["name"], profile["email"]),
                )
                profile_id = 1
            take_over = take_over and profile_id != 1
            people.append((profile_id if profile_id is not None else self._new_profile(profile, now), parts))

        counts = {"favorites": 0, "changes": 0, "scans": 0, "matches": 0, "skipped": skipped}
        for profile_id, (favorites, flags, changes, scans) in people:
            for name, value in self._import_person(profile_id, favorites, flags, changes, scans, now).items():
                counts[name] += value

        for raw_match in matches:
            match = validation.clean_match(raw_match)
            if match is None:
                counts["skipped"] += 1
                continue
            stored = self.get_id(match["film_key"])
            if stored and (stored["tmdb_id"], stored["source"]) == (match["tmdb_id"], "manual"):
                continue
            self.set_id(
                match["film_key"], match["tmdb_id"], "manual", title=match["title"], year=match["year"]
            )
            counts["matches"] += 1
        if counts["matches"]:
            self.set_setting(MATCHES_CHANGED_SETTING, str(now))
        return counts

    def _new_profile(self, profile: dict, now: float) -> int:
        cursor = self._write(
            "INSERT INTO profiles (name, email, created) VALUES (?, ?, ?)",
            (profile["name"], profile["email"], now),
        )
        return int(cursor.lastrowid or 0)

    def _fresh_install(self) -> bool:
        """Only profile 1, still unnamed ("Me") and without any data of its own."""
        rows = self._read(
            "SELECT (SELECT count(*) FROM profiles) = 1"
            " AND (SELECT name FROM profiles WHERE id = 1) = 'Me'"
            " AND NOT EXISTS (SELECT 1 FROM favorites WHERE profile_id = 1)"
            " AND NOT EXISTS (SELECT 1 FROM flags WHERE profile_id = 1)"
            " AND NOT EXISTS (SELECT 1 FROM scans WHERE profile_id = 1)"
            " AND NOT EXISTS (SELECT 1 FROM changes WHERE profile_id = 1)"
            " AND NOT EXISTS (SELECT 1 FROM profile_settings WHERE profile_id = 1)"
        )
        return bool(rows[0][0])

    def _import_person(
        self, profile_id: int, favorites: list, flags: list, changes: list, scans: list, now: float
    ) -> dict[str, int]:
        skipped = 0
        imported_favorites = 0
        for raw_favorite in favorites:
            favorite = validation.clean_favorite(raw_favorite)
            if favorite is None:
                skipped += 1
                continue
            self.add_favorite(favorite, profile_id=profile_id)
            imported_favorites += 1

        for raw_flag in flags:
            flag = validation.clean_flag(raw_flag, now)
            if flag is None:
                skipped += 1
                continue
            self.set_flag(flag["key"], flag["flag"], flag["until"], profile_id=profile_id)

        known = {
            tuple(row)
            for row in self._read(
                f"SELECT {', '.join(CHANGE_IDENTITY)} FROM changes WHERE profile_id = ?", (profile_id,)
            )
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
            self.add_changes(country, group, created=created, profile_id=profile_id)

        existing_scans = {
            tuple(row)
            for row in self._read("SELECT created, country FROM scans WHERE profile_id = ?", (profile_id,))
        }
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
                profile_id=profile_id,
            )
            imported_scans += 1
        return {
            "favorites": imported_favorites,
            "changes": sum(len(group) for group in new_changes.values()),
            "scans": imported_scans,
            "skipped": skipped,
        }
