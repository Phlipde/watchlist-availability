"""Tests for the scan service, the schedule and the settings."""

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from tests.helpers import BUNDLE
from watchlist_app import scan_service, scheduler, tmdb
from watchlist_app.config import Settings
from watchlist_app.models import WatchlistEntry
from watchlist_app.scan_service import ScanService, perform_scan, result_stats, watchlist_key
from watchlist_app.settings import AppSettings
from watchlist_app.store import Store

ENTRIES = [WatchlistEntry("Heat", 1995)]


class SyncThread:
    """Runs the scan right away on the calling thread."""

    def __init__(self, target, args, daemon):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


class IdleThread:
    def __init__(self, target, args, daemon):
        pass

    def start(self):
        pass


@pytest.fixture
def store():
    database = Store(":memory:")
    yield database
    database.close()


@pytest.fixture
def settings(store, tmp_path):
    defaults = Settings(
        tmdb_api_key="test-key", letterboxd_username=None, country="DE", downloads_dir=tmp_path
    )
    return AppSettings(store, defaults)


def tmdb_answers(bundle=BUNDLE):
    return (
        patch("watchlist_app.tmdb.search_movie_id", return_value=949),
        patch("watchlist_app.tmdb.get_movie_bundle", return_value=bundle),
    )


class TestPerformScan:
    def test_saves_scan_and_rekeys_favorites(self, store):
        store.add_favorite({"key": "Heat|1995", "title": "Heat", "year": 1995})
        search, bundle = tmdb_answers()
        with search, bundle:
            outcome = perform_scan(store, ENTRIES, "src", "DE", "key")
        assert outcome.results[0]["key"] == "949"
        assert outcome.results[0]["providers"] == {"Netflix": ["flatrate"]}
        assert store.get_scan(outcome.scan_id)["results"][0]["key"] == "949"
        assert [favorite["key"] for favorite in store.list_favorites()] == ["949"]

    def test_same_watchlist_within_a_day_is_reused(self, store):
        search, bundle = tmdb_answers()
        with search, bundle as fetched:
            first = perform_scan(store, ENTRIES, "src", "DE", "key")
            again = perform_scan(store, ENTRIES, "src", "DE", "key")
        assert fetched.call_count == 1
        assert again.reused and again.scan_id == first.scan_id
        assert again.films[0].key == "949"

    def test_changes_are_stored_and_attached(self, store):
        first = {**BUNDLE, "providers": {"DE": {"Netflix": ["flatrate"], "MUBI": ["flatrate"]}}}
        second = {**BUNDLE, "providers": {"DE": {"Netflix": ["flatrate"], "Arte": ["free"]}}}
        with patch("watchlist_app.tmdb.search_movie_id", return_value=949):
            with patch("watchlist_app.tmdb.get_movie_bundle", return_value=first):
                assert perform_scan(store, ENTRIES, "src", "DE", "key").changes == []
            store._write("UPDATE films SET fetched_at = 0")
            store._write("UPDATE scans SET watchlist_key = 'older list'")
            with patch("watchlist_app.tmdb.get_movie_bundle", return_value=second):
                outcome = perform_scan(store, ENTRIES, "src", "DE", "key")
        changes = outcome.results[0]["provider_changes"]
        assert (changes["added"], changes["removed"]) == (["Arte"], ["MUBI"])
        reused = perform_scan(store, ENTRIES, "src", "DE", "key")
        assert reused.reused and reused.results[0]["provider_changes"]["added"] == ["Arte"]

    def test_unavailable_film_keeps_its_details(self, store):
        search, bundle = tmdb_answers({**BUNDLE, "providers": {"US": {"Hulu": ["ads"]}}})
        with search, bundle:
            outcome = perform_scan(store, ENTRIES, "src", "DE", "key")
        assert outcome.results == []
        assert outcome.unavailable[0]["key"] == "949"
        assert outcome.unavailable[0]["overview"] == "A thief."

    def test_cancelled_scan_is_not_saved(self, store):
        search, bundle = tmdb_answers()
        with search, bundle:
            assert perform_scan(store, ENTRIES, "src", "DE", "key", is_cancelled=lambda: True) is None
        assert store.latest_scan("DE") is None

    def test_timeout_and_rate_limit_are_failed_lookups(self, store, monkeypatch):
        monkeypatch.setattr(tmdb.time, "sleep", lambda seconds: None)

        def timeout(*args, **kwargs):
            raise requests.Timeout("slow")

        monkeypatch.setattr(tmdb, "_http_get", timeout)
        outcome = perform_scan(store, ENTRIES, "src", "DE", "key")
        assert outcome.unavailable == []
        assert outcome.failed[0]["title"] == "Heat" and "Timeout" in outcome.failed[0]["message"]

        rate_limited = MagicMock(status_code=429, headers={"Retry-After": "1"})
        monkeypatch.setattr(tmdb, "_http_get", lambda *args, **kwargs: rate_limited)
        outcome = perform_scan(store, [WatchlistEntry("Alien", 1979)], "other", "DE", "key")
        assert outcome.failed[0]["message"] == "TMDB rate limit reached."

    def test_scan_where_nothing_worked_is_not_saved(self, store):
        search, bundle = tmdb_answers()
        with search, bundle:
            good = perform_scan(store, ENTRIES, "src", "DE", "key")
        store._write("UPDATE scans SET created = created - 25 * 3600")
        store._write("UPDATE films SET fetched_at = 0")
        with (
            search,
            patch("watchlist_app.tmdb.get_movie_bundle", side_effect=tmdb.TmdbError("TMDB returned 401.")),
        ):
            outcome = perform_scan(store, ENTRIES, "src", "DE", "bad key")
        assert outcome.scan_id is None and len(outcome.failed) == 1
        assert store.latest_scan("DE")["id"] == good.scan_id  # the page keeps the last good scan

    def test_scan_with_failed_lookups_is_not_reused(self, store):
        entries = [*ENTRIES, WatchlistEntry("Alien", 1979)]
        tmdb_down = [True]

        def bundle(tmdb_id, api_key=None):
            if tmdb_id == 348 and tmdb_down[0]:
                raise tmdb.TmdbError("down")
            return BUNDLE

        with (
            patch("watchlist_app.tmdb.search_movie_id", side_effect=lambda title, *rest: len(title) + 344),
            patch("watchlist_app.tmdb.get_movie_bundle", side_effect=bundle),
        ):
            first = perform_scan(store, entries, "src", "DE", "key")
            tmdb_down[0] = False
            again = perform_scan(store, entries, "src", "DE", "key")
        assert len(first.failed) == 1 and first.scan_id is not None
        assert not again.reused and again.failed == [] and len(again.results) == 2


