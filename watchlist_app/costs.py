"""Subscription costs: price per film, what cancelling loses, what to book next, rent-only films."""

import re
from typing import Any

from .base import service_group
from .cost_settings import (  # re-exported: callers use them as costs.<name>
    clean_costs,
    not_ended,
    reminders,
    upcoming_deadlines,
)
from .providers import mostly_free_from_scan

__all__ = ["clean_costs", "not_ended", "reminders", "upcoming_deadlines"]

WATCH_KINDS = frozenset({"free", "ads", "flatrate"})  # watchable without paying per film
FREE_KINDS = frozenset({"free", "ads"})


def _kinds_by_group(film: dict) -> dict[str, set[str]]:
    """Offer kinds of a film per service group (plans and Amazon Channels of a provider merged)."""
    groups: dict[str, set[str]] = {}
    for name, kinds in film.get("providers", {}).items():
        groups.setdefault(service_group(name), set()).update(kinds)
    return groups


def _watchable(film: dict, name: str) -> bool:
    return bool(WATCH_KINDS & _kinds_by_group(film).get(service_group(name), set()))


def _free_anywhere(film: dict) -> bool:
    return any(FREE_KINDS & set(kinds) for kinds in film.get("providers", {}).values())


def only_on_my_services(film: dict, subscriptions: list[str]) -> bool:
    """Only here: one own service (group) has the film and no other service shows it for free.

    The same rule as "Only here" on the stats page (`lostOnCancel`, stats-compute.js): what cancelling loses.
    """
    groups = _kinds_by_group(film)
    own = {service_group(name) for name in subscriptions}
    mine = {group for group in own if WATCH_KINDS & groups.get(group, set())}
    if len(mine) != 1:
        return False
    return not any(FREE_KINDS & kinds for group, kinds in groups.items() if group not in mine)


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
CANCEL_FROM = 0.50  # € a month per film you would lose: from here on cancelling is worth a tip
WEEKS_PER_MONTH = 4.345


def film_weight(film: dict, favorites: frozenset[str] = frozenset()) -> int:
    """What losing a film costs: 3 for a favorite, 2 for a well rated one, otherwise 1."""
    if (film.get("key") or film.get("title")) in favorites:
        return 3
    return 2 if (film.get("letterboxd_rating") or 0) >= GOOD_RATING else 1


def service_counts(films: list[dict], subscriptions: list[str]) -> dict[str, tuple[int, int]]:
    """For each own paid service: (watchable films, films only there). Free services are left out."""
    free = mostly_free_from_scan(films, [])
    counts = {}
    for name in subscriptions:
        if name in free:
            continue
        on = [film for film in films if _watchable(film, name)]
        counts[name] = (len(on), sum(1 for film in on if only_on_my_services(film, subscriptions)))
    return counts


def overview(
    films: list[dict],
    subscriptions: list[str],
    costs: dict[str, dict],
    unavailable: int = 0,
    favorites: frozenset[str] = frozenset(),
    weekly_hours: float | None = None,
    cancel_from: float = CANCEL_FROM,
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
        # Free services are one compact block, not a table row each. A service with no film in the scan and no
        # saved price joins it too: with no offers it cannot be told from a free one (ZDF without films).
        if name in free or (not on and not (costs.get(name) or {}).get("price")):
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
                "ends_on": entry.get("ends_on"),
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
    gains: dict[str, list[int]] = {}  # per service: [films, minutes, favorites]
    for film in uncovered:
        # "X" and "X Amazon Channel" are one catalogue: count the film once for it.
        for name in {
            catalog_name(name) for name, kinds in film.get("providers", {}).items() if "flatrate" in kinds
        }:
            gain = gains.setdefault(name, [0, 0, 0])
            gain[0] += 1
            gain[1] += film.get("runtime") or 0
            gain[2] += 1 if (film.get("key") or film.get("title")) in favorites else 0
    book = sorted(gains.items(), key=lambda item: (-item[1][0], item[0]))[:5]

    cancel = cancel_ranking(services, weekly_hours, cancel_from)
    loses_nothing = [
        name for name in cancel if not next(s for s in services if s["name"] == name)["only_here"]
    ]
    rent_only = [
        _label(film)
        for film in films
        if not any(WATCH_KINDS & set(kinds) for kinds in film.get("providers", {}).values())
        and any("rent" in kinds for kinds in film.get("providers", {}).values())
    ]
    coverage = _coverage(films, subscriptions, free, unavailable)
    recommendations = _recommendations(services, cancel, book, weekly_hours, cancel_from)
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
        "book": [
            {"name": name, "films": gain[0], "hours": round(gain[1] / 60), "favorites": gain[2]}
            for name, gain in book
        ],
        "plan": plan_data(films, subscriptions, favorites, free, services),
        "cancel": cancel,
        "cancel_loses_nothing": bool(loses_nothing),
        "rent_only": sorted(
            rent_only, key=lambda item: (-(item["letterboxd_rating"] or 0), item["title"] or "")
        ),
    }


