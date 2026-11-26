"""Messages about changes: a favorite left a service, a film is new, a renewal date is near, a weekly summary.

The target (ntfy, Gotify or a webhook) is chosen on the settings page. At most one message goes out per
day, nothing between 22:00 and 08:00 (events wait), and the secret token never leaves the database
(it is not part of a backup).
"""

import datetime
import json
import logging
import time
from typing import Any

import requests

from . import costs
from .settings import AppSettings
from .store import Store

KINDS = ("ntfy", "gotify", "webhook")
EVENTS = ("favorite_gone", "deadline", "weekly", "new_available")
DEFAULT_EVENTS = {"favorite_gone": True, "deadline": True, "weekly": True, "new_available": False}
QUIET_FROM, QUIET_TO = 22, 8
DAY = 24 * 3600
STATE_KEY = "notify_state"
TIMEOUT_SECONDS = 10


def in_quiet_hours(now: float) -> bool:
    hour = datetime.datetime.fromtimestamp(now).hour
    return hour >= QUIET_FROM or hour < QUIET_TO


def _state(store: Store, profile_id: int) -> dict[str, Any]:
    try:
        state = json.loads(store.get_profile_setting(STATE_KEY, profile_id=profile_id) or "{}")
    except ValueError:
        state = {}
    return state if isinstance(state, dict) else {}


def send(kind: str, url: str, token: str, title: str, body: str, click: str | None = None) -> None:
    """One message to the chosen target. Raises requests.RequestException when it cannot be delivered."""
    if kind == "ntfy":
        headers = {"Title": title}
        if click:
            headers["Click"] = click
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = requests.post(url, data=body.encode("utf-8"), headers=headers, timeout=TIMEOUT_SECONDS)
    elif kind == "gotify":
        response = requests.post(
            url.rstrip("/") + "/message",
            params={"token": token},
            json={"title": title, "message": body, "priority": 5},
            timeout=TIMEOUT_SECONDS,
        )
    else:
        response = requests.post(
            url, json={"title": title, "message": body, "url": click}, timeout=TIMEOUT_SECONDS
        )
    response.raise_for_status()


def build_message(
    store: Store, settings: AppSettings, since: float, now: float, base_url: str = ""
) -> dict | None:
    """What happened since `since` that the user wants to hear about, as one message (or None)."""
    events = settings.notify_events
    country = settings.country
    own = set(settings.subscriptions(country))
    favorites = {favorite["key"]: favorite["title"] for favorite in store.list_favorites()}
    changes = [change for change in store.recent_changes(country, since) if change["provider"] in own]
    lines: list[str] = []
    click = None
    if events["favorite_gone"]:
        gone = sorted(
            {
                (change["title"], change["provider"])
                for change in changes
                if change["change"] == "removed" and change["film_key"] in favorites
            }
        )
        lines += [f"{title} left {provider}" for title, provider in gone]
        if gone:
            click = f"{base_url}/watchlist?changes=removed" if base_url else None
    if events["new_available"]:
        new = sorted(
            {(change["title"], change["provider"]) for change in changes if change["change"] == "added"}
        )
        lines += [f"{title} is new on {provider}" for title, provider in new[:10]]
        if len(new) > 10:
            lines.append(f"… and {len(new) - 10} more")
    if events["deadline"]:
        today = datetime.date.fromtimestamp(now)
        sent = set(_state(store, settings.profile_id).get("deadlines", []))
        for item in costs.upcoming_deadlines(settings.costs(country), today, days=3):
            marker = f"{item['name']}|{item['date']}|{1 if item['days'] <= 1 else 3}"
            if item["days"] in (1, 3) and marker not in sent:
                unit = "day" if item["days"] == 1 else "days"
                lines.append(f"{item['name']}: renewal or cancellation date in {item['days']} {unit}")
    if not lines:
        return None
    return {"title": "Watchlist Availability", "body": "\n".join(lines), "click": click}


def weekly_message(store: Store, settings: AppSettings, now: float) -> dict:
    """Friday summary: what became available and what left in the last 7 days on the own services."""
    own = set(settings.subscriptions(settings.country))
    changes = [c for c in store.recent_changes(settings.country, now - 7 * DAY) if c["provider"] in own]
    added = sorted({c["title"] for c in changes if c["change"] == "added"})
    removed = sorted({c["title"] for c in changes if c["change"] == "removed"})
    lines = [
        f"New on your services: {len(added)}"
        + (f" ({', '.join(added[:5])}{' …' if len(added) > 5 else ''})" if added else "")
    ]
    lines.append(
        f"Gone: {len(removed)}"
        + (f" ({', '.join(removed[:5])}{' …' if len(removed) > 5 else ''})" if removed else "")
    )
    return {"title": "Your week", "body": "\n".join(lines), "click": None}


def run_notifications(
    store: Store, settings: AppSettings, now: float | None = None, base_url: str = ""
) -> bool:
    """Send what is due: the weekly summary on Friday from 17:00, otherwise the events since the last check.

    Returns True when a message went out. Failures are logged and retried at the next check.
    """
    now = now if now is not None else time.time()
    kind, url = settings.notify_kind, settings.notify_url
    if not kind or not url or in_quiet_hours(now):
        return False
    state = _state(store, settings.profile_id)
    if now - state.get("last_sent", 0) < DAY:
        return False
    local = datetime.datetime.fromtimestamp(now)
    week = local.strftime("%G-%V")
    message = None
    if (
        settings.notify_events["weekly"]
        and local.weekday() == 4
        and local.hour >= 17
        and state.get("weekly") != week
    ):
        message = weekly_message(store, settings, now)
        state["weekly"] = week
    else:
        message = build_message(store, settings, state.get("checked", now - DAY), now, base_url)
    if message is None:
        state["checked"] = now
        store.set_profile_setting(STATE_KEY, json.dumps(state), profile_id=settings.profile_id)
        return False
    try:
        send(kind, url, settings.notify_token, message["title"], message["body"], message.get("click"))
    except requests.RequestException:
        logging.exception("Could not send the notification")
        return False
    state.update(last_sent=now, checked=now)
    sent = state.setdefault("deadlines", [])
    today = datetime.date.fromtimestamp(now)
    for item in costs.upcoming_deadlines(settings.costs(settings.country), today, days=3):
        if item["days"] in (1, 3):
            sent.append(f"{item['name']}|{item['date']}|{1 if item['days'] <= 1 else 3}")
    state["deadlines"] = sent[-200:]
    store.set_profile_setting(STATE_KEY, json.dumps(state), profile_id=settings.profile_id)
    return True
