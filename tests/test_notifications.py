"""Tests for the notifications: what is sent, when, and how often."""

import datetime
import json
import time

import pytest
import requests

from tests.helpers import know_services
from watchlist_app import notifications
from watchlist_app.config import Settings
from watchlist_app.settings import AppSettings
from watchlist_app.store import Store


def at(day: int, hour: int, minute: int = 0) -> float:
    """A local time in November 2026 (the 20th is a Friday)."""
    return time.mktime((2026, 11, day, hour, minute, 0, 0, 0, -1))


@pytest.fixture
def store():
    database = Store(":memory:")
    know_services(database)
    yield database
    database.close()


@pytest.fixture
def settings(store, tmp_path):
    defaults = Settings(tmdb_api_key="k", letterboxd_username=None, country="DE", downloads_dir=tmp_path)
    app_settings = AppSettings(store, defaults)
    app_settings.update(
        {"subscriptions": ["Netflix"], "notify_kind": "webhook", "notify_url": "https://hook.example/x"}
    )
    return app_settings


@pytest.fixture
def sent(monkeypatch):
    calls = []

    class Answer:
        def raise_for_status(self):
            return None

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return Answer()

    monkeypatch.setattr(notifications.requests, "post", fake_post)
    return calls


def leave(store, key="1", title="Heat", when=None):
    store.add_changes(
        "DE",
        [{"film_key": key, "title": title, "year": 1995, "provider": "Netflix", "change": "removed"}],
        created=when,
    )


def test_the_three_targets_get_their_own_request(sent):
    notifications.send("ntfy", "https://ntfy.example/topic", "tok", "T", "body", "https://app/x")
    notifications.send("gotify", "https://gotify.example/", "tok", "T", "body")
    notifications.send("webhook", "https://hook.example/x", "", "T", "body", "https://app/x")
    (ntfy_url, ntfy), (gotify_url, gotify), (hook_url, hook) = sent
    assert ntfy_url == "https://ntfy.example/topic" and ntfy["headers"]["Click"] == "https://app/x"
    assert ntfy["headers"]["Authorization"] == "Bearer tok"
    assert gotify_url == "https://gotify.example/message" and gotify["params"] == {"token": "tok"}
    assert hook["json"] == {"title": "T", "message": "body", "url": "https://app/x"}


def test_a_favorite_that_left_is_announced_once_a_day_and_never_at_night(store, settings, sent):
    store.add_favorite({"key": "1", "title": "Heat"})
    leave(store, when=at(18, 11))
    assert notifications.run_notifications(store, settings, at(18, 23)) is False  # quiet hours: it waits
    assert notifications.run_notifications(store, settings, at(19, 9, 30)) is True
    assert "Heat left Netflix" in sent[0][1]["json"]["message"]
    leave(store, "2", "Alien", when=at(19, 10))
    store.add_favorite({"key": "2", "title": "Alien"})
    assert notifications.run_notifications(store, settings, at(19, 12)) is False  # one message per day
    assert notifications.run_notifications(store, settings, at(20, 10)) is True
    assert "Alien left Netflix" in sent[1][1]["json"]["message"]


def test_films_that_are_not_favorites_stay_quiet_unless_asked(store, settings, sent):
    leave(store, when=at(18, 9))
    assert notifications.run_notifications(store, settings, at(19, 9)) is False
    settings.update({"notify_events": {"new_available": True}})
    store.add_changes(
        "DE",
        [{"film_key": "3", "title": "Ran", "year": 1985, "provider": "Netflix", "change": "added"}],
        created=at(19, 9, 5),
    )
    assert notifications.run_notifications(store, settings, at(19, 10)) is True
    assert "Ran is new on Netflix" in sent[0][1]["json"]["message"]


