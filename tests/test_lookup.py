from unittest.mock import patch

import pytest

from tests.helpers import API_KEY, BUNDLE
from watchlist_app import lookup, tmdb
from watchlist_app.store import Store


@pytest.fixture
def store():
    database = Store(":memory:")
    yield database
    database.close()


class TestLookupFilm:
    def test_letterboxd_id_preferred_over_search(self, store):
        with (
            patch("watchlist_app.letterboxd.fetch_tmdb_id", return_value=27205),
            patch("watchlist_app.tmdb.search_movie_id") as search,
            patch("watchlist_app.tmdb.get_movie_bundle", return_value=BUNDLE),
        ):
            film = lookup.lookup_film("Inception", 2010, "inception", "DE", API_KEY, store)
        search.assert_not_called()
        assert film["tmdb_id"] == 27205
        assert film["providers"] == {"Netflix": {"flatrate"}}
        assert film["details"]["runtime"] == 148
        assert store.get_id("lb:inception")["source"] == "letterboxd"

    def test_falls_back_to_search_without_slug_or_letterboxd_id(self, store):
        with (
            patch("watchlist_app.letterboxd.fetch_tmdb_id", return_value=None),
            patch("watchlist_app.tmdb.search_movie_id", return_value=7) as search,
            patch("watchlist_app.tmdb.get_movie_bundle", return_value=BUNDLE),
        ):
            with_slug = lookup.lookup_film("Alien", 1979, "alien", "DE", API_KEY, store)
            without_slug = lookup.lookup_film("Heat", 1995, None, "DE", API_KEY, store)
        assert with_slug["tmdb_id"] == 7 and without_slug["tmdb_id"] == 7
        assert search.call_count == 2

    def test_second_lookup_makes_no_request(self, store):
        with (
            patch("watchlist_app.letterboxd.fetch_tmdb_id", return_value=1) as letterboxd_id,
            patch("watchlist_app.tmdb.get_movie_bundle", return_value=BUNDLE) as bundle,
        ):
            lookup.lookup_film("Inception", 2010, "inception", "DE", API_KEY, store)
            again = lookup.lookup_film("Inception", 2010, "inception", "DE", API_KEY, store)
        assert letterboxd_id.call_count == 1
        assert bundle.call_count == 1
        assert again["providers"] == {"Netflix": {"flatrate"}}
        assert again["details"]["runtime"] == 148

    def test_other_country_served_from_cache(self, store):
        with (
            patch("watchlist_app.letterboxd.fetch_tmdb_id", return_value=1),
            patch("watchlist_app.tmdb.get_movie_bundle", return_value=BUNDLE) as bundle,
        ):
            lookup.lookup_film("Inception", 2010, "inception", "DE", API_KEY, store)
            us = lookup.lookup_film("Inception", 2010, "inception", "US", API_KEY, store)
            gb = lookup.lookup_film("Inception", 2010, "inception", "GB", API_KEY, store)
        assert bundle.call_count == 1
        assert us["providers"] == {"Hulu": {"ads"}}
        assert gb["providers"] == {}

    def test_release_dates_of_the_scanned_country(self, store):
        bundle = {
            **BUNDLE,
            "details": {**BUNDLE["details"], "release_dates": {"DE": {"certification": "12"}}},
        }
        with (
            patch("watchlist_app.letterboxd.fetch_tmdb_id", return_value=1),
            patch("watchlist_app.tmdb.get_movie_bundle", return_value=bundle),
        ):
            de = lookup.lookup_film("Inception", 2010, "inception", "DE", API_KEY, store)
            us = lookup.lookup_film("Inception", 2010, "inception", "US", API_KEY, store)
        assert de["release"] == {"certification": "12"}
        assert us["release"] == {}

    @pytest.mark.letterboxd_rating
    def test_letterboxd_rating_loaded_once_a_month(self, store):
        with (
            patch("watchlist_app.letterboxd.fetch_tmdb_id", return_value=1),
            patch("watchlist_app.letterboxd.fetch_rating", return_value=4.3) as rating,
            patch("watchlist_app.tmdb.search_movie_id", return_value=2),
            patch("watchlist_app.tmdb.get_movie_bundle", return_value=BUNDLE),
        ):
            first = lookup.lookup_film("Inception", 2010, "inception", "DE", API_KEY, store)
            again = lookup.lookup_film("Inception", 2010, "inception", "DE", API_KEY, store)
            without_slug = lookup.lookup_film("Heat", 1995, None, "DE", API_KEY, store)
        assert rating.call_count == 1
        assert first["letterboxd_rating"] == again["letterboxd_rating"] == 4.3
        assert without_slug["letterboxd_rating"] is None

    @pytest.mark.letterboxd_rating
    def test_letterboxd_failure_keeps_the_film(self, store):
        from watchlist_app import letterboxd

        with (
            patch("watchlist_app.letterboxd.fetch_tmdb_id", return_value=1),
            patch("watchlist_app.letterboxd.fetch_rating", side_effect=letterboxd.LetterboxdError("429")),
            patch("watchlist_app.tmdb.get_movie_bundle", return_value=BUNDLE),
        ):
            found = lookup.lookup_film("Inception", 2010, "inception", "DE", API_KEY, store)
        assert found["tmdb_id"] == 1 and found["letterboxd_rating"] is None
        assert store.get_id("lb:inception")["lb_checked_at"] is None

    def test_details_in_an_older_format_are_refetched(self, store):
        old = {**BUNDLE, "details": {"runtime": 148}}
        with (
            patch("watchlist_app.letterboxd.fetch_tmdb_id", return_value=1),
            patch("watchlist_app.tmdb.get_movie_bundle", side_effect=[old, BUNDLE]) as bundle,
        ):
            lookup.lookup_film("Inception", 2010, "inception", "DE", API_KEY, store)
            again = lookup.lookup_film("Inception", 2010, "inception", "DE", API_KEY, store)
        assert bundle.call_count == 2
        assert again["details"]["origin_countries"] == []

    def test_stale_providers_refetched_but_id_kept(self, store):
        with (
            patch("watchlist_app.letterboxd.fetch_tmdb_id", return_value=1) as letterboxd_id,
            patch("watchlist_app.tmdb.get_movie_bundle", return_value=BUNDLE) as bundle,
        ):
            lookup.lookup_film("Inception", 2010, "inception", "DE", API_KEY, store)
            lookup.lookup_film("Inception", 2010, "inception", "DE", API_KEY, store, providers_ttl=0)
        assert letterboxd_id.call_count == 1
        assert bundle.call_count == 2

    def test_not_found_is_remembered(self, store):
        with patch("watchlist_app.tmdb.search_movie_id", return_value=None) as search:
            assert lookup.lookup_film("Nope", 1900, None, "DE", API_KEY, store) is None
            assert lookup.lookup_film("Nope", 1900, None, "DE", API_KEY, store) is None
        assert search.call_count == 1

    def test_tmdb_failure_is_not_cached(self, store):
        with patch("watchlist_app.tmdb.search_movie_id", side_effect=tmdb.TmdbError("down")):
            with pytest.raises(tmdb.TmdbError):
                lookup.lookup_film("Heat", 1995, None, "DE", API_KEY, store)
        assert store.get_id(lookup.film_key("Heat", 1995, None)) is None

    def test_bundle_failure_keeps_id_and_retries_later(self, store):
        with (
            patch("watchlist_app.tmdb.search_movie_id", return_value=3) as search,
            patch("watchlist_app.tmdb.get_movie_bundle", side_effect=[tmdb.TmdbError("down"), BUNDLE]),
        ):
            with pytest.raises(tmdb.TmdbError):
                lookup.lookup_film("Heat", 1995, None, "DE", API_KEY, store)
            film = lookup.lookup_film("Heat", 1995, None, "DE", API_KEY, store)
        assert search.call_count == 1
        assert film["providers"] == {"Netflix": {"flatrate"}}

    def test_works_without_cache(self):
        with (
            patch("watchlist_app.tmdb.search_movie_id", return_value=3),
            patch("watchlist_app.tmdb.get_movie_bundle", return_value=BUNDLE),
        ):
            film = lookup.lookup_film("Heat", 1995, None, "DE", API_KEY)
        assert film["tmdb_id"] == 3
