"""Tests for the scan service, the schedule and the settings."""

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from tests.helpers import BUNDLE, know_services
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
    know_services(database)
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
    def test_saves_the_scan(self, store):
        search, bundle = tmdb_answers()
        with search, bundle:
            outcome = perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1)
        assert outcome.results[0]["key"] == "949"
        assert outcome.results[0]["providers"] == {"Netflix": ["flatrate"]}
        assert store.get_scan(outcome.scan_id)["results"][0]["key"] == "949"

    def test_same_watchlist_within_a_day_is_reused(self, store):
        search, bundle = tmdb_answers()
        with search, bundle as fetched:
            first = perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1)
            again = perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1)
        assert fetched.call_count == 1
        assert again.reused and again.scan_id == first.scan_id
        assert again.films[0].key == "949"

    def test_changes_are_stored_and_attached(self, store):
        first = {**BUNDLE, "providers": {"DE": {"Netflix": ["flatrate"], "MUBI": ["flatrate"]}}}
        second = {**BUNDLE, "providers": {"DE": {"Netflix": ["flatrate"], "Arte": ["free"]}}}
        with patch("watchlist_app.tmdb.search_movie_id", return_value=949):
            with patch("watchlist_app.tmdb.get_movie_bundle", return_value=first):
                assert perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1).changes == []
            store._write("UPDATE films SET fetched_at = 0")
            store._write("UPDATE scans SET watchlist_key = 'older list'")
            with patch("watchlist_app.tmdb.get_movie_bundle", return_value=second):
                outcome = perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1)
        changes = outcome.results[0]["provider_changes"]
        # MUBI is missing for the first time: "removed" waits for a second scan without it.
        assert (changes["added"], changes["removed"]) == (["Arte"], [])
        store._write("UPDATE films SET fetched_at = 0")
        store._write("UPDATE scans SET watchlist_key = 'older list'")
        with patch("watchlist_app.tmdb.search_movie_id", return_value=949):
            with patch("watchlist_app.tmdb.get_movie_bundle", return_value=second):
                outcome = perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1)
        changes = outcome.results[0]["provider_changes"]
        assert (changes["added"], changes["removed"]) == (["Arte"], ["MUBI"])
        reused = perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1)
        assert reused.reused and reused.results[0]["provider_changes"]["added"] == ["Arte"]

    def test_unavailable_film_keeps_its_details(self, store):
        search, bundle = tmdb_answers({**BUNDLE, "providers": {"US": {"Hulu": ["ads"]}}})
        with search, bundle:
            outcome = perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1)
        assert outcome.results == []
        assert outcome.unavailable[0]["key"] == "949"
        assert outcome.unavailable[0]["overview"] == "A thief."

    def test_cancelled_scan_is_not_saved(self, store):
        search, bundle = tmdb_answers()
        with search, bundle:
            assert (
                perform_scan(store, ENTRIES, "src", "DE", "key", is_cancelled=lambda: True, profile_id=1)
                is None
            )
        assert store.latest_scan("DE", profile_id=1) is None

    def test_timeout_and_rate_limit_are_failed_lookups(self, store, monkeypatch):
        monkeypatch.setattr(tmdb.time, "sleep", lambda seconds: None)

        def timeout(*args, **kwargs):
            raise requests.Timeout("slow")

        monkeypatch.setattr(tmdb, "_http_get", timeout)
        outcome = perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1)
        assert outcome.unavailable == []
        assert outcome.failed[0]["title"] == "Heat" and "Timeout" in outcome.failed[0]["message"]

        rate_limited = MagicMock(status_code=429, headers={"Retry-After": "1"})
        monkeypatch.setattr(tmdb, "_http_get", lambda *args, **kwargs: rate_limited)
        outcome = perform_scan(store, [WatchlistEntry("Alien", 1979)], "other", "DE", "key", profile_id=1)
        assert outcome.failed[0]["message"] == "TMDB rate limit reached."

    def test_scan_where_nothing_worked_is_not_saved(self, store):
        search, bundle = tmdb_answers()
        with search, bundle:
            good = perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1)
        store._write("UPDATE scans SET created = created - 25 * 3600")
        store._write("UPDATE films SET fetched_at = 0")
        with (
            search,
            patch("watchlist_app.tmdb.get_movie_bundle", side_effect=tmdb.TmdbError("TMDB returned 401.")),
        ):
            outcome = perform_scan(store, ENTRIES, "src", "DE", "bad key", profile_id=1)
        assert outcome.scan_id is None and len(outcome.failed) == 1
        assert (
            store.latest_scan("DE", profile_id=1)["id"] == good.scan_id
        )  # the page keeps the last good scan

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
            first = perform_scan(store, entries, "src", "DE", "key", profile_id=1)
            tmdb_down[0] = False
            again = perform_scan(store, entries, "src", "DE", "key", profile_id=1)
        assert len(first.failed) == 1 and first.scan_id is not None
        assert not again.reused and again.failed == [] and len(again.results) == 2