class TestScanService:
    def test_run_records_the_job_in_the_database(self, store, settings):
        service = ScanService(store, settings, thread_factory=SyncThread)
        search, bundle = tmdb_answers()
        with search, bundle:
            job_id, joined = service.start("DE", entries=ENTRIES, source_name="list.csv")
        assert not joined
        live = service.status(job_id)
        assert (live["status"], live["message"], live["results"][0]["key"]) == (
            "complete",
            "All films loaded.",
            "949",
        )
        stored = store.get_job(job_id)
        assert (stored["status"], stored["available"], stored["completed"], stored["total"]) == (
            "complete",
            1,
            1,
            1,
        )
        assert stored["scan_id"] == store.latest_scan("DE")["id"]
        assert stored["finished_at"] >= stored["started_at"]
        assert stored["tmdb_requests"] == 0  # both TMDB calls are mocked above the counter

    def test_status_survives_a_restart(self, store, settings):
        search, bundle = tmdb_answers()
        with search, bundle:
            job_id, _ = ScanService(store, settings, thread_factory=SyncThread).start("DE", entries=ENTRIES)
        restarted = ScanService(store, settings, thread_factory=IdleThread)
        status = restarted.status(job_id)
        assert status["status"] == "complete"
        assert status["results"][0]["key"] == "949"
        assert status["last_updated"] is not None

    def test_interrupted_scan_is_closed_and_started_again(self, store, settings):
        ScanService(store, settings, thread_factory=IdleThread).start("GB")
        restarted = ScanService(store, settings, thread_factory=IdleThread)
        interrupted = restarted.recover_interrupted()
        assert len(interrupted) == 1
        assert store.get_job(interrupted[0])["status"] == "interrupted"
        assert restarted.status(interrupted[0])["status"] == "interrupted"
        running = store.list_jobs(status="running")
        assert len(running) == 1 and running[0]["trigger"] == "resume" and running[0]["country"] == "GB"

    def test_watchlist_error_ends_the_job(self, store, settings):
        service = ScanService(store, settings, thread_factory=SyncThread)
        job_id, _ = service.start("DE")  # no username and no CSV in the downloads folder
        assert service.status(job_id)["status"] == "error"
        assert "watchlist" in store.get_job(job_id)["message"]

    def test_page_does_not_stop_a_background_scan(self, store, settings):
        service = ScanService(store, settings, thread_factory=IdleThread)
        background, _ = service.start("GB", trigger="schedule")
        page, joined = service.start("DE")
        assert not joined and page != background
        assert service._live[background]["cancel_requested"] is False
        # The page joins a background scan of its own country.
        assert service.start("GB") == (background, True)

    def test_cancel(self, store, settings):
        service = ScanService(store, settings, thread_factory=IdleThread)
        job_id, _ = service.start("DE")
        assert service.cancel(job_id) and not service.cancel("unknown")

    def test_stale_scan_expires_and_old_live_jobs_are_dropped(self, store, settings, monkeypatch):
        service = ScanService(store, settings, thread_factory=IdleThread)
        job_id, _ = service.start("DE")
        service._live[job_id]["heartbeat_at"] = time.time() - 31 * 60
        new_id, joined = service.start("DE")
        assert not joined and new_id != job_id
        assert store.get_job(job_id)["status"] == "error"
        service._live[job_id]["finished_at"] = time.time() - 2 * 3600
        service.start("GB")
        assert job_id not in service._live
        assert service.status(job_id)["status"] == "error"  # still known from the database


