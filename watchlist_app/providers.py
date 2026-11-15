"""Streaming provider definitions and country configuration."""

import tomllib
from pathlib import Path

_ALL_PROVIDERS: dict[str, str] = {
    # --- Typically free / ad-supported ---
    "Arte": "Arte",
    "Molotov": "Molotov TV",
    "Pluto TV": "Pluto TV",
    "Plex": "Plex",
    # --- Typically subscription (flatrate) ---
    "Netflix": "Netflix",
    "Canal+": "Canal+",
    "TF1+": "TF1+",
    "M6+": "M6+",
    "Prime Video": "Amazon Prime Video",
    "Disney+": "Disney Plus",
    "Apple TV+": "Apple TV",
    "Paramount+": "Paramount Plus",
    "HBO Max": "HBO Max",
    "Crunchyroll": "Crunchyroll",
    "MUBI": "MUBI",
    # --- Germany ---
    "Joyn": "Joyn",  # free with ads; TMDB lists the subscription as "Joyn Plus"
    "Joyn Plus": "Joyn Plus",
    "MagentaTV": "MagentaTV",
    "Magenta TV+": "Magenta TV+",
    "Sky Go": "Sky Go",
    "WOW": "WOW",
    "FilmBox+": "FilmBox+",
    "Filmtastic": "Filmtastic",
    "Arthaus+": "Arthaus+",
    "Netzkino": "Netzkino",
    "Kino on Demand": "Kino on Demand",
    "filmfriend": "filmfriend",
    "filmingo": "filmingo",
    "Alleskino": "Alleskino",
    "Artiflix": "Artiflix",
    "Freenet meinVOD": "Freenet meinVOD",
    # --- Germany rental / VOD ---
    "Sky Store": "Sky Store",
    "Verleihshop": "Verleihshop",
    "Videobuster": "Videobuster",
    "Videoload": "Videoload",
    "maxdome Store": "maxdome Store",
    # --- Typically rental / VOD ---
    "Canal VOD": "Canal VOD",
    "Google Play": "Google Play Movies",
    "Amazon VOD": "Amazon Video",
    "Pathé Home": "Pathé Home",
    "Rakuten TV": "Rakuten TV",
    "Orange VOD": "Orange VOD",
    "YouTube": "YouTube",
    "Sooner": "Sooner",
    # --- International ---
    "BBC iPlayer": "BBC iPlayer",
    "ITVX": "ITVX",
    "Channel 4": "Channel 4",
    "Hulu": "Hulu",
    "Peacock": "Peacock Premium",
    "Now": "Now TV",
    "Discovery+": "Discovery+",
    "Rakuten Viki": "Rakuten Viki",
    # ================================================================
    # Additional TMDB providers detected in Germany
    # ================================================================
    # --- Public broadcasters ---
    "ARD Mediathek": "ARD Mediathek",
    "ZDF": "ZDF",
    # --- ARD Plus ---
    "ARD Plus": "ARD Plus",
    "ARD Plus Amazon Channel": "ARD Plus Amazon channel",
    "ARD Plus Apple TV Channel": "ARD Plus Apple TV channel",
    # --- Amazon / Amazon Channels ---
    "Amazon Arthaus Channel": "Amazon Arthaus Channel",
    "Amazon MX Player": "Amazon MX Player",
    "Amazon Prime Video Free with Ads": "Amazon Prime Video Free with Ads",
    "Amazon Prime Video with Ads": "Amazon Prime Video with Ads",
    "Apple TV Amazon Channel": "Apple TV Amazon Channel",
    # --- Apple TV / Arthaus ---
    "Apple TV Store": "Apple TV Store",
    "Arthaus+ Apple TV Channel": "Arthaus+ Apple TV channel",
    "Arthouse CNMA Amazon Channel": "Arthouse CNMA Amazon Channel",
    "ArthouseCNMA": "ArthouseCNMA",
    # --- Amazon Channels ---
    "AXN Black Amazon Channel": "AXN Black Amazon Channel",
    "Allstars Amazon Channel": "Allstars Amazon Channel",
    "BATTLEZONE Amazon Channel": "BATTLEZONE Amazon Channel",
    "CineMix+ Amazon Channel": "CineMix+ Amazon Channel",
    "Cinema of Hearts Amazon Channel": "Cinema of Hearts Amazon Channel",
    "Crunchyroll Amazon Channel": "Crunchyroll Amazon Channel",
    "Film Total Amazon Channel": "Film Total Amazon Channel",
    "Filmlegenden Amazon Channel": "Filmlegenden Amazon Channel",
    "Filmtastic Amazon Channel": "Filmtastic Amazon Channel",
    "Galactic Stream Amazon Channel": "Galactic Stream Amazon Channel",
    "HBO Max Amazon Channel": "HBO Max Amazon Channel",
    "Kabel Eins Classics Amazon Channel": "Kabel Eins Classics Amazon Channel",
    "Lionsgate+ Amazon Channels": "Lionsgate+ Amazon Channel",
    "MGM Plus Amazon Channel": "MGM Plus Amazon Channel",
    "MUBI Amazon Channel": "MUBI Amazon Channel",
    "Made in Europe Amazon Channel": "Made in Europe Amazon Channel",
    "Moviedome Plus Amazon Channel": "Moviedome Plus Amazon Channel",
    "Netzkino Select Amazon Channel": "Netzkino Select Amazon Channel",
    "Paramount+ Amazon Channel": "Paramount+ Amazon Channel",
    "ProSieben Fun Amazon Channel": "ProSieben Fun Amazon Channel",
    "Seven Entertainment Amazon Channel": "Seven Entertainment Amazon Channel",
    "Sony Pictures Core Amazon Channel": "Sony Pictures Core Amazon Channel",
    "Studiocanal Presents ALLSTARS Amazon Channel": "Studiocanal Presents ALLSTARS Amazon Channel",
    "Superfresh Amazon Channel": "Superfresh Amazon Channel",
    "Thrillbox Amazon Channel": "Thrillbox Amazon Channel",
    "WOW Fiction Amazon Channel": "Wow Fiction Amazon Channel",
    # --- Other services ---
    "Behind the Tree": "Behind the Tree",
    "Home of Horror": "Home of Horror",
    "Home of Horror Amazon Channel": "Home of Horror Amazon Channel",
    "Netflix Kids": "Netflix Kids",
    "Netflix Standard with Ads": "Netflix Standard with Ads",
    "Plex Channel": "Plex Channel",
    "RTL+": "RTL+",
    "RTL+ Max Amazon Channel": "RTL+ Max Amazon Channel",
    "YouTube Free": "YouTube Free",
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

# Providers that are usually free or ad-supported (shown with a "Free" tag).
MOSTLY_FREE: frozenset[str] = frozenset(
    {
        "Arte",
        "Molotov",
        "Pluto TV",
        "Plex",
        "ARD Mediathek",
        "filmfriend",
        "Netzkino",
        "YouTube Free",
        "ZDF",
        "Alleskino",
        "Joyn",
        "Amazon MX Player",
        "Amazon Prime Video Free with Ads",
        "Amazon Prime Video with Ads",
        "Plex Channel",
    }
)

# Shops where films are rented one by one; kept apart from subscriptions.
RENTAL_SHOPS: frozenset[str] = frozenset(
    {
        "Sky Store",
        "Verleihshop",
        "Videobuster",
        "Videoload",
        "maxdome Store",
        "Canal VOD",
        "Google Play",
        "Amazon VOD",
        "Pathé Home",
        "Rakuten TV",
        "Orange VOD",
        "YouTube",
        "Apple TV Store",
        "Freenet meinVOD",
        "Kino on Demand",
    }
)

_FREE_SERVICES = ("Arte", "Molotov", "Pluto TV", "Plex")
_MAIN_SUBSCRIPTIONS = (
    "Netflix",
    "Canal+",
    "TF1+",
    "M6+",
    "Prime Video",
    "Disney+",
    "Apple TV+",
    "Paramount+",
    "HBO Max",
    "Crunchyroll",
    "MUBI",
)


# TMDB name -> the short name shown in the app. Providers TMDB knows but this list
# does not are shown under their TMDB name.
_DISPLAY_NAMES: dict[str, str] = {tmdb_name: display for display, tmdb_name in _ALL_PROVIDERS.items()}


def is_amazon_channel(name: str) -> bool:
    return "amazon channel" in name.casefold()


# Built-in providers that were matched differently before the provider list came
# from TMDB (renamed at TMDB, or a TMDB name with spaces around it). The first scan
# after the update does not compare them, so they are not reported as "new on ...".
MATCHING_CHANGED: frozenset[str] = frozenset(
    {"Joyn", "Joyn Plus", "Lionsgate+ Amazon Channels", "ARD Plus Amazon Channel"}
)


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
    """Every provider name the app accepts: the built-in list plus the ones loaded from TMDB."""
    return {*_ALL_PROVIDERS, *extra}


def tmdb_names(names: list[str]) -> dict[str, str]:
    """{display name: TMDB name} for display names, as the CLI report needs them."""
    return {name: _ALL_PROVIDERS.get(name, name) for name in names}


def provider_groups(
    extra: "list[str] | set[str] | tuple[str, ...]" = (),
) -> list[tuple[str, list[tuple[str, list[str]]]]]:
    """Providers grouped for the sidebar and the settings page: (group, [(subgroup, names)]).

    `extra` are names loaded from TMDB that the built-in list does not know; they
    are added to "More services" or, if they are Amazon Channels, to that group.
    """
    standard = {*_FREE_SERVICES, *_MAIN_SUBSCRIPTIONS}
    new_names = sorted(set(extra) - set(_ALL_PROVIDERS), key=str.casefold)
    names = [*_ALL_PROVIDERS, *new_names]
    other = [
        name
        for name in names
        if name not in standard and name not in RENTAL_SHOPS and not is_amazon_channel(name)
    ]
    return [
        (
            "Services",
            [
                ("Free and ad-supported", list(_FREE_SERVICES)),
                ("Subscriptions", list(_MAIN_SUBSCRIPTIONS)),
                ("More services", other),
            ],
        ),
        ("Rental shops", [("Rental shops", [name for name in names if name in RENTAL_SHOPS])]),
        ("Amazon Channels", [("Amazon Channels", [name for name in names if is_amazon_channel(name)])]),
    ]


# Default selection when platforms.toml is missing or has no section for COUNTRY.
_DEFAULT_ENABLED: frozenset[str] = frozenset({"Arte", "Netflix", "Canal+", "TF1+", "M6+"})


def load_platforms_config(
    country: str = "FR",
    toml_path: Path | None = None,
) -> dict[str, str]:
    """Load enabled, known providers for a country from platforms.toml."""
    path = toml_path or (Path(__file__).parent.parent / "platforms.toml")

    def _defaults() -> dict[str, str]:
        return {k: v for k, v in _ALL_PROVIDERS.items() if k in _DEFAULT_ENABLED}

    if not path.exists():
        return _defaults()

    with open(path, "rb") as file:
        config = tomllib.load(file)

    section = config.get(country, {})
    if not section:
        return _defaults()

    return {
        display: _ALL_PROVIDERS[display]
        for display, enabled in section.items()
        if enabled and display in _ALL_PROVIDERS
    }