class TestScanService:
    def test_run_records_the_job_in_the_database(self, store, settings):
        service = ScanService(store, settings, thread_factory=SyncThread)
        search, bundle = tmdb_answers()
        with search, bundle:
            job_id, joined = service.start("DE", entries=ENTRIES, source_name="list.csv", profile_id=1)
        assert not joined
        live = service.status(job_id, profile_id=1)
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
        assert stored["scan_id"] == store.latest_scan("DE", profile_id=1)["id"]
        assert stored["finished_at"] >= stored["started_at"]
        assert stored["tmdb_requests"] == 0  # both TMDB calls are mocked above the counter

    def test_status_survives_a_restart(self, store, settings):
        search, bundle = tmdb_answers()
        with search, bundle:
            job_id, _ = ScanService(store, settings, thread_factory=SyncThread).start(
                "DE", entries=ENTRIES, profile_id=1
            )
        restarted = ScanService(store, settings, thread_factory=IdleThread)
        status = restarted.status(job_id, profile_id=1)
        assert status["status"] == "complete"
        assert status["results"][0]["key"] == "949"
        assert "only_on_my_services" in status["results"][0]  # for the page filter
        assert status["last_updated"] is not None

    def test_a_running_scan_sends_only_new_films(self, store, settings):
        service = ScanService(store, settings, thread_factory=IdleThread)
        job_id, _ = service.start("DE", entries=ENTRIES, profile_id=1)
        service._live[job_id]["results"] = [{"key": "1", "providers": {}}, {"key": "2", "providers": {}}]
        assert [film["key"] for film in service.status(job_id, start=1, profile_id=1)["results"]] == ["2"]
        service._live[job_id]["status"] = "complete"
        assert (
            len(service.status(job_id, start=1, profile_id=1)["results"]) == 2
        )  # finished: always everything

    def test_interrupted_scan_is_closed_and_started_again(self, store, settings):
        ScanService(store, settings, thread_factory=IdleThread).start("GB", profile_id=1)
        restarted = ScanService(store, settings, thread_factory=IdleThread)
        interrupted = restarted.recover_interrupted()
        assert len(interrupted) == 1
        assert store.get_job(interrupted[0])["status"] == "interrupted"
        assert restarted.status(interrupted[0], profile_id=1)["status"] == "interrupted"
        running = store.list_jobs(status="running", profile_id=1)
        assert len(running) == 1 and running[0]["trigger"] == "resume" and running[0]["country"] == "GB"

    def test_watchlist_error_ends_the_job(self, store, settings):
        service = ScanService(store, settings, thread_factory=SyncThread)
        job_id, _ = service.start("DE", profile_id=1)  # no username and no CSV in the downloads folder
        assert service.status(job_id, profile_id=1)["status"] == "error"
        assert "watchlist" in store.get_job(job_id)["message"]

    def test_page_does_not_stop_a_background_scan(self, store, settings):
        service = ScanService(store, settings, thread_factory=IdleThread)
        background, _ = service.start("GB", trigger="schedule", profile_id=1)
        page, joined = service.start("DE", profile_id=1)
        assert not joined and page != background
        assert service._live[background]["cancel_requested"] is False
        # The page joins a background scan of its own country.
        assert service.start("GB", profile_id=1) == (background, True)

    def test_cancel(self, store, settings):
        service = ScanService(store, settings, thread_factory=IdleThread)
        job_id, _ = service.start("DE", profile_id=1)
        assert service.cancel(job_id, profile_id=1) and not service.cancel("unknown", profile_id=1)

    def test_stale_scan_expires_and_old_live_jobs_are_dropped(self, store, settings, monkeypatch):
        service = ScanService(store, settings, thread_factory=IdleThread)
        job_id, _ = service.start("DE", profile_id=1)
        service._live[job_id]["heartbeat_at"] = time.time() - 31 * 60
        new_id, joined = service.start("DE", profile_id=1)
        assert not joined and new_id != job_id
        assert store.get_job(job_id)["status"] == "error"
        service._live[job_id]["finished_at"] = time.time() - 2 * 3600
        service.start("GB", profile_id=1)
        assert job_id not in service._live
        assert service.status(job_id, profile_id=1)["status"] == "error"  # still known from the database


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
        store.save_scan("DE", "src", "k", [], [], {}, created=time.time() - 25 * 3600, profile_id=1)
        service = ScanService(store, settings, thread_factory=IdleThread)
        assert scheduler.run_due_scan(store, settings, service)
        assert store.list_jobs(profile_id=1)[0]["trigger"] == "schedule"
        assert not scheduler.run_due_scan(store, settings, service)  # already running

    def test_not_due_yet(self, store, settings):
        settings.update({"scan_interval_hours": 24})
        store.save_scan("DE", "src", "k", [], [], {}, created=time.time() - 3600, profile_id=1)
        assert not scheduler.run_due_scan(store, settings, ScanService(store, settings, IdleThread))

    def test_interval_under_a_day_counts_as_a_day(self, store, settings):
        store.set_setting("scan_interval_hours", "6")  # saved by an older version
        store.save_scan("DE", "src", "k", [], [], {}, created=time.time() - 7 * 3600, profile_id=1)
        assert not scheduler.run_due_scan(store, settings, ScanService(store, settings, IdleThread))

    def test_failed_automatic_scan_waits_an_hour(self, store, settings):
        settings.update({"scan_interval_hours": 24})
        store.create_job("old", "DE", "schedule", time.time() - 600, profile_id=1)
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

    def test_a_country_without_a_platforms_section_starts_with_no_services(self, settings):
        assert settings.subscriptions("IT") == []
        # The start values count only for services TMDB has listed (here Netflix and Arte of the DE section).
        assert set(settings.subscriptions("DE")) == {"Netflix", "Arte", "Prime Video", "Apple TV+"}

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
            outcome = perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1)
        assert outcome.results[0]["providers"] == {"Prime Video": ["flatrate"], "Brand New Stream": ["ads"]}
        assert store.latest_scan("DE", profile_id=1)["stats"]["providers"] == "all"

    def test_the_scan_brings_its_free_services_and_rental_shops(self, store):
        # The page does not reload on a country switch, so both lists come from the scan's offers.
        bundle = {
            **BUNDLE,
            "providers": {
                "DE": {"Netflix": ["flatrate"], "Brand New Stream": ["ads"], "Videoload": ["rent"]}
            },
        }
        search, fetched = tmdb_answers(bundle)
        with search, fetched:
            outcome = perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1)
        assert (outcome.free_services, outcome.rental_shops) == (["Brand New Stream"], ["Videoload"])

    def test_a_scan_before_the_change_is_not_reused(self, store):
        search, fetched = tmdb_answers()
        with search, fetched as bundle:
            perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1)
            store._write("UPDATE scans SET stats = '{}'")
            assert not perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1).reused
        assert bundle.call_count == 1  # the film data itself is still cached

    def test_a_scan_in_an_older_film_format_is_not_reused(self, store):
        search, fetched = tmdb_answers()
        with search, fetched:
            perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1)
            assert perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1).reused
            store._write("""UPDATE scans SET stats = '{"providers": "all", "film_format": 1}'""")
            assert not perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1).reused

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
            assert perform_scan(store, ENTRIES, "src", "DE", "key", profile_id=1).results
        assert store.provider_catalog("DE") == []


