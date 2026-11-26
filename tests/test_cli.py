from unittest.mock import patch

import pytest

from tests.helpers import API_KEY, BUNDLE, know_services
from tests.test_letterboxd import make_zip
from watchlist_app import cli, config, letterboxd, tmdb
from watchlist_app.models import WatchlistEntry


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "TMDB_API_KEY", API_KEY)
    monkeypatch.setattr(config, "COUNTRY", "DE")
    monkeypatch.setattr(config, "DOWNLOADS_DIR", tmp_path)
    monkeypatch.setenv("WATCHLIST_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("WATCHLIST_DB", raising=False)


class TestPromptForCsv:
    def test_returns_csv_after_enter(self, tmp_path):
        (tmp_path / "watchlist.csv").write_text("Name,Year")
        with patch("builtins.input", return_value=""):
            assert cli.prompt_for_csv(downloads_dir=tmp_path).name == "watchlist.csv"

    def test_loops_until_file_appears(self, tmp_path):
        target = tmp_path / "watchlist.csv"
        calls = {"n": 0}

        def fake_input(_prompt):
            calls["n"] += 1
            if calls["n"] == 2:
                target.write_text("Name,Year")
            return ""

        with patch("builtins.input", fake_input):
            assert cli.prompt_for_csv(downloads_dir=tmp_path) == target
        assert calls["n"] == 2

    def test_eoferror_raises_filenotfound(self, tmp_path):
        with patch("builtins.input", side_effect=EOFError), pytest.raises(FileNotFoundError):
            cli.prompt_for_csv(downloads_dir=tmp_path)

    def test_includes_username_in_guidance(self, tmp_path, capsys):
        (tmp_path / "watchlist.csv").write_text("Name,Year")
        with patch("builtins.input", return_value=""):
            cli.prompt_for_csv(downloads_dir=tmp_path, username="lucas")
        out = capsys.readouterr().out
        assert "letterboxd.com/lucas/watchlist/" in out
        assert "letterboxd.com/data/export" in out

    def test_zip_detected_and_extracted(self, tmp_path):
        make_zip(tmp_path, "Name,Year\nAlien,1979")
        with patch("builtins.input", return_value=""):
            result = cli.prompt_for_csv(downloads_dir=tmp_path)
        assert result.read_text().strip() == "Name,Year\nAlien,1979"
        assert not any(tmp_path.glob("*.zip"))


class TestLoadWatchlistSource:
    def test_scraping_used_when_username_set(self, monkeypatch):
        monkeypatch.setattr(config, "LETTERBOXD_USERNAME", "lucas")
        with (
            patch(
                "watchlist_app.letterboxd.fetch_watchlist_from_letterboxd",
                return_value=[WatchlistEntry("Inception", 2010)],
            ) as fetch,
            patch("watchlist_app.letterboxd.find_watchlist_csv") as find_csv,
        ):
            entries, source, _ = cli.load_watchlist_source()
        fetch.assert_called_once()
        find_csv.assert_not_called()
        assert "lucas" in source
        assert entries == [WatchlistEntry("Inception", 2010)]

    @pytest.mark.parametrize("scrape", [letterboxd.LetterboxdError("private"), []])
    def test_falls_back_to_csv(self, monkeypatch, tmp_path, scrape):
        monkeypatch.setattr(config, "LETTERBOXD_USERNAME", "lucas")
        csv = tmp_path / "watchlist-2024-01-01.csv"
        csv.write_text("Name,Year\nAlien,1979\n")
        fetch = {"side_effect": scrape} if isinstance(scrape, Exception) else {"return_value": scrape}
        with (
            patch("watchlist_app.letterboxd.fetch_watchlist_from_letterboxd", **fetch),
            patch("watchlist_app.letterboxd.find_watchlist_csv", return_value=csv),
        ):
            entries, source, out_dir = cli.load_watchlist_source()
        assert source == csv.name
        assert out_dir == tmp_path
        assert entries == [WatchlistEntry("Alien", 1979)]

    def test_prompts_when_no_username_and_no_csv(self, monkeypatch, tmp_path):
        monkeypatch.setattr(config, "LETTERBOXD_USERNAME", None)
        csv = tmp_path / "watchlist.csv"
        csv.write_text("Name,Year\nAlien,1979\n")
        with (
            patch("watchlist_app.letterboxd.find_watchlist_csv", side_effect=FileNotFoundError),
            patch("watchlist_app.cli.prompt_for_csv", return_value=csv) as prompt,
        ):
            entries, source, _ = cli.load_watchlist_source()
        prompt.assert_called_once()
        assert source == csv.name
        assert entries[0].title == "Alien"


class TestMain:
    def test_saved_settings_win_over_the_environment(self, monkeypatch, tmp_path, capsys):
        from watchlist_app.settings import AppSettings
        from watchlist_app.store import Store

        store = Store(tmp_path / "data" / ".watchlist.sqlite3")
        know_services(store)
        AppSettings(store).update({"country": "GB", "subscriptions": ["MUBI"]})
        store.close()
        monkeypatch.setattr(config, "LETTERBOXD_USERNAME", None)
        csv = tmp_path / "watchlist-2024-01-01.csv"
        csv.write_text("Name,Year\nInception,2010\n")
        with (
            patch("watchlist_app.letterboxd.find_watchlist_csv", return_value=csv),
            patch("watchlist_app.cli.perform_scan") as scan,
            patch("watchlist_app.rendering.display_results"),
            patch("watchlist_app.rendering.save_results", return_value=tmp_path / "out.html") as save,
        ):
            scan.return_value.failed = []
            cli.main()
        assert scan.call_args[0][3] == "GB"
        assert save.call_args[0][2] == {"MUBI": "MUBI"}

    def test_raises_if_no_api_key(self, monkeypatch):
        monkeypatch.setattr(config, "TMDB_API_KEY", None)
        with pytest.raises(EnvironmentError, match="TMDB_API_KEY"):
            cli.main()

    def _run_main(self, monkeypatch, tmp_path, search):
        from watchlist_app.store import Store

        store = Store(tmp_path / "data" / ".watchlist.sqlite3")
        know_services(store)
        store.close()
        monkeypatch.setattr(config, "LETTERBOXD_USERNAME", None)
        csv = tmp_path / "watchlist-2024-01-01.csv"
        csv.write_text("Name,Year\nInception,2010\n")
        with (
            patch("watchlist_app.letterboxd.find_watchlist_csv", return_value=csv),
            # The subscriptions come from AppSettings, which starts from platforms.toml.
            patch("watchlist_app.providers.load_platforms_config", return_value={"Netflix": "Netflix"}),
            patch("watchlist_app.tmdb.search_movie_id", **search),
            patch("watchlist_app.tmdb.get_movie_bundle", return_value=BUNDLE),
            patch("watchlist_app.rendering.save_results", return_value=tmp_path / "out.html") as save,
        ):
            cli.main()
        return save

    def test_full_pipeline_uses_the_shared_database(self, monkeypatch, tmp_path, capsys):
        save = self._run_main(monkeypatch, tmp_path, {"return_value": 27205})
        out = capsys.readouterr().out
        assert "Inception" in out
        saved_films = save.call_args[0][0]
        assert saved_films[0].key == "27205"
        assert (tmp_path / "data" / ".watchlist.sqlite3").exists()

    def test_failed_lookups_are_listed(self, monkeypatch, tmp_path, capsys):
        self._run_main(monkeypatch, tmp_path, {"side_effect": tmdb.TmdbError("TMDB rate limit reached.")})
        out = capsys.readouterr().out
        assert "1 lookup(s) failed" in out
        assert "Inception: TMDB rate limit reached." in out
