"""The RSS feed of newly available films and the pick for the home-page tile."""

from datetime import UTC, datetime
from email.utils import format_datetime
from xml.sax.saxutils import escape

from .costs import WATCH_KINDS


def build_rss(changes: list[dict], base_url: str, own: set[str]) -> str:
    """RSS 2.0: one item per film that became available on one of the own services (newest first)."""
    items = []
    for change in changes:
        if change["change"] != "added" or change["provider"] not in own:
            continue
        year = f" ({change['year']})" if change.get("year") else ""
        title = f"{change['title']}{year} is now on {change['provider']}"
        when = format_datetime(datetime.fromtimestamp(change["created"], UTC))
        guid = f"{change['film_key']}|{change['provider']}|{int(change['created'])}"
        items.append(
            f"<item><title>{escape(title)}</title><link>{escape(base_url)}/watchlist</link>"
            f'<guid isPermaLink="false">{escape(guid)}</guid><pubDate>{when}</pubDate></item>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
        f"<title>Watchlist Availability: new on your services</title><link>{escape(base_url)}/</link>"
        "<description>Films from your watchlist that just became watchable on your services.</description>"
        + "".join(items)
        + "</channel></rss>"
    )


def pick_of_the_day(films: list[dict], own: list[str], hidden: set[str], today: str) -> dict | None:
    """One film to watch: among the films on the own services that are not watched or snoozed, the same
    one all day (chosen by the date) from the better rated half, so the tip changes daily."""
    candidates = [
        film
        for film in films
        if film.get("key") not in hidden
        and any(WATCH_KINDS & set(film.get("providers", {}).get(name, [])) for name in own)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda film: (-(film.get("rating") or 0), film.get("title") or ""))
    top = candidates[: max(1, (len(candidates) + 1) // 2)]
    return top[sum(map(ord, today)) % len(top)]
