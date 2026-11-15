"""Subscription costs: price per film, what cancelling loses, what to book next, rent-only films."""

import datetime
from typing import Any

from .providers import MOSTLY_FREE

WATCH_KINDS = frozenset({"free", "ads", "flatrate"})  # watchable without paying per film
FREE_KINDS = frozenset({"free", "ads"})


def _watchable(film: dict, name: str) -> bool:
    return bool(WATCH_KINDS & set(film.get("providers", {}).get(name, [])))


def _free_anywhere(film: dict) -> bool:
    return any(FREE_KINDS & set(kinds) for kinds in film.get("providers", {}).values())


def _label(film: dict) -> dict:
    return {"key": film.get("key"), "title": film.get("title"), "year": film.get("year")}


def overview(films: list[dict], subscriptions: list[str], costs: dict[str, dict]) -> dict:
    """What the costs page shows for the films of one scan.

    A film is "only here" when no other own service has it and no provider shows it
    for free. `costs` maps a service to {"price": monthly price, "remind_on": date}.
    """
    services: list[dict[str, Any]] = []
    for name in subscriptions:
        on = [film for film in films if _watchable(film, name)]
        only = [
            film
            for film in on
            if not _free_anywhere(film)
            and not any(_watchable(film, other) for other in subscriptions if other != name)
        ]
        price = (costs.get(name) or {}).get("price")
        services.append(
            {
                "name": name,
                "price": price,
                "remind_on": (costs.get(name) or {}).get("remind_on"),
                "films": len(on),
                "per_film": round(price / len(on), 2) if price and on else None,
                "only_here": sorted((_label(film) for film in only), key=lambda item: item["title"] or ""),
            }
        )

    uncovered = [
        film
        for film in films
        if not _free_anywhere(film) and not any(_watchable(film, name) for name in subscriptions)
    ]
    gains: dict[str, int] = {}
    for film in uncovered:
        for name, kinds in film.get("providers", {}).items():
            if "flatrate" in kinds:
                gains[name] = gains.get(name, 0) + 1
    book = sorted(gains.items(), key=lambda item: (-item[1], item[0]))[:5]

    # Cancel what loses nothing first, then the service with the fewest films of its own.
    # Free services (and ones saved with price 0) cost nothing to keep.
    paid = [item for item in services if item["name"] not in MOSTLY_FREE and item["price"] != 0]
    ranked = sorted(paid, key=lambda item: (len(item["only_here"]), -(item["price"] or 0)))
    loses_nothing = [item["name"] for item in ranked if not item["only_here"]]
    rent_only = [
        _label(film)
        for film in films
        if not any(WATCH_KINDS & set(kinds) for kinds in film.get("providers", {}).values())
        and any("rent" in kinds for kinds in film.get("providers", {}).values())
    ]
    return {
        "services": services,
        "monthly_total": round(sum(item["price"] or 0 for item in services), 2),
        "book": [{"name": name, "films": count} for name, count in book],
        "cancel": loses_nothing or [item["name"] for item in ranked[:1]],
        "cancel_loses_nothing": bool(loses_nothing),
        "rent_only": sorted(rent_only, key=lambda item: item["title"] or ""),
    }


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
        if price is not None or remind_on is not None:
            clean[name] = {"price": price, "remind_on": remind_on}
    return clean


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
