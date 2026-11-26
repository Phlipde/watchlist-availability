"""Together: the watchlists of several profiles merged into one list of films nobody has seen yet."""

# Each member is a dict:
#   id, name       the profile
#   results        films of the member's latest scan in the shared country (Film dicts), None without a scan
#   unavailable    the scan's films without an offer
#   watched        keys the member has seen: `lb:{slug}` and the film keys (str(tmdb_id)) they resolve to
#   hidden         film keys the member has hidden or set aside ("not now")
#   subscriptions  the member's services in that country


def _identity(film: dict) -> tuple:
    """Films are the same across lists by TMDB id; a film TMDB does not know by its key."""
    tmdb_id = film.get("tmdb_id")
    return ("tmdb", tmdb_id) if tmdb_id is not None else ("key", film.get("key"))


def merge(members: list[dict]) -> dict:
    """Merge the lists of the members; the first member (the active profile) gives a shared film's data.

    A film anyone has watched, hidden or set aside drops out. Of the rest, `both` are on the list of every
    member that has a scan, `one` on some of them; the two groups do not overlap. Each film says
    `on_lists` (profile ids) and `group`.
    """
    films: dict[tuple, dict] = {}  # identity -> {"film", "section", "on_lists"}
    for member in members:
        for section in ("results", "unavailable"):
            for film in member.get(section) or []:
                entry = films.setdefault(_identity(film), {"film": film, "section": section, "on_lists": []})
                if member["id"] not in entry["on_lists"]:
                    entry["on_lists"].append(member["id"])
    with_lists = [member["id"] for member in members if member.get("results") is not None]
    excluded = set().union(*(member["watched"] | member["hidden"] for member in members))
    merged: dict[str, list[dict]] = {"results": [], "unavailable": []}
    groups: dict[str, list[str]] = {"both": [], "one": []}
    for entry in films.values():
        film = entry["film"]
        keys = {film.get("key"), str(film["tmdb_id"]) if film.get("tmdb_id") is not None else None}
        if keys & excluded:
            continue
        group = "both" if all(pid in entry["on_lists"] for pid in with_lists) else "one"
        merged[entry["section"]].append({**film, "on_lists": entry["on_lists"], "group": group})
        groups[group].append(film.get("key"))
    owners: dict[str, list[int]] = {}
    for member in members:
        for service in member.get("subscriptions") or []:
            owners.setdefault(service, []).append(member["id"])
    return {
        **merged,
        "subscriptions": list(owners),
        "service_owners": owners,
        "members": [{"id": member["id"], "name": member["name"]} for member in members],
        "groups": groups,
    }
