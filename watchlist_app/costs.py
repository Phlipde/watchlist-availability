"""Subscription costs: price per film, what cancelling loses, what to book next, rent-only films."""

import datetime
import re
from typing import Any

from .providers import mostly_free_from_scan

WATCH_KINDS = frozenset({"free", "ads", "flatrate"})  # watchable without paying per film
FREE_KINDS = frozenset({"free", "ads"})


def _watchable(film: dict, name: str) -> bool:
    return bool(WATCH_KINDS & set(film.get("providers", {}).get(name, [])))


def _free_anywhere(film: dict) -> bool:
    return any(FREE_KINDS & set(kinds) for kinds in film.get("providers", {}).values())


def only_on_my_services(film: dict, subscriptions: list[str]) -> bool:
    """Whether a film would be lost when cancelling any one own service."""
    return not _free_anywhere(film) and sum(_watchable(film, name) for name in subscriptions) == 1


def mark_only_on_my_services(films: list[dict], subscriptions: list[str]) -> list[dict]:
    """Copies of the films with `only_on_my_services`, for the page filter of the same name."""
    return [{**film, "only_on_my_services": only_on_my_services(film, subscriptions)} for film in films]


def catalog_name(name: str) -> str:
    """The main service of an Amazon Channel: "HBO Max Amazon Channel" shows the same films as "HBO Max"."""
    return re.sub(r"\s+Amazon channels?$", "", name, flags=re.IGNORECASE)


def _label(film: dict) -> dict:
    return {
        "key": film.get("key"),
        "title": film.get("title"),
        "year": film.get("year"),
        "poster_path": film.get("poster_path"),
        "letterboxd_rating": film.get("letterboxd_rating"),
    }


GOOD_RATING = 3.8  # a Letterboxd average from which a film counts as well rated


def film_weight(film: dict, favorites: frozenset[str] = frozenset()) -> int:
    """What losing a film costs: 3 for a favorite, 2 for a well rated one, otherwise 1."""
    if (film.get("key") or film.get("title")) in favorites:
        return 3
    return 2 if (film.get("letterboxd_rating") or 0) >= GOOD_RATING else 1


def overview(
    films: list[dict],
    subscriptions: list[str],
    costs: dict[str, dict],
    unavailable: int = 0,
    favorites: frozenset[str] = frozenset(),
) -> dict:
    """What the costs page shows for the films of one scan.

    A film is "only here" when no other own service has it and no provider shows it
    for free. `costs` maps a service to {"price": monthly price, "remind_on": date}.
    """
    free = mostly_free_from_scan(films, [])  # the same rule as the "Free" label in the filter bar
    services: list[dict[str, Any]] = []
    free_block: list[dict[str, Any]] = []
    free_films: set[Any] = set()
    for name in subscriptions:
        on = [film for film in films if _watchable(film, name)]
        only = [film for film in on if only_on_my_services(film, subscriptions)]
        if name in free:
            # Free services are one compact block, not a table row each.
            free_block.append({"name": name, "films": len(on)})
            free_films.update(film.get("key") or film.get("title") for film in on)
            continue
        entry = costs.get(name) or {}
        price = entry.get("price")
        shared = entry.get("shared") or 1
        own_share = price / shared if price else price  # a shared account splits the price
        value = sum(film_weight(film, favorites) for film in only)
        elsewhere = [film for film in on if film not in only]
        services.append(
            {
                "name": name,
                "price": price,
                "own_share": round(own_share, 2) if own_share else own_share,
                "shared": shared,
                "notice_days": entry.get("notice_days"),
                "trial_on": entry.get("trial_on"),
                "note": entry.get("note") or "",
                "cancel_url": entry.get("cancel_url") or "",
                "remind_on": entry.get("remind_on"),
                "films": len(on),
                "value": value,
                "value_per_euro": round(value / own_share, 1) if own_share and value else None,
                "favorites": sum(1 for film in only if (film.get("key") or film.get("title")) in favorites),
                "elsewhere": sorted(
                    (_label(film) for film in elsewhere), key=lambda item: item["title"] or ""
                ),
                "per_film": round(own_share / len(only), 2) if own_share and only else None,
                "hours": round(sum(film.get("runtime") or 0 for film in only) / 60, 1),
                "only_here": sorted((_label(film) for film in only), key=lambda item: item["title"] or ""),
            }
        )
    # The service whose loss costs the most comes first: weighted films only there.
    services.sort(key=lambda item: (-item["value"], -item["films"], item["name"].casefold()))

    uncovered = [
        film
        for film in films
        if not _free_anywhere(film) and not any(_watchable(film, name) for name in subscriptions)
    ]
    gains: dict[str, list[int]] = {}  # per service: [films, minutes]
    for film in uncovered:
        # "X" and "X Amazon Channel" are one catalogue: count the film once for it.
        for name in {
            catalog_name(name) for name, kinds in film.get("providers", {}).items() if "flatrate" in kinds
        }:
            gain = gains.setdefault(name, [0, 0])
            gain[0] += 1
            gain[1] += film.get("runtime") or 0
    book = sorted(gains.items(), key=lambda item: (-item[1][0], item[0]))[:5]

    # Cancel what loses nothing first, then the service with the fewest films of its own.
    # Free services (and ones saved with price 0) cost nothing to keep.
    paid = [item for item in services if item["price"] != 0]
    # Least value for the money first (value per euro), without prices the least weighted films first.
    ranked = sorted(
        paid,
        key=lambda item: (
            item["value"] > 0,
            item["value_per_euro"] if item["value_per_euro"] is not None else float("inf"),
            item["value"],
            -(item["price"] or 0),
        ),
    )
    loses_nothing = [item["name"] for item in ranked if not item["only_here"]]
    rent_only = [
        _label(film)
        for film in films
        if not any(WATCH_KINDS & set(kinds) for kinds in film.get("providers", {}).values())
        and any("rent" in kinds for kinds in film.get("providers", {}).values())
    ]
    cancel = loses_nothing or [item["name"] for item in ranked[:1]]
    coverage = _coverage(films, subscriptions, free, unavailable)
    recommendations = _recommendations(services, cancel, bool(loses_nothing), book)
    return {
        "coverage": coverage,
        "recommendations": recommendations,
        "services": services,
        "monthly_total": round(sum(item["own_share"] or 0 for item in services), 2),
        "yearly_total": round(sum(item["own_share"] or 0 for item in services) * 12, 2),
        "free_block": sorted(
            (item for item in free_block if item["films"]), key=lambda item: (-item["films"], item["name"])
        ),
        "free_empty": sum(1 for item in free_block if not item["films"]),
        "free_films": len(free_films),
        "book": [{"name": name, "films": gain[0], "hours": round(gain[1] / 60)} for name, gain in book],
        "cancel": cancel,
        "cancel_loses_nothing": bool(loses_nothing),
        "rent_only": sorted(
            rent_only, key=lambda item: (-(item["letterboxd_rating"] or 0), item["title"] or "")
        ),
    }