@pytest.fixture
def anna(store):
    return store.add_profile("Anna")


class TestProfiles:
    def test_another_profile_neither_joins_nor_stops_a_running_scan(self, store, settings, anna):
        service = ScanService(store, settings, thread_factory=IdleThread)
        first, _ = service.start("DE", profile_id=1)
        second, joined = service.start("DE", profile_id=anna)
        assert not joined and second != first
        other_country, _ = service.start("GB", profile_id=anna)  # stops only the second profile's scan
        assert service._live[first]["cancel_requested"] is False
        assert service._live[second]["cancel_requested"] is True
        assert service.start("DE", profile_id=1) == (first, True)
        assert service.start("GB", profile_id=anna) == (other_country, True)
        assert service.is_running(anna) and service.is_running(1) and not service.is_running(99)

    def test_status_and_cancel_only_for_the_own_profile(self, store, settings, anna):
        service = ScanService(store, settings, thread_factory=IdleThread)
        job_id, _ = service.start("DE", profile_id=1)
        assert service.status(job_id, profile_id=anna) is None
        assert not service.cancel(job_id, profile_id=anna)
        assert service._live[job_id]["cancel_requested"] is False
        restarted = ScanService(store, settings, thread_factory=IdleThread)  # read from the database
        assert restarted.status(job_id, profile_id=anna) is None
        assert restarted.status(job_id, profile_id=1)["job_id"] == job_id

    def test_scan_of_a_second_profile_is_saved_under_it(self, store, settings, anna):
        settings.for_profile(anna).update({"subscriptions": ["Netflix"]})
        service = ScanService(store, settings, thread_factory=SyncThread)
        search, bundle = tmdb_answers()
        with search, bundle:
            job_id, _ = service.start("DE", entries=ENTRIES, source_name="list.csv", profile_id=anna)
        stored = store.get_job(job_id)
        assert stored["profile_id"] == anna and stored["status"] == "complete"
        assert store.latest_scan("DE", profile_id=anna)["id"] == stored["scan_id"]
        assert store.latest_scan("DE", profile_id=1) is None and store.list_jobs(profile_id=1) == []
        assert store.service_history("DE", profile_id=anna) and not store.service_history("DE", profile_id=1)
        assert service.status(job_id, profile_id=anna)["results"][0]["only_on_my_services"] is True

    def test_a_restart_resumes_each_profile_with_its_own_profile(self, store, settings, anna):
        service = ScanService(store, settings, thread_factory=IdleThread)
        service.start("GB", profile_id=1)
        service.start("FR", profile_id=anna)
        restarted = ScanService(store, settings, thread_factory=IdleThread)
        assert len(restarted.recover_interrupted()) == 2
        for profile_id, country in ((1, "GB"), (anna, "FR")):
            running = store.list_jobs(status="running", profile_id=profile_id)
            assert [(job["trigger"], job["country"]) for job in running] == [("resume", country)]
            assert restarted._live[running[0]["id"]]["profile_id"] == profile_id

    def test_a_second_profile_fetches_only_its_new_films_from_tmdb(self, store, anna):
        ids = {"Heat": 949, "Alien": 348}
        with (
            patch(
                "watchlist_app.tmdb.search_movie_id", side_effect=lambda title, *rest: ids[title]
            ) as search,
            patch("watchlist_app.tmdb.get_movie_bundle", return_value=BUNDLE) as bundle,
        ):
            perform_scan(store, ENTRIES, "anton.csv", "DE", "key", profile_id=1)
            search.reset_mock()
            bundle.reset_mock()
            both = [*ENTRIES, WatchlistEntry("Alien", 1979)]
            outcome = perform_scan(store, both, "anna.csv", "DE", "key", profile_id=anna)
            assert [call.args[0] for call in search.call_args_list] == ["Alien"]
            assert [call.args[0] for call in bundle.call_args_list] == [348]
            assert not outcome.reused and len(outcome.results) == 2
            # The bundle keeps every country: another country needs no new request either.
            perform_scan(store, ENTRIES, "anna.csv", "US", "key", profile_id=anna)
            assert bundle.call_count == 1


