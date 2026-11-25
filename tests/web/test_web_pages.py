"""Route tests: the HTML pages."""

import datetime
import json


class TestPages:
    def test_main_page_uses_saved_subscriptions(self, client, settings, store):
        settings.update({"subscriptions": ["MUBI"]})

        def config():
            page = client.get("/").get_data(as_text=True)
            return json.loads(page.split("window.WATCHLIST_CONFIG = ")[1].split(";</script>")[0]), page

        assert (config()[0]["rentalShops"], config()[0]["freeServices"]) == ([], [])  # no scan, no labels
        offers = {"Apple TV Store": ["rent"], "Arte": ["free"], "MUBI": ["flatrate"]}
        store.save_scan("DE", "src", "k", [{"key": "1", "title": "Heat", "providers": offers}], [], {})
        data, page = config()
        assert data["subscriptions"]["DE"] == ["MUBI"]
        assert data["rentalShops"] == ["Apple TV Store"]
        assert data["freeServices"] == ["Arte"]
        # The services menu is drawn in the browser from this config; the sidebar is gone.
        assert 'id="services-menu"' in page and 'id="provider-panel"' not in page

    def test_settings_page(self, client):
        page = client.get("/settings").get_data(as_text=True)
        assert 'id="letterboxd-username"' in page
        assert 'href="/subscriptions"' in page and 'name="subscriptions"' not in page
        assert "Once a day" in page
        # The services are chosen under Settings -> My services, not on the subscriptions page.
        services = client.get("/settings/services").get_data(as_text=True)
        assert 'type="checkbox" value="Netflix"' in services
        assert 'type="checkbox"' not in client.get("/subscriptions").get_data(as_text=True)

    def test_status_page_lists_scans(self, client, store):
        store.create_job("abc", "DE", "schedule", 100.0)
        store.update_job("abc", status="complete", finished_at=112.5, tmdb_requests=42, completed=3, total=3)
        page = client.get("/settings/data").get_data(as_text=True)
        assert "schedule" in page and "12.5 s" in page and ">42<" in page
        overview = client.get("/api/status").get_json()
        assert overview["jobs"][0]["tmdb_requests"] == 42
        assert overview["jobs"][0]["duration_seconds"] == 12.5


def test_loaded_providers_appear_on_the_pages(client, store, settings):
    store.save_provider_catalog("DE", [{"name": "Brand New Stream"}, {"name": "Amazon Prime Video"}])
    assert b"Brand New Stream" in client.get("/settings/services").data
    # A loaded provider can be saved as a subscription; the built-in name is kept for known ones.
    saved = client.put("/api/settings", json={"subscriptions": ["Brand New Stream", "Prime Video"]})
    assert saved.status_code == 200
    assert settings.subscriptions() == ["Brand New Stream", "Prime Video"]
    assert client.get("/api/status").get_json()["provider_catalog"]["count"] == 2


def test_services_page_groups_come_from_the_latest_scan(client, store, settings):
    settings.update({"subscriptions": []})
    names = ["Netflix", "Videoload", "Arte", "Brand New Stream"]
    store.save_provider_catalog("DE", [{"name": name, "priority": rank} for rank, name in enumerate(names)])
    offers = {"Arte": ["ads"], "Netflix": ["flatrate"], "Videoload": ["rent"], "Canal+": ["flatrate"]}
    store.save_scan("DE", "src", "k", [{"key": "1", "title": "Heat", "providers": offers}], [], {})
    page = client.get("/settings/services").get_data(as_text=True)

    def section(title):
        part = page.split(f'data-section="{title}"', 1)[1].split("</details>", 1)[0]
        return [name for name in names + ["Canal+"] if f'value="{name}"' in part]

    assert section("Free and ad-supported") == ["Arte"]
    assert section("Subscriptions") == ["Netflix"]
    assert section("Rental shops") == ["Videoload"]
    assert section("More services") == ["Brand New Stream"]
    assert 'value="Canal+"' not in page  # in the scan, but TMDB does not list it in DE


def test_provider_logos_reach_the_page_under_their_display_name(client, store):
    store.save_provider_catalog(
        "DE",
        [
            {"name": "Amazon Prime Video", "logo_path": "/prime.png"},
            {"name": "Odd", "logo_path": '"><script>x()</script>'},
            {"name": "No Logo"},
        ],
    )
    page = client.get("/").get_data(as_text=True)
    config = json.loads(page.split("window.WATCHLIST_CONFIG = ", 1)[1].split(";</script>", 1)[0])
    assert config["providerLogos"] == {"Prime Video": "/prime.png"}


class TestHeader:
    PAGES = [
        "/",
        "/watchlist",
        "/subscriptions",
        "/stats",
        "/settings",
        "/settings/data",
        "/settings/matches",
    ]

    def test_every_page_has_the_same_header(self, client):
        headers = set()
        for path in self.PAGES:
            html = client.get(path).get_data(as_text=True)
            start = html.index('<header class="app-header"')
            head = html[start : html.index("</header>", start)]
            assert 'id="country-select"' in head, path
            assert 'class="page-nav"' in head, path
            assert 'id="sync-toggle"' in head, path
            headers.add(head.count("<a ") >= 5)
        assert headers == {True}

    def test_sort_menu_groups_the_sorts_with_a_line_each(self, client):
        html = client.get("/watchlist").get_data(as_text=True)
        assert html.count('class="sort-option"') == 9
        assert "Favorites first, then the Letterboxd rating." in html
        assert 'id="sort-order" value="priority"' in html


