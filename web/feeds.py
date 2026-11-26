"""Connection tests, feeds and sensors for other apps, settings, status and backup."""

import json
import time

import requests
from flask import Flask, Response, jsonify, render_template, request

from watchlist_app import base, calendar, costs, feed, notifications, tmdb
from watchlist_app.scan_service import ScanService
from watchlist_app.settings import AppSettings
from watchlist_app.store import Store
from web.common import active_profile_id, active_settings, status_overview


def register(app: Flask, store: Store, settings: AppSettings, service: ScanService) -> None:
    # ----- notifications and sensors -----

    @app.post("/api/tmdb/test")
    def tmdb_test():
        s = active_settings(settings)
        try:
            tmdb.check_key(s.tmdb_api_key)
        except tmdb.TmdbError as exc:
            return jsonify({"error": str(exc)}), 400 if "key" in str(exc).lower() else 502
        return jsonify({"ok": True})

    @app.post("/api/notify/test")
    def notify_test():
        s = active_settings(settings)
        if not s.notify_kind or not s.notify_url:
            return jsonify({"error": "Choose a target and an address first."}), 400
        try:
            notifications.send(
                s.notify_kind,
                s.notify_url,
                s.notify_token,
                "Watchlist Availability",
                "This is a test message. Notifications work.",
                request.host_url.rstrip("/"),
            )
        except requests.RequestException as exc:
            return jsonify(
                {"error": f"The target did not accept the message: {exc.__class__.__name__}."}
            ), 502
        return jsonify({"ok": True})

    @app.get("/calendar.ics")
    def calendar_feed():
        """The dates entered on the subscriptions page, for a calendar app to subscribe to."""
        s = active_settings(settings)
        body = calendar.build_ics({country: s.costs(country) for country in s.countries_in_use()})
        return Response(body, mimetype="text/calendar", headers={"Cache-Control": "no-store"})

    @app.get("/feed.xml")
    def rss_feed():
        """Films that became watchable on the own services in the last 30 days, for a feed reader."""
        s = active_settings(settings)
        changes = store.recent_changes(s.country, time.time() - 30 * 24 * 3600, profile_id=s.profile_id)
        body = feed.build_rss(changes, request.host_url.rstrip("/"), set(s.subscriptions()))
        return Response(body, mimetype="application/rss+xml", headers={"Cache-Control": "no-store"})

    @app.get("/tile")
    def tile():
        """A small page for Homepage or Homarr to embed: new this week and the pick of the day."""
        s, pid = active_settings(settings), active_profile_id()
        scan = store.latest_scan(s.country, profile_id=pid)
        own = s.subscriptions()
        week = store.recent_changes(s.country, time.time() - 7 * 24 * 3600, profile_id=pid)
        new = [c for c in week if c["change"] == "added" and c["provider"] in own]
        hidden = {flag["key"] for flag in store.list_flags(profile_id=pid)}
        pick = feed.pick_of_the_day(scan["results"] if scan else [], own, hidden, time.strftime("%Y-%m-%d"))
        return render_template("tile.html", new=new[:5], new_total=len(new), pick=pick)

    @app.get("/api/sensors")
    def sensors():
        """Numbers for Home Assistant (a REST sensor): what changed this week, the next date, the coverage."""
        s, pid = active_settings(settings), active_profile_id()
        scan = store.latest_scan(s.country, profile_id=pid)
        own = set(s.subscriptions())
        week = [
            c
            for c in store.recent_changes(s.country, time.time() - 7 * 24 * 3600, profile_id=pid)
            if c["provider"] in own
        ]
        deadlines = costs.reminders({s.country: s.costs(s.country)})
        upcoming = next((item for item in deadlines if item["days"] >= 0), None)
        overview = costs.overview(
            scan["results"] if scan else [],
            s.subscriptions(),
            s.costs(),
            base.base_counts(scan)["not_available"],
        )
        return jsonify(
            {
                "new_on_my_services": len({c["film_key"] for c in week if c["change"] == "added"}),
                "gone_from_my_services": len({c["film_key"] for c in week if c["change"] == "removed"}),
                "next_subscription_deadline": upcoming,
                "watchlist_coverage": overview["coverage"]["percent"],
                "films_available": overview["coverage"]["covered"],
                "last_scan": scan["created"] if scan else None,
            }
        )

    # ----- settings, status, backup -----

    @app.get("/api/settings")
    def get_settings():
        return jsonify(active_settings(settings).as_dict())

    @app.put("/api/settings")
    def put_settings():
        changes = request.get_json(silent=True)
        if not isinstance(changes, dict):
            return jsonify({"error": "Send the settings as a JSON object."}), 400
        s = active_settings(settings)
        try:
            s.update(changes)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        # A profile that just got its Letterboxd name and has no scan yet is scanned right away;
        # while another scan runs, the schedule picks it up later.
        if (
            changes.get("letterboxd_username")
            and s.letterboxd_username
            and s.tmdb_api_key
            and store.latest_scan_created(s.country, profile_id=s.profile_id) is None
            and not service.is_running()
        ):
            service.start(s.country, trigger="schedule", profile_id=s.profile_id)
        return jsonify(s.as_dict())

    @app.get("/api/status")
    def get_status():
        return jsonify(status_overview(store, active_settings(settings), service))

    @app.get("/api/backup")
    def download_backup():
        name = f"watchlist-backup-{time.strftime('%Y-%m-%d')}.json"
        return Response(
            json.dumps(store.export_backup()),
            mimetype="application/json",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @app.post("/api/backup")
    def restore_backup():
        uploaded = request.files.get("backup")
        if uploaded is None:
            return jsonify({"error": "Choose a backup file."}), 400
        try:
            backup = json.loads(uploaded.read().decode("utf-8"))
            # A version 1 file (one person) goes into the active profile.
            counts = store.import_backup(backup, target_profile=active_profile_id())
        except (UnicodeDecodeError, ValueError) as exc:
            message = str(exc) if "backup" in str(exc) else "The file is not valid JSON."
            return jsonify({"error": message}), 400
        s = active_settings(settings)
        restored, skipped = s.restore_backup(backup, target_profile=s.profile_id)
        counts["settings"] = restored
        counts["skipped"] += skipped
        return jsonify({"ok": True, "imported": counts})
