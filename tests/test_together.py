"""together.merge: which films two or more profiles can watch together."""

from watchlist_app import together


def _film(tmdb_id, title, providers=None, key=None):
    return {
        "key": key or str(tmdb_id),
        "tmdb_id": tmdb_id,
        "title": title,
        "providers": providers or {"Netflix": ["flatrate"]},
    }


HEAT = _film(949, "Heat")
ALIEN = _film(348, "Alien", {"MUBI": ["flatrate"]})
UP = _film(14160, "Up")
LOST: dict = {"key": "Lost Film|1931", "tmdb_id": None, "title": "Lost Film", "providers": {}}


def _member(pid, results, unavailable=(), watched=(), hidden=(), subscriptions=()):
    return {
        "id": pid,
        "name": f"P{pid}",
        "results": list(results) if results is not None else None,
        "unavailable": list(unavailable),
        "watched": set(watched),
        "hidden": set(hidden),
        "subscriptions": list(subscriptions),
    }


def _keys(films):
    return [film["key"] for film in films]


def test_overlap_is_both_the_rest_is_one():
    merged = together.merge([_member(1, [HEAT, ALIEN], [LOST]), _member(2, [UP, HEAT], [LOST])])
    assert _keys(merged["results"]) == ["949", "348", "14160"]  # the active profile's order first
    assert merged["groups"] == {"both": ["949", "Lost Film|1931"], "one": ["348", "14160"]}
    heat, alien, up = merged["results"]
    assert (heat["on_lists"], heat["group"]) == ([1, 2], "both")
    assert (alien["on_lists"], up["on_lists"]) == ([1], [2])
    assert merged["unavailable"][0]["on_lists"] == [1, 2]  # matched by key without a TMDB id
    assert merged["members"] == [{"id": 1, "name": "P1"}, {"id": 2, "name": "P2"}]


def test_a_film_anyone_has_watched_drops_out():
    merged = together.merge(
        [_member(1, [HEAT, ALIEN], watched={"lb:heat", "949"}), _member(2, [HEAT, UP], watched={"14160"})]
    )
    assert _keys(merged["results"]) == ["348"]


def test_a_film_anyone_has_hidden_or_set_aside_drops_out():
    merged = together.merge(
        [_member(1, [HEAT, ALIEN, UP], hidden={"348"}), _member(2, [HEAT], hidden={"949"})]
    )
    assert _keys(merged["results"]) == ["14160"]


def test_a_csv_film_without_slug_stays_when_the_watched_slug_is_not_resolved():
    csv_heat = {**HEAT, "title": "Heat (CSV)"}  # a CSV entry has no slug, only its TMDB id
    # Profile 2 has seen Heat on Letterboxd, but no scan has matched its slug to a TMDB id yet.
    merged = together.merge([_member(1, [csv_heat]), _member(2, [], watched={"lb:heat"})])
    assert _keys(merged["results"]) == ["949"] and merged["results"][0]["on_lists"] == [1]
    # Once the slug is matched, the API adds the id to the watched keys and the film drops out.
    assert (
        together.merge([_member(1, [csv_heat]), _member(2, [], watched={"lb:heat", "949"})])["results"] == []
    )


def test_three_members_services_and_a_member_without_a_scan():
    merged = together.merge(
        [
            _member(1, [HEAT, ALIEN], subscriptions=["Netflix"]),
            _member(2, [HEAT, ALIEN], subscriptions=["MUBI", "Netflix"]),
            _member(3, [HEAT], subscriptions=["Arte"]),
        ]
    )
    assert merged["groups"] == {"both": ["949"], "one": ["348"]}
    assert merged["subscriptions"] == ["Netflix", "MUBI", "Arte"]
    assert merged["service_owners"] == {"Netflix": [1, 2], "MUBI": [2], "Arte": [3]}
    # Without a scan profile 3 has no list: "both" means on the lists of 1 and 2; its marks still count.
    no_scan = together.merge(
        [_member(1, [HEAT, ALIEN]), _member(2, [HEAT, ALIEN]), _member(3, None, hidden={"348"})]
    )
    assert no_scan["groups"] == {"both": ["949"], "one": []}
