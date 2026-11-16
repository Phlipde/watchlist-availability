"""End-to-end tests in a real browser (Playwright): scan, filters, favorites, settings, title matches.

The app runs on a local port with its own empty database; Letterboxd and TMDB
are replaced by fixed answers, so no request leaves the computer.

Run with `pytest -m browser`. Needs `pip install -r requirements-dev.txt` and a
browser: `playwright install chromium`, or an installed Chrome or Edge.
"""

import json
import re
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from flask import Flask
from werkzeug.serving import make_server

from watchlist_app.config import Settings
from watchlist_app.models import WatchlistEntry
from watchlist_app.scan_service import ScanService
from watchlist_app.settings import AppSettings
from watchlist_app.store import Store
from web import routes

playwright_api = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.browser

PROJECT = Path(__file__).resolve().parents[2]
ENTRIES = [WatchlistEntry("Heat", 1995), WatchlistEntry("Alien", 1979), WatchlistEntry("Nope Film", 2001)]
IDS = {"Heat": 949, "Alien": 348}
BUNDLES = {
    949: {
        "poster_path": None,
        "details": {
            "tmdb_title": "Heat",
            "release_date": "1995-12-15",
            "overview": "A thief.",
            "rating": 8.0,
            "runtime": 120,
            "genres": ["Action"],
            "trailer_url": "https://www.youtube.com/watch?v=abc",
        },
        "providers": {"DE": {"Netflix": ["flatrate"]}, "GB": {"BBC iPlayer": ["free"]}},
    },
    348: {
        "poster_path": None,
        "details": {
            "tmdb_title": "Alien",
            "release_date": "1979-05-25",
            "overview": "In space.",
            "rating": 8.1,
        },
        "providers": {"DE": {"Arte": ["free"]}, "GB": {"Arte": ["flatrate"]}},
    },
    111: {
        "poster_path": None,
        "details": {
            "tmdb_title": "Heat 2",
            "release_date": "2026-01-01",
            "overview": "Sequel.",
            "rating": 6.0,
        },
        "providers": {},
    },
}
CANDIDATES = [
    {
        "tmdb_id": 949,
        "title": "Heat",
        "original_title": "Heat",
        "year": 1995,
        "poster_path": None,
        "overview": "",
    },
    {
        "tmdb_id": 111,
        "title": "Heat 2",
        "original_title": "Heat 2",
        "year": 2026,
        "poster_path": None,
        "overview": "",
    },
]


