"""
Tests pour watchlist_availability.py

Toutes les interactions réseau et fichier sont mockées — aucune clé API réelle requise.
"""

import io
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

import watchlist_availability as wa


# =========================
# Fixtures
# =========================

FAKE_API_KEY = "fake_key_for_tests"


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    """Injecte une clé API factice pour tous les tests."""
    monkeypatch.setattr(wa, "TMDB_API_KEY", FAKE_API_KEY)


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Construit un objet Response mocké."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    if status_code >= 400:
        mock.raise_for_status.side_effect = requests.HTTPError(response=mock)
    else:
        mock.raise_for_status.return_value = None
    return mock


# =========================
# get_tmdb_id
# =========================


class TestGetTmdbId:
    def test_found(self):
        mock_resp = _mock_response({"results": [{"id": 42}]})
        with patch("watchlist_availability.requests.get", return_value=mock_resp):
            result = wa.get_tmdb_id("Inception", 2010, api_key=FAKE_API_KEY)
        assert result == 42

    def test_not_found_empty_results(self):
        mock_resp = _mock_response({"results": []})
        with patch("watchlist_availability.requests.get", return_value=mock_resp):
            result = wa.get_tmdb_id("Film Inexistant XYZ", 1900, api_key=FAKE_API_KEY)
        assert result is None

    def test_network_error_returns_none(self):
        with patch(
            "watchlist_availability.requests.get",
            side_effect=requests.ConnectionError("timeout"),
        ):
            result = wa.get_tmdb_id("Inception", 2010, api_key=FAKE_API_KEY)
        assert result is None

    def test_rate_limit_retries_and_succeeds(self):
        mock_429 = _mock_response({}, status_code=429)
        mock_ok = _mock_response({"results": [{"id": 7}]})
        with patch(
            "watchlist_availability.requests.get", side_effect=[mock_429, mock_ok]
        ), patch("watchlist_availability.time.sleep"):
            result = wa.get_tmdb_id("Interstellar", 2014, api_key=FAKE_API_KEY)
        assert result == 7

    def test_rate_limit_twice_returns_none(self):
        mock_429 = _mock_response({}, status_code=429)
        with patch(
            "watchlist_availability.requests.get", side_effect=[mock_429, mock_429]
        ), patch("watchlist_availability.time.sleep"):
            result = wa.get_tmdb_id("Interstellar", 2014, api_key=FAKE_API_KEY)
        assert result is None

    def test_uses_module_level_key_when_none_passed(self):
        mock_resp = _mock_response({"results": [{"id": 1}]})
        with patch("watchlist_availability.requests.get", return_value=mock_resp) as mock_get:
            wa.get_tmdb_id("Alien", 1979)
        call_params = mock_get.call_args[1]["params"]
        assert call_params["api_key"] == FAKE_API_KEY


# =========================
# get_streaming_platforms
# =========================


class TestGetStreamingPlatforms:
    def test_netflix_in_flatrate(self):
        data = {
            "results": {
                "FR": {"flatrate": [{"provider_name": "Netflix"}, {"provider_name": "Disney+"}]}
            }
        }
        mock_resp = _mock_response(data)
        with patch("watchlist_availability.requests.get", return_value=mock_resp):
            result = wa.get_streaming_platforms(42, country="FR", api_key=FAKE_API_KEY)
        assert "Netflix" in result
        assert "Disney+" in result

    def test_country_not_in_results(self):
        data = {"results": {"US": {"flatrate": [{"provider_name": "Netflix"}]}}}
        mock_resp = _mock_response(data)
        with patch("watchlist_availability.requests.get", return_value=mock_resp):
            result = wa.get_streaming_platforms(42, country="FR", api_key=FAKE_API_KEY)
        assert result == set()

    def test_no_flatrate_key(self):
        data = {"results": {"FR": {"rent": [{"provider_name": "Amazon"}]}}}
        mock_resp = _mock_response(data)
        with patch("watchlist_availability.requests.get", return_value=mock_resp):
            result = wa.get_streaming_platforms(42, country="FR", api_key=FAKE_API_KEY)
        assert result == set()

    def test_network_error_returns_empty_set(self):
        with patch(
            "watchlist_availability.requests.get",
            side_effect=requests.ConnectionError("timeout"),
        ):
            result = wa.get_streaming_platforms(42, country="FR", api_key=FAKE_API_KEY)
        assert result == set()

    def test_http_error_returns_empty_set(self):
        mock_resp = _mock_response({}, status_code=500)
        with patch("watchlist_availability.requests.get", return_value=mock_resp):
            result = wa.get_streaming_platforms(42, country="FR", api_key=FAKE_API_KEY)
        assert result == set()


# =========================
# load_watchlist
# =========================


class TestLoadWatchlist:
    def _csv_path(self, content: str, tmp_path: Path) -> Path:
        p = tmp_path / "watchlist-2024-01-01.csv"
        p.write_text(content)
        return p

    def test_valid_csv(self, tmp_path):
        csv = self._csv_path("Name,Year,Rating\nInception,2010,5\nAlien,1979,4", tmp_path)
        df = wa.load_watchlist(csv)
        assert len(df) == 2
        assert list(df.columns) == ["Name", "Year", "Rating"]

    def test_missing_name_column(self, tmp_path):
        csv = self._csv_path("Title,Year\nInception,2010", tmp_path)
        with pytest.raises(ValueError, match="Name"):
            wa.load_watchlist(csv)

    def test_missing_year_column(self, tmp_path):
        csv = self._csv_path("Name,Date\nInception,2010-01-01", tmp_path)
        with pytest.raises(ValueError, match="Year"):
            wa.load_watchlist(csv)

    def test_missing_both_columns(self, tmp_path):
        csv = self._csv_path("Title,Date\nInception,2010-01-01", tmp_path)
        with pytest.raises(ValueError):
            wa.load_watchlist(csv)


