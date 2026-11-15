"""Shared helpers for the tests. All network access is mocked."""

from unittest.mock import MagicMock

API_KEY = "fake_key_for_tests"


def response(json_data=None, status_code=200, headers=None, text=""):
    """A mocked requests.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.ok = status_code < 400
    mock.json.return_value = json_data or {}
    mock.headers = headers or {}
    mock.text = text
    return mock


MOVIE = {
    "id": 27205,
    "overview": "A thief.",
    "vote_average": 8.4,
    "backdrop_path": "/b.jpg",
    "poster_path": "/p.jpg",
    "runtime": 148,
    "release_date": "2010-07-15",
    "genres": [{"name": "Action"}],
    "videos": {"results": [{"site": "YouTube", "type": "Trailer", "key": "abc"}]},
    "watch/providers": {
        "results": {
            "DE": {
                "link": "https://example.invalid",
                "flatrate": [{"provider_name": "Netflix"}],
                "rent": [{"provider_name": "Netflix"}, {"provider_name": "Apple TV Store"}],
                "buy": [{"provider_name": "Apple TV Store"}],
            },
            "US": {"ads": [{"provider_name": "Pluto TV"}]},
            "FR": {"buy": [{"provider_name": "Canal VOD"}]},
        }
    },
}

BUNDLE: dict = {
    "poster_path": "/p.jpg",
    "details": {"runtime": 148, "genres": ["Action"], "overview": "A thief.", "rating": 8.4},
    "providers": {"DE": {"Netflix": ["flatrate"]}, "US": {"Hulu": ["ads"]}},
}
