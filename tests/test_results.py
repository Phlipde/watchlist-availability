import threading
import time

from tests.helpers import API_KEY
from watchlist_app import results, tmdb
from watchlist_app.models import Film, WatchlistEntry


def _entries(count):
    return [WatchlistEntry(f"Film {i}", 2000 + i, f"film-{i}") for i in range(count)]


def _found(providers, tmdb_id=1):
    return {
        "tmdb_id": tmdb_id,
        "poster_path": "/p.jpg",
        "details": {"runtime": 100, "overview": "Plot", "genres": ["Drama"]},
        "providers": providers,
    }


def _run(entries, targets, providers):
    return results.build_results(entries, targets, lookup=lambda *args: _found(providers), workers=1)


class TestFilmResults:
    def test_film_on_netflix_records_offer_types(self):
        found = _run([WatchlistEntry("Inception", 2010)], {"Netflix": "Netflix"}, {"Netflix": {"flatrate"}})
        assert found == [
            Film(
                title="Inception",
                year=2010,
                tmdb_id=1,
                poster_path="/p.jpg",
                overview="Plot",
                runtime=100,
                genres=["Drama"],
                providers={"Netflix": ["flatrate"]},
            )
        ]

    def test_rent_only_film_kept(self):
        found = _run([WatchlistEntry("Inception", 2010)], {"TF1+": "TF1+"}, {"TF1+": {"rent"}})
        assert found[0].providers == {"TF1+": ["rent"]}

    def test_several_offer_types_in_fixed_order(self):
        found = _run([WatchlistEntry("Un Film", 2020)], {"M6+": "M6+"}, {"M6+": {"flatrate", "ads"}})
        assert found[0].providers == {"M6+": ["ads", "flatrate"]}

    def test_provider_not_in_targets_is_unavailable(self):
        unavailable = []
        found = results.build_results(
            [WatchlistEntry("Inception", 2010)],
            {"Netflix": "Netflix"},
            lookup=lambda *args: _found({"Disney Plus": {"flatrate"}}, tmdb_id=27205),
            unavailable_callback=unavailable.append,
            workers=1,
        )
        assert found == []
        assert unavailable[0].tmdb_id == 27205
        assert unavailable[0].providers == {}

    def test_film_not_on_tmdb_is_unavailable(self):
        unavailable = []
        results.build_results(
            [WatchlistEntry("Unknown", 1900)],
            {"Netflix": "Netflix"},
            lookup=lambda *args: None,
            unavailable_callback=unavailable.append,
        )
        assert unavailable == [Film(title="Unknown", year=1900)]

    def test_display_names_map_to_tmdb_names(self):
        found = _run(
            [WatchlistEntry("Alien", 1979)],
            {"Prime Video": "Amazon Prime Video", "Arte": "Arte"},
            {"Amazon Prime Video": {"flatrate"}},
        )
        assert found[0].providers == {"Prime Video": ["flatrate"]}

    def test_year_is_normalized_to_integer(self):
        found = _run(
            [WatchlistEntry("Jurassic Park", 1993.0)], {"Netflix": "Netflix"}, {"Netflix": {"flatrate"}}
        )
        assert found[0].year == 1993

    def test_default_lookup_uses_tmdb_without_cache(self, monkeypatch):
        monkeypatch.setattr(tmdb, "search_movie_id", lambda *args: 949)
        monkeypatch.setattr(
            tmdb,
            "get_movie_bundle",
            lambda *args: {"poster_path": None, "details": {}, "providers": {"DE": {"Netflix": ["rent"]}}},
        )
        found = results.build_results(
            [WatchlistEntry("Heat", 1995)], {"Netflix": "Netflix"}, country="DE", api_key=API_KEY
        )
        assert found[0].key == "949"


class TestParallelBuildResults:
    def test_results_keep_watchlist_order(self):
        def slow_first(title, year, slug, country, api_key):
            if title == "Film 0":
                time.sleep(0.05)
            return _found({"Netflix": {"flatrate"}})

        found = results.build_results(
            _entries(8), {"Netflix": "Netflix"}, country="DE", lookup=slow_first, workers=4
        )
        assert [film.title for film in found] == [f"Film {i}" for i in range(8)]

    def test_lookups_run_concurrently(self):
        active = 0
        peak = 0
        lock = threading.Lock()

        def tracked(title, year, slug, country, api_key):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            return _found({"Netflix": {"flatrate"}})

        results.build_results(_entries(12), {"Netflix": "Netflix"}, lookup=tracked, workers=4)
        assert 1 < peak <= 4

    def test_slug_and_country_are_passed_to_lookup(self):
        seen = []

        def record(title, year, slug, country, api_key):
            seen.append((title, year, slug, country, api_key))
            return None

        results.build_results(
            _entries(1), {"Netflix": "Netflix"}, country="DE", api_key=API_KEY, lookup=record, workers=1
        )
        assert seen == [("Film 0", 2000, "film-0", "DE", API_KEY)]

    def test_callbacks_cover_every_film_once(self):
        def mixed(title, year, slug, country, api_key):
            number = int(title.split()[1])
            if number % 3 == 0:
                return _found({"Netflix": {"flatrate"}})
            if number % 3 == 1:
                return None
            raise tmdb.TmdbError("TMDB rate limit reached.")

        available, unavailable, failed, progress = [], [], [], []
        results.build_results(
            _entries(9),
            {"Netflix": "Netflix"},
            lookup=mixed,
            workers=3,
            result_callback=available.append,
            unavailable_callback=unavailable.append,
            failed_callback=lambda entry, error: failed.append((entry.title, str(error))),
            progress_callback=lambda done, total, title: progress.append((done, total)),
        )
        assert len(available) == 3 and len(unavailable) == 3 and len(failed) == 3
        assert all(message == "TMDB rate limit reached." for _, message in failed)
        assert [done for done, _ in progress] == list(range(1, 10))
        assert {total for _, total in progress} == {9}

    def test_unexpected_error_does_not_stop_the_scan(self):
        def broken(title, year, slug, country, api_key):
            if title == "Film 1":
                raise RuntimeError("boom")
            return _found({"Netflix": {"flatrate"}})

        failed = []
        found = results.build_results(
            _entries(3),
            {"Netflix": "Netflix"},
            lookup=broken,
            workers=2,
            failed_callback=lambda entry, error: failed.append(entry.title),
        )
        assert [film.title for film in found] == ["Film 0", "Film 2"]
        assert failed == ["Film 1"]

    def test_cancel_stops_remaining_lookups(self):
        calls = []
        cancelled = threading.Event()

        def lookup_then_cancel(title, year, slug, country, api_key):
            calls.append(title)
            cancelled.set()
            return _found({"Netflix": {"flatrate"}})

        results.build_results(
            _entries(50),
            {"Netflix": "Netflix"},
            lookup=lookup_then_cancel,
            workers=2,
            cancel_callback=cancelled.is_set,
        )
        assert len(calls) < 50


def test_without_targets_every_provider_is_kept():
    from watchlist_app.models import WatchlistEntry
    from watchlist_app.results import make_film

    found = {"tmdb_id": 1, "providers": {"Amazon Prime Video": {"rent", "flatrate"}, "Other": set()}}
    film = make_film(WatchlistEntry("A", 2000), found, None)
    assert film.providers == {"Prime Video": ["flatrate", "rent"]}
