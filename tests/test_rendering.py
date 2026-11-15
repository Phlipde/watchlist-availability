import re
from unittest.mock import patch

from watchlist_app import rendering
from watchlist_app.models import Film


def film(title="Film", year=2020, poster_path=None, **providers):
    return Film(title=title, year=year, poster_path=poster_path, providers=providers)


class TestSplitBySection:
    def test_free_section_from_free(self):
        sections = rendering._split_by_section([film(Arte=["free"])], {"Arte": "Arte"})
        assert sections[0][0] == "Free"

    def test_free_section_from_ads(self):
        sections = rendering._split_by_section([film(**{"Pluto TV": ["ads"]})], {"Pluto TV": "Pluto TV"})
        assert sections[0][0] == "Free"

    def test_paid_section_from_flatrate(self):
        sections = rendering._split_by_section([film(Netflix=["flatrate"])], {"Netflix": "Netflix"})
        assert sections[0][0] == "Paid"

    def test_paid_section_from_rent(self):
        sections = rendering._split_by_section([film(**{"Canal VOD": ["rent"]})], {"Canal VOD": "Canal VOD"})
        assert sections[0][0] == "Paid"

    def test_multi_monetization_appears_in_each_section(self):
        sections = rendering._split_by_section([film(**{"M6+": ["ads", "flatrate"]})], {"M6+": "M6+"})
        by_label = {section[0]: section for section in sections}
        assert by_label["Free"][1][0]["M6+"] == "✓"
        assert by_label["Paid"][1][0]["M6+"] == "✓"

    def test_same_provider_spans_sections_across_films(self):
        films = [film("A", **{"TF1+": ["ads"]}), film("B", **{"TF1+": ["flatrate"]})]
        labels = [section[0] for section in rendering._split_by_section(films, {"TF1+": "TF1+"})]
        assert labels == ["Free", "Paid"]

    def test_section_order_free_then_paid(self):
        films = [film(Arte=["free"], Netflix=["flatrate"], **{"Canal VOD": ["rent"]})]
        targets = {"Canal VOD": "Canal VOD", "Netflix": "Netflix", "Arte": "Arte"}
        assert [section[0] for section in rendering._split_by_section(films, targets)] == ["Free", "Paid"]

    def test_all_blank_column_dropped(self):
        labels = [
            section[0]
            for section in rendering._split_by_section(
                [film(Netflix=["flatrate"])], {"Netflix": "Netflix", "Arte": "Arte"}
            )
        ]
        assert labels == ["Paid"]

    def test_view_targets_keyed_display_to_tmdb(self):
        sections = rendering._split_by_section(
            [film(**{"Prime Video": ["flatrate"]})], {"Prime Video": "Amazon Prime Video"}
        )
        assert sections[0][2] == {"Prime Video": "Amazon Prime Video"}


class TestDisplayResults:
    def test_empty_results_prints_message(self, capsys):
        rendering.display_results([])
        assert "No film" in capsys.readouterr().out

    def test_free_section_shown(self, capsys):
        rendering.display_results([film("Un Film", Arte=["free"])], targets={"Arte": "Arte"})
        out = capsys.readouterr().out
        assert "Free" in out and "Un Film" in out

    def test_paid_section_shown_for_flatrate_and_rent(self, capsys):
        films = [film("Inception", Netflix=["flatrate"]), film("Heat", **{"Canal VOD": ["rent"]})]
        rendering.display_results(films, targets={"Netflix": "Netflix", "Canal VOD": "Canal VOD"})
        out = capsys.readouterr().out
        assert "## Paid" in out and "Inception" in out and "Heat" in out

    def test_summary_line_shown(self, capsys):
        rendering.display_results([film("Inception", Netflix=["flatrate"])], targets={"Netflix": "Netflix"})
        assert "Netflix: 1" in capsys.readouterr().out

    def test_most_platforms_sorted_first(self, capsys):
        films = [
            film("Film A", **{"Canal+": ["flatrate"]}),
            film("Film B", Netflix=["flatrate"], **{"Canal+": ["flatrate"]}),
        ]
        rendering.display_results(films, targets={"Netflix": "Netflix", "Canal+": "Canal+"})
        out = capsys.readouterr().out
        assert out.index("Film B") < out.index("Film A")

    def test_film_in_multiple_sections(self, capsys):
        rendering.display_results([film("Un Film", **{"M6+": ["ads", "flatrate"]})], targets={"M6+": "M6+"})
        out = capsys.readouterr().out
        assert "## Free" in out and "## Paid" in out

    def test_poster_path_is_not_a_table_column(self, capsys):
        rendering.display_results(
            [film("Heat", poster_path="/p.jpg", Netflix=["rent"])], targets={"Netflix": "Netflix"}
        )
        assert "PosterPath" not in capsys.readouterr().out


