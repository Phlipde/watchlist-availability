"""Store methods for the backup file: export and import."""

import time

from . import validation
from .store_films import FilmStore
from .store_marks import MarkStore
from .store_scans import ScanStore
from .store_schema import CHANGE_IDENTITY, INTERNAL_SETTINGS, MATCHES_CHANGED_SETTING


class BackupStore(FilmStore, ScanStore, MarkStore):
    # ----- backup -----

    def export_backup(self) -> dict:
        """Everything worth keeping: settings, favorites, change history and the last scan per country.

        Film data and offers are left out; the next scan fetches them again.
        """
        from . import store as store_module  # read at call time, so tests can change the version

        latest_ids = [row[0] for row in self._read("SELECT max(id) FROM scans GROUP BY country")]
        changes = self._read(
            "SELECT created, country, film_key, title, year, provider, change FROM changes ORDER BY id"
        )
        change_names = ("created", "country", "film_key", "title", "year", "provider", "change")
        return {
            "version": store_module.BACKUP_VERSION,
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
        from . import store as store_module  # read at call time, so tests can change the version

        if not isinstance(backup, dict) or backup.get("version") != store_module.BACKUP_VERSION:
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
