"""Settings in one place: stored in the database, with environment values as start values."""

import json

from . import config, providers
from .store import Store

# Shorter than a day would change nothing: a scan and its offers are reused for 24 hours.
SCAN_INTERVALS_HOURS = (0, 24, 48, 168)


class AppSettings:
    """What the user can change on the settings page, plus the fixed values from the environment.

    A value saved in the database wins; `.env` and `platforms.toml` only provide
    the start values. The TMDB key stays in the environment and is never stored.
    """

    def __init__(self, store: Store, defaults: config.Settings | None = None):
        self._store = store
        self._defaults = defaults or config.load_settings()

    @property
    def tmdb_api_key(self) -> str | None:
        return self._defaults.tmdb_api_key

    @property
    def downloads_dir(self):
        return self._defaults.downloads_dir

    @property
    def letterboxd_username(self) -> str | None:
        stored = self._store.get_setting("letterboxd_username")
        if stored is None:
            return self._defaults.letterboxd_username
        return stored or None

    @property
    def country(self) -> str:
        stored = self._store.get_setting("country")
        return stored if stored in config.COUNTRIES else self._defaults.country

    @property
    def scan_interval_hours(self) -> int:
        """Hours between automatic scans; 0 switches the schedule off."""
        try:
            return max(0, int(self._store.get_setting("scan_interval_hours") or "0"))
        except (TypeError, ValueError):
            return 0

    def loaded_providers(self) -> list[str]:
        """Display names of the providers loaded from TMDB, for all countries."""
        return sorted({providers.display_name(item["name"]) for item in self._store.provider_catalog()})

    def known_providers(self) -> set[str]:
        return providers.known_names(self.loaded_providers())

    def subscriptions(self, country: str | None = None) -> list[str]:
        """The user's own services for a country (display names)."""
        country = country or self.country
        stored = self._store.get_setting(f"subscriptions:{country}")
        if stored is not None:
            try:
                known = self.known_providers()
                return [name for name in json.loads(stored) if name in known]
            except (ValueError, TypeError):
                pass
        return list(providers.load_platforms_config(country))

    def targets(self, country: str | None = None) -> dict[str, str]:
        """Subscriptions as {display name: TMDB name}, as the CLI report needs them."""
        return providers.tmdb_names(self.subscriptions(country))

    def as_dict(self) -> dict:
        return {
            "letterboxd_username": self.letterboxd_username or "",
            "country": self.country,
            "scan_interval_hours": self.scan_interval_hours,
            "subscriptions": self.subscriptions(),
            "tmdb_api_key_set": bool(self.tmdb_api_key),
        }

    def restore(self, stored: object) -> tuple[int, int]:
        """Settings from a backup, checked like the settings page. Returns (restored, skipped).

        Unknown keys are ignored. Subscriptions may name providers this instance has
        not loaded from TMDB yet; they are kept and shown once the provider is known.
        """
        if not isinstance(stored, dict):
            return 0, 0
        restored = skipped = 0
        for key, value in stored.items():
            try:
                if key in {"letterboxd_username", "country", "scan_interval_hours"}:
                    self.update({key: value})
                elif isinstance(key, str) and key.startswith("subscriptions:"):
                    country = key.split(":", 1)[1]
                    names = json.loads(value) if isinstance(value, str) else value
                    if country not in config.COUNTRIES or not isinstance(names, list):
                        raise ValueError("Invalid subscriptions.")
                    clean = [name[:200] for name in names[:500] if isinstance(name, str) and name.strip()]
                    self._store.set_setting(key, json.dumps(clean))
                else:
                    continue
                restored += 1
            except (ValueError, TypeError):
                skipped += 1
        return restored, skipped

    def update(self, changes: dict) -> None:
        """Validate and save changed settings. Raises ValueError with a message for the user."""
        validated: dict[str, str] = {}
        if "letterboxd_username" in changes:
            username = str(changes["letterboxd_username"] or "").strip()
            if username and not all(character.isalnum() or character in "_-" for character in username):
                raise ValueError("The Letterboxd username may only contain letters, digits, _ and -.")
            validated["letterboxd_username"] = username
        if "country" in changes:
            if changes["country"] not in config.COUNTRIES:
                raise ValueError("Unsupported country.")
            validated["country"] = changes["country"]
        if "scan_interval_hours" in changes:
            try:
                interval = int(changes["scan_interval_hours"])
            except (TypeError, ValueError):
                raise ValueError("The scan interval must be a number of hours.") from None
            if interval not in SCAN_INTERVALS_HOURS:
                raise ValueError("Unsupported scan interval.")
            validated["scan_interval_hours"] = str(interval)
        if "subscriptions" in changes:
            names = changes["subscriptions"]
            known = self.known_providers()
            if not isinstance(names, list) or any(name not in known for name in names):
                raise ValueError("Unknown provider in the subscriptions.")
            country = validated.get("country", self.country)
            validated[f"subscriptions:{country}"] = json.dumps(names)
        for key, value in validated.items():
            self._store.set_setting(key, value)
