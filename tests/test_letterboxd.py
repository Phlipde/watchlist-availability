import time
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from tests.helpers import response
from watchlist_app import letterboxd
from watchlist_app.models import WatchlistEntry

_POSTER = (
    '<div class="react-component" data-component-class="LazyPoster" '
    'data-item-name="{name}" data-item-slug="{slug}" data-item-link="/film/{slug}/">'
    '<div class="poster film-poster">'
    '<img class="image" alt="{alt}"/></div></div>'
)


def _grid_html(films: list[tuple[str, str]], num_entries: int | None = None) -> str:
    """films: list of (data-item-name, alt). Builds a mocked grid page."""
    posters = "".join(
        _POSTER.format(name=name, alt=alt, slug=alt.lower().replace(" ", "-")) for name, alt in films
    )
    attr = f' data-num-entries="{num_entries}"' if num_entries is not None else ""
    return (
        f'<html><body><div class="js-watchlist-content"{attr}>'
        f'<div class="poster-grid"><ul class="grid">{posters}</ul></div>'
        "</div></body></html>"
    )


class TestParseWatchlistPage:
    def test_extracts_title_year_and_slug(self):
        entries = letterboxd.parse_watchlist_page(_grid_html([("Inception (2010)", "Inception")]))
        assert entries == [WatchlistEntry("Inception", 2010, "inception")]

    def test_missing_year_is_none(self):
        entries = letterboxd.parse_watchlist_page(_grid_html([("Ray Gunn", "Ray Gunn")]))
        assert entries == [WatchlistEntry("Ray Gunn", None, "ray-gunn")]

    def test_title_with_colon_and_year(self):
        html = _grid_html([("Spider-Man: Brand New Day (2026)", "Spider-Man: Brand New Day")])
        entry = letterboxd.parse_watchlist_page(html)[0]
        assert (entry.title, entry.year) == ("Spider-Man: Brand New Day", 2026)

    def test_empty_page_returns_empty(self):
        assert letterboxd.parse_watchlist_page("<html><body></body></html>") == []


class TestFetchWatchlist:
    def test_single_partial_page_stops(self):
        session = MagicMock()
        session.get.return_value = response(
            text=_grid_html([("Inception (2010)", "Inception"), ("Alien (1979)", "Alien")])
        )
        entries = letterboxd.fetch_watchlist_from_letterboxd("lucas", session=session, show_progress=False)
        assert [entry.title for entry in entries] == ["Inception", "Alien"]
        assert session.get.call_count == 1

    def test_pagination_full_then_partial(self):
        full = _grid_html([(f"Film {i} (2000)", f"Film {i}") for i in range(letterboxd.FILMS_PER_PAGE)])
        partial = _grid_html([("Last (2024)", "Last")])
        session = MagicMock()
        session.get.side_effect = [response(text=full), response(text=partial)]
        entries = letterboxd.fetch_watchlist_from_letterboxd("lucas", session=session, show_progress=False)
        assert len(entries) == letterboxd.FILMS_PER_PAGE + 1
        assert session.get.call_count == 2

    def test_watchlist_longer_than_the_page_limit_raises(self):
        full = _grid_html([(f"Film {i} (2000)", f"Film {i}") for i in range(letterboxd.FILMS_PER_PAGE)])
        session = MagicMock()
        session.get.return_value = response(text=full)
        with pytest.raises(letterboxd.LetterboxdError, match="more than 56 films"):
            letterboxd.fetch_watchlist_from_letterboxd(
                "lucas", max_pages=2, session=session, show_progress=False
            )

    def test_empty_first_page_stops(self):
        session = MagicMock()
        session.get.return_value = response(text="<html></html>")
        assert letterboxd.fetch_watchlist_from_letterboxd("ghost", session=session, show_progress=False) == []

    def test_404_raises(self):
        session = MagicMock()
        session.get.return_value = response(status_code=404, text="not found")
        with pytest.raises(letterboxd.LetterboxdError, match="not found"):
            letterboxd.fetch_watchlist_from_letterboxd("nope", session=session, show_progress=False)

    def test_network_error_raises(self):
        session = MagicMock()
        session.get.side_effect = requests.ConnectionError("down")
        with pytest.raises(letterboxd.LetterboxdError):
            letterboxd.fetch_watchlist_from_letterboxd("lucas", session=session, show_progress=False)

    def test_user_agent_header_sent(self):
        session = MagicMock()
        session.get.return_value = response(text=_grid_html([("Inception (2010)", "Inception")]))
        letterboxd.fetch_watchlist_from_letterboxd("lucas", session=session, show_progress=False)
        headers = session.get.call_args[1]["headers"]
        assert "User-Agent" in headers and "Mozilla" in headers["User-Agent"]

    def test_progress_total_read_from_num_entries(self):
        session = MagicMock()
        session.get.return_value = response(
            text=_grid_html([("Inception (2010)", "Inception")], num_entries=42)
        )
        with patch("watchlist_app.letterboxd.tqdm") as mock_tqdm:
            letterboxd.fetch_watchlist_from_letterboxd("lucas", session=session)
        assert mock_tqdm.call_args[1]["total"] == 42
        mock_tqdm.return_value.update.assert_called_once_with(1)
        mock_tqdm.return_value.close.assert_called_once()


