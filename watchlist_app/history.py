"""Availability changes between scans: "new on ..." and "no longer on ..."."""

# "Recently gone" looks back 30 days; "new on" badges use the last 14 (static/js/events.js).
CHANGE_WINDOW_SECONDS = 30 * 24 * 60 * 60


def _provider_index(scan: dict) -> dict[str, set[str]]:
    """Providers per film of a stored scan, by film key."""
    return {
        film["key"]: set(film.get("providers") or {})
        for film in [*scan.get("results", []), *scan.get("unavailable", [])]
    }


def diff_scans(
    previous: dict | None,
    results: list[dict],
    unavailable: list[dict],
    compare_only: set[str] | None = None,
    older: dict | None = None,
) -> list[dict]:
    """Compare a new scan with the previous one of the same watchlist.

    Only films present in both scans count, so a film that was just added to or
    removed from the watchlist does not show up as a change. With `compare_only`,
    only these providers are compared (the previous scan knew no others).

    Two-scan rule against TMDB hiccups: "removed" needs two scans in a row without the
    provider (it was in `older`, the scan before `previous`), and a provider that only
    dropped out of `previous` and is back now is not "added". Without `older` (only one
    earlier scan) nothing is reported as removed yet.
    """
    if not previous:
        return []
    before = _provider_index(previous)
    earlier = _provider_index(older) if older else {}
    changes = []
    for film in [*results, *unavailable]:
        key = film["key"]
        old = before.get(key)
        if old is None:
            continue
        new = set(film.get("providers") or {})
        oldest = earlier.get(key, old)
        if compare_only is not None:
            old, new, oldest = old & compare_only, new & compare_only, oldest & compare_only
        added = new - old - oldest if older else new - old
        removed = (oldest - old) - new if older else set()
        for change, providers in (("added", added), ("removed", removed)):
            for provider in sorted(providers):
                changes.append(
                    {
                        "film_key": key,
                        "title": film.get("title"),
                        "year": film.get("year"),
                        "provider": provider,
                        "change": change,
                    }
                )
    return changes


def apply_changes(films: list[dict], changes: list[dict]) -> list[dict]:
    """Return copies of the films with `provider_changes` = {"added": [...], "removed": [...]}.

    `changes` must be ordered newest first; per film and provider the newest change
    wins, and a change that no longer matches the current offers is dropped.
    """
    latest: dict[str, dict[str, dict]] = {}
    for change in changes:
        latest.setdefault(change["film_key"], {}).setdefault(change["provider"], change)
    annotated = []
    for film in films:
        film_changes = latest.get(film["key"], {})
        current = set(film.get("providers") or {})
        added = sorted(
            provider
            for provider, change in film_changes.items()
            if change["change"] == "added" and provider in current
        )
        removed = sorted(
            provider
            for provider, change in film_changes.items()
            if change["change"] == "removed" and provider not in current
        )
        copy = {key: value for key, value in film.items() if key != "provider_changes"}
        if added or removed:
            copy["provider_changes"] = {
                "added": added,
                "removed": removed,
                "since": max(film_changes[provider]["created"] for provider in [*added, *removed]),
            }
        annotated.append(copy)
    return annotated
