"""One base set for every number: what "the watchlist" means on all pages.

The watchlist is the films that are released and matched to TMDB. Films whose cinema or home release is still
ahead are counted apart ("coming soon"), as are matches that need a look ("to check").
"""

import re
from datetime import date


def is_coming_soon(film: dict, today: str | None = None) -> bool:
    """A film without an offer whose cinema or home release is still ahead (dates "YYYY-MM-DD")."""
    today = today or date.today().isoformat()
    return any(day and day >= today for day in (film.get("cinema_date"), film.get("home_date")))


def base_counts(scan: dict | None, to_check: int = 0, today: str | None = None) -> dict[str, int]:
    """Counts of one scan: the watchlist (released), with and without an offer, coming soon, to check."""
    results = scan["results"] if scan else []
    unavailable = scan["unavailable"] if scan else []
    coming = sum(1 for film in unavailable if is_coming_soon(film, today))
    return {
        "watchlist": len(results) + len(unavailable) - coming,
        "available": len(results),
        "not_available": len(unavailable) - coming,
        "coming_soon": coming,
        "to_check": to_check,
    }


# Plans of one provider are one service ("Netflix ... with Ads" is Netflix); as serviceGroup in catalog.js.
def service_group(name: str) -> str:
    base = re.sub(r"\s+Amazon channels?$", "", name, flags=re.IGNORECASE)
    base = re.sub(r"\s+(Apple TV|Amazon) channels?$", "", base, flags=re.IGNORECASE)
    if re.match(r"^Netflix(\s|$)", base, re.IGNORECASE):
        return "Netflix"
    if re.match(r"^(Amazon )?Prime Video( with Ads)?$", base, re.IGNORECASE):
        return "Prime Video"
    if re.match(r"^RTL\+( Premium| Max)?$", base, re.IGNORECASE):
        return "RTL+"
    return base
