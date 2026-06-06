"""
Tests for watchlist_availability.py

All network and file interactions are mocked — no real API key required.
"""

import time
import zipfile
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
    """Inject a fake API key for all tests."""
    monkeypatch.setattr(wa, "TMDB_API_KEY", FAKE_API_KEY)


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Build a mocked Response object."""
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

    def test_year_included_when_present(self):
        mock_resp = _mock_response({"results": [{"id": 1}]})
        with patch("watchlist_availability.requests.get", return_value=mock_resp) as mock_get:
            wa.get_tmdb_id("Inception", 2010, api_key=FAKE_API_KEY)
        assert mock_get.call_args[1]["params"]["year"] == 2010

    def test_year_omitted_when_missing(self):
        mock_resp = _mock_response({"results": [{"id": 1}]})
        for missing in (None, float("nan")):
            with patch("watchlist_availability.requests.get", return_value=mock_resp) as mock_get:
                wa.get_tmdb_id("Ray Gunn", missing, api_key=FAKE_API_KEY)
            assert "year" not in mock_get.call_args[1]["params"]

    def test_float_year_coerced_to_int(self):
        mock_resp = _mock_response({"results": [{"id": 1}]})
        with patch("watchlist_availability.requests.get", return_value=mock_resp) as mock_get:
            wa.get_tmdb_id("Inception", 2010.0, api_key=FAKE_API_KEY)
        assert mock_get.call_args[1]["params"]["year"] == 2010


# =========================
# get_streaming_platforms
# =========================


class TestGetStreamingPlatforms:
    def test_netflix_in_flatrate(self):
        data = {
            "results": {
                "FR": {"flatrate": [{"provider_name": "Netflix"}, {"provider_name": "Disney Plus"}]}
            }
        }
        mock_resp = _mock_response(data)
        with patch("watchlist_availability.requests.get", return_value=mock_resp):
            result = wa.get_streaming_platforms(42, country="FR", api_key=FAKE_API_KEY)
        assert result["Netflix"] == {"flatrate"}
        assert result["Disney Plus"] == {"flatrate"}

    def test_free_ads_flatrate_tracked(self):
        data = {
            "results": {
                "FR": {
                    "flatrate": [{"provider_name": "Netflix"}],
                    "free": [{"provider_name": "Arte"}],
                    "ads": [{"provider_name": "Pluto TV"}],
                }
            }
        }
        mock_resp = _mock_response(data)
        with patch("watchlist_availability.requests.get", return_value=mock_resp):
            result = wa.get_streaming_platforms(42, country="FR", api_key=FAKE_API_KEY)
        assert result == {"Netflix": {"flatrate"}, "Arte": {"free"}, "Pluto TV": {"ads"}}

    def test_rent_category_tracked(self):
        data = {
            "results": {
                "FR": {"rent": [{"provider_name": "Canal VOD"}, {"provider_name": "Google Play Movies"}]}
            }
        }
        mock_resp = _mock_response(data)
        with patch("watchlist_availability.requests.get", return_value=mock_resp):
            result = wa.get_streaming_platforms(42, country="FR", api_key=FAKE_API_KEY)
        assert result["Canal VOD"] == {"rent"}
        assert result["Google Play Movies"] == {"rent"}

    def test_provider_in_multiple_categories(self):
        # M6+ offers the film both free-with-ads and by subscription.
        data = {
            "results": {
                "FR": {
                    "ads": [{"provider_name": "M6+"}],
                    "flatrate": [{"provider_name": "M6+"}],
                }
            }
        }
        mock_resp = _mock_response(data)
        with patch("watchlist_availability.requests.get", return_value=mock_resp):
            result = wa.get_streaming_platforms(42, country="FR", api_key=FAKE_API_KEY)
        assert result["M6+"] == {"ads", "flatrate"}

    def test_buy_category_excluded(self):
        data = {
            "results": {
                "FR": {"buy": [{"provider_name": "Apple TV Store"}]}
            }
        }
        mock_resp = _mock_response(data)
        with patch("watchlist_availability.requests.get", return_value=mock_resp):
            result = wa.get_streaming_platforms(42, country="FR", api_key=FAKE_API_KEY)
        assert result == {}

    def test_country_not_in_results(self):
        data = {"results": {"US": {"flatrate": [{"provider_name": "Netflix"}]}}}
        mock_resp = _mock_response(data)
        with patch("watchlist_availability.requests.get", return_value=mock_resp):
            result = wa.get_streaming_platforms(42, country="FR", api_key=FAKE_API_KEY)
        assert result == {}

    def test_network_error_returns_empty_dict(self):
        with patch(
            "watchlist_availability.requests.get",
            side_effect=requests.ConnectionError("timeout"),
        ):
            result = wa.get_streaming_platforms(42, country="FR", api_key=FAKE_API_KEY)
        assert result == {}

    def test_http_error_returns_empty_dict(self):
        mock_resp = _mock_response({}, status_code=500)
        with patch("watchlist_availability.requests.get", return_value=mock_resp):
            result = wa.get_streaming_platforms(42, country="FR", api_key=FAKE_API_KEY)
        assert result == {}


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

    def test_accepts_letterboxd_export_name_without_dash(self, tmp_path):
        # The Letterboxd export is named 'watchlist.csv' (no dash).
        plain = tmp_path / "watchlist.csv"
        plain.write_text("Name,Year")
        result = wa.find_watchlist_csv(downloads_dir=tmp_path)
        assert result == plain


# =========================
# load_platforms_config
# =========================


class TestLoadPlatformsConfig:
    def test_returns_defaults_when_no_file(self, tmp_path):
        targets = wa.load_platforms_config("FR", toml_path=tmp_path / "missing.toml")
        assert "Arte" in targets
        assert "Netflix" in targets

    def test_reads_enabled_only(self, tmp_path):
        toml = tmp_path / "platforms.toml"
        toml.write_text(
            '[FR]\nArte = true\nMolotov = false\n'
            'Netflix = true\n"Canal+" = false\n"TF1+" = true\n'
        )
        targets = wa.load_platforms_config("FR", toml_path=toml)
        assert "Arte" in targets
        assert "Molotov" not in targets
        assert "Netflix" in targets
        assert "Canal+" not in targets
        assert "TF1+" in targets

    def test_unknown_key_ignored(self, tmp_path):
        toml = tmp_path / "platforms.toml"
        toml.write_text("[FR]\nInconnu = true\nNetflix = true\n")
        targets = wa.load_platforms_config("FR", toml_path=toml)
        assert "Inconnu" not in targets
        assert "Netflix" in targets

    def test_values_are_tmdb_names(self, tmp_path):
        toml = tmp_path / "platforms.toml"
        toml.write_text('[FR]\n"Prime Video" = true\n')
        targets = wa.load_platforms_config("FR", toml_path=toml)
        assert targets["Prime Video"] == "Amazon Prime Video"

    def test_falls_back_to_defaults_when_country_section_missing(self, tmp_path):
        toml = tmp_path / "platforms.toml"
        toml.write_text("[US]\nNetflix = true\n")
        targets = wa.load_platforms_config("FR", toml_path=toml)
        assert "Arte" in targets  # no [FR] → fallback to defaults

    def test_different_country_section(self, tmp_path):
        toml = tmp_path / "platforms.toml"
        toml.write_text("[US]\nHulu = true\nNetflix = true\n[FR]\nArte = true\n")
        us = wa.load_platforms_config("US", toml_path=toml)
        fr = wa.load_platforms_config("FR", toml_path=toml)
        assert "Hulu" in us and "Hulu" not in fr
        assert "Arte" in fr and "Arte" not in us


# =========================
# build_results
# =========================


class TestBuildResults:
    def _df(self, rows):
        return pd.DataFrame(rows, columns=["Name", "Year"])

    def _run(self, df, targets, providers):
        with patch("watchlist_availability.get_tmdb_id", return_value=1), patch(
            "watchlist_availability.get_streaming_platforms", return_value=providers
        ), patch("watchlist_availability.time.sleep"):
            return wa.build_results(df, targets, api_key=FAKE_API_KEY)

    def test_film_on_netflix_records_monetization(self):
        results = self._run(
            self._df([("Inception", 2010)]),
            {"Netflix": "Netflix"},
            {"Netflix": {"flatrate"}},
        )
        assert len(results) == 1
        assert results[0]["Netflix"] == {"flatrate"}
        assert results[0]["Title"] == "Inception"

    def test_film_on_arte_records_free(self):
        results = self._run(
            self._df([("Un Film", 2020)]),
            {"Arte": "Arte"},
            {"Arte": {"free"}},
        )
        assert results[0]["Arte"] == {"free"}

    def test_rent_only_film_kept(self):
        results = self._run(
            self._df([("Inception", 2010)]),
            {"TF1+": "TF1+"},
            {"TF1+": {"rent"}},
        )
        assert results[0]["TF1+"] == {"rent"}

    def test_multiple_monetization_types_recorded(self):
        results = self._run(
            self._df([("Un Film", 2020)]),
            {"M6+": "M6+"},
            {"M6+": {"ads", "flatrate"}},
        )
        assert results[0]["M6+"] == {"ads", "flatrate"}

    def test_provider_not_in_targets_excluded(self):
        results = self._run(
            self._df([("Inception", 2010)]),
            {"Netflix": "Netflix"},
            {"Disney Plus": {"flatrate"}},
        )
        assert results == []

    def test_tmdb_id_not_found_skipped(self):
        df = self._df([("Film Inconnu XYZ", 1900)])
        with patch("watchlist_availability.get_tmdb_id", return_value=None), patch(
            "watchlist_availability.time.sleep"
        ):
            results = wa.build_results(df, {"Netflix": "Netflix"}, api_key=FAKE_API_KEY)
        assert results == []

    def test_film_with_multiple_providers(self):
        results = self._run(
            self._df([("Alien", 1979)]),
            {"Arte": "Arte", "Netflix": "Netflix"},
            {"Arte": {"free"}, "Netflix": {"flatrate"}},
        )
        assert results[0]["Arte"] == {"free"}
        assert results[0]["Netflix"] == {"flatrate"}

    def test_prime_video_matched_by_tmdb_name(self):
        results = self._run(
            self._df([("Alien", 1979)]),
            {"Prime Video": "Amazon Prime Video"},
            {"Amazon Prime Video": {"flatrate"}},
        )
        assert results[0]["Prime Video"] == {"flatrate"}

    def test_empty_set_when_provider_absent(self):
        results = self._run(
            self._df([("Alien", 1979)]),
            {"Arte": "Arte", "Netflix": "Netflix"},
            {"Netflix": {"flatrate"}},
        )
        assert results[0]["Arte"] == set()
        assert results[0]["Netflix"] == {"flatrate"}


# =========================
# _split_by_section
# =========================


class TestSplitBySection:
    def _result(self, **checks):
        return [{"Title": "Film", "Year": 2020, **checks}]

    def test_free_section_from_free(self):
        sections = wa._split_by_section(self._result(Arte={"free"}), {"Arte": "Arte"})
        assert sections[0][0] == "Free"

    def test_free_section_from_ads(self):
        sections = wa._split_by_section(
            self._result(**{"Pluto TV": {"ads"}}), {"Pluto TV": "Pluto TV"}
        )
        assert sections[0][0] == "Free"

    def test_paid_section_from_flatrate(self):
        sections = wa._split_by_section(self._result(Netflix={"flatrate"}), {"Netflix": "Netflix"})
        assert sections[0][0] == "Paid"

    def test_paid_section_from_rent(self):
        sections = wa._split_by_section(
            self._result(**{"Canal VOD": {"rent"}}), {"Canal VOD": "Canal VOD"}
        )
        assert sections[0][0] == "Paid"

    def test_multi_monetization_appears_in_each_section(self):
        # M6+ available as ads + flatrate → appears in Free AND Paid.
        results = self._result(**{"M6+": {"ads", "flatrate"}})
        sections = wa._split_by_section(results, {"M6+": "M6+"})
        by_label = {s[0]: s for s in sections}
        assert "Free" in by_label and "Paid" in by_label
        assert by_label["Free"][1][0]["M6+"] == "✓"
        assert by_label["Paid"][1][0]["M6+"] == "✓"

    def test_same_provider_spans_sections_across_films(self):
        # TF1+ is free for one film, paid (subscription) for another.
        results = [
            {"Title": "A", "Year": 2020, "TF1+": {"ads"}},
            {"Title": "B", "Year": 2021, "TF1+": {"flatrate"}},
        ]
        labels = [s[0] for s in wa._split_by_section(results, {"TF1+": "TF1+"})]
        assert "Free" in labels and "Paid" in labels

    def test_section_order_free_then_paid(self):
        results = self._result(Arte={"free"}, Netflix={"flatrate"}, **{"Canal VOD": {"rent"}})
        targets = {"Canal VOD": "Canal VOD", "Netflix": "Netflix", "Arte": "Arte"}
        labels = [s[0] for s in wa._split_by_section(results, targets)]
        assert labels == ["Free", "Paid"]

    def test_all_blank_column_dropped(self):
        results = [{"Title": "Film", "Year": 2020, "Netflix": {"flatrate"}, "Arte": set()}]
        targets = {"Netflix": "Netflix", "Arte": "Arte"}
        labels = [s[0] for s in wa._split_by_section(results, targets)]
        assert "Free" not in labels      # Arte has no hit → no Free section
        assert "Paid" in labels

    def test_view_targets_keyed_display_to_tmdb(self):
        sections = wa._split_by_section(
            self._result(**{"Prime Video": {"flatrate"}}),
            {"Prime Video": "Amazon Prime Video"},
        )
        _, _, view_targets = sections[0]
        assert view_targets == {"Prime Video": "Amazon Prime Video"}


# =========================
# display_results
# =========================


class TestDisplayResults:
    def test_empty_results_prints_message(self, capsys):
        wa.display_results([])
        out = capsys.readouterr().out
        assert "No film" in out

    def test_free_section_shown(self, capsys):
        results = [{"Title": "Un Film", "Year": 2020, "Arte": {"free"}}]
        wa.display_results(results, targets={"Arte": "Arte"})
        out = capsys.readouterr().out
        assert "Free" in out
        assert "Un Film" in out

    def test_paid_section_shown_for_flatrate(self, capsys):
        results = [{"Title": "Inception", "Year": 2010, "Netflix": {"flatrate"}, "Canal+": set()}]
        wa.display_results(results, targets={"Netflix": "Netflix", "Canal+": "Canal+"})
        out = capsys.readouterr().out
        assert "Paid" in out
        assert "Inception" in out

    def test_paid_section_shown_for_rent(self, capsys):
        results = [{"Title": "Heat", "Year": 1995, "Canal VOD": {"rent"}}]
        wa.display_results(results, targets={"Canal VOD": "Canal VOD"})
        out = capsys.readouterr().out
        assert "Paid" in out
        assert "Heat" in out

    def test_summary_line_shown(self, capsys):
        results = [{"Title": "Inception", "Year": 2010, "Netflix": {"flatrate"}}]
        wa.display_results(results, targets={"Netflix": "Netflix"})
        out = capsys.readouterr().out
        assert "Netflix: 1" in out

    def test_most_platforms_sorted_first(self, capsys):
        results = [
            {"Title": "Film A", "Year": 2020, "Netflix": set(), "Canal+": {"flatrate"}},
            {"Title": "Film B", "Year": 2021, "Netflix": {"flatrate"}, "Canal+": {"flatrate"}},
        ]
        targets = {"Netflix": "Netflix", "Canal+": "Canal+"}
        wa.display_results(results, targets=targets)
        out = capsys.readouterr().out
        assert out.index("Film B") < out.index("Film A")

    def test_film_in_multiple_sections(self, capsys):
        # M6+ as ads + flatrate → film listed under both Free and Paid.
        results = [{"Title": "Un Film", "Year": 2020, "M6+": {"ads", "flatrate"}}]
        wa.display_results(results, targets={"M6+": "M6+"})
        out = capsys.readouterr().out
        assert "## Free" in out
        assert "## Paid" in out


# =========================
# _sort_results / _render_section (sort + alignment)
# =========================


class TestSortResults:
    def test_most_platforms_then_by_platform_then_title(self):
        results = [
            {"Title": "Ocean's Eleven", "Year": 2001, "Netflix": "", "Canal+": "✓"},
            {"Title": "Black Swan", "Year": 2010, "Netflix": "✓", "Canal+": ""},
            {"Title": "Heat", "Year": 1995, "Netflix": "✓", "Canal+": "✓"},
            {"Title": "Jurassic Park III", "Year": 2001, "Netflix": "", "Canal+": "✓"},
            {"Title": "Catch Me If You Can", "Year": 2002, "Netflix": "✓", "Canal+": ""},
        ]
        targets = {"Netflix": "Netflix", "Canal+": "Canal+"}
        order = list(wa._sort_results(results, targets)["Title"])
        assert order == [
            "Heat",                 # 2 platforms first
            "Black Swan",           # then the Netflix group (column 1), alphabetical
            "Catch Me If You Can",
            "Jurassic Park III",    # then the Canal+ group (column 2), alphabetical
            "Ocean's Eleven",
        ]


class TestRenderSection:
    def test_colalign_title_right_checkmarks_center(self):
        results = [{"Title": "Heat", "Year": 1995, "Netflix": "✓", "Canal+": "✓"}]
        targets = {"Netflix": "Netflix", "Canal+": "Canal+"}
        with patch("watchlist_availability.tabulate", return_value="") as mock_tab:
            wa._render_section("Paid", results, targets)
        assert mock_tab.call_args[1]["colalign"] == ["right", "right", "center", "center"]

    def test_markdown_carries_alignment_colons(self):
        results = [{"Title": "Heat", "Year": 1995, "Netflix": "✓"}]
        targets = {"Netflix": "Netflix"}
        md = wa._render_section("Paid", results, targets)
        # pipe format: title/year right-aligned (---:), platform centered (:---:)
        assert "---:|" in md      # right alignment present
        assert ":---" in md       # center alignment present


# =========================
# save_results
# =========================


class TestSaveResults:
    def test_file_created_with_date_in_name(self, tmp_path):
        out = wa.save_results([], "src.csv", {}, output_dir=tmp_path)
        assert out.parent == tmp_path
        import re
        assert re.search(r"\d{4}-\d{2}-\d{2}", out.name)

    def test_file_contains_film(self, tmp_path):
        results = [{"Title": "Inception", "Year": 2010, "Netflix": {"flatrate"}}]
        out = wa.save_results(results, "src.csv", {"Netflix": "Netflix"}, output_dir=tmp_path)
        content = out.read_text(encoding="utf-8")
        assert "Inception" in content
        assert "Netflix" in content

    def test_source_name_in_header(self, tmp_path):
        out = wa.save_results([], "Letterboxd @lucas", {}, output_dir=tmp_path)
        content = out.read_text(encoding="utf-8")
        assert "Letterboxd @lucas" in content

    def test_file_contains_paid_section(self, tmp_path):
        results = [{"Title": "Inception", "Year": 2010, "Netflix": {"flatrate"}}]
        out = wa.save_results(results, "src.csv", {"Netflix": "Netflix"}, output_dir=tmp_path)
        content = out.read_text(encoding="utf-8")
        assert "## Paid" in content

    def test_file_contains_free_and_paid_sections(self, tmp_path):
        results = [
            {"Title": "Un Film", "Year": 2020, "Arte": {"free"}, "Netflix": set()},
            {"Title": "Inception", "Year": 2010, "Arte": set(), "Netflix": {"flatrate"}},
        ]
        targets = {"Arte": "Arte", "Netflix": "Netflix"}
        out = wa.save_results(results, "src.csv", targets, output_dir=tmp_path)
        content = out.read_text(encoding="utf-8")
        assert "## Free" in content
        assert "## Paid" in content


# =========================
# Scraping Letterboxd
# =========================

_POSTER = (
    '<div class="react-component" data-component-class="LazyPoster" '
    'data-item-name="{name}" data-item-slug="{slug}" data-item-link="/film/{slug}/">'
    '<div class="poster film-poster">'
    '<img class="image" alt="{alt}"/></div></div>'
)


def _grid_html(films: list[tuple[str, str]], num_entries: int | None = None) -> str:
    """films: list of (data-item-name, alt). Builds a mocked grid page."""
    posters = "".join(
        _POSTER.format(name=name, alt=alt, slug=alt.lower().replace(" ", "-"))
        for name, alt in films
    )
    attr = f' data-num-entries="{num_entries}"' if num_entries is not None else ""
    return (
        f'<html><body><div class="js-watchlist-content"{attr}>'
        f'<div class="poster-grid"><ul class="grid">{posters}</ul></div>'
        "</div></body></html>"
    )


class TestParseWatchlistPage:
    def test_extracts_title_and_year(self):
        html = _grid_html([("Inception (2010)", "Inception")])
        rows = wa._parse_watchlist_page(html)
        assert rows == [{"Name": "Inception", "Year": 2010}]

    def test_missing_year_is_none(self):
        html = _grid_html([("Ray Gunn", "Ray Gunn")])
        rows = wa._parse_watchlist_page(html)
        assert rows == [{"Name": "Ray Gunn", "Year": None}]

    def test_title_with_colon_and_year(self):
        html = _grid_html([("Spider-Man: Brand New Day (2026)", "Spider-Man: Brand New Day")])
        rows = wa._parse_watchlist_page(html)
        assert rows[0]["Name"] == "Spider-Man: Brand New Day"
        assert rows[0]["Year"] == 2026

    def test_empty_page_returns_empty(self):
        rows = wa._parse_watchlist_page("<html><body></body></html>")
        assert rows == []


class TestFetchWatchlist:
    def _resp(self, html: str, status: int = 200) -> MagicMock:
        m = MagicMock()
        m.status_code = status
        m.ok = status < 400
        m.text = html
        return m

    def test_single_partial_page_stops(self):
        html = _grid_html([("Inception (2010)", "Inception"), ("Alien (1979)", "Alien")])
        session = MagicMock()
        session.get.return_value = self._resp(html)
        df = wa.fetch_watchlist_from_letterboxd("lucas", session=session, show_progress=False)
        assert list(df["Name"]) == ["Inception", "Alien"]
        # a partial page (< 28) => a single network call
        assert session.get.call_count == 1

    def test_pagination_full_then_partial(self):
        full = _grid_html([(f"Film {i} (2000)", f"Film {i}") for i in range(wa.FILMS_PER_PAGE)])
        partial = _grid_html([("Last (2024)", "Last")])
        session = MagicMock()
        session.get.side_effect = [self._resp(full), self._resp(partial)]
        df = wa.fetch_watchlist_from_letterboxd("lucas", session=session, show_progress=False)
        assert len(df) == wa.FILMS_PER_PAGE + 1
        assert session.get.call_count == 2

    def test_empty_first_page_stops(self):
        session = MagicMock()
        session.get.return_value = self._resp("<html></html>")
        df = wa.fetch_watchlist_from_letterboxd("ghost", session=session, show_progress=False)
        assert len(df) == 0

    def test_404_raises(self):
        session = MagicMock()
        session.get.return_value = self._resp("not found", status=404)
        with pytest.raises(wa.LetterboxdError, match="not found"):
            wa.fetch_watchlist_from_letterboxd("nope", session=session, show_progress=False)

    def test_network_error_raises(self):
        session = MagicMock()
        session.get.side_effect = requests.ConnectionError("down")
        with pytest.raises(wa.LetterboxdError):
            wa.fetch_watchlist_from_letterboxd("lucas", session=session, show_progress=False)

    def test_user_agent_header_sent(self):
        html = _grid_html([("Inception (2010)", "Inception")])
        session = MagicMock()
        session.get.return_value = self._resp(html)
        wa.fetch_watchlist_from_letterboxd("lucas", session=session, show_progress=False)
        headers = session.get.call_args[1]["headers"]
        assert "User-Agent" in headers and "Mozilla" in headers["User-Agent"]

    def test_progress_total_read_from_num_entries(self):
        html = _grid_html([("Inception (2010)", "Inception")], num_entries=42)
        session = MagicMock()
        session.get.return_value = self._resp(html)
        with patch("watchlist_availability.tqdm") as mock_tqdm:
            wa.fetch_watchlist_from_letterboxd("lucas", session=session)
        assert mock_tqdm.call_args[1]["total"] == 42
        mock_tqdm.return_value.update.assert_called_once_with(1)
        mock_tqdm.return_value.close.assert_called_once()


class TestExtractNumEntries:
    def test_present(self):
        html = _grid_html([("Inception (2010)", "Inception")], num_entries=602)
        assert wa._extract_num_entries(html) == 602

    def test_absent_returns_none(self):
        html = _grid_html([("Inception (2010)", "Inception")])
        assert wa._extract_num_entries(html) is None


# =========================
# ZIP auto-extraction
# =========================


def _make_zip(tmp_path: Path, csv_content: str, zip_name: str = "letterboxd.zip",
              subfolder: str | None = None) -> Path:
    """Create a Letterboxd-like export ZIP in tmp_path."""
    zip_path = tmp_path / zip_name
    entry_name = f"{subfolder}/watchlist.csv" if subfolder else "watchlist.csv"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(entry_name, csv_content)
    return zip_path


class TestFindLetterboxdZip:
    def test_finds_zip_with_watchlist(self, tmp_path):
        _make_zip(tmp_path, "Name,Year\nAlien,1979")
        result = wa._find_letterboxd_zip(tmp_path)
        assert result is not None
        assert result.suffix == ".zip"

    def test_ignores_zip_without_watchlist(self, tmp_path):
        zip_path = tmp_path / "other.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("ratings.csv", "Name,Year")
        result = wa._find_letterboxd_zip(tmp_path)
        assert result is None

    def test_ignores_corrupt_zip(self, tmp_path):
        (tmp_path / "bad.zip").write_bytes(b"not a zip")
        result = wa._find_letterboxd_zip(tmp_path)
        assert result is None

    def test_no_zip_returns_none(self, tmp_path):
        assert wa._find_letterboxd_zip(tmp_path) is None


class TestExtractWatchlistFromZip:
    def test_extracts_csv_and_deletes_zip(self, tmp_path):
        zip_path = _make_zip(tmp_path, "Name,Year\nAlien,1979")
        csv_path = wa._extract_watchlist_from_zip(zip_path, tmp_path)
        assert csv_path.exists()
        assert csv_path.read_text().strip() == "Name,Year\nAlien,1979"
        assert not zip_path.exists()

    def test_handles_subfolder_inside_zip(self, tmp_path):
        zip_path = _make_zip(tmp_path, "Name,Year\nAlien,1979", subfolder="letterboxd-2024")
        csv_path = wa._extract_watchlist_from_zip(zip_path, tmp_path)
        assert csv_path == tmp_path / "watchlist.csv"
        assert csv_path.exists()
        assert not zip_path.exists()


# =========================
# _prompt_for_csv (guided fallback)
# =========================


class TestPromptForCsv:
    def test_returns_csv_after_enter(self, tmp_path, capsys):
        (tmp_path / "watchlist.csv").write_text("Name,Year")
        with patch("builtins.input", return_value=""):
            result = wa._prompt_for_csv(downloads_dir=tmp_path)
        assert result.name == "watchlist.csv"

    def test_loops_until_file_appears(self, tmp_path, capsys):
        target = tmp_path / "watchlist.csv"
        calls = {"n": 0}

        def fake_input(_prompt):
            calls["n"] += 1
            if calls["n"] == 2:  # the file shows up on the 2nd pass
                target.write_text("Name,Year")
            return ""

        with patch("builtins.input", fake_input):
            result = wa._prompt_for_csv(downloads_dir=tmp_path)
        assert result == target
        assert calls["n"] == 2

    def test_eoferror_raises_filenotfound(self, tmp_path):
        with patch("builtins.input", side_effect=EOFError):
            with pytest.raises(FileNotFoundError):
                wa._prompt_for_csv(downloads_dir=tmp_path)

    def test_includes_username_in_guidance(self, tmp_path, capsys):
        (tmp_path / "watchlist.csv").write_text("Name,Year")
        with patch("builtins.input", return_value=""):
            wa._prompt_for_csv(downloads_dir=tmp_path, username="lucas")
        out = capsys.readouterr().out
        assert "letterboxd.com/lucas/watchlist/" in out
        assert "letterboxd.com/data/export" in out

    def test_zip_detected_and_extracted(self, tmp_path, capsys):
        _make_zip(tmp_path, "Name,Year\nAlien,1979")
        with patch("builtins.input", return_value=""):
            result = wa._prompt_for_csv(downloads_dir=tmp_path)
        assert result.name == "watchlist.csv"
        assert result.read_text().strip() == "Name,Year\nAlien,1979"
        # ZIP should be deleted
        assert not any(tmp_path.glob("*.zip"))

    def test_zip_detected_on_second_enter(self, tmp_path, capsys):
        calls = {"n": 0}

        def fake_input(_prompt):
            calls["n"] += 1
            if calls["n"] == 2:
                _make_zip(tmp_path, "Name,Year\nAlien,1979", zip_name="letterboxd.zip")
            return ""

        with patch("builtins.input", fake_input):
            result = wa._prompt_for_csv(downloads_dir=tmp_path)
        assert result.name == "watchlist.csv"
        assert calls["n"] == 2


# =========================
# load_watchlist_source
# =========================


class TestLoadWatchlistSource:
    def test_scraping_used_when_username_set(self, monkeypatch, tmp_path):
        monkeypatch.setattr(wa, "LETTERBOXD_USERNAME", "lucas")
        df = pd.DataFrame({"Name": ["Inception"], "Year": [2010]})
        with patch(
            "watchlist_availability.fetch_watchlist_from_letterboxd", return_value=df
        ) as fetch, patch("watchlist_availability.find_watchlist_csv") as find_csv:
            out_df, source, out_dir = wa.load_watchlist_source()
        fetch.assert_called_once()
        find_csv.assert_not_called()
        assert "lucas" in source
        assert len(out_df) == 1

    def test_falls_back_to_csv_on_letterboxd_error(self, monkeypatch, tmp_path):
        monkeypatch.setattr(wa, "LETTERBOXD_USERNAME", "lucas")
        csv = tmp_path / "watchlist-2024-01-01.csv"
        csv.write_text("Name,Year\nAlien,1979\n")
        with patch(
            "watchlist_availability.fetch_watchlist_from_letterboxd",
            side_effect=wa.LetterboxdError("private"),
        ), patch("watchlist_availability.find_watchlist_csv", return_value=csv):
            out_df, source, out_dir = wa.load_watchlist_source()
        assert source == csv.name
        assert list(out_df["Name"]) == ["Alien"]

    def test_falls_back_to_csv_when_scrape_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(wa, "LETTERBOXD_USERNAME", "lucas")
        csv = tmp_path / "watchlist-2024-01-01.csv"
        csv.write_text("Name,Year\nAlien,1979\n")
        empty = pd.DataFrame(columns=["Name", "Year"])
        with patch(
            "watchlist_availability.fetch_watchlist_from_letterboxd", return_value=empty
        ), patch("watchlist_availability.find_watchlist_csv", return_value=csv):
            out_df, source, out_dir = wa.load_watchlist_source()
        assert source == csv.name

    def test_csv_only_when_no_username(self, monkeypatch, tmp_path):
        monkeypatch.setattr(wa, "LETTERBOXD_USERNAME", None)
        csv = tmp_path / "watchlist-2024-01-01.csv"
        csv.write_text("Name,Year\nAlien,1979\n")
        with patch("watchlist_availability.find_watchlist_csv", return_value=csv):
            out_df, source, out_dir = wa.load_watchlist_source()
        assert source == csv.name
        assert out_dir == tmp_path

    def test_prompts_when_no_username_and_no_csv(self, monkeypatch, tmp_path):
        monkeypatch.setattr(wa, "LETTERBOXD_USERNAME", None)
        csv = tmp_path / "watchlist.csv"
        csv.write_text("Name,Year\nAlien,1979\n")
        with patch(
            "watchlist_availability.find_watchlist_csv", side_effect=FileNotFoundError
        ), patch("watchlist_availability._prompt_for_csv", return_value=csv) as prompt:
            out_df, source, out_dir = wa.load_watchlist_source()
        prompt.assert_called_once()
        assert source == csv.name
        assert list(out_df["Name"]) == ["Alien"]


# =========================
# main
# =========================


class TestMain:
    def test_raises_if_no_api_key(self, monkeypatch):
        monkeypatch.setattr(wa, "TMDB_API_KEY", None)
        with pytest.raises(EnvironmentError, match="TMDB_API_KEY"):
            wa.main()

    def test_full_pipeline(self, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(wa, "LETTERBOXD_USERNAME", None)
        csv = tmp_path / "watchlist-2024-01-01.csv"
        csv.write_text("Name,Year\nInception,2010\n")

        with patch("watchlist_availability.find_watchlist_csv", return_value=csv), patch(
            "watchlist_availability.load_platforms_config",
            return_value={"Netflix": "Netflix"},
        ), patch(
            "watchlist_availability.get_tmdb_id", return_value=27205
        ), patch(
            "watchlist_availability.get_streaming_platforms",
            return_value={"Netflix": {"flatrate"}},
        ), patch(
            "watchlist_availability.time.sleep"
        ), patch(
            "watchlist_availability.save_results",
            return_value=tmp_path / f"watchlist_{wa.date.today().isoformat()}.md",
        ):
            wa.main()

        out = capsys.readouterr().out
        assert "Inception" in out