def other_countries(
    offers: dict[str, dict[int, dict[str, list[str]]]], subscriptions: list[str], current: str, total: int
) -> list[dict]:
    """Where the same services show more of the watchlist: [{country, films, gain}] for countries that have
    stored offers for at least half of the films, best first. `offers`: {country: {id: {provider: kinds}}}.
    """
    own = set(subscriptions)

    def watchable(by_film: dict[int, dict[str, list[str]]]) -> int:
        return sum(
            1
            for providers in by_film.values()
            if any(name in own and WATCH_KINDS & set(kinds) for name, kinds in providers.items())
        )

    here = watchable(offers.get(current, {}))
    found = []
    for country, by_film in offers.items():
        if country == current or total == 0 or len(by_film) * 2 < total:
            continue
        films = watchable(by_film)
        if films > here:
            found.append({"country": country, "films": films, "gain": films - here})
    return sorted(found, key=lambda item: (-item["gain"], item["country"]))


def abroad_map(
    offers: dict[str, dict[int, dict[str, list[str]]]], own: set[str], region: str
) -> dict[int, dict[str, dict[str, str]]]:
    """Which films your services have abroad but not at home: {tmdb_id: {service: {country: kind}}}.

    `offers` is {country: {tmdb_id: {provider: kinds}}} (display names). Only free, with-ads and subscription
    offers count, and a service that carries the film in `region` itself is left out (that is not abroad).
    "X Amazon Channel" counts as "X".
    """

    def watch_kind(kinds: list[str]) -> str | None:
        return next((kind for kind in ("free", "ads", "flatrate") if kind in kinds), None)

    mine = own | {catalog_name(name) for name in own}
    at_home = {
        tmdb_id: {catalog_name(name) for name, kinds in providers.items() if watch_kind(kinds)}
        for tmdb_id, providers in offers.get(region, {}).items()
    }
    found: dict[int, dict[str, dict[str, str]]] = {}
    for country, films in offers.items():
        if country == region:
            continue
        for tmdb_id, providers in films.items():
            for name, kinds in providers.items():
                service = catalog_name(name)
                kind = watch_kind(kinds)
                if (
                    not kind
                    or (name not in mine and service not in mine)
                    or service in at_home.get(tmdb_id, set())
                ):
                    continue
                found.setdefault(tmdb_id, {}).setdefault(service, {})[country] = kind
    return found


def plan_data(
    films: list[dict],
    subscriptions: list[str],
    favorites: frozenset[str],
    free: frozenset[str],
    services: list[dict],
    candidates: int = 12,
) -> dict:
    """What the planner on the page needs: film weights, the films free for you, and per service its films.

    Services: your paid ones plus the `candidates` that would add the most films none of yours has.
    """

    def key_of(film: dict) -> Any:
        return film.get("key") or film.get("title")

    weights = {key_of(film): film_weight(film, favorites) for film in films}
    free_own = [name for name in subscriptions if name in free]
    base = [key_of(film) for film in films if any(_watchable(film, name) for name in free_own)]
    owned = [item["name"] for item in services]
    candidate_names: dict[str, int] = {}
    for film in films:
        if any(_watchable(film, name) for name in subscriptions):
            continue
        for name in {
            catalog_name(name) for name, kinds in film.get("providers", {}).items() if "flatrate" in kinds
        }:
            candidate_names[name] = candidate_names.get(name, 0) + 1
    top = sorted(candidate_names, key=lambda name: (-candidate_names[name], name))[:candidates]
    by_service: dict[str, list[Any]] = {}
    for name in [*owned, *top]:
        by_service[name] = [
            key_of(film)
            for film in films
            if any(_watchable(film, other) for other in films_services(film, name))
        ]
    return {
        "weights": weights,
        "base": base,
        "services": by_service,
        "owned": owned,
        "prices": {item["name"]: item["own_share"] for item in services if item["own_share"]},
    }


def films_services(film: dict, name: str) -> list[str]:
    """The provider names of the film that belong to the catalogue `name` (channels included)."""
    return [other for other in film.get("providers", {}) if catalog_name(other) == name]