class TestExtractNumEntries:
    def test_present(self):
        html = _grid_html([("Inception (2010)", "Inception")], num_entries=602)
        assert letterboxd.extract_num_entries(html) == 602

    def test_absent_returns_none(self):
        assert letterboxd.extract_num_entries(_grid_html([("Inception (2010)", "Inception")])) is None


class TestTmdbIdFromFilmPage:
    def test_movie_id_parsed(self):
        assert letterboxd.parse_tmdb_id('<body data-tmdb-type="movie" data-tmdb-id="530915">') == 530915

    def test_tv_entry_ignored(self):
        assert letterboxd.parse_tmdb_id('<body data-tmdb-type="tv" data-tmdb-id="1396">') is None

    def test_missing_id(self):
        assert letterboxd.parse_tmdb_id("<body>") is None

    def test_fetch_uses_film_url_and_user_agent(self):
        session = MagicMock()
        session.get.return_value = response(text='<body data-tmdb-type="movie" data-tmdb-id="42">')
        assert letterboxd.fetch_tmdb_id("inception", session=session) == 42
        assert session.get.call_args[0][0] == "https://letterboxd.com/film/inception/"
        assert "Mozilla" in session.get.call_args[1]["headers"]["User-Agent"]

    def test_missing_page_returns_none(self):
        session = MagicMock()
        session.get.return_value = response(status_code=404)
        assert letterboxd.fetch_tmdb_id("inception", session=session) is None

    @pytest.mark.parametrize("failure", [response(status_code=500), response(status_code=429)])
    def test_page_that_cannot_be_loaded_raises(self, failure):
        # Returning None here would store a guess from the title search for good.
        session = MagicMock()
        session.get.return_value = failure
        with pytest.raises(letterboxd.LetterboxdError):
            letterboxd.fetch_tmdb_id("inception", session=session)
        session.get.side_effect = requests.ConnectionError("down")
        with pytest.raises(letterboxd.LetterboxdError):
            letterboxd.fetch_tmdb_id("inception", session=session)

    def test_suspicious_slug_is_not_requested(self):
        session = MagicMock()
        assert letterboxd.fetch_tmdb_id("../settings", session=session) is None
        session.get.assert_not_called()


