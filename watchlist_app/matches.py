"""Check and correct which TMDB film a watchlist entry was matched to.

Most entries get their TMDB id from the Letterboxd film page and are certain.
An entry is uncertain when its id came from a TMDB title search, when nothing
was found, or when the TMDB release year differs from the watchlist year. A
correction is stored as source "manual" and kept for good (also in backups).
"""

import re
import time

from . import tmdb
from .store import MATCHES_CHANGED_SETTING, Store

# Entries not seen in a scan for this long are left off the page (no longer on the watchlist).
SEEN_WITHIN_SECONDS = 60 * 24 * 60 * 60

REASONS = {
    "not_found": "Not found on TMDB",
    "search": "Matched by title search",
    "year": "Release year differs by more than a year",
}

_TMDB_URL_RE = re.compile(r"themoviedb\.org/movie/(\d+)")


def tmdb_year(details: dict | None) -> int | None:
    release = (details or {}).get("release_date") or ""
    return int(release[:4]) if release[:4].isdigit() else None


def uncertain_reason(match: dict) -> str | None:
    """Why a match should be checked, or None when it is certain or was set by hand."""
    if match["source"] == "manual":
        return None
    if match["tmdb_id"] is None:
        return "not_found"
    if match["source"] == "search":
        return "search"
    # One year apart is normal (festival screening vs. cinema release), more is suspicious.
    found_year = tmdb_year(match.get("details"))
    if match.get("year") and found_year and abs(match["year"] - found_year) > 1:
        return "year"
    return None


def list_matches(store: Store, include_certain: bool = False, now: float | None = None) -> list[dict]:
    """Matches of the current watchlist entries for the review page, uncertain ones first."""
    moment = now if now is not None else time.time()
    rows = []
    for match in store.list_matches(seen_since=moment - SEEN_WITHIN_SECONDS):
        reason = uncertain_reason(match)
        if reason is None and not include_certain:
            continue
        details = match.get("details") or {}
        rows.append(
            {
                "film_key": match["film_key"],
                "title": match["title"] or match["film_key"],
                "year": match["year"],
                "tmdb_id": match["tmdb_id"],
                "source": match["source"],
                "reason": reason,
                "reason_text": REASONS.get(reason or "", ""),
                "tmdb_title": details.get("tmdb_title") or "",
                "tmdb_year": tmdb_year(details),
                "poster_path": match.get("poster_path"),
                "tmdb_url": f"https://www.themoviedb.org/movie/{match['tmdb_id']}"
                if match["tmdb_id"]
                else None,
                "letterboxd_url": (
                    f"https://letterboxd.com/film/{match['film_key'][3:]}/"
                    if match["film_key"].startswith("lb:")
                    else None
                ),
            }
        )
    rows.sort(key=lambda row: (row["reason"] is None, (row["title"] or "").casefold()))
    return rows


def parse_tmdb_reference(text: str | int | None) -> int | None:
    """A TMDB id from "603", "https://www.themoviedb.org/movie/603-the-matrix" or 603."""
    if isinstance(text, int):
        return text if text > 0 else None
    value = (text or "").strip()
    if value.isdigit():
        return int(value) or None
    found = _TMDB_URL_RE.search(value)
    return int(found.group(1)) if found else None


def correct_match(store: Store, film_key: str, tmdb_id: int, api_key: str | None) -> dict:
    """Map a watchlist entry to another TMDB film for good. Raises ValueError for the user.

    The film is fetched once to check the id and to have its data ready.
    """
    known = store.get_id(film_key)
    if known is None:
        raise ValueError("This watchlist entry is unknown.")
    bundle = tmdb.get_movie_bundle(tmdb_id, api_key)
    if bundle is None:
        raise ValueError(f"TMDB has no film with the id {tmdb_id}.")
    store.save_bundle(tmdb_id, bundle)
    store.set_id(film_key, tmdb_id, "manual")
    store.set_setting(MATCHES_CHANGED_SETTING, str(time.time()))
    details = bundle.get("details") or {}
    return {
        "tmdb_id": tmdb_id,
        "tmdb_title": details.get("tmdb_title") or "",
        "tmdb_year": tmdb_year(details),
    }


def reset_match(store: Store, film_key: str) -> None:
    """Forget a match; the next scan looks the entry up again."""
    store.remove_id(film_key)
    store.set_setting(MATCHES_CHANGED_SETTING, str(time.time()))


def changed_since(store: Store, moment: float) -> bool:
    """True when a match was corrected after `moment`."""
    try:
        return float(store.get_setting(MATCHES_CHANGED_SETTING) or 0) > moment
    except ValueError:
        return False