class TestRecommendationsAndDeadlines:
    def _scan(self, store, settings):
        settings.update({"subscriptions": ["Netflix", "MUBI"]})
        films = [
            {
                "key": "1",
                "title": "Heat",
                "runtime": 120,
                "providers": {"Netflix": ["flatrate"], "MUBI": ["flatrate"]},
            },
            {"key": "2", "title": "Alien", "runtime": 90, "providers": {"Netflix": ["flatrate"]}},
            {"key": "3", "title": "Ran", "runtime": 150, "providers": {"Disney+": ["flatrate"]}},
        ]
        store.save_scan("DE", "letterboxd", None, films, [], {})

    def test_cards_name_the_service_the_numbers_and_the_actions(self, client, store, settings):
        self._scan(store, settings)
        page = client.get("/subscriptions").get_data(as_text=True)
        assert "Cancel MUBI" in page and "You lose no watchlist film" in page
        assert "Subscribe to Disney+ for a month" in page and "Based on the film count only" in page
        assert 'href="/watchlist?providers=Disney%2B&cost=subscription"' in page
        assert "Not interested" in page

    def test_a_date_within_a_week_makes_the_banner_data(self, client, store, settings):
        self._scan(store, settings)
        soon = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
        later = (datetime.date.today() + datetime.timedelta(days=40)).isoformat()
        settings.update(
            {"costs": {"Netflix": {"price": 10, "remind_on": soon}, "MUBI": {"price": 8, "remind_on": later}}}
        )
        page = client.get("/subscriptions").get_data(as_text=True)
        assert (
            "Netflix" in page.split('id="deadline-banner"')[1].split(">")[0]
            and "MUBI" not in page.split('id="deadline-banner"')[1].split(">")[0]
        )
        config = json.loads(
            client.get("/")
            .get_data(as_text=True)
            .split("window.WATCHLIST_CONFIG = ")[1]
            .split(";</script>")[0]
        )
        assert [item["name"] for item in config["deadlines"]] == ["Netflix"]


class TestInstallable:
    def test_manifest_icons_exist_and_the_worker_is_served_from_the_root(self, client):
        manifest = client.get("/manifest.webmanifest").get_json()
        assert {"192x192", "512x512"} <= {icon["sizes"] for icon in manifest["icons"]}
        assert any(icon.get("purpose") == "maskable" for icon in manifest["icons"])
        for icon in manifest["icons"]:
            answer = client.get(icon["src"])
            assert answer.status_code == 200 and answer.data[1:4] == b"PNG"
        worker = client.get("/sw.js")
        assert worker.status_code == 200 and "javascript" in worker.mimetype
        assert worker.headers["Cache-Control"] == "no-cache"
        assert b"addEventListener('fetch'" in worker.data

    def test_no_script_removes_the_service_worker_again(self, client):
        # An old clean-up line in app.js once unregistered the worker on every visit.
        for name in ("app.js", "header.js", "register-sw.js"):
            assert "unregister" not in client.get(f"/static/js/{name}").get_data(as_text=True), name

    def test_every_page_links_the_manifest_and_an_icon(self, client):
        for path in ("/", "/watchlist", "/subscriptions", "/stats", "/settings"):
            page = client.get(path).get_data(as_text=True)
            assert 'rel="manifest"' in page and 'rel="icon"' in page, path


class TestFirstStart:
    def test_tonight_says_what_to_do_until_there_is_a_user_name_or_a_scan(self, client, store, settings):
        page = client.get("/").get_data(as_text=True)
        assert "Set up in a minute" in page and "Letterboxd user name" in page
        settings.update({"letterboxd_username": "someone"})
        assert "Set up in a minute" not in client.get("/").get_data(as_text=True)


class TestFlagPictures:
    def test_flags_are_small_and_cached_for_a_month(self, client):
        for code in ("es", "rs", "mx", "us"):
            response = client.get(f"/static/flags/{code}.svg")
            assert response.status_code == 200 and response.mimetype == "image/svg+xml"
            assert "max-age=2592000" in response.headers["Cache-Control"]
            assert len(response.data) < 12_000  # the coats of arms were 80 to 180 KB before they were shrunk


class TestDevUi:
    def test_the_states_page_exists_only_in_development(self, client, monkeypatch):
        monkeypatch.delenv("WATCHLIST_DEV", raising=False)  # a local .env may set it
        assert client.get("/dev/ui").status_code == 404
        monkeypatch.setenv("WATCHLIST_DEV", "1")
        page = client.get("/dev/ui")
        assert page.status_code == 200 and b"Dropdown trigger" in page.data


def test_service_lists_only_offer_services_of_the_apps_country(client, store):
    """Canal+ is a French service: it is no candidate in Germany once Germany's services are loaded."""
    store.save_provider_catalog("DE", [{"name": "Netflix", "logo_path": None, "priority": 1}])
    store.save_provider_catalog("FR", [{"name": "Canal+", "logo_path": None, "priority": 1}])
    page = client.get("/subscriptions").get_data(as_text=True)
    assert 'data-name="Canal+"' not in page
    assert "Canal+" not in client.get("/settings/services").get_data(as_text=True)