def _coverage(films: list[dict], subscriptions: list[str], free: frozenset[str], unavailable: int) -> dict:
    """How much of the watchlist the own services cover: free, subscription, rent only, the rest."""
    free_own = [name for name in subscriptions if name in free]
    paid_own = [name for name in subscriptions if name not in free]
    counts = {"free": 0, "subscription": 0, "rent": 0, "other": unavailable}
    for film in films:
        if any(_watchable(film, name) for name in free_own):
            counts["free"] += 1
        elif any(_watchable(film, name) for name in paid_own):
            counts["subscription"] += 1
        elif not any(WATCH_KINDS & set(kinds) for kinds in film.get("providers", {}).values()):
            counts[
                "rent" if any("rent" in kinds for kinds in film.get("providers", {}).values()) else "other"
            ] += 1
        else:
            counts["other"] += 1  # on services the user does not have
    total = sum(counts.values())
    covered = counts["free"] + counts["subscription"]
    return {
        "total": total,
        "covered": covered,
        "percent": round(100 * covered / total) if total else 0,
        "segments": [
            {"id": key, "films": counts[key], "percent": round(100 * counts[key] / total, 1) if total else 0}
            for key in ("subscription", "free", "rent", "other")
        ],
    }


def _recommendations(services: list[dict], cancel: list[str], loses_nothing: bool, book: list) -> list[dict]:
    """At most two cards, each with the numbers behind it: what to cancel and what to book for a month.

    Without a price a card says so (it is based on the film count only).
    """
    cards: list[dict[str, Any]] = []
    by_name = {item["name"]: item for item in services}
    if cancel and cancel[0] in by_name:
        item = by_name[cancel[0]]
        cards.append(
            {
                "type": "cancel",
                "name": item["name"],
                "films": len(item["only_here"]),
                "hours": item["hours"],
                "price": item["price"],
                "per_film": item["per_film"],
                "loses_nothing": loses_nothing,
                "based_on": "price" if item["price"] else "count",
            }
        )
    if book:
        name, gain = book[0]
        cards.append(
            {
                "type": "subscribe",
                "name": name,
                "films": gain[0],
                "hours": round(gain[1] / 60),
                "based_on": "count",
            }
        )
    return cards


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


def _clean_management(name: str, entry: dict) -> dict:
    """The optional fields of a service: shared with n people, notice days, trial date, note, link."""
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
