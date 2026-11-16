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
        assert (netflix["films"], netflix["per_film"]) == (2, 6.0)
        assert [item["title"] for item in netflix["only_here"]] == ["Alien"]
        # Heat is also on Netflix and Brazil is free on Arte: cancelling MUBI loses nothing.
        assert (mubi["films"], mubi["per_film"], mubi["only_here"]) == (2, None, [])
        assert result["monthly_total"] == 12.0

    def test_only_on_my_services(self):
        assert costs.only_on_my_services(FILMS[1], ["Netflix", "MUBI"])
        assert not costs.only_on_my_services(FILMS[0], ["Netflix", "MUBI"])
        assert not costs.only_on_my_services(FILMS[2], ["MUBI"])

    def test_rotation(self):
        result = costs.overview(FILMS, ["Netflix", "MUBI"], {})
        assert (result["cancel"], result["cancel_loses_nothing"]) == (["MUBI"], True)
        assert result["book"] == [{"name": "Disney+", "films": 1}]

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