class TestWatchlistCsv:
    def _csv(self, content: str, tmp_path: Path) -> Path:
        path = tmp_path / "watchlist-2024-01-01.csv"
        path.write_text(content, encoding="utf-8")
        return path

    def test_valid_csv(self, tmp_path):
        entries = letterboxd.load_watchlist(
            self._csv("Name,Year,Rating\nInception,2010,5\nAlien,1979,4", tmp_path)
        )
        assert entries == [WatchlistEntry("Inception", 2010), WatchlistEntry("Alien", 1979)]

    def test_letterboxd_export_with_bom_quotes_and_empty_year(self, tmp_path):
        content = (
            "﻿Date,Name,Year,Letterboxd URI\n"
            '2024-01-01,"Crouching Tiger, Hidden Dragon",2000,x\n'
            "2024-01-02,Untitled,,y\n"
        )
        entries = letterboxd.load_watchlist(self._csv(content, tmp_path))
        # Most recently added first, as on the website.
        assert entries == [
            WatchlistEntry("Untitled", None),
            WatchlistEntry("Crouching Tiger, Hidden Dragon", 2000),
        ]

    def test_rows_without_name_skipped(self):
        assert letterboxd.parse_watchlist_csv("Name,Year\n,2010\nHeat,1995\n") == [
            WatchlistEntry("Heat", 1995)
        ]

    @pytest.mark.parametrize(
        ("content", "missing"),
        [
            ("Title,Year\nInception,2010", "Name"),
            ("Name,Date\nInception,2010-01-01", "Year"),
            ("Title,Date\nx,y", "Name"),
        ],
    )
    def test_missing_columns(self, tmp_path, content, missing):
        with pytest.raises(ValueError, match=missing):
            letterboxd.load_watchlist(self._csv(content, tmp_path))


class TestFindWatchlistCsv:
    def test_returns_most_recent(self, tmp_path):
        older = tmp_path / "watchlist-2023-01-01.csv"
        newer = tmp_path / "watchlist-2024-06-15.csv"
        older.write_text("Name,Year")
        time.sleep(0.01)
        newer.write_text("Name,Year")
        assert letterboxd.find_watchlist_csv(downloads_dir=tmp_path) == newer

    def test_no_csv_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            letterboxd.find_watchlist_csv(downloads_dir=tmp_path)

    def test_ignores_non_watchlist_csv(self, tmp_path):
        (tmp_path / "export.csv").write_text("Name,Year")
        with pytest.raises(FileNotFoundError):
            letterboxd.find_watchlist_csv(downloads_dir=tmp_path)

    def test_accepts_letterboxd_export_name_without_dash(self, tmp_path):
        plain = tmp_path / "watchlist.csv"
        plain.write_text("Name,Year")
        assert letterboxd.find_watchlist_csv(downloads_dir=tmp_path) == plain


def make_zip(
    tmp_path: Path, csv_content: str, zip_name: str = "letterboxd.zip", subfolder: str | None = None
):
    """Create a Letterboxd-like export ZIP in tmp_path."""
    zip_path = tmp_path / zip_name
    entry_name = f"{subfolder}/watchlist.csv" if subfolder else "watchlist.csv"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(entry_name, csv_content)
    return zip_path


class TestLetterboxdZip:
    def test_finds_zip_with_watchlist(self, tmp_path):
        make_zip(tmp_path, "Name,Year\nAlien,1979")
        assert letterboxd.find_letterboxd_zip(tmp_path).suffix == ".zip"

    def test_ignores_zip_without_watchlist(self, tmp_path):
        with zipfile.ZipFile(tmp_path / "other.zip", "w") as archive:
            archive.writestr("ratings.csv", "Name,Year")
        assert letterboxd.find_letterboxd_zip(tmp_path) is None

    def test_ignores_corrupt_zip(self, tmp_path):
        (tmp_path / "bad.zip").write_bytes(b"not a zip")
        assert letterboxd.find_letterboxd_zip(tmp_path) is None

    def test_no_zip_returns_none(self, tmp_path):
        assert letterboxd.find_letterboxd_zip(tmp_path) is None

    def test_extracts_csv_and_deletes_zip(self, tmp_path):
        zip_path = make_zip(tmp_path, "Name,Year\nAlien,1979")
        csv_path = letterboxd.extract_watchlist_from_zip(zip_path, tmp_path)
        assert csv_path.read_text().strip() == "Name,Year\nAlien,1979"
        assert not zip_path.exists()

    def test_handles_subfolder_inside_zip(self, tmp_path):
        zip_path = make_zip(tmp_path, "Name,Year\nAlien,1979", subfolder="letterboxd-2024")
        csv_path = letterboxd.extract_watchlist_from_zip(zip_path, tmp_path)
        assert csv_path == tmp_path / "watchlist.csv"
        assert csv_path.exists()
        assert not zip_path.exists()
