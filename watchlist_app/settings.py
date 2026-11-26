"""Settings in one place: stored in the database, with environment values as start values."""

import json

from . import config, costs, providers, validation
from .store import REGIONS_SETTING, Store
from .store_schema import is_profile_setting

# Shorter than a day would change nothing: a scan and its offers are reused for 24 hours.
SCAN_INTERVALS_HOURS = (0, 24, 48, 168)
DEFAULT_WEEKLY_HOURS = 5.0
NOTIFY_KINDS = ("", "ntfy", "gotify", "webhook")
DEFAULT_NOTIFY_EVENTS = {"favorite_gone": True, "deadline": True, "weekly": True, "new_available": False}


class AppSettings:
    """What the user can change on the settings page, plus the fixed values from the environment.

    A value saved in the database wins; `.env` and `platforms.toml` only provide
    the start values. The TMDB key stays in the environment and is never stored.
    """

    def __init__(self, store: Store, defaults: config.Settings | None = None, profile_id: int = 1):
        self._store = store
        self._defaults = defaults or config.load_settings()
        self.profile_id = profile_id

    def for_profile(self, profile_id: int) -> "AppSettings":
        """The same settings, read and written for another profile."""
        return AppSettings(self._store, self._defaults, profile_id)

    def _get(self, key: str) -> str | None:
        """A stored value: the profile's own for a per-person key, else the global one."""
        if is_profile_setting(key):
            return self._store.get_profile_setting(key, profile_id=self.profile_id)
        return self._store.get_setting(key)

    def _set(self, key: str, value: str) -> None:
        if is_profile_setting(key):
            self._store.set_profile_setting(key, value, profile_id=self.profile_id)
        else:
            self._store.set_setting(key, value)

    @property
    def tmdb_api_key(self) -> str | None:
        return self._defaults.tmdb_api_key

    @property
    def downloads_dir(self):
        return self._defaults.downloads_dir

    @property
    def letterboxd_username(self) -> str | None:
        stored = self._get("letterboxd_username")
        if stored is None:  # the name from the environment belongs to the first profile only
            return self._defaults.letterboxd_username if self.profile_id == 1 else None
        return stored or None

    @property
    def country(self) -> str:
        stored = self._get("country")
        return stored if config.valid_country(stored) else self._defaults.country

    @property
    def scan_interval_hours(self) -> int:
        """Hours between automatic scans; 0 switches the schedule off."""
        try:
            return max(0, int(self._get("scan_interval_hours") or "0"))
        except (TypeError, ValueError):
            return 0

    @property
    def weekly_hours(self) -> float:
        """Hours of films the user watches in a week (for "your pace" on the subscriptions page)."""
        try:
            hours = float(self._get("weekly_hours") or DEFAULT_WEEKLY_HOURS)
        except (TypeError, ValueError):
            return DEFAULT_WEEKLY_HOURS
        return hours if 0.5 <= hours <= 80 else DEFAULT_WEEKLY_HOURS

    @property
    def notify_kind(self) -> str:
        kind = self._get("notify_kind") or ""
        return kind if kind in NOTIFY_KINDS else ""

    @property
    def notify_url(self) -> str:
        return self._get("notify_url") or ""

    @property
    def notify_token(self) -> str:
        return self._get("notify_token") or ""

    @property
    def notify_events(self) -> dict[str, bool]:
        try:
            stored = json.loads(self._get("notify_events") or "{}")
        except ValueError:
            stored = {}
        stored = stored if isinstance(stored, dict) else {}
        return {name: bool(stored.get(name, default)) for name, default in DEFAULT_NOTIFY_EVENTS.items()}

    def loaded_providers(self, country: str | None = None) -> list[str]:
        """Display names of the providers loaded from TMDB, for one country or all of them."""
        return sorted(
            {providers.display_name(item["name"]) for item in self._store.provider_catalog(country)}
        )

    def known_providers(self) -> set[str]:
        return providers.known_names(self.loaded_providers())

    def subscriptions(self, country: str | None = None) -> list[str]:
        """The user's own services for a country (display names)."""
        country = country or self.country
        stored = self._get(f"subscriptions:{country}")
        known = self.known_providers()
        # platforms.toml is only a start value; a country without a section starts empty.
        names = [name for name in providers.load_platforms_config(country) if name in known]
        if stored is not None:
            try:
                names = [name for name in json.loads(stored) if name in known]
            except (ValueError, TypeError):
                pass
        return costs.not_ended(names, self.costs(country))

    def costs(self, country: str | None = None) -> dict[str, dict]:
        """Monthly price and reminder date per own service: {name: {"price", "remind_on"}}."""
        stored = self._get(f"subscription_costs:{country or self.country}")
        try:
            return json.loads(stored) if stored else {}
        except ValueError:
            return {}

    def country_choices(self) -> list[str]:
        """Countries the picker offers: TMDB's list (a scan loads it), else every flag."""
        try:
            stored = json.loads(self._get(REGIONS_SETTING) or "{}")
        except ValueError:
            stored = {}
        codes = stored.get("codes") if isinstance(stored, dict) else None
        codes = codes if isinstance(codes, list) and codes else config.flag_countries()
        return sorted(code for code in {*codes, self.country} if config.valid_country(code))

    def countries_in_use(self) -> list[str]:
        """The app's country plus every country with saved services or prices, sorted."""
        codes = {self.country}
        for prefix in ("subscriptions:", "subscription_costs:"):
            codes.update(
                key[len(prefix) :]
                for key in self._store.profile_setting_keys(prefix, profile_id=self.profile_id)
            )
        return sorted(code for code in codes if config.valid_country(code))

    def targets(self, country: str | None = None) -> dict[str, str]:
        """Subscriptions as {display name: TMDB name}, as the CLI report needs them."""
        return providers.tmdb_names(self.subscriptions(country))

    def as_dict(self) -> dict:
        return {
            "letterboxd_username": self.letterboxd_username or "",
            "country": self.country,
            "scan_interval_hours": self.scan_interval_hours,
            "weekly_hours": self.weekly_hours,
            "notify_kind": self.notify_kind,
            "notify_url": self.notify_url,
            "notify_token_set": bool(self.notify_token),
            "notify_events": self.notify_events,
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
                if key in {
                    "letterboxd_username",
                    "country",
                    "scan_interval_hours",
                    "weekly_hours",
                    "notify_kind",
                    "notify_url",
                    "notify_events",
                }:
                    self.update({key: value})
                elif isinstance(key, str) and key.startswith("subscriptions:"):
                    country = key.split(":", 1)[1]
                    names = json.loads(value) if isinstance(value, str) else value
                    if not config.valid_country(country) or not isinstance(names, list):
                        raise ValueError("Invalid subscriptions.")
                    clean = [name[:200] for name in names[:500] if isinstance(name, str) and name.strip()]
                    self._set(key, json.dumps(clean))
                elif isinstance(key, str) and key.startswith("subscription_costs:"):
                    raw = json.loads(value) if isinstance(value, str) else value
                    if not config.valid_country(key.split(":", 1)[1]) or not isinstance(raw, dict):
                        raise ValueError("Invalid costs.")
                    names = {name for name in raw if isinstance(name, str) and len(name) <= 200}
                    self._set(key, json.dumps(costs.clean_costs(raw, names)))
                else:
                    continue
                restored += 1
            except (ValueError, TypeError):
                skipped += 1
        return restored, skipped

    def restore_backup(self, backup: dict, target_profile: int = 1) -> tuple[int, int]:
        """The settings of a backup that Store.import_backup has read. Returns (restored, skipped).

        Version 1 holds one person: all of it goes into target_profile. Version 2 holds the global
        settings plus each profile's own, matched by name (import_backup has created missing ones).
        Each part only restores the keys that belong there.
        """
        if backup.get("version") == 1:
            return AppSettings(self._store, self._defaults, target_profile).restore(backup.get("settings"))
        parts: list[tuple[int, object, bool]] = [(self.profile_id, backup.get("settings"), False)]
        for entry in backup.get("profiles") or []:
            profile = validation.clean_profile(entry)
            profile_id = self._store.find_profile(profile["name"]) if profile else None
            if profile_id is not None:
                parts.append((profile_id, entry.get("settings"), True))
        restored = skipped = 0
        for profile_id, stored, personal in parts:
            if not isinstance(stored, dict):
                continue
            mine = {key: value for key, value in stored.items() if is_profile_setting(str(key)) == personal}
            counts = AppSettings(self._store, self._defaults, profile_id).restore(mine)
            restored, skipped = restored + counts[0], skipped + counts[1]
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
            if not config.valid_country(changes["country"]):
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
        if "notify_kind" in changes:
            if changes["notify_kind"] not in NOTIFY_KINDS:
                raise ValueError("The notification target must be ntfy, Gotify or a webhook.")
            validated["notify_kind"] = changes["notify_kind"]
        if "notify_url" in changes:
            address = str(changes["notify_url"] or "").strip()
            if address and not (
                address.startswith(("https://", "http://")) and len(address) <= 300 and " " not in address
            ):
                raise ValueError("The notification address must be a web address (http or https).")
            validated["notify_url"] = address
        if "notify_token" in changes:
            token = str(changes["notify_token"] or "").strip()
            if len(token) > 200:
                raise ValueError("The notification token is too long.")
            # An empty field keeps the saved token; "-" removes it.
            if token:
                validated["notify_token"] = "" if token == "-" else token
        if "notify_events" in changes:
            events = changes["notify_events"]
            if not isinstance(events, dict) or any(name not in DEFAULT_NOTIFY_EVENTS for name in events):
                raise ValueError("Unknown notification type.")
            validated["notify_events"] = json.dumps(
                {name: bool(events.get(name, False)) for name in DEFAULT_NOTIFY_EVENTS}
            )
        if "weekly_hours" in changes:
            try:
                hours = float(changes["weekly_hours"])
            except (TypeError, ValueError):
                raise ValueError("The film time per week must be a number of hours.") from None
            if not 0.5 <= hours <= 80:
                raise ValueError("The film time per week must be between 0.5 and 80 hours.")
            validated["weekly_hours"] = str(round(hours, 1))
        # The subscriptions page edits any country without switching the app's country.
        country = changes.get("subscriptions_country") or validated.get("country", self.country)
        if not config.valid_country(country):
            raise ValueError("Unsupported country.")
        if "subscriptions" in changes:
            names = changes["subscriptions"]
            known = self.known_providers()
            if not isinstance(names, list) or any(name not in known for name in names):
                raise ValueError("Unknown provider in the subscriptions.")
            validated[f"subscriptions:{country}"] = json.dumps(names)
        if "costs" in changes:
            own = changes.get("subscriptions", self.subscriptions(country))
            validated[f"subscription_costs:{country}"] = json.dumps(
                costs.clean_costs(changes["costs"], set(own))
            )
        for key, value in validated.items():
            self._set(key, value)