class TestLoadWatchlist:
    def test_letterboxd_error_is_reported_when_there_is_no_csv(self, store, settings):
        settings.update({"letterboxd_username": "typo"})
        error = scan_service.letterboxd.LetterboxdError('Watchlist not found for "typo".')
        with patch("watchlist_app.letterboxd.fetch_watchlist_from_letterboxd", side_effect=error):
            with pytest.raises(scan_service.letterboxd.LetterboxdError, match="typo"):
                scan_service.load_watchlist(settings)


class TestScheduler:
    def test_off_by_default(self, store, settings):
        assert scheduler.next_scan_at(store, settings) is None
        assert not scheduler.run_due_scan(store, settings, ScanService(store, settings, IdleThread))

    def test_due_scan_starts_once(self, store, settings):
        settings.update({"scan_interval_hours": 24})
        store.save_scan("DE", "src", "k", [], [], {}, created=time.time() - 25 * 3600)
        service = ScanService(store, settings, thread_factory=IdleThread)
        assert scheduler.run_due_scan(store, settings, service)
        assert store.list_jobs()[0]["trigger"] == "schedule"
        assert not scheduler.run_due_scan(store, settings, service)  # already running

    def test_not_due_yet(self, store, settings):
        settings.update({"scan_interval_hours": 24})
        store.save_scan("DE", "src", "k", [], [], {}, created=time.time() - 3600)
        assert not scheduler.run_due_scan(store, settings, ScanService(store, settings, IdleThread))

    def test_interval_under_a_day_counts_as_a_day(self, store, settings):
        store.set_setting("scan_interval_hours", "6")  # saved by an older version
        store.save_scan("DE", "src", "k", [], [], {}, created=time.time() - 7 * 3600)
        assert not scheduler.run_due_scan(store, settings, ScanService(store, settings, IdleThread))

    def test_failed_automatic_scan_waits_an_hour(self, store, settings):
        settings.update({"scan_interval_hours": 24})
        store.create_job("old", "DE", "schedule", time.time() - 600)
        store.update_job("old", status="error")
        assert not scheduler.run_due_scan(store, settings, ScanService(store, settings, IdleThread))


