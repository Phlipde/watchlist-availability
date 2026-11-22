"""Tests for subscription costs, rotation and reminders."""

import datetime

import pytest

from watchlist_app import costs


def film(title, **providers):
    return {"key": title, "title": title, "year": 2000, "providers": providers}


FILMS = [
    film("Heat", Netflix=["flatrate"], MUBI=["flatrate"]),
    film("Alien", Netflix=["flatrate"]),
    film("Brazil", MUBI=["flatrate"], Arte=["free"]),
    film("Ran", **{"Disney+": ["flatrate"], "Apple TV Store": ["rent"]}),
    film("Kes", **{"Apple TV Store": ["rent"]}),
]


class TestOverview:
    def test_price_per_film_and_only_here(self):
        result = costs.overview(FILMS, ["Netflix", "MUBI"], {"Netflix": {"price": 12.0}})
        netflix, mubi = result["services"]
        assert (netflix["films"], netflix["per_film"]) == (2, 12.0)  # price divided by the films only here
        assert [item["title"] for item in netflix["only_here"]] == ["Alien"]
        # Heat is also on Netflix and Brazil is free on Arte: cancelling MUBI loses nothing.
        assert (mubi["films"], mubi["per_film"], mubi["only_here"]) == (2, None, [])
        assert result["monthly_total"] == 12.0

    def test_free_services_form_a_block_and_the_table_is_sorted_by_what_cancelling_loses(self):
        result = costs.overview(FILMS, ["MUBI", "Arte", "Netflix", "ZDF"], {})
        assert [item["name"] for item in result["services"]] == [
            "Netflix",
            "MUBI",
        ]  # Netflix: Alien is only there
        assert result["free_block"] == [{"name": "Arte", "films": 1}]
        assert (result["free_empty"], result["free_films"]) == (1, 1)  # ZDF has no film

    def test_hours_and_price_per_only_here_film_and_year(self):
        films = [{**FILMS[1], "runtime": 90}, {**FILMS[0], "runtime": 120}]
        result = costs.overview(films, ["Netflix", "MUBI"], {"Netflix": {"price": 12.0}})
        netflix = result["services"][0]
        assert (netflix["name"], netflix["hours"], netflix["per_film"]) == ("Netflix", 1.5, 12.0)
        assert result["yearly_total"] == 144.0

    def test_amazon_channels_count_as_their_main_service(self):
        assert costs.catalog_name("HBO Max Amazon Channel") == "HBO Max"
        assert costs.catalog_name("Netflix") == "Netflix"
        films = [
            film("A", **{"HBO Max": ["flatrate"]}),
            film("B", **{"HBO Max Amazon Channel": ["flatrate"], "HBO Max": ["flatrate"]}),
        ]
        book = costs.overview(films, [], {})["book"]
        assert book == [{"name": "HBO Max", "films": 2, "hours": 0, "favorites": 0}]

    def test_two_recommendation_cards_with_the_numbers_behind_them(self):
        films = [{**FILMS[1], "runtime": 90}, {**FILMS[3], "runtime": 120}, FILMS[0]]
        result = costs.overview(films, ["Netflix"], {"Netflix": {"price": 12.0}})
        cancel, subscribe = result["recommendations"]
        assert (cancel["type"], cancel["name"], cancel["films"], cancel["per_film"]) == (
            "cancel",
            "Netflix",
            2,
            6.0,
        )
        assert cancel["based_on"] == "price" and cancel["hours"] == 1.5
        assert (subscribe["type"], subscribe["name"], subscribe["films"], subscribe["hours"]) == (
            "subscribe",
            "Disney+",
            1,
            2,
        )
        # Without a price the card says it rests on the film count only.
        assert costs.overview(films, ["Netflix"], {})["recommendations"][0]["based_on"] == "count"
        assert costs.overview(FILMS, [], {})["recommendations"][0]["type"] == "subscribe"

    def test_coverage_splits_the_watchlist_into_four_parts(self):
        films = [
            film("A", Arte=["free"]),
            film("B", Netflix=["flatrate"]),
            film("C", **{"Apple TV Store": ["rent"]}),
            film("D", **{"Disney+": ["flatrate"]}),  # only on a service the user does not have
        ]
        coverage = costs.overview(films, ["Netflix", "Arte"], {}, unavailable=2)["coverage"]
        counts = {item["id"]: item["films"] for item in coverage["segments"]}
        assert counts == {"subscription": 1, "free": 1, "rent": 1, "other": 3}
        assert (coverage["total"], coverage["covered"], coverage["percent"]) == (6, 2, 33)
        assert costs.overview([], [], {})["coverage"]["percent"] == 0

    def test_rent_only_films_come_best_rated_first(self):
        films = [
            {**film("Low", **{"Apple TV Store": ["rent"]}), "letterboxd_rating": 2.5},
            {**film("High", **{"Apple TV Store": ["rent"]}), "letterboxd_rating": 4.1},
        ]
        assert [item["title"] for item in costs.overview(films, [], {})["rent_only"]] == ["High", "Low"]

    def test_value_weights_favorites_and_good_ratings_and_ranks_by_value_for_money(self):
        films = [
            {**FILMS[1], "letterboxd_rating": 4.2},  # Alien: only on Netflix, well rated -> 2
            film("Solo", MUBI=["flatrate"]),  # only on MUBI, a favorite -> 3
            film("Plain", MUBI=["flatrate"]),  # only on MUBI -> 1
        ]
        result = costs.overview(
            films,
            ["Netflix", "MUBI"],
            {"Netflix": {"price": 10.0}, "MUBI": {"price": 4.0}},
            favorites=frozenset({"Solo"}),
        )
        mubi, netflix = result["services"]  # value 4 against 2: MUBI first
        assert (mubi["value"], mubi["favorites"], netflix["value"]) == (4, 1, 2)
        assert (mubi["value_per_euro"], netflix["value_per_euro"]) == (1.0, 0.2)
        # Netflix gives the least for the money, so it is the one to cancel.
        assert result["cancel"] == ["Netflix"]

    def test_a_shared_account_splits_the_price(self):
        films = [FILMS[1]]
        result = costs.overview(films, ["Netflix"], {"Netflix": {"price": 12.0, "shared": 3}})
        assert (result["services"][0]["own_share"], result["monthly_total"]) == (4.0, 4.0)

    def test_management_fields_are_checked(self):
        clean = costs.clean_costs(
            {
                "Netflix": {
                    "price": 10,
                    "shared": "2",
                    "notice_days": 14,
                    "note": " hi ",
                    "cancel_url": "https://x.example/cancel",
                }
            },
            {"Netflix"},
        )
        assert clean["Netflix"]["shared"] == 2 and clean["Netflix"]["note"] == "hi"
        for bad in (
            {"shared": 0},
            {"notice_days": -1},
            {"cancel_url": "javascript:alert(1)"},
            {"trial_on": "soon"},
        ):
            with pytest.raises(ValueError):
                costs.clean_costs({"Netflix": {"price": 1, **bad}}, {"Netflix"})

    def test_plan_data_has_weights_free_films_and_the_services_that_add_most(self):
        films = [
            film("A", Netflix=["flatrate"]),
            film("B", Arte=["free"]),
            film("C", **{"Disney+": ["flatrate"]}),
            film("D", **{"Disney+": ["flatrate"], "Disney+ Amazon Channel": ["flatrate"]}),
        ]
        plan = costs.overview(
            films, ["Netflix", "Arte"], {"Netflix": {"price": 9.0}}, favorites=frozenset({"C"})
        )["plan"]
        assert plan["weights"] == {"A": 1, "B": 1, "C": 3, "D": 1}
        assert plan["base"] == ["B"] and plan["owned"] == ["Netflix"] and plan["prices"] == {"Netflix": 9.0}
        assert plan["services"]["Netflix"] == ["A"]
        assert plan["services"]["Disney+"] == ["C", "D"]  # the Amazon Channel counts as Disney+
        assert costs.overview(films, ["Netflix"], {}, favorites=frozenset({"C"}))["book"][0]["favorites"] == 1

    def test_only_on_my_services(self):
        assert costs.only_on_my_services(FILMS[1], ["Netflix", "MUBI"])
        assert not costs.only_on_my_services(FILMS[0], ["Netflix", "MUBI"])
        assert not costs.only_on_my_services(FILMS[2], ["MUBI"])

    def test_rotation(self):
        result = costs.overview(FILMS, ["Netflix", "MUBI"], {})
        assert (result["cancel"], result["cancel_loses_nothing"]) == (["MUBI"], True)
        assert result["book"] == [{"name": "Disney+", "films": 1, "hours": 0, "favorites": 0}]

    def test_free_services_are_never_cancelled(self):
        result = costs.overview(FILMS, ["Netflix", "Arte", "MUBI"], {"MUBI": {"price": 0}})
        assert result["cancel"] == ["Netflix"]

    def test_services_free_in_the_scan_are_never_cancelled(self):
        # BBC iPlayer is not on the built-in free list, but the scan shows it free.
        films = [*FILMS, film("Brief Encounter", **{"BBC iPlayer": ["free"]})]
        assert "BBC iPlayer" not in costs.overview(films, ["Netflix", "BBC iPlayer"], {})["cancel"]

    def test_cancel_the_service_with_fewest_own_films_when_each_has_some(self):
        result = costs.overview(FILMS, ["Netflix", "Disney+"], {})
        assert result["cancel_loses_nothing"] is False
        assert len(result["cancel"]) == 1

    def test_rent_only(self):
        assert [item["title"] for item in costs.overview(FILMS, [], {})["rent_only"]] == ["Kes"]

    def test_no_subscriptions(self):
        result = costs.overview(FILMS, [], {})
        assert (result["services"], result["cancel"], result["monthly_total"]) == ([], [], 0)


