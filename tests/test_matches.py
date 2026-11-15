"""Tests for checking and correcting title matches."""

import time
from unittest.mock import patch

import pytest

from tests.helpers import BUNDLE
from watchlist_app import matches
from watchlist_app.models import WatchlistEntry
from watchlist_app.scan_service import perform_scan
from watchlist_app.store import Store

HEAT = {**BUNDLE, "details": {**BUNDLE["details"], "tmdb_title": "Heat", "release_date": "1995-12-15"}}


@pytest.fixture
def store():
    database = Store(":memory:")
    yield database
    database.close()


def fill(store):
    store.save_bundle(949, HEAT)
    store.set_id("lb:heat-1995", 949, "letterboxd", title="Heat", year=1995)
    store.set_id("lb:heat-1986", 949, "letterboxd", title="Heat", year=1986)  # year differs
    store.set_id("lb:heat-1994", 949, "letterboxd", title="Heat", year=1994)  # one year apart is fine
    store.set_id("title:alien|1979", 1, "search", title="Alien", year=1979)
    store.set_id("lb:unknown", None, "search", title="Unknown Film", year=2001)
    store.set_id("lb:fixed", 949, "manual", title="Fixed", year=1990)


class TestReasons:
    def test_uncertain_ones_first_and_certain_hidden(self, store):
        fill(store)
        rows = matches.list_matches(store)
        assert [(row["film_key"], row["reason"]) for row in rows] == [
            ("title:alien|1979", "search"),
            ("lb:heat-1986", "year"),
            ("lb:unknown", "not_found"),
        ]
        heat = rows[1]
        assert (heat["tmdb_title"], heat["tmdb_year"]) == ("Heat", 1995)
        assert heat["letterboxd_url"] == "https://letterboxd.com/film/heat-1986/"
        assert heat["tmdb_url"] == "https://www.themoviedb.org/movie/949"

    def test_show_all_includes_certain_and_manual(self, store):
        fill(store)
        rows = {row["film_key"]: row for row in matches.list_matches(store, include_certain=True)}
        assert rows["lb:heat-1995"]["reason"] is None
        assert rows["lb:fixed"]["reason"] is None and rows["lb:fixed"]["source"] == "manual"

    def test_entries_not_seen_for_long_are_left_out(self, store):
        store.set_id("lb:old", None, "search", checked_at=time.time() - 90 * 86400, title="Old")
        assert matches.list_matches(store) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("603", 603),
        (" https://www.themoviedb.org/movie/603-the-matrix ", 603),
        ("themoviedb.org/movie/42?language=de", 42),
        (603, 603),
        ("0", None),
        ("matrix", None),
        (None, None),
        (-3, None),
    ],
)
def test_parse_tmdb_reference(text, expected):
    assert matches.parse_tmdb_reference(text) == expected


class TestCorrection:
    def test_correct_and_reset(self, store):
        fill(store)
        with patch("watchlist_app.tmdb.get_movie_bundle", return_value=HEAT) as fetched:
            corrected = matches.correct_match(store, "title:alien|1979", 949, "key")
        fetched.assert_called_once_with(949, "key")
        assert corrected == {"tmdb_id": 949, "tmdb_title": "Heat", "tmdb_year": 1995}
        assert store.get_id("title:alien|1979")["source"] == "manual"
        assert matches.changed_since(store, time.time() - 5)
        matches.reset_match(store, "title:alien|1979")
        assert store.get_id("title:alien|1979") is None

    def test_unknown_entry_or_id_is_refused(self, store):
        fill(store)
        with pytest.raises(ValueError, match="unknown"):
            matches.correct_match(store, "lb:nothing", 949, "key")
        with patch("watchlist_app.tmdb.get_movie_bundle", return_value=None):
            with pytest.raises(ValueError, match="no film with the id 5"):
                matches.correct_match(store, "lb:unknown", 5, "key")
        assert store.get_id("lb:unknown")["tmdb_id"] is None

    def test_a_correction_is_used_by_the_next_scan(self, store):
        entries = [WatchlistEntry("Heat", 1995, "heat-1995")]
        wrong = {**HEAT, "details": {**HEAT["details"], "tmdb_title": "Heat 2"}}
        with (
            patch("watchlist_app.letterboxd.fetch_tmdb_id", return_value=111),
            patch("watchlist_app.tmdb.get_movie_bundle", return_value=wrong),
        ):
            first = perform_scan(store, entries, "src", "DE", "key")
        assert first.results[0]["key"] == "111"
        with patch("watchlist_app.tmdb.get_movie_bundle", return_value=HEAT):
            matches.correct_match(store, "lb:heat-1995", 949, "key")
            again = perform_scan(store, entries, "src", "DE", "key")
        # The recent scan is not reused after a correction, and the manual id is kept.
        assert not again.reused
        assert again.results[0]["key"] == "949"
        assert store.get_id("lb:heat-1995")["source"] == "manual"
        assert store.list_matches()[0]["last_seen"] >= first.created
