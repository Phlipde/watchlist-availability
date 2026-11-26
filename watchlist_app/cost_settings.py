"""Cost settings: cleaning the saved prices and dates, reminders, deadlines, services not yet ended."""

import datetime
from typing import Any


def upcoming_deadlines(
    costs: dict[str, dict], today: datetime.date | None = None, days: int = 7
) -> list[dict]:
    """Renewal or cancellation dates of one country at most `days` away (today counts), soonest first."""
    return [
        {"name": item["name"], "date": item["date"], "days": item["days"]}
        for item in reminders({"": costs}, today)
        if 0 <= item["days"] <= days
    ]


def clean_costs(raw: object, allowed: set[str]) -> dict[str, dict]:
    """Prices and reminder dates as the settings store them. Raises ValueError for the user."""
    if not isinstance(raw, dict):
        raise ValueError("Send the costs as an object per service.")
    clean: dict[str, dict] = {}
    for name, entry in raw.items():
        if name not in allowed or not isinstance(entry, dict):
            raise ValueError("Unknown service in the costs.")
        price = entry.get("price")
        if price in (None, ""):
            price = None
        else:
            try:
                price = round(float(price), 2)
            except (TypeError, ValueError):
                raise ValueError(f"The price for {name} must be a number.") from None
            if not 0 <= price <= 1000:
                raise ValueError(f"The price for {name} must be between 0 and 1000.")
        remind_on = entry.get("remind_on") or None
        if remind_on is not None:
            try:
                remind_on = datetime.date.fromisoformat(str(remind_on)).isoformat()
            except ValueError:
                raise ValueError(f"The reminder date for {name} must be a date.") from None
        extra = _clean_management(name, entry)
        if price is not None or remind_on is not None or extra:
            clean[name] = {"price": price, "remind_on": remind_on, **extra}
    return clean


def not_ended(names: list[str], entries: dict[str, dict], today: datetime.date | None = None) -> list[str]:
    """The services that are still yours: one cancelled "to the end date" stays until that day is over."""
    today = today or datetime.date.today()
    last_day = {name: (entries.get(name) or {}).get("ends_on") or "9999-12-31" for name in names}
    return [name for name in names if last_day[name] >= today.isoformat()]


def _clean_management(name: str, entry: dict) -> dict:
    """The optional fields of a service: shared, notice days, trial date, end date, note, link."""
    extra: dict[str, Any] = {}
    shared = entry.get("shared")
    if shared not in (None, "", 1, "1"):
        try:
            shared = int(shared)
        except (TypeError, ValueError):
            raise ValueError(f"The number of people sharing {name} must be a whole number.") from None
        if not 1 <= shared <= 20:
            raise ValueError(f"The number of people sharing {name} must be between 1 and 20.")
        extra["shared"] = shared
    notice = entry.get("notice_days")
    if notice not in (None, ""):
        try:
            notice = int(notice)
        except (TypeError, ValueError):
            raise ValueError(f"The notice period for {name} must be a number of days.") from None
        if not 0 <= notice <= 365:
            raise ValueError(f"The notice period for {name} must be between 0 and 365 days.")
        extra["notice_days"] = notice
    trial = entry.get("trial_on")
    if trial not in (None, ""):
        try:
            extra["trial_on"] = datetime.date.fromisoformat(str(trial)).isoformat()
        except ValueError:
            raise ValueError(f"The trial date for {name} must be a date.") from None
    ends = entry.get("ends_on")
    if ends not in (None, ""):
        try:
            extra["ends_on"] = datetime.date.fromisoformat(str(ends)).isoformat()
        except ValueError:
            raise ValueError(f"The end date for {name} must be a date.") from None
    note = str(entry.get("note") or "").strip()
    if note:
        extra["note"] = note[:300]
    url = str(entry.get("cancel_url") or "").strip()
    if url:
        if not (url.startswith(("https://", "http://")) and len(url) <= 300 and " " not in url):
            raise ValueError(f"The cancellation link for {name} must be a web address.")
        extra["cancel_url"] = url
    return extra


def reminders(costs_by_country: dict[str, dict[str, dict]], today: datetime.date | None = None) -> list[dict]:
    """Reminder dates of all countries, soonest first, with the days left (negative when past)."""
    today = today or datetime.date.today()
    found = []
    for country, costs in costs_by_country.items():
        for name, entry in costs.items():
            if entry.get("remind_on"):
                date = datetime.date.fromisoformat(entry["remind_on"])
                found.append(
                    {
                        "country": country,
                        "name": name,
                        "date": entry["remind_on"],
                        "days": (date - today).days,
                    }
                )
    return sorted(found, key=lambda item: item["date"])
