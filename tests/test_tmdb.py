from unittest.mock import patch

import pytest
import requests

from tests.helpers import API_KEY, MOVIE, response
from watchlist_app import tmdb


class TestMovieBundle:
    def test_single_request_returns_details_and_all_countries(self):
        with patch("watchlist_app.tmdb._http_get", return_value=response(MOVIE)) as get:
            bundle = tmdb.get_movie_bundle(27205, API_KEY)
        assert get.call_count == 1
        assert get.call_args[1]["params"]["append_to_response"] == "videos,watch/providers"
        assert bundle["poster_path"] == "/p.jpg"
        assert bundle["details"]["runtime"] == 148
        assert bundle["details"]["release_date"] == "2010-07-15"
        assert bundle["details"]["trailer_url"].endswith("v=abc")
        assert bundle["providers"]["DE"] == {
            "Netflix": ["flatrate", "rent"],
            "Apple TV Store": ["rent"],
        }
        assert bundle["providers"]["US"] == {"Pluto TV": ["ads"]}

    def test_buy_only_country_is_left_out(self):
        with patch("watchlist_app.tmdb._http_get", return_value=response(MOVIE)):
            bundle = tmdb.get_movie_bundle(27205, API_KEY)
        assert "FR" not in bundle["providers"]

    def test_unknown_id_returns_none(self):
        with patch("watchlist_app.tmdb._http_get", return_value=response(status_code=404)):
            assert tmdb.get_movie_bundle(1, API_KEY) is None

    def test_rate_limit_is_retried(self):
        responses = [response(status_code=429, headers={"Retry-After": "1"}), response(MOVIE)]
        with (
            patch("watchlist_app.tmdb._http_get", side_effect=responses),
            patch("watchlist_app.tmdb.time.sleep") as sleep,
        ):
            bundle = tmdb.get_movie_bundle(27205, API_KEY)
        assert bundle is not None
        sleep.assert_called_once_with(1.0)

    def test_persistent_rate_limit_raises(self):
        with (
            patch("watchlist_app.tmdb._http_get", return_value=response(status_code=429)),
            patch("watchlist_app.tmdb.time.sleep"),
        ):
            with pytest.raises(tmdb.TmdbError, match="rate limit"):
                tmdb.get_movie_bundle(27205, API_KEY)

    def test_network_error_raises_without_leaking_the_key(self):
        error = requests.ConnectionError(f"https://api.example/?api_key={API_KEY}")
        with patch("watchlist_app.tmdb._http_get", side_effect=error), patch("watchlist_app.tmdb.time.sleep"):
            with pytest.raises(tmdb.TmdbError) as raised:
                tmdb.get_movie_bundle(27205, API_KEY)
        assert API_KEY not in str(raised.value)

    def test_timeout_is_retried_then_raises(self):
        with (
            patch("watchlist_app.tmdb._http_get", side_effect=requests.Timeout("slow")) as get,
            patch("watchlist_app.tmdb.time.sleep"),
        ):
            with pytest.raises(tmdb.TmdbError, match="Timeout"):
                tmdb.get_movie_bundle(27205, API_KEY)
        assert get.call_count == tmdb._MAX_ATTEMPTS

    def test_client_error_raises(self):
        with patch("watchlist_app.tmdb._http_get", return_value=response(status_code=401)):
            with pytest.raises(tmdb.TmdbError, match="401"):
                tmdb.get_movie_bundle(27205, API_KEY)


class TestSearchMovieId:
    def test_first_hit(self):
        with patch(
            "watchlist_app.tmdb._http_get",
            return_value=response({"results": [{"id": 5}, {"id": 6}]}),
        ) as get:
            assert tmdb.search_movie_id("Alien", 1979.0, API_KEY) == 5
        assert get.call_args[1]["params"]["year"] == 1979

    def test_no_hit(self):
        with patch("watchlist_app.tmdb._http_get", return_value=response({"results": []})):
            assert tmdb.search_movie_id("Nope", None, API_KEY) is None

    def test_year_omitted_when_missing(self):
        with patch("watchlist_app.tmdb._http_get", return_value=response({"results": []})) as get:
            tmdb.search_movie_id("Nope", None, API_KEY)
        assert "year" not in get.call_args[1]["params"]

    def test_exact_title_and_year_beat_the_first_hit(self):
        hits = [
            {"id": 1, "title": "Alien Resurrection", "release_date": "1997-11-12"},
            {"id": 348, "title": "Alien", "original_title": "Alien", "release_date": "1979-05-25"},
        ]
        with patch("watchlist_app.tmdb._http_get", return_value=response({"results": hits})):
            assert tmdb.search_movie_id("alien", 1979, API_KEY) == 348

    def test_candidates(self):
        hits = [
            {"id": 348, "title": "Alien", "release_date": "1979-05-25", "poster_path": "/a.jpg"},
            {"title": "x"},
        ]
        with patch("watchlist_app.tmdb._http_get", return_value=response({"results": hits})):
            found = tmdb.search_movies("Alien", api_key=API_KEY)
        assert found == [
            {
                "tmdb_id": 348,
                "title": "Alien",
                "original_title": "",
                "year": 1979,
                "poster_path": "/a.jpg",
                "overview": "",
            }
        ]


@pytest.mark.provider_catalog
def test_region_providers():
    data = {
        "results": [
            {"provider_name": "Netflix", "logo_path": "/n.jpg", "display_priorities": {"DE": 3}},
            {"provider_name": "Joyn Plus", "display_priority": 40},
            {"logo_path": "/nameless.jpg"},
        ]
    }
    with patch("watchlist_app.tmdb._http_get", return_value=response(data)) as get:
        found = tmdb.get_region_providers("DE", API_KEY)
    assert get.call_args[1]["params"]["watch_region"] == "DE"
    assert found == [
        {"name": "Netflix", "logo_path": "/n.jpg", "priority": 3},
        {"name": "Joyn Plus", "logo_path": None, "priority": 40},
    ]


def test_details_carry_the_tmdb_title():
    with patch("watchlist_app.tmdb._http_get", return_value=response({**MOVIE, "title": "Inception"})):
        assert tmdb.get_movie_bundle(27205, API_KEY)["details"]["tmdb_title"] == "Inception"


class TestSessionReuse:
    def test_same_thread_reuses_one_session(self):
        tmdb._LOCAL.__dict__.pop("session", None)
        with patch("watchlist_app.tmdb.requests.Session") as session_class:
            tmdb._http_get("https://example.invalid/a")
            tmdb._http_get("https://example.invalid/b")
        assert session_class.call_count == 1
        assert session_class.return_value.get.call_count == 2
        tmdb._LOCAL.__dict__.pop("session", None)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1993, 1993),
        (1993.0, 1993),
        ("1993", 1993),
        ("1993.0", 1993),
        ("", None),
        (None, None),
        (float("nan"), None),
    ],
)
def test_clean_year(value, expected):
    assert tmdb.clean_year(value) == expected