def test_the_weekly_summary_comes_on_friday_evening_once(store, settings, sent):
    leave(store, when=at(17, 9))
    store.add_changes(
        "DE",
        [{"film_key": "3", "title": "Ran", "year": 1985, "provider": "Netflix", "change": "added"}],
        created=at(18, 9),
    )
    assert notifications.run_notifications(store, settings, at(20, 16)) is False  # before 17:00
    assert notifications.run_notifications(store, settings, at(20, 17, 30)) is True
    body = sent[0][1]["json"]["message"]
    assert "New on your services: 1 (Ran)" in body and "Gone: 1 (Heat)" in body
    assert notifications.run_notifications(store, settings, at(21, 17, 30)) is False


def test_a_renewal_date_is_announced_once_per_stage(store, settings, sent):
    soon = datetime.date.fromtimestamp(at(21, 12)).isoformat()
    settings.update({"costs": {"Netflix": {"price": 10, "remind_on": soon}}})
    assert notifications.run_notifications(store, settings, at(18, 9)) is True  # 3 days before
    assert "in 3 days" in sent[0][1]["json"]["message"]
    assert notifications.run_notifications(store, settings, at(19, 9)) is False  # not a stage day
    assert notifications.run_notifications(store, settings, at(20, 9, 10)) is True  # 1 day before
    assert "in 1 day" in sent[1][1]["json"]["message"]
    assert notifications.run_notifications(store, settings, at(21, 9)) is False


def test_a_target_that_fails_is_tried_again_and_nothing_is_lost(store, settings, monkeypatch):
    store.add_favorite({"key": "1", "title": "Heat"})
    leave(store, when=at(18, 11))

    def broken(url, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(notifications.requests, "post", broken)
    assert notifications.run_notifications(store, settings, at(19, 10)) is False
    monkeypatch.undo()
    calls = []
    monkeypatch.setattr(
        notifications.requests,
        "post",
        lambda url, **kwargs: calls.append(url) or type("A", (), {"raise_for_status": lambda self: None})(),
    )
    assert notifications.run_notifications(store, settings, at(19, 11)) is True


def test_settings_are_checked_and_the_token_stays_out_of_backups(store, settings):
    for bad in ({"notify_kind": "sms"}, {"notify_url": "ftp://x"}, {"notify_events": {"party": True}}):
        with pytest.raises(ValueError):
            settings.update(bad)
    settings.update({"notify_token": "secret"})
    assert settings.notify_token == "secret" and settings.as_dict()["notify_token_set"] is True
    assert "secret" not in str(settings.as_dict())
    assert "notify_token" not in json.dumps(store.export_backup())
    settings.update({"notify_token": "-"})
    assert settings.notify_token == ""


def test_each_profile_gets_only_its_own_messages_once_a_day(store, settings, sent):
    anna = settings.for_profile(store.add_profile("Anna"))
    anna.update(
        {"subscriptions": ["Netflix"], "notify_kind": "webhook", "notify_url": "https://hook.example/anna"}
    )
    store.add_favorite({"key": "1", "title": "Heat"})
    leave(store, when=at(18, 11))  # profile 1's favorite left
    store.add_favorite({"key": "2", "title": "Alien"}, profile_id=anna.profile_id)
    store.add_changes(
        "DE",
        [{"film_key": "2", "title": "Alien", "year": 1979, "provider": "Netflix", "change": "removed"}],
        created=at(18, 11),
        profile_id=anna.profile_id,
    )
    assert notifications.run_notifications(store, settings, at(19, 9)) is True
    assert notifications.run_notifications(store, anna, at(19, 9)) is True  # its own daily limit
    (first_url, first), (anna_url, anna_message) = sent
    assert first_url == "https://hook.example/x" and "Heat" in first["json"]["message"]
    assert "Alien" not in first["json"]["message"]
    assert anna_url == "https://hook.example/anna" and anna_message["json"]["message"] == "Alien left Netflix"
    assert notifications.run_notifications(store, anna, at(19, 12)) is False  # one message a day