class TestLoadWatchlistPerProfile:
    def test_csv_in_the_downloads_folder_only_for_the_first_profile(self, store, settings, anna, tmp_path):
        (tmp_path / "watchlist.csv").write_text("Name,Year\nHeat,1995\n", encoding="utf-8")
        entries, source = scan_service.load_watchlist(settings)
        assert entries == ENTRIES and source == "watchlist.csv"
        with pytest.raises(ValueError, match="Letterboxd username"):
            scan_service.load_watchlist(settings.for_profile(anna))

    def test_the_name_from_the_environment_belongs_to_the_first_profile(self, store, tmp_path, anna):
        defaults = Settings(
            tmdb_api_key="k", letterboxd_username="anton", country="DE", downloads_dir=tmp_path
        )
        settings = AppSettings(store, defaults)
        assert settings.letterboxd_username == "anton"
        assert settings.for_profile(anna).letterboxd_username is None

    def test_a_letterboxd_error_of_a_second_profile_is_reported(self, store, settings, anna):
        anna_settings = settings.for_profile(anna)
        anna_settings.update({"letterboxd_username": "typo"})
        error = scan_service.letterboxd.LetterboxdError('Watchlist not found for "typo".')
        with patch("watchlist_app.letterboxd.fetch_watchlist_from_letterboxd", side_effect=error):
            with pytest.raises(scan_service.letterboxd.LetterboxdError, match="typo"):
                scan_service.load_watchlist(anna_settings)


