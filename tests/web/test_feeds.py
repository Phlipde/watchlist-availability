"""Route tests: notifications, Home Assistant sensors, calendar, RSS and the tile."""

from web import routes


class TestNotificationsAndSensors:
    def test_settings_page_has_the_notification_form(self, client):
        page = client.get("/settings").get_data(as_text=True)
        assert 'id="notify-kind"' in page and 'name="notify_event" value="weekly"' in page

    def test_test_message_needs_a_target_and_reports_a_refusal(self, client, settings, monkeypatch):
        assert client.post("/api/notify/test").status_code == 400
        settings.update({"notify_kind": "webhook", "notify_url": "https://hook.example/x"})

        def refuse(*args, **kwargs):
            raise routes.requests.ConnectionError("down")

        monkeypatch.setattr(routes.notifications.requests, "post", refuse)
        answer = client.post("/api/notify/test")
        assert answer.status_code == 502 and "did not accept" in answer.get_json()["error"]

    def test_sensors_for_home_assistant(self, client, store, settings):
        settings.update({"subscriptions": ["Netflix"]})
        store.save_scan(
            "DE",
            "letterboxd",
            None,
            [{"key": "1", "title": "Heat", "providers": {"Netflix": ["flatrate"]}}],
            [],
            {},
        )
        data = client.get("/api/sensors").get_json()
        assert data["watchlist_coverage"] == 100 and data["films_available"] == 1
        assert data["new_on_my_services"] == 0 and data["next_subscription_deadline"] is None


class TestCalendar:
    def test_feed_has_one_event_per_date_and_one_for_the_last_day_to_cancel(self, client, settings):
        settings.update({"subscriptions": ["Netflix", "MUBI"]})
        settings.update(
            {
                "costs": {
                    "Netflix": {"price": 10, "remind_on": "2026-12-01", "notice_days": 14},
                    "MUBI": {"price": 8},
                }
            }
        )
        answer = client.get("/calendar.ics")
        assert answer.mimetype == "text/calendar"
        body = answer.get_data(as_text=True)
        assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
        assert body.count("BEGIN:VEVENT") == 2  # MUBI has no date
        assert "DTSTART;VALUE=DATE:20261201" in body and "DTSTART;VALUE=DATE:20261117" in body
        assert "SUMMARY:Netflix: last day to cancel" in body

    def test_long_lines_are_folded_without_cutting_a_character(self):
        from watchlist_app.calendar import _fold

        folded = _fold("SUMMARY:" + "ä" * 60)
        assert all(len(part.encode("utf-8")) <= 76 for part in folded)
        assert (
            "".join(part.lstrip(" ") if index else part for index, part in enumerate(folded))
            == "SUMMARY:" + "ä" * 60
        )


class TestFeedAndTile:
    def _scan(self, store, settings):
        settings.update({"subscriptions": ["Netflix"]})
        store.save_scan(
            "DE",
            "letterboxd",
            None,
            [
                {
                    "key": "1",
                    "title": "Heat & Co",
                    "year": 1995,
                    "rating": 8.0,
                    "providers": {"Netflix": ["flatrate"]},
                },
                {
                    "key": "2",
                    "title": "Alien",
                    "year": 1979,
                    "rating": 8.4,
                    "providers": {"MUBI": ["flatrate"]},
                },
            ],
            [],
            {},
        )
        store.add_changes(
            "DE",
            [{"film_key": "1", "title": "Heat & Co", "year": 1995, "provider": "Netflix", "change": "added"}],
        )

    def test_rss_lists_new_films_on_own_services_and_escapes_text(self, client, store, settings):
        self._scan(store, settings)
        response = client.get("/feed.xml")
        assert response.mimetype == "application/rss+xml"
        assert "Heat &amp; Co (1995) is now on Netflix" in response.get_data(as_text=True)

    def test_tile_shows_the_new_film_and_a_pick_on_own_services(self, client, store, settings):
        self._scan(store, settings)
        html = client.get("/tile").get_data(as_text=True)
        assert "Heat &amp; Co" in html and "Alien" not in html  # Alien is not on an own service

    def test_tile_without_a_scan_is_still_a_page(self, client):
        assert "No film to suggest yet." in client.get("/tile").get_data(as_text=True)