def _coverage(films: list[dict], subscriptions: list[str], free: frozenset[str], unavailable: int) -> dict:
    """How much of the watchlist the own services cover: free, subscription, rent only, the rest."""
    # Ownership is by service group: a Netflix subscription covers every Netflix plan (as on the stats page).
    free_own = {service_group(name) for name in subscriptions if name in free}
    paid_own = {service_group(name) for name in subscriptions if name not in free}

    def has(film: dict, groups: set[str]) -> bool:
        return any(
            service_group(name) in groups and WATCH_KINDS & set(kinds)
            for name, kinds in film.get("providers", {}).items()
        )

    counts = {"free": 0, "subscription": 0, "rent": 0, "other": unavailable}
    for film in films:
        if has(film, free_own):
            counts["free"] += 1
        elif has(film, paid_own):
            counts["subscription"] += 1
        elif not any(WATCH_KINDS & set(kinds) for kinds in film.get("providers", {}).values()):
            counts[
                "rent" if any("rent" in kinds for kinds in film.get("providers", {}).values()) else "other"
            ] += 1
        else:
            counts["other"] += 1  # on services the user does not have
    total = sum(counts.values())
    covered = counts["free"] + counts["subscription"]
    keys = ("subscription", "free", "rent", "other")
    return {
        "total": total,
        "covered": covered,
        "percent": round(100 * covered / total) if total else 0,
        "segments": [
            {
                "id": key,
                "films": counts[key],
                "percent": round(100 * counts[key] / total, 1) if total else 0,
                "share": share,
            }
            for key, share in zip(keys, whole_percents([counts[key] for key in keys]), strict=True)
        ],
    }


def whole_percents(counts: list[int]) -> list[int]:
    """Whole percents that add up to 100 (largest remainder), so a bar never says 101 %."""
    total = sum(counts)
    if not total:
        return [0] * len(counts)
    exact = [100 * count / total for count in counts]
    shares = [int(value) for value in exact]
    by_remainder = sorted(range(len(counts)), key=lambda index: exact[index] - shares[index], reverse=True)
    for index in by_remainder[: 100 - sum(shares)]:
        shares[index] += 1
    return shares


def cancel_ranking(
    services: list[dict], weekly_hours: float | None = None, cancel_from: float = CANCEL_FROM
) -> list[str]:
    """Own paid services worth cancelling, the highest price per film you would lose first (ties by name).

    Worth cancelling: you lose no film, or each film only there costs more than `cancel_from` a month, or at
    your pace (`weekly_hours`) you would watch the films only there within a month. A service without a price
    counts only when it loses nothing; one saved with price 0 is free and never cancelled.
    """

    def worth(item: dict) -> bool:
        if item["price"] == 0:
            return False
        if not item["only_here"]:
            return True
        if item["per_film"] is None:
            return False
        quick = bool(weekly_hours) and item["hours"] / weekly_hours < WEEKS_PER_MONTH
        return item["per_film"] > cancel_from or quick

    def per_film(item: dict) -> float:
        return float("inf") if not item["only_here"] else item["per_film"]

    found = sorted(
        (item for item in services if worth(item)), key=lambda i: (-per_film(i), i["name"].casefold())
    )
    return [item["name"] for item in found]


def cancel_hint(recommendations: list[dict]) -> str | None:
    """One line for the Tonight page when there is a cancel tip, e.g. "54 films only on Prime Video ·
    cancelling saves €8.99/month"; None without a tip (or when it is "keep")."""
    card = next((card for card in recommendations if card["type"] == "cancel"), None)
    if card is None:
        return None
    saves = f" · cancelling saves €{card['price']:.2f}/month" if card.get("price") else ""
    if card["loses_nothing"]:
        return f"Nothing on {card['name']} is only there{saves}"
    return f"{card['films']} film{'' if card['films'] == 1 else 's'} only on {card['name']}{saves}"


def _recommendations(
    services: list[dict],
    cancel: list[str],
    book: list,
    weekly_hours: float | None = None,
    cancel_from: float = CANCEL_FROM,
) -> list[dict]:
    """At most two cards, each with the numbers behind it: what to cancel and what to book for a month.

    The cancel card names the cheapest other priced service as the comparison ("vs"). When no service is worth
    cancelling but prices are set, a "keep" card says so.
    """
    cards: list[dict[str, Any]] = []
    by_name = {item["name"]: item for item in services}
    priced = sorted(
        (item for item in services if item["per_film"] is not None),
        key=lambda item: (item["per_film"], item["name"].casefold()),
    )
    if cancel and cancel[0] in by_name:
        item = by_name[cancel[0]]
        other = next((o for o in priced if o["name"] != item["name"]), None)
        weeks = item["hours"] / weekly_hours if weekly_hours and item["only_here"] else None
        cards.append(
            {
                "type": "cancel",
                "name": item["name"],
                "films": len(item["only_here"]),
                "hours": item["hours"],
                "price": item["price"],
                "per_film": item["per_film"],
                "loses_nothing": not item["only_here"],
                "based_on": "price" if item["price"] else "count",
                "weeks": round(weeks, 1) if weeks is not None and weeks < WEEKS_PER_MONTH else None,
                "vs": {"name": other["name"], "films": len(other["only_here"]), "per_film": other["per_film"]}
                if other
                else None,
            }
        )
    elif priced:
        cards.append({"type": "keep", "name": "", "cancel_from": cancel_from})
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