class TestCleanCosts:
    def test_valid_values(self):
        cleaned = costs.clean_costs(
            {
                "Netflix": {"price": "12.99", "remind_on": "2026-12-01"},
                "MUBI": {"price": "", "remind_on": ""},
            },
            {"Netflix", "MUBI"},
        )
        assert cleaned == {"Netflix": {"price": 12.99, "remind_on": "2026-12-01"}}

    @pytest.mark.parametrize(
        "raw",
        [
            [],
            {"Other": {"price": 1}},
            {"Netflix": {"price": "abc"}},
            {"Netflix": {"price": -1}},
            {"Netflix": {"remind_on": "tomorrow"}},
        ],
    )
    def test_invalid_values(self, raw):
        with pytest.raises(ValueError):
            costs.clean_costs(raw, {"Netflix"})


def test_deadlines_within_a_week_only():
    today = datetime.date(2026, 11, 18)
    entries = {
        "Netflix": {"price": 10, "remind_on": "2026-11-21"},
        "MUBI": {"price": 8, "remind_on": "2026-11-18"},
        "Disney+": {"price": 9, "remind_on": "2026-12-30"},
        "Arte": {"price": None, "remind_on": "2026-11-10"},  # already past
    }
    found = costs.upcoming_deadlines(entries, today)
    assert [(item["name"], item["days"]) for item in found] == [("MUBI", 0), ("Netflix", 3)]


