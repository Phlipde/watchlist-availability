"""Streaming provider names and the groups derived from TMDB data."""

import tomllib
from pathlib import Path

# Short app name -> TMDB name, only where they differ. Saved subscriptions, costs, scans and
# favorites use the short names, so these must keep mapping. Every other provider keeps its TMDB name.
_ALIASES: dict[str, str] = {
    "Molotov": "Molotov TV",
    "Prime Video": "Amazon Prime Video",
    "Disney+": "Disney Plus",
    "Apple TV+": "Apple TV",
    "Paramount+": "Paramount Plus",
    "Google Play": "Google Play Movies",
    "Amazon VOD": "Amazon Video",
    "Peacock": "Peacock Premium",
    "Now": "Now TV",
    "ARD Plus Amazon Channel": "ARD Plus Amazon channel",
    "ARD Plus Apple TV Channel": "ARD Plus Apple TV channel",
    "Arthaus+ Apple TV Channel": "Arthaus+ Apple TV channel",
    "Lionsgate+ Amazon Channels": "Lionsgate+ Amazon Channel",
    "WOW Fiction Amazon Channel": "Wow Fiction Amazon Channel",
}


# Display sections, in order, with the TMDB monetization types each one covers.
# A film's section is decided per (film, provider) from TMDB's real monetization,
# NOT from platforms.toml. Only two buckets: Free (no cost) vs Paid (subscription
# or rental). A film available on a provider under both kinds appears in both
# sections (e.g. M6+ as ads + flatrate → Free AND Paid). "buy" is always excluded.
_SECTION_ORDER: list[tuple[str, frozenset[str]]] = [
    ("Free", frozenset({"free", "ads"})),
    ("Paid", frozenset({"flatrate", "rent"})),
]


def mostly_free_from_scan(results: list[dict], unavailable: list[dict]) -> frozenset[str]:
    """Providers that offer at least half of their scanned films free or with ads (no scan: none)."""
    offered: dict[str, int] = {}
    free: dict[str, int] = {}
    for film in [*results, *unavailable]:
        for provider, kinds in film.get("providers", {}).items():
            offered[provider] = offered.get(provider, 0) + 1
            if any(kind in {"free", "ads"} for kind in kinds):
                free[provider] = free.get(provider, 0) + 1
    return frozenset(provider for provider, count in offered.items() if free.get(provider, 0) * 2 >= count)


def _offer_kinds(results: list[dict], unavailable: list[dict]) -> dict[str, set[str]]:
    """{provider: every offer kind it has in the scan}."""
    kinds: dict[str, set[str]] = {}
    for film in [*results, *unavailable]:
        for provider, offered in film.get("providers", {}).items():
            kinds.setdefault(provider, set()).update(offered)
    return kinds


def rental_from_scan(results: list[dict], unavailable: list[dict]) -> frozenset[str]:
    """Shops: providers whose offers in the scan are only rent or buy."""
    kinds = _offer_kinds(results, unavailable)
    return frozenset(name for name, offered in kinds.items() if offered and offered <= {"rent", "buy"})


# TMDB name -> the short name shown in the app.
_DISPLAY_NAMES: dict[str, str] = {tmdb_name: display for display, tmdb_name in _ALIASES.items()}


def is_amazon_channel(name: str) -> bool:
    return "amazon channel" in name.casefold()


def display_name(tmdb_name: str) -> str:
    """The name shown in the app; TMDB sometimes has spaces around a name."""
    name = tmdb_name.strip()
    return _DISPLAY_NAMES.get(name, name)


def display_providers(available: dict) -> dict[str, list[str]]:
    """TMDB offers {TMDB name: kinds} under the names shown in the app."""
    shown: dict[str, list[str]] = {}
    for name, kinds in available.items():
        merged = shown.setdefault(display_name(name), [])
        merged.extend(kind for kind in kinds if kind not in merged)
    return shown


def known_names(extra: "list[str] | set[str] | tuple[str, ...]" = ()) -> set[str]:
    """Every provider name the app accepts: the short alias names plus the ones loaded from TMDB."""
    return {*_ALIASES, *extra}


def tmdb_names(names: list[str]) -> dict[str, str]:
    """{display name: TMDB name} for display names, as the CLI report needs them."""
    return {name: _ALIASES.get(name, name) for name in names}


def provider_groups(
    results: list[dict], unavailable: list[dict], catalog: list[str]
) -> list[tuple[str, list[str]]]:
    """The country's services grouped for the services page and "Add a service": [(group, names)].

    `catalog` are the display names TMDB lists in the country, by TMDB priority; when it was never
    loaded, the providers of the scan are used. Each name lands in one group, decided by its offers.
    """
    kinds = _offer_kinds(results, unavailable)
    free = mostly_free_from_scan(results, unavailable)
    rental = rental_from_scan(results, unavailable)
    groups: dict[str, list[str]] = {
        "Free and ad-supported": [],
        "Subscriptions": [],
        "More services": [],
        "Rental shops": [],
        "Amazon Channels": [],
    }
    for name in dict.fromkeys(catalog or sorted(kinds, key=str.casefold)):
        if is_amazon_channel(name):
            group = "Amazon Channels"
        elif name in free:
            group = "Free and ad-supported"
        elif name in rental:
            group = "Rental shops"
        elif "flatrate" in kinds.get(name, ()):
            group = "Subscriptions"
        else:
            group = "More services"
        groups[group].append(name)
    return list(groups.items())


def load_platforms_config(
    country: str = "FR",
    toml_path: Path | None = None,
) -> dict[str, str]:
    """Optional start values from platforms.toml: {display name: TMDB name}; no file or section: {}."""
    path = toml_path or (Path(__file__).parent.parent / "platforms.toml")
    if not path.exists():
        return {}
    with open(path, "rb") as file:
        section = tomllib.load(file).get(country, {})
    return {display: _ALIASES.get(display, display) for display, enabled in section.items() if enabled}