def wait_until(condition, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        if condition():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def app_server(tmp_path):
    """The web app with fixed answers for Letterboxd and TMDB, on a free local port."""
    store = Store(tmp_path / "test.sqlite3")
    defaults = Settings(
        tmdb_api_key="test-key", letterboxd_username="tester", country="DE", downloads_dir=tmp_path
    )
    settings = AppSettings(store, defaults)
    settings.update({"subscriptions": ["Netflix"]})
    service = ScanService(store, settings)
    app = Flask(
        "watchlist", template_folder=str(PROJECT / "templates"), static_folder=str(PROJECT / "static")
    )
    routes.register_routes(app, store=store, settings=settings, service=service)
    fakes = [
        patch("watchlist_app.scan_service.load_watchlist", return_value=(ENTRIES, "Letterboxd @tester")),
        patch("watchlist_app.tmdb.search_movie_id", side_effect=lambda title, year, key=None: IDS.get(title)),
        patch(
            "watchlist_app.tmdb.get_movie_bundle", side_effect=lambda tmdb_id, key=None: BUNDLES.get(tmdb_id)
        ),
        patch("watchlist_app.tmdb.search_movies", return_value=CANDIDATES),
        patch("watchlist_app.tmdb.get_region_providers", return_value=[]),
    ]
    for fake in fakes:
        fake.start()
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {"url": f"http://127.0.0.1:{server.server_port}", "store": store, "settings": settings}
    server.shutdown()
    for fake in fakes:
        fake.stop()
    store.close()


@pytest.fixture(scope="session")
def browser():
    with playwright_api.sync_playwright() as playwright:
        launched = None
        for options in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
            try:
                launched = playwright.chromium.launch(**options)
                break
            except playwright_api.Error:
                continue
        if launched is None:
            pytest.skip("No browser for Playwright: run `playwright install chromium`.")
        yield launched
        launched.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(service_workers="block")
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield page
    context.close()
    assert errors == [], f"JavaScript errors: {errors}"


def visible_titles(page) -> list[str]:
    return sorted(page.locator("article.film:visible .film-title").all_inner_texts())


def test_scan_filters_and_favorite(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"])
    # The page starts a scan; only the saved subscription (Netflix) is selected.
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    expect(page.locator("#visible-count")).to_have_text("1")
    assert visible_titles(page) == ["Heat"]

    page.locator("#select-all-providers").click()
    expect(page.locator("#visible-count")).to_have_text("2")
    assert visible_titles(page) == ["Alien", "Heat"]

    page.locator("#film-search").fill("ali")
    expect(page.locator("#visible-count")).to_have_text("1")
    assert visible_titles(page) == ["Alien"]

    page.locator("#reset-providers").click()  # My subscriptions
    expect(page.locator("#visible-count")).to_have_text("0")

    page.locator("#film-search").fill("")
    expect(page.locator("#visible-count")).to_have_text("1")
    # The search field still has the focus: the first click must not get lost
    # (the cards used to be redrawn when the field lost the focus).
    page.locator('article.film[data-key="949"] button.favorite').click()
    store = app_server["store"]
    assert wait_until(lambda: [favorite["key"] for favorite in store.list_favorites()] == ["949"])

    # After a reload the favorite and the scan come back from the database.
    page.reload()
    expect(page.locator('article.film[data-key="949"] button.favorite')).to_have_attribute(
        "data-favorite", "true"
    )


def test_evening_mode_suggests_from_subscriptions(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"])
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    page.locator("#evening-mode").click()
    page.locator("#evening-runtime").fill("120")
    page.locator("#evening-genre").select_option("Action")
    page.get_by_role("button", name="Suggest films").click()
    expect(page.locator("#evening-results")).to_contain_text("Heat")
    expect(page.locator("#evening-results")).not_to_contain_text("Alien")


def test_trailer_from_the_details_window_is_in_front(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"])
    page.locator('article.film[data-key="949"] .film-details-button').click()
    page.locator("#film-details-content .trailer-link").click()
    expect(page.locator("#trailer-modal")).to_be_visible()
    expect(page.locator("#film-details-modal")).to_be_hidden()


def free_tagged(page) -> list[str]:
    return sorted(
        page.locator("label:has(.free-tag)").evaluate_all(
            "labels => labels.map(l => l.dataset.providerLabel)"
        )
    )


def test_free_labels_follow_the_country(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"])
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    assert "Arte" in free_tagged(page) and "BBC iPlayer" not in free_tagged(page)
    # A country switch scans without reloading the page; the labels must follow the new scan.
    page.locator("#country-select").select_option("GB")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    assert wait_until(lambda: "BBC iPlayer" in free_tagged(page))
    assert "Arte" not in free_tagged(page)
    # Back to a country that already has a scan: its saved films are shown, no new scan.
    requests: list[str] = []
    page.on("request", lambda request: requests.append(f"{request.method} {request.url}"))
    page.locator("#country-select").select_option("DE")
    expect(page.locator("#status-message")).to_have_text("Showing saved results.")
    assert wait_until(lambda: "Arte" in free_tagged(page))
    assert not [line for line in requests if line.startswith("POST") and line.endswith("/api/scan")]


def test_saved_results_show_the_tools(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"])
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    # A second visit finds the saved scan and starts none: sorting, random and the rest must still be there.
    page.goto(app_server["url"])
    expect(page.locator("#status-message")).to_have_text("Showing saved results.")
    expect(page.locator("#random-film")).to_be_visible()
    expect(page.locator("#stats-section")).to_be_visible()
    expect(page.locator("#retry-scan")).to_have_text("Scan again")
    # A rare filter set from a link sits behind "More filters"; the summary must still show it.
    page.goto(app_server["url"] + "/?votes=1000")
    expect(page.locator("#min-votes")).to_be_hidden()
    expect(page.locator("#more-filters summary")).to_have_text("More filters (1 active)")


def test_a_note_that_could_not_be_saved_is_marked(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"])
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    card = page.locator('article.film[data-key="949"]')
    card.locator("button.favorite").click()
    expect(card.locator("button.favorite")).to_have_attribute("data-favorite", "true")
    page.route(
        "**/api/favorites/*",
        lambda route: route.abort() if route.request.method == "PATCH" else route.continue_(),
    )
    card.locator(".favorite-note").fill("Watch with Lisa")
    card.locator(".favorite-note").blur()
    expect(card.locator(".favorite-note")).to_have_class(re.compile("is-invalid"))
    expect(page.locator("#app-toast")).to_have_class(re.compile("toast-error"))
    expect(page.locator("#toast-message")).to_contain_text("Could not save the note")
    assert app_server["store"].list_favorites()[0].get("notes", "") == ""


def test_settings_are_saved_and_checked(app_server, page):
    expect = playwright_api.expect
    page.goto(f"{app_server['url']}/settings")
    page.locator("#letterboxd-username").fill("bad name!")
    page.get_by_role("button", name="Save settings").click()
    expect(page.locator("#settings-message")).to_contain_text("may only contain")

    page.locator("#letterboxd-username").fill("someone_else")
    page.locator('input[name="subscriptions"][value="MUBI"]').check()
    page.get_by_role("button", name="Save settings").click()
    expect(page.locator("#settings-message")).to_have_text("Saved.")
    settings = app_server["settings"]
    assert settings.letterboxd_username == "someone_else"
    assert sorted(settings.subscriptions("DE")) == ["MUBI", "Netflix"]


def test_title_match_is_corrected_and_undone(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"])  # the scan stores the matches
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)

    page.goto(f"{app_server['url']}/matches")
    rows = page.locator(".match-row")
    expect(rows).to_have_count(3)  # two title searches and one film TMDB does not know
    heat = rows.filter(has_text="Heat (1995)")
    heat.get_by_role("button", name="Correct").click()
    heat.locator(".candidate").filter(has_text="Heat 2").get_by_role("button", name="Use this").click()
    expect(page.locator("#matches-message")).to_contain_text("Heat (1995) → Heat 2 (2026)")
    expect(page.locator("#rescan")).to_be_visible()
    store = app_server["store"]
    assert store.get_id("title:heat|1995")["tmdb_id"] == 111
    expect(rows).to_have_count(2)  # a corrected match is certain

    page.locator("#show-all").check()
    page.locator(".match-row").filter(has_text="Heat (1995)").get_by_role(
        "button", name="Undo correction"
    ).click()
    expect(page.locator("#matches-message")).to_contain_text("looked up again")
    assert store.get_id("title:heat|1995") is None


ATTACK = '<img src=x onerror="window.attacked = true">'
HOSTILE_BACKUP = {
    "version": 1,
    "favorites": [{"key": "1", "title": "Evil favorite", "year": ATTACK}],
    "scans": [
        {
            "created": 1000.0,
            "country": "DE",
            "results": [
                {
                    "title": "Evil",
                    "tmdb_id": 5,
                    "year": ATTACK,
                    "runtime": ATTACK,
                    "providers": {"Netflix": ["flatrate"]},
                }
            ],
            "unavailable": [{"title": "Evil too", "key": "x", "year": ATTACK}],
        }
    ],
}


def test_hostile_backup_restored_on_the_settings_page_runs_no_script(app_server, page, tmp_path):
    expect = playwright_api.expect
    backup_file = tmp_path / "backup.json"
    backup_file.write_text(json.dumps(HOSTILE_BACKUP), encoding="utf-8")
    page.goto(f"{app_server['url']}/settings")
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#backup-file").set_input_files(str(backup_file))
    expect(page.locator("#backup-message")).to_contain_text("Restored: 1 favorites")

    # Open the page without a new scan replacing the restored one.
    with patch("watchlist_app.scan_service.load_watchlist", side_effect=FileNotFoundError("no list")):
        page.goto(app_server["url"])
        expect(page.locator('article.film[data-key="5"]')).to_have_count(1, timeout=15000)
    assert page.evaluate("() => window.attacked") is None
    assert page.locator("article.film img[src='x']").count() == 0
    expect(page.locator('article.film[data-key="5"] .year')).to_contain_text("Year unknown")


def test_another_web_site_cannot_restore_a_backup(app_server, page):
    """A page on another origin posts a backup to the app, as an attack would."""
    attacker = Flask("attacker")

    @attacker.get("/")
    def evil_page():
        return f"""<script>
        const body = new FormData();
        body.append('backup', new Blob([{json.dumps(json.dumps(HOSTILE_BACKUP))}]), 'backup.json');
        fetch('{app_server["url"]}/api/backup', {{method: 'POST', mode: 'no-cors', body}})
          .finally(() => {{ document.title = 'sent'; }});
        </script>"""

    server = make_server("127.0.0.1", 0, attacker)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        page.goto(f"http://127.0.0.1:{server.server_port}/")
        playwright_api.expect(page).to_have_title("sent")
    finally:
        server.shutdown()
    assert app_server["store"].list_favorites() == []
    assert app_server["store"].latest_scan("DE") is None