class TestSortResults:
    def test_most_platforms_then_by_platform_then_title(self):
        rows = [
            {"Title": "Ocean's Eleven", "Year": 2001, "Netflix": "", "Canal+": "✓"},
            {"Title": "Black Swan", "Year": 2010, "Netflix": "✓", "Canal+": ""},
            {"Title": "Heat", "Year": 1995, "Netflix": "✓", "Canal+": "✓"},
            {"Title": "Jurassic Park III", "Year": 2001, "Netflix": "", "Canal+": "✓"},
            {"Title": "Catch Me If You Can", "Year": 2002, "Netflix": "✓", "Canal+": ""},
        ]
        order = [
            row["Title"] for row in rendering._sort_results(rows, {"Netflix": "Netflix", "Canal+": "Canal+"})
        ]
        assert order == ["Heat", "Black Swan", "Catch Me If You Can", "Jurassic Park III", "Ocean's Eleven"]


class TestRenderSection:
    def test_colalign_title_right_checkmarks_center(self):
        rows = [{"Title": "Heat", "Year": 1995, "Netflix": "✓", "Canal+": "✓"}]
        with patch("watchlist_app.rendering.tabulate", return_value="") as mock_tabulate:
            rendering._render_section("Paid", rows, {"Netflix": "Netflix", "Canal+": "Canal+"})
        assert mock_tabulate.call_args[1]["colalign"] == ["right", "right", "center", "center"]

    def test_markdown_carries_alignment_colons(self):
        markdown = rendering._render_section(
            "Paid", [{"Title": "Heat", "Year": 1995, "Netflix": "✓"}], {"Netflix": "Netflix"}
        )
        assert "---:|" in markdown
        assert ":---" in markdown


class TestSaveResults:
    def test_file_created_with_date_in_name(self, tmp_path):
        out = rendering.save_results([], "src.csv", {}, output_dir=tmp_path)
        assert out.parent == tmp_path
        assert re.search(r"\d{4}-\d{2}-\d{2}", out.name)

    def test_source_name_in_header(self, tmp_path):
        out = rendering.save_results([], "Letterboxd @lucas", {}, output_dir=tmp_path)
        assert "Letterboxd @lucas" in out.read_text(encoding="utf-8")

    def test_file_contains_free_and_paid_sections(self, tmp_path):
        films = [film("Un Film", Arte=["free"]), film("Inception", 2010, Netflix=["flatrate"])]
        out = rendering.save_results(
            films, "src.csv", {"Arte": "Arte", "Netflix": "Netflix"}, output_dir=tmp_path
        )
        content = out.read_text(encoding="utf-8")
        assert "<h2>Free</h2>" in content and "<h2>Paid</h2>" in content
        assert "Inception" in content

    def test_html_contains_poster_cover_title_year_and_provider(self, tmp_path):
        films = [film("Inception & Dreams", 2010, poster_path="/poster.jpg", Netflix=["flatrate"])]
        out = rendering.save_results(films, "src.csv", {"Netflix": "Netflix"}, output_dir=tmp_path)
        content = out.read_text(encoding="utf-8")
        assert out.suffix == ".html"
        assert 'src="https://image.tmdb.org/t/p/w500/poster.jpg"' in content
        assert "Inception &amp; Dreams" in content
        assert "2010" in content

    def test_html_contains_filters_and_normalized_card_data(self, tmp_path):
        films = [film("Jurassic Park", 1993, Netflix=["flatrate"], **{"Apple TV+": ["flatrate"]})]
        out = rendering.save_results(
            films, "src.csv", {"Netflix": "Netflix", "Apple TV+": "Apple TV"}, output_dir=tmp_path
        )
        content = out.read_text(encoding="utf-8")
        for element_id in ("search", "section-filter", "provider-filter", "year-from", "year-to"):
            assert f'id="{element_id}"' in content
        assert 'data-title="jurassic park"' in content
        assert 'data-year="1993"' in content

    def test_missing_year_is_empty(self, tmp_path):
        out = rendering.save_results(
            [film("Ray Gunn", None, Netflix=["rent"])], "src", {"Netflix": "Netflix"}, tmp_path
        )
        assert 'data-year=""' in out.read_text(encoding="utf-8")