class TestSchedulerPerProfile:
    def test_two_profiles_are_scanned_one_after_another_on_the_same_day(self, store, settings, anna):
        settings.update({"scan_interval_hours": 24})
        settings.for_profile(anna).update({"letterboxd_username": "anna", "country": "GB"})
        store.add_profile("Nameless")  # no Letterboxd name: never scanned on a schedule
        service = ScanService(store, settings, thread_factory=IdleThread)
        assert scheduler.run_due_scan(store, settings, service)
        first = store.list_jobs(profile_id=1)[0]
        assert not scheduler.run_due_scan(store, settings, service)  # one scan at a time
        service._live[first["id"]]["status"] = "complete"
        store.save_scan("DE", "src", "k", [], [], {}, profile_id=1)
        assert scheduler.run_due_scan(store, settings, service)
        second = store.list_jobs(profile_id=anna)[0]
        assert (second["trigger"], second["country"]) == ("schedule", "GB")
        service._live[second["id"]]["status"] = "complete"
        store.save_scan("GB", "src", "k", [], [], {}, profile_id=anna)
        assert not scheduler.run_due_scan(store, settings, service)  # both done for today

    def test_a_failed_scan_waits_only_for_its_own_profile(self, store, settings, anna):
        settings.update({"scan_interval_hours": 24})
        settings.for_profile(anna).update({"letterboxd_username": "anna"})
        store.create_job("old", "DE", "schedule", time.time() - 600, profile_id=1)
        store.update_job("old", status="error")
        service = ScanService(store, settings, thread_factory=IdleThread)
        assert scheduler.run_due_scan(store, settings, service)
        assert store.list_jobs(profile_id=anna)[0]["trigger"] == "schedule"

    def test_next_scan_is_per_profile(self, store, settings, anna):
        settings.update({"scan_interval_hours": 24})
        anna_settings = settings.for_profile(anna)
        assert scheduler.next_scan_at(store, anna_settings) is None  # no Letterboxd name yet
        anna_settings.update({"letterboxd_username": "anna"})
        store.save_scan("DE", "src", "k", [], [], {}, created=1000, profile_id=anna)
        assert scheduler.next_scan_at(store, anna_settings) == 1000 + 24 * 3600
        assert scheduler.next_scan_at(store, settings) == 24 * 3600  # profile 1 has no scan


class TestWatchedRefresh:
    def test_a_good_scan_loads_the_watched_films_at_most_once_a_day(self, store, settings, anna):
        anna_settings = settings.for_profile(anna)
        anna_settings.update({"letterboxd_username": "anna"})
        service = ScanService(store, settings, thread_factory=SyncThread)
        search, bundle = tmdb_answers()
        fetch = patch("watchlist_app.letterboxd.fetch_watched_slugs", return_value=["heat", "alien"])
        with search, bundle, fetch as fetched:
            service.start("DE", entries=ENTRIES, source_name="a.csv", profile_id=anna)
            service.start("DE", entries=ENTRIES, source_name="b.csv", profile_id=anna)
            service.start("DE", entries=ENTRIES, source_name="c.csv", profile_id=1)  # no Letterboxd name
            fetched.assert_called_once_with("anna")
            assert store.watched_keys(profile_id=anna) == {"lb:heat", "lb:alien"}
            assert store.watched_keys(profile_id=1) == set()
            store.replace_watched(["lb:heat"], now=time.time() - 25 * 3600, profile_id=anna)  # a day old
            assert scan_service.refresh_watched(store, anna_settings)
        assert store.watched_keys(profile_id=anna) == {"lb:heat", "lb:alien"}

    def test_a_letterboxd_failure_keeps_the_old_list_and_the_scan(self, store, settings, anna, caplog):
        settings.for_profile(anna).update({"letterboxd_username": "anna"})
        store.replace_watched(["lb:heat"], now=1.0, profile_id=anna)
        service = ScanService(store, settings, thread_factory=SyncThread)
        search, bundle = tmdb_answers()
        error = scan_service.letterboxd.LetterboxdError("Letterboxd returned 403.")
        with search, bundle, patch("watchlist_app.letterboxd.fetch_watched_slugs", side_effect=error):
            job_id, _ = service.start("DE", entries=ENTRIES, profile_id=anna)
            assert service.status(job_id, profile_id=anna)["status"] == "complete"
        assert store.watched_keys(profile_id=anna) == {"lb:heat"}
        assert store.watched_fetched_at(profile_id=anna) == 1.0  # tried again by the next scan
        assert "403" in caplog.text

    def test_an_unexpected_error_does_not_fail_the_scan(self, store, settings, anna):
        service = ScanService(store, settings, thread_factory=SyncThread)
        search, bundle = tmdb_answers()
        with search, bundle, patch.object(scan_service, "refresh_watched", side_effect=RuntimeError("boom")):
            job_id, _ = service.start("DE", entries=ENTRIES, profile_id=1)
        assert service.status(job_id, profile_id=1)["status"] == "complete"
