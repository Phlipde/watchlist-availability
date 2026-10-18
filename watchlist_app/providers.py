"""Streaming provider definitions and country configuration."""

import tomllib
from pathlib import Path

_ALL_PROVIDERS: dict[str, str] = {
    # --- Typically free / ad-supported ---
    "Arte":         "Arte",
    "Molotov":      "Molotov TV",
    "Pluto TV":     "Pluto TV",
    "Plex":         "Plex",

    # --- Typically subscription (flatrate) ---
    "Netflix":      "Netflix",
    "Canal+":       "Canal+",
    "TF1+":         "TF1+",
    "M6+":          "M6+",
    "Prime Video":  "Amazon Prime Video",
    "Disney+":      "Disney Plus",
    "Apple TV+":    "Apple TV",
    "Paramount+":   "Paramount Plus",
    "HBO Max":      "HBO Max",
    "Crunchyroll":  "Crunchyroll",
    "MUBI":         "MUBI",

    # --- Germany ---
    "Joyn":             "Joyn Plus",
    "MagentaTV":        "MagentaTV",
    "Magenta TV+":      "Magenta TV+",
    "Sky Go":           "Sky Go",
    "WOW":              "WOW",
    "FilmBox+":         "FilmBox+",
    "Filmtastic":       "Filmtastic",
    "Arthaus+":         "Arthaus+",
    "Netzkino":         "Netzkino",
    "Kino on Demand":   "Kino on Demand",
    "filmfriend":       "filmfriend",
    "filmingo":         "filmingo",
    "Alleskino":        "Alleskino",
    "Artiflix":         "Artiflix",
    "Freenet meinVOD":  "Freenet meinVOD",

    # --- Germany rental / VOD ---
    "Sky Store":        "Sky Store",
    "Verleihshop":      "Verleihshop",
    "Videobuster":      "Videobuster",
    "Videoload":        "Videoload",
    "maxdome Store":    "maxdome Store",

    # --- Typically rental / VOD ---
    "Canal VOD":        "Canal VOD",
    "Google Play":      "Google Play Movies",
    "Amazon VOD":       "Amazon Video",
    "Pathé Home":       "Pathé Home",
    "Rakuten TV":       "Rakuten TV",
    "Orange VOD":       "Orange VOD",
    "YouTube":          "YouTube",
    "Sooner":           "Sooner",

    # --- International ---
    "BBC iPlayer":      "BBC iPlayer",
    "ITVX":             "ITVX",
    "Channel 4":        "Channel 4",
    "Hulu":             "Hulu",
    "Peacock":          "Peacock Premium",
    "Now":              "Now TV",
    "Discovery+":       "Discovery+",
    "Rakuten Viki":     "Rakuten Viki",

    # ================================================================
    # Additional TMDB providers detected in Germany
    # ================================================================

    # --- Public broadcasters ---
    "ARD Mediathek":                    "ARD Mediathek",
    "ZDF":                              "ZDF",

    # --- ARD Plus ---
    "ARD Plus":                         "ARD Plus",
    "ARD Plus Amazon Channel":          "ARD Plus Amazon channel",
    "ARD Plus Apple TV Channel":        "ARD Plus Apple TV channel",

    # --- Amazon / Amazon Channels ---
    "Amazon Arthaus Channel":           "Amazon Arthaus Channel",
    "Amazon MX Player":                 "Amazon MX Player",
    "Amazon Prime Video Free with Ads": "Amazon Prime Video Free with Ads",
    "Amazon Prime Video with Ads":      "Amazon Prime Video with Ads",
    "Apple TV Amazon Channel":          "Apple TV Amazon Channel",

    # --- Apple TV / Arthaus ---
    "Apple TV Store":                   "Apple TV Store",
    "Arthaus+ Apple TV Channel":        "Arthaus+ Apple TV channel",
    "Arthouse CNMA Amazon Channel":     "Arthouse CNMA Amazon Channel",
    "ArthouseCNMA":                     "ArthouseCNMA",

    # --- Amazon Channels ---
    "AXN Black Amazon Channel":         "AXN Black Amazon Channel",
    "Allstars Amazon Channel":          "Allstars Amazon Channel",
    "BATTLEZONE Amazon Channel":        "BATTLEZONE Amazon Channel",
    "CineMix+ Amazon Channel":          "CineMix+ Amazon Channel",
    "Cinema of Hearts Amazon Channel":  "Cinema of Hearts Amazon Channel",
    "Crunchyroll Amazon Channel":       "Crunchyroll Amazon Channel",
    "Film Total Amazon Channel":        "Film Total Amazon Channel",
    "Filmlegenden Amazon Channel":      "Filmlegenden Amazon Channel",
    "Filmtastic Amazon Channel":        "Filmtastic Amazon Channel",
    "Galactic Stream Amazon Channel":   "Galactic Stream Amazon Channel",
    "HBO Max Amazon Channel":            "HBO Max Amazon Channel",
    "Kabel Eins Classics Amazon Channel": "Kabel Eins Classics Amazon Channel",
    "Lionsgate+ Amazon Channels":        "Lionsgate+ Amazon Channels",
    "MGM Plus Amazon Channel":           "MGM Plus Amazon Channel",
    "MUBI Amazon Channel":              "MUBI Amazon Channel",
    "Made in Europe Amazon Channel":    "Made in Europe Amazon Channel",
    "Moviedome Plus Amazon Channel":    "Moviedome Plus Amazon Channel",
    "Netzkino Select Amazon Channel":   "Netzkino Select Amazon Channel",
    "Paramount+ Amazon Channel":        "Paramount+ Amazon Channel",
    "ProSieben Fun Amazon Channel":      "ProSieben Fun Amazon Channel",
    "Seven Entertainment Amazon Channel": "Seven Entertainment Amazon Channel",
    "Sony Pictures Core Amazon Channel": "Sony Pictures Core Amazon Channel",
    "Studiocanal Presents ALLSTARS Amazon Channel":
        "Studiocanal Presents ALLSTARS Amazon Channel",
    "Superfresh Amazon Channel":        "Superfresh Amazon Channel",
    "Thrillbox Amazon Channel":         "Thrillbox Amazon Channel",
    "WOW Fiction Amazon Channel":       "Wow Fiction Amazon Channel",

    # --- Other services ---
    "Behind the Tree":                  "Behind the Tree",
    "Home of Horror":                   "Home of Horror",
    "Home of Horror Amazon Channel":    "Home of Horror Amazon Channel",
    "Netflix Kids":                     "Netflix Kids",
    "Netflix Standard with Ads":        "Netflix Standard with Ads",
    "Plex Channel":                     "Plex Channel",
    "RTL+":                             "RTL+",
    "RTL+ Max Amazon Channel":           "RTL+ Max Amazon Channel",
    "YouTube Free":                     "YouTube Free",
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

# Default selection when platforms.toml is missing or has no section for COUNTRY.
_DEFAULT_ENABLED: frozenset[str] = frozenset(
    {"Arte", "Netflix", "Canal+", "TF1+", "M6+"}
)


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