# =========================
# find_watchlist_csv
# =========================


class TestFindWatchlistCsv:
    def test_returns_most_recent(self, tmp_path):
        older = tmp_path / "watchlist-2023-01-01.csv"
        newer = tmp_path / "watchlist-2024-06-15.csv"
        older.write_text("Name,Year")
        time.sleep(0.01)
        newer.write_text("Name,Year")
        result = wa.find_watchlist_csv(downloads_dir=tmp_path)
        assert result == newer

    def test_no_csv_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            wa.find_watchlist_csv(downloads_dir=tmp_path)

    def test_ignores_non_watchlist_csv(self, tmp_path):
        (tmp_path / "export.csv").write_text("Name,Year")
        with pytest.raises(FileNotFoundError):
            wa.find_watchlist_csv(downloads_dir=tmp_path)


# =========================
# build_results
# =========================


class TestBuildResults:
    def _df(self, rows):
        return pd.DataFrame(rows, columns=["Name", "Year"])

    def test_film_on_netflix_included(self):
        df = self._df([("Inception", 2010)])
        targets = {"Netflix": "nfx"}
        with patch("watchlist_availability.get_tmdb_id", return_value=1), patch(
            "watchlist_availability.get_streaming_platforms", return_value={"Netflix"}
        ), patch("watchlist_availability.time.sleep"):
            results = wa.build_results(df, streaming_targets=targets, api_key=FAKE_API_KEY)
        assert len(results) == 1
        assert results[0]["Netflix"] == "X"
        assert results[0]["Titre"] == "Inception"

    def test_film_not_on_targets_excluded(self):
        df = self._df([("Inception", 2010)])
        targets = {"Netflix": "nfx"}
        with patch("watchlist_availability.get_tmdb_id", return_value=1), patch(
            "watchlist_availability.get_streaming_platforms", return_value={"Disney+"}
        ), patch("watchlist_availability.time.sleep"):
            results = wa.build_results(df, streaming_targets=targets, api_key=FAKE_API_KEY)
        assert results == []

    def test_tmdb_id_not_found_skipped(self):
        df = self._df([("Film Inconnu XYZ", 1900)])
        with patch("watchlist_availability.get_tmdb_id", return_value=None), patch(
            "watchlist_availability.time.sleep"
        ):
            results = wa.build_results(df, api_key=FAKE_API_KEY)
        assert results == []

    def test_multiple_platforms(self):
        df = self._df([("Alien", 1979)])
        targets = {"Netflix": "nfx", "Canal+": "cpl"}
        with patch("watchlist_availability.get_tmdb_id", return_value=5), patch(
            "watchlist_availability.get_streaming_platforms",
            return_value={"Netflix", "Canal+"},
        ), patch("watchlist_availability.time.sleep"):
            results = wa.build_results(df, streaming_targets=targets, api_key=FAKE_API_KEY)
        assert results[0]["Netflix"] == "X"
        assert results[0]["Canal+"] == "X"


# =========================
# display_results
# =========================


class TestDisplayResults:
    def test_empty_results_prints_message(self, capsys):
        wa.display_results([])
        out = capsys.readouterr().out
        assert "Aucun film" in out

    def test_results_displayed(self, capsys):
        results = [{"Titre": "Inception", "Année": 2010, "Netflix": "X", "Canal+": ""}]
        targets = {"Netflix": "nfx", "Canal+": "cpl"}
        wa.display_results(results, streaming_targets=targets)
        out = capsys.readouterr().out
        assert "Inception" in out

    def test_netflix_sorted_first(self, capsys):
        results = [
            {"Titre": "Film A", "Année": 2020, "Netflix": "", "Canal+": "X"},
            {"Titre": "Film B", "Année": 2021, "Netflix": "X", "Canal+": ""},
        ]
        targets = {"Netflix": "nfx", "Canal+": "cpl"}
        wa.display_results(results, streaming_targets=targets)
        out = capsys.readouterr().out
        assert out.index("Film B") < out.index("Film A")


# =========================
# main
# =========================


class TestMain:
    def test_raises_if_no_api_key(self, monkeypatch):
        monkeypatch.setattr(wa, "TMDB_API_KEY", None)
        with pytest.raises(EnvironmentError, match="TMDB_API_KEY"):
            wa.main()

    def test_full_pipeline(self, tmp_path, capsys):
        csv = tmp_path / "watchlist-2024-01-01.csv"
        csv.write_text("Name,Year\nInception,2010\n")

        with patch("watchlist_availability.find_watchlist_csv", return_value=csv), patch(
            "watchlist_availability.get_tmdb_id", return_value=27205
        ), patch(
            "watchlist_availability.get_streaming_platforms", return_value={"Netflix"}
        ), patch(
            "watchlist_availability.time.sleep"
        ):
            wa.main()

        out = capsys.readouterr().out
        assert "Inception" in out