class TestAppSettings:
    def test_environment_values_are_start_values(self, store, settings):
        assert settings.country == "DE" and settings.letterboxd_username is None
        settings.update({"country": "GB", "letterboxd_username": "someone"})
        assert settings.country == "GB" and settings.letterboxd_username == "someone"
        settings.update({"letterboxd_username": ""})
        assert settings.letterboxd_username is None

    def test_subscriptions_per_country(self, store, settings):
        default_de = settings.subscriptions("DE")
        settings.update({"country": "GB", "subscriptions": ["MUBI"]})
        assert settings.subscriptions("GB") == ["MUBI"]
        assert settings.subscriptions("DE") == default_de
        assert settings.targets("GB") == {"MUBI": "MUBI"}

    def test_api_key_is_never_stored(self, store, settings):
        settings.update({"country": "FR"})
        assert "test-key" not in str(store._read("SELECT * FROM settings"))
        assert settings.as_dict()["tmdb_api_key_set"] is True


def test_watchlist_key_and_stats():
    assert watchlist_key(ENTRIES, "src", "DE") != watchlist_key(ENTRIES, "src", "GB")
    stats = result_stats(
        [{"providers": {"Arte": ["free"], "Netflix": ["rent"]}}, {"providers": {"Netflix": ["flatrate"]}}]
    )
    assert stats == {"total": 2, "free": 1, "paid": 2, "top_provider": "Netflix", "top_provider_count": 2}


class TestProviderList:
    def test_every_tmdb_provider_is_kept_under_its_display_name(self, store):
        bundle = {
            **BUNDLE,
            "providers": {"DE": {"Amazon Prime Video": ["flatrate"], "Brand New Stream": ["ads"]}},
        }
        search, fetched = tmdb_answers(bundle)
        with search, fetched:
            outcome = perform_scan(store, ENTRIES, "src", "DE", "key")
        assert outcome.results[0]["providers"] == {"Prime Video": ["flatrate"], "Brand New Stream": ["ads"]}
        assert store.latest_scan("DE")["stats"]["providers"] == "all"

    def test_old_scans_do_not_report_new_providers_as_changes(self, store):
        old = {"key": "949", "title": "Heat", "year": 1995, "providers": {"Netflix": ["flatrate"]}}
        store.save_scan("DE", "src", "older list", [old], [], {}, created=time.time() - 3600)
        bundle = {
            **BUNDLE,
            "providers": {"DE": {"Netflix": ["flatrate"], "Brand New Stream": ["ads"], "MUBI": ["flatrate"]}},
        }
        search, fetched = tmdb_answers(bundle)
        with search, fetched:
            outcome = perform_scan(store, ENTRIES, "src", "DE", "key")
        assert [(change["provider"], change["change"]) for change in outcome.changes] == [("MUBI", "added")]

    def test_a_scan_before_the_change_is_not_reused(self, store):
        search, fetched = tmdb_answers()
        with search, fetched as bundle:
            perform_scan(store, ENTRIES, "src", "DE", "key")
            store._write("UPDATE scans SET stats = '{}'")
            assert not perform_scan(store, ENTRIES, "src", "DE", "key").reused
        assert bundle.call_count == 1  # the film data itself is still cached

    @pytest.mark.provider_catalog
    def test_catalog_is_loaded_once_a_week(self, store, monkeypatch):
        calls = []

        def region(country, api_key=None):
            calls.append(country)
            return [{"name": "Netflix", "logo_path": "/n.jpg", "priority": 1}]

        monkeypatch.setattr(tmdb, "get_region_providers", region)
        assert scan_service.refresh_provider_catalog(store, "DE", "key")
        assert not scan_service.refresh_provider_catalog(store, "DE", "key")
        assert not scan_service.refresh_provider_catalog(store, "GB", None)  # no key, no request
        assert calls == ["DE"]
        assert store.provider_catalog("DE")[0]["logo_path"] == "/n.jpg"
        store._write("UPDATE provider_catalog SET fetched_at = 0")
        assert scan_service.refresh_provider_catalog(store, "DE", "key")

    @pytest.mark.provider_catalog
    def test_catalog_failure_does_not_stop_the_scan(self, store, monkeypatch):
        def broken(country, api_key=None):
            raise tmdb.TmdbError("down")

        monkeypatch.setattr(tmdb, "get_region_providers", broken)
        search, fetched = tmdb_answers()
        with search, fetched:
            assert perform_scan(store, ENTRIES, "src", "DE", "key").results
        assert store.provider_catalog("DE") == []
