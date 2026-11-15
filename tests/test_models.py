from watchlist_app.models import Film, legacy_key, sort_kinds


class TestFilmKey:
    def test_tmdb_id_is_the_key(self):
        assert Film(title="Heat", year=1995, tmdb_id=949).key == "949"

    def test_title_and_year_without_tmdb_id(self):
        assert Film(title="Heat", year=1995).key == "Heat|1995"

    def test_missing_year_matches_old_browser_keys(self):
        assert legacy_key("Ray Gunn", None) == "Ray Gunn|null"


class TestFilmDict:
    def test_round_trip(self):
        film = Film(title="Heat", year=1995, tmdb_id=949, genres=["Crime"], providers={"Netflix": ["rent"]})
        data = film.to_dict()
        assert data["key"] == "949"
        assert Film.from_dict(data) == film

    def test_old_snapshot_without_tmdb_id(self):
        film = Film.from_dict(
            {"title": "Heat", "year": 1995, "overview": None, "providers": {"A": ["rent", "free"]}}
        )
        assert film.tmdb_id is None
        assert film.overview == ""
        assert film.providers == {"A": ["free", "rent"]}


def test_sort_kinds_uses_fixed_order():
    assert sort_kinds({"rent", "free", "flatrate", "ads"}) == ["free", "ads", "flatrate", "rent"]
