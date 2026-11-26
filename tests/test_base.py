from watchlist_app import base, costs


def test_one_base_set_counts_released_films_and_sets_coming_soon_apart():
    scan = {
        "results": [{"key": "a"}, {"key": "b"}],
        "unavailable": [
            {"key": "c", "home_date": "2026-01-01"},  # released, nowhere to watch
            {"key": "d", "cinema_date": "2027-06-30"},  # still ahead
            {"key": "e"},
        ],
    }
    counts = base.base_counts(scan, to_check=1, today="2026-11-24")
    assert counts == {"watchlist": 4, "available": 2, "not_available": 2, "coming_soon": 1, "to_check": 1}
    assert base.base_counts(None)["watchlist"] == 0


def test_service_group_folds_plans_like_the_stats_page():
    assert base.service_group("Netflix Standard with Ads") == "Netflix"
    assert base.service_group("Amazon Prime Video with Ads") == "Prime Video"
    assert base.service_group("HBO Max Amazon Channel") == "HBO Max"
    assert base.service_group("MagentaTV") == "MagentaTV"


def test_coverage_counts_a_plan_of_an_own_service_as_covered():
    films = [
        {"key": "a", "providers": {"Netflix Standard with Ads": ["flatrate"]}},
        {"key": "b", "providers": {}},
    ]
    coverage = costs._coverage(films, ["Netflix"], frozenset(), 1)
    assert coverage["covered"] == 1
    assert coverage["total"] == 3  # the two films plus one released film nowhere to watch