def test_reminders_soonest_first():
    found = costs.reminders(
        {
            "DE": {
                "Netflix": {"price": 1, "remind_on": "2026-12-01"},
                "MUBI": {"price": 2, "remind_on": None},
            },
            "FR": {"Canal+": {"price": None, "remind_on": "2026-11-10"}},
        },
        today=datetime.date(2026, 11, 15),
    )
    assert [(item["name"], item["days"]) for item in found] == [("Canal+", -5), ("Netflix", 16)]


def test_other_countries_where_your_services_show_more():
    offers = {
        "DE": {1: {"Netflix": ["flatrate"]}, 2: {"Disney+": ["flatrate"]}, 3: {}},
        "AT": {1: {"Netflix": ["flatrate"]}, 2: {"Netflix": ["flatrate"]}, 3: {"Netflix": ["ads"]}},
        "US": {1: {"Netflix": ["flatrate"]}},  # offers for under half of the films: not comparable
        "FR": {1: {"Netflix": ["rent"]}, 2: {}, 3: {}},  # rent does not count
    }
    found = costs.other_countries(offers, ["Netflix"], "DE", total=3)
    assert found == [{"country": "AT", "films": 3, "gain": 2}]
    assert costs.other_countries({}, ["Netflix"], "DE", total=0) == []


def test_service_counts_leave_free_services_out():
    films = [
        film("A", Netflix=["flatrate"]),
        film("B", Netflix=["flatrate"], MUBI=["flatrate"]),
        film("C", Arte=["free"]),
    ]
    assert costs.service_counts(films, ["Netflix", "MUBI", "Arte"]) == {"Netflix": (2, 1), "MUBI": (1, 0)}


def test_abroad_map_finds_own_services_abroad_but_not_at_home():
    offers = {
        "DE": {1: {"Netflix": ["flatrate"]}, 2: {"Disney+": ["flatrate"]}, 3: {}},
        "AT": {
            1: {"Netflix": ["flatrate"]},
            2: {"Netflix": ["flatrate"], "Disney+": ["rent"]},
            3: {"Netflix": ["ads"]},
        },
        "IT": {2: {"Netflix Amazon Channel": ["flatrate"]}, 3: {"MUBI": ["flatrate"], "Netflix": ["rent"]}},
    }
    found = costs.abroad_map(offers, {"Netflix"}, "DE")
    assert 1 not in found  # Netflix has film 1 at home, so it is not abroad
    assert found[2] == {
        "Netflix": {"AT": "flatrate", "IT": "flatrate"}
    }  # the channel counts as Netflix; rent does not count
    assert found[3] == {"Netflix": {"AT": "ads"}}  # MUBI is not yours


def test_a_service_cancelled_to_an_end_date_stays_until_that_day_is_over():
    entries = {"Netflix": {"ends_on": "2026-12-01"}, "MUBI": {"price": 5}}
    names = ["Netflix", "MUBI", "Disney+"]
    assert costs.not_ended(names, entries, datetime.date(2026, 12, 1)) == names  # the end day still counts
    assert costs.not_ended(names, entries, datetime.date(2026, 12, 2)) == ["MUBI", "Disney+"]


def test_the_end_date_is_validated_and_kept():
    cleaned = costs.clean_costs({"Netflix": {"price": "", "ends_on": "2026-12-01"}}, {"Netflix"})
    assert cleaned["Netflix"]["ends_on"] == "2026-12-01"
    with pytest.raises(ValueError, match="end date"):
        costs.clean_costs({"Netflix": {"ends_on": "soon"}}, {"Netflix"})
