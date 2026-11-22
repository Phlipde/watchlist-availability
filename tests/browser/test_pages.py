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

from watchlist_app import letterboxd
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
            "release_dates": {"DE": {"certification": "16", "home": "2099-03-01"}},
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
            "similar_ids": [949, 111],
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
    # Wide, so that Year, Runtime and Rating stay in the filter bar; one test makes the window narrow on purpose.
    context = browser.new_context(service_workers="block", viewport={"width": 2400, "height": 1000})
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield page
    context.close()
    assert errors == [], f"JavaScript errors: {errors}"


def tick_all_services(page) -> None:
    """Tick every service in the services menu, group by group, as a person would."""
    page.locator("#services-button").click()
    for toggle in page.locator("#services-menu [data-group-toggle]:visible").all():
        group = toggle.locator("xpath=ancestor::section[1]")
        if group.locator("input:not(:checked)").count():
            toggle.click()
    page.locator("#services-button").click()


def clear_services(page) -> None:
    page.locator("#services-button").click()
    page.locator("#clear-providers").click()
    page.keyboard.press("Escape")


def visible_titles(page) -> list[str]:
    return sorted(page.locator("article.film:visible .film-title").all_inner_texts())


def test_scan_filters_and_favorite(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    # The page starts a scan; only the saved subscription (Netflix) is selected.
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    expect(page.locator("#visible-count")).to_have_text("1")
    assert visible_titles(page) == ["Heat"]

    tick_all_services(page)
    expect(page.locator("#visible-count")).to_have_text("2")
    assert visible_titles(page) == ["Alien", "Heat"]

    page.locator("#film-search").fill("ali")
    expect(page.locator("#visible-count")).to_have_text("1")
    assert visible_titles(page) == ["Alien"]

    # The services chip goes back to the saved subscriptions.
    page.locator(".filter-chip[data-services] .chip-remove").click()
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


def test_tonight_page_rows_chips_and_pick_for_me(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"])
    # Only Netflix is a saved subscription: one row for it, nothing free.
    expect(page.locator(".film-row h2").first).to_have_text("On Netflix 1", timeout=15000)
    expect(page.locator("#context-text")).to_contain_text("1 films available on 1 services")
    expect(page.locator(".film-row .film-title")).to_have_text(["Heat"])
    # Quick chips narrow every row: Heat runs 120 minutes.
    page.locator('.quick-chip[data-chip="tonight"]').click()
    expect(page.locator(".film-row .film-title")).to_have_text(["Heat"])
    page.locator('.quick-chip[data-chip="short"]').click()
    expect(page.locator("#tonight-rows")).to_contain_text("No film fits")
    page.locator('.quick-chip[data-chip="short"]').click()
    page.locator('.quick-chip[data-chip="tonight"]').click()
    # "Pick for me" opens the details of a film from the rows.
    page.locator("#pick-for-me").click()
    expect(page.locator("#film-details-title")).to_have_text("Heat")
    expect(page.locator("#pick-for-me")).to_contain_text("Again")
    # The drawer covers the button, so it carries the reason and a way to roll again.
    expect(page.locator("#film-details-content .pick-reason")).to_contain_text("Picked for you")
    page.get_by_role("button", name="Pick another").click()
    expect(page.locator("#film-details-title")).to_have_text("Heat")  # the only film that fits
    # An old watchlist link to "/" with filters goes to the watchlist page.
    page.goto(app_server["url"] + "/?genre=Action")
    expect(page).to_have_url(re.compile(r"/watchlist\?genre=Action"))


def test_trailer_from_the_details_window_is_in_front(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    page.locator('article.film[data-key="949"] .film-open').click()
    # Bootstrap ignores hide() while a dialog is still fading in; a person never clicks that fast.
    page.wait_for_function("document.getElementById('film-details-modal').contains(document.activeElement)")
    page.locator("#film-details-content .trailer-link").click()
    expect(page.locator("#trailer-modal")).to_be_visible()
    expect(page.locator("#film-details-modal")).to_be_hidden()


def free_tagged(page) -> list[str]:
    return sorted(
        page.locator("label:has(.free-tag)").evaluate_all(
            "labels => labels.map(l => l.dataset.providerLabel)"
        )
    )


def test_similar_film_on_own_service_opens_from_the_details(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    tick_all_services(page)
    page.locator('article.film[data-key="348"] .film-open').click()
    # Heat runs on Netflix (a subscription); Heat 2 is not on the watchlist.
    similar = page.locator("#film-details-content .film-modal-similar")
    expect(similar).to_contain_text("Similar on your services")
    similar.get_by_role("button", name="Heat (1995)").click()
    expect(page.locator("#film-details-title")).to_have_text("Heat")


def test_coming_soon_and_age_rating(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    # Heat comes out at home in 2099 and is rated 16 in Germany.
    page.locator("#coming-panel summary").click()
    expect(page.locator("#coming-list")).to_contain_text("Heat (1995)")
    expect(page.locator("#coming-list")).to_contain_text("rated 16")
    page.locator("#coming-list .film-open").click()
    expect(page.locator("#film-details-content .film-modal-release")).to_contain_text("Coming at home")
    page.locator("#film-details-modal .btn-close").click()
    expect(page.locator("#film-details-modal")).to_be_hidden()
    page.locator("#more-filters > summary").click()
    page.locator("#age-chips .chip[data-age='16']").click()
    expect(page.locator("#visible-count")).to_have_text("1")
    expect(page.locator("#age-filter")).to_have_value("16")
    expect(page.locator("#age-chips .chip[data-age='16']")).to_have_attribute("aria-pressed", "true")
    assert "ages=16" in page.url


def test_free_labels_follow_the_country(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
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
    expect(page.locator("#status-message")).to_have_text(re.compile(r"^Saved results from "))
    assert wait_until(lambda: "Arte" in free_tagged(page))
    assert not [line for line in requests if line.startswith("POST") and line.endswith("/api/scan")]


def test_saved_results_show_the_tools(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    # A second visit finds the saved scan and starts none: sorting, compare and the rest must still be there.
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#status-message")).to_have_text(re.compile(r"^Saved results from "))
    expect(page.locator("#favorites-view")).to_be_visible()
    expect(page.locator(".stats-link a")).to_have_attribute("href", "/stats")
    expect(page.locator("#retry-scan")).to_have_text("Scan now")
    # A filter set from a link must show as a chip, also when its control sits in a closed panel.
    page.goto(app_server["url"] + "/watchlist?votes=1000")
    expect(page.locator("#filter-chips")).to_contain_text("Votes: 1k+")
    page.goto(app_server["url"] + "/watchlist?age=16&ages=")
    expect(page.locator("#more-filters > summary")).to_have_text("More filters · 1")


def test_filters_from_a_link_survive_the_scan(app_server, page):
    expect = playwright_api.expect
    # The genre list is filled only when films arrive; the genre from the link must wait for it.
    page.goto(app_server["url"] + "/watchlist?genre=Action&rating=7&providers=Netflix,Arte")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    expect(page.locator('#genre-list input[value="Action"]')).to_be_checked()
    expect(page.locator("#visible-count")).to_have_text("1")
    assert visible_titles(page) == ["Heat"]
    # The same link again, now from the saved scan.
    page.reload()
    expect(page.locator('#genre-list input[value="Action"]')).to_be_checked()
    # An old link's rating=7 is the TMDB rating; its chip clears it.
    expect(page.locator("#rating-filter")).to_have_value("tmdb:7")
    page.locator('.filter-chip[data-filter-id="rating-filter"] .chip-remove').click()
    expect(page.locator("#rating-filter")).to_have_value("")
    # The genre chip clears the genre.
    page.locator('.filter-chip[data-genre-include="Action"] .chip-remove').click()
    expect(page.locator('#genre-list input[value="Action"]')).not_to_be_checked()
    # The favorite status only belongs to the favorites view.
    expect(page.locator("#favorite-status-filter")).to_be_hidden()
    page.locator("#favorites-view").click()
    expect(page.locator("#favorite-status-filter")).to_be_visible()


def test_keyboard_keeps_its_place(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    # The star redraws the card; the focus must stay on the same star.
    star = page.locator('article.film[data-key="949"] button.favorite')
    star.focus()
    page.keyboard.press("Enter")
    expect(star).to_have_attribute("aria-pressed", "true")
    expect(star).to_be_focused()
    # Details open from the keyboard and Escape brings the focus back to the title link.
    details = page.locator('article.film[data-key="949"] .film-open')
    details.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#film-details-modal")).to_be_visible()
    # Bootstrap moves the focus into the dialog once it has faded in; Escape works from then on.
    page.wait_for_function("document.getElementById('film-details-modal').contains(document.activeElement)")
    page.keyboard.press("Escape")
    expect(page.locator("#film-details-modal")).to_be_hidden()
    expect(details).to_be_focused()


def test_phone_filter_sheet_stays_open_while_choosing(app_server, page):
    expect = playwright_api.expect
    page.set_viewport_size({"width": 375, "height": 800})
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    page.locator("#tools-toggle").click()
    expect(page.locator("#film-search")).to_be_focused()
    # Open on a phone, the filter sheet is a modal dialog and the page behind it cannot be reached.
    sheet = page.locator("#film-filters")
    expect(sheet).to_have_attribute("role", "dialog")
    expect(sheet).to_have_attribute("aria-modal", "true")
    # The sheet reaches the bottom edge and has a way out and a Reset.
    assert page.evaluate("document.getElementById('film-filters').getBoundingClientRect().bottom") == 800
    expect(page.locator("#filter-sheet-close")).to_be_visible()
    expect(page.locator("#filter-sheet-reset")).to_be_visible()
    assert page.evaluate("document.getElementById('app-header').inert")
    page.locator("#services-button").click()
    for name, checked in (("Arte", True), ("Netflix", False), ("Netflix", True)):
        page.locator(f'#services-menu input[value="{name}"]').set_checked(checked)
        expect(page.locator("body")).to_have_class(re.compile("tools-open"))
    expect(page.locator("#filter-sheet-done")).to_have_text("Show 2 films")
    page.locator("#filter-sheet-done").click()
    expect(page.locator("body")).not_to_have_class(re.compile("tools-open"))
    expect(page.locator("#tools-toggle")).to_be_focused()
    expect(sheet).to_have_attribute("role", "search")
    assert not page.evaluate("document.getElementById('app-header').inert")


def test_skip_link_and_three_stops_per_card(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    # The first Tab reaches the skip link; it jumps past header and services to the films.
    page.keyboard.press("Tab")
    expect(page.locator(".skip-link")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#results")).to_be_focused()
    # Per card the keyboard stops at the title (it opens the details), the line about where to watch, the
    # heart and the three actions; only the active card has stops, so one more Tab leaves the list.
    first = page.locator("article.film").first
    stops = []
    for _ in range(9):
        page.keyboard.press("Tab")
        inside = first.evaluate("card => card.contains(document.activeElement)")
        if not inside:
            break
        stops.append(page.evaluate("document.activeElement.className.split(' ')[0]"))
    assert stops[0] == "film-open"
    assert "favorite" in stops and "best-way-link" in stops and stops.count("card-action") == 3
    # After the skip link, closing the details returns the focus to the title (no #results to go back to).
    first.locator(".film-open").focus()
    page.keyboard.press("Enter")
    page.wait_for_function("document.getElementById('film-details-modal').contains(document.activeElement)")
    page.keyboard.press("Escape")
    expect(first.locator(".film-open")).to_be_focused()


def test_no_match_offers_a_way_out(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    page.locator("#film-search").fill("nothing like this")
    expect(page.locator("#filters-empty")).to_be_visible()
    expect(page.locator("#filter-chips")).to_contain_text("Reset all")
    # The way out names the filter that keeps the films away.
    expect(page.locator("#filters-empty-hint")).to_have_text("Without the search filter there would be 1.")
    page.locator("#empty-reset").click()
    expect(page.locator("#film-search")).to_have_value("")
    expect(page.locator("#filters-empty")).to_be_hidden()
    expect(page.locator("#visible-count")).to_have_text("1")
    # Without any ticked service the empty state offers the saved subscriptions.
    clear_services(page)
    expect(page.locator("#empty-subscriptions")).to_be_visible()
    page.locator("#empty-subscriptions").click()
    expect(page.locator("#visible-count")).to_have_text("1")


def test_removed_favorite_comes_back_with_undo(app_server, page):
    expect = playwright_api.expect
    store = app_server["store"]
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    star = page.locator('article.film[data-key="949"] button.favorite')
    star.click()
    expect(star).to_have_attribute("aria-pressed", "true")
    page.locator("#favorites-view").click()
    page.locator('article.film[data-key="949"] .favorite-note').fill("with Lisa")
    page.locator('article.film[data-key="949"] .favorite-note').blur()
    assert wait_until(lambda: store.list_favorites()[0].get("notes") == "with Lisa")
    page.locator("#favorites-view").click()
    star.click()
    assert wait_until(lambda: store.list_favorites() == [])
    page.locator("#toast-undo").click()
    assert wait_until(lambda: [f.get("notes") for f in store.list_favorites()] == ["with Lisa"])
    expect(star).to_have_attribute("aria-pressed", "true")


def test_a_note_that_could_not_be_saved_is_marked(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    # The finished scan redraws the cards; typing before that would land in a card that is replaced.
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    card = page.locator('article.film[data-key="949"]')
    card.locator("button.favorite").click()
    expect(card.locator("button.favorite")).to_have_attribute("data-favorite", "true")
    # Status and note sit on the card only in the favorites view.
    expect(card.locator(".favorite-note")).to_have_count(0)
    page.locator("#favorites-view").click()
    # A redraw while typing (a finished scan does the same) keeps the text and the focus.
    card.locator(".favorite-note").press_sequentially("Watch with")
    page.evaluate("document.getElementById('sort-order').dispatchEvent(new Event('change', {bubbles: true}))")
    expect(card.locator(".favorite-note")).to_have_value("Watch with")
    expect(card.locator(".favorite-note")).to_be_focused()
    page.route(
        "**/api/favorites/*",
        lambda route: route.abort() if route.request.method == "PATCH" else route.continue_(),
    )
    card.locator(".favorite-note").fill("Watch with Lisa")
    card.locator(".favorite-note").blur()
    expect(card.locator(".favorite-note")).to_have_class(re.compile("is-invalid"))
    expect(page.locator("#app-toast")).to_have_class(re.compile("toast-error"))
    expect(page.locator("#toast-message")).to_contain_text("Could not save the note")
    # The text typed before the redraw was saved; the failed save did not replace it.
    assert app_server["store"].list_favorites()[0].get("notes", "") == "Watch with"


def test_settings_are_saved_and_checked(app_server, page):
    expect = playwright_api.expect
    page.goto(f"{app_server['url']}/settings")
    page.locator("#letterboxd-username").fill("bad name!")
    page.get_by_role("button", name="Save settings").click()
    expect(page.locator("#settings-message")).to_contain_text("may only contain")

    page.locator("#letterboxd-username").fill("someone_else")
    page.get_by_role("button", name="Save settings").click()
    expect(page.locator("#settings-message")).to_have_text("Saved.")
    assert app_server["settings"].letterboxd_username == "someone_else"


def test_price_is_saved_when_you_leave_the_field(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    page.goto(f"{app_server['url']}/subscriptions")
    netflix = page.locator('tr[data-service="Netflix"]')
    netflix.locator('[name="price"]').fill("10,5")  # a comma is fine
    netflix.locator('[name="price"]').blur()
    expect(page.locator("#save-state")).to_have_text("Saved")
    assert app_server["settings"].costs("DE")["Netflix"]["price"] == 10.5
    # The total follows without a reload.
    expect(page.locator("#total-month")).to_contain_text(re.compile(r"10[.,]50"))
    page.reload()
    expect(netflix.locator('[name="price"]')).to_have_value("10.5")


def test_services_are_saved_as_you_tick_and_can_be_undone(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    page.goto(f"{app_server['url']}/settings/services")
    page.locator('#services-sections input[value="MUBI"]').check(force=True)
    expect(page.locator("#toast-text")).to_have_text("Saved")
    assert sorted(app_server["settings"].subscriptions("DE")) == ["MUBI", "Netflix"]
    page.locator("#toast-undo").click()
    expect(page.locator("#toast-text")).to_have_text("Undone")
    assert app_server["settings"].subscriptions("DE") == ["Netflix"]
    expect(page.locator('#services-sections input[value="MUBI"]')).not_to_be_checked()
    assert app_server["settings"].country == "DE"


def test_title_match_is_corrected_and_undone(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")  # the scan stores the matches
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)

    page.goto(f"{app_server['url']}/settings/matches")
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
        page.goto(app_server["url"] + "/watchlist")
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


def test_details_window_has_its_own_address(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    modal = page.locator("#film-details-modal")
    # A click anywhere on the card opens the details and writes ?film= into the address.
    page.locator('article.film[data-key="949"]').click(position={"x": 60, "y": 60})
    expect(modal).to_be_visible()
    expect(page).to_have_url(re.compile(r"[?&]film=949"))
    page.wait_for_function("document.getElementById('film-details-modal').contains(document.activeElement)")
    # Back closes the window and takes film= out again.
    page.go_back()
    expect(modal).to_be_hidden()
    assert "film=" not in page.url
    # Ctrl-click leaves the page alone (the browser opens a new tab).
    with page.context.expect_page() as new_tab:
        page.locator('article.film[data-key="949"] .film-open').click(modifiers=["Control"])
    new_tab.value.close()
    expect(modal).to_be_hidden()
    # A shared link opens the film; an unknown one gets a note and is taken out of the address.
    page.goto(f"{app_server['url']}/watchlist?film=949")
    expect(page.locator("#film-details-title")).to_have_text("Heat", timeout=15000)
    page.goto(f"{app_server['url']}/watchlist?film=nope")
    expect(page.locator("#toast-message")).to_contain_text("not on this watchlist", timeout=15000)
    assert "film=" not in page.url


def test_stats_page_shows_the_numbers_of_the_last_scan(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    page.get_by_role("link", name="Stats").first.click()
    expect(page.locator("#stats-root")).to_have_attribute("aria-busy", "false")
    expect(page.locator(".stat-tile").first).to_contain_text("films on the watchlist")
    expect(page.locator(".stats-card", has_text="Genres").locator(".bars li").first).to_be_visible()
    expect(page.locator(".stats-table").last).to_contain_text("Netflix")


def test_filter_bar_cost_genres_runtime_and_the_address(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    tick_all_services(page)
    expect(page.locator("#visible-count")).to_have_text("2")
    # Cost: Free leaves Heat (Netflix subscription) out; each segment shows its count.
    expect(page.locator('[data-cost-count="free"]')).to_have_text("1")
    page.locator('#cost-options label:has(input[value="free"])').click()
    assert visible_titles(page) == ["Alien"]
    expect(page).to_have_url(re.compile(r"[?&]cost=free"))
    page.locator('#cost-options label:has(input[value="all"])').click()
    # Genres: "No" excludes Action; the menu counts per genre.
    page.locator("#genre-pop summary").click()
    expect(page.locator('[data-genre-count="Action"]')).to_have_text("1")
    page.locator('#genre-list .genre-exclude[data-genre="Action"]').click()
    page.keyboard.press("Escape")
    assert visible_titles(page) == ["Alien"]
    expect(page.locator('.filter-chip[data-genre-exclude="Action"]')).to_have_text("No Action")
    expect(page).to_have_url(re.compile(r"[?&]nogenre=Action"))
    # The whole state survives a reload through the address.
    page.reload()
    expect(page.locator("#progress-count")).to_have_text(re.compile("Complete|Saved"), timeout=15000)
    assert visible_titles(page) == ["Alien"]
    page.locator('.filter-chip[data-genre-exclude="Action"] .chip-remove').click()
    # Runtime: Heat runs 120 min, Alien has no runtime, so a limit keeps only Heat.
    page.locator("#runtime-pop summary").click()
    page.locator('#runtime-pop label:has(input[value="120"])').click()
    page.keyboard.press("Escape")
    assert visible_titles(page) == ["Heat"]
    runtime_chip = page.locator('.filter-chip[data-filter-id="runtime-filter"]')
    expect(runtime_chip).to_have_text("Runtime: Up to 120 min")


def test_filter_menus_stay_inside_the_window(app_server, page):
    expect = playwright_api.expect
    page.set_viewport_size({"width": 820, "height": 800})
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    for name in ("services-pop", "genre-pop", "runtime-pop", "more-filters", "sort-pop"):
        if page.locator(f"#{name}.is-moved").count():
            continue  # it moved into the "More filters" panel (see the test below)
        page.locator(f"#{name} > summary").click()
        box = page.locator(f"#{name} > .filter-menu").bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= 820, name
        page.locator(f"#{name} > summary").click()  # close it again: an open panel may cover the next button


def test_year_and_runtime_move_into_more_filters_when_the_bar_wraps(app_server, page):
    expect = playwright_api.expect
    page.set_viewport_size({"width": 2400, "height": 900})
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    page.set_viewport_size({"width": 830, "height": 900})
    expect(page.locator("#moved-slot > #year-pop.is-moved")).to_have_count(1)
    page.locator("#more-filters > summary").click()
    expect(page.locator("#moved-slot #year-chips")).to_be_visible()  # shown inline in the panel
    page.locator("#moved-slot #year-chips .chip", has_text="Before 2000").click()
    assert page.locator("#year-to").input_value() == "1999"
    expect(page.locator("#more-filters-count")).to_have_text("· 1")  # a moved filter is counted on the button
    expect(page.locator("#moved-slot > #rating-pop.is-moved")).to_have_count(1)  # Rating gives way after Year and Runtime
    page.locator("#moved-slot #rating-pop input[value=tmdb]").check(force=True)
    page.locator("#moved-slot #rating-chips-tmdb .chip", has_text="7+").first.click()
    expect(page.locator("#rating-filter")).to_have_value("tmdb:7")
    expect(page.locator("#more-filters-count")).to_have_text("· 2")
    expect(page.locator("#more-filters")).to_have_attribute("open", "")  # clicking inside did not close the panel
    page.keyboard.press("Escape")
    page.set_viewport_size({"width": 2400, "height": 900})
    expect(page.locator("#moved-slot > .filter-pop")).not_to_have_count(2)  # with room, at least one control moves back
    expect(page.locator("#year-to")).to_have_value("1999")  # the value stays


def test_year_and_rating_panels_and_service_search(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    page.locator("#year-pop > summary").click()
    page.locator(
        "#year-chips .chip", has_text="1990s"
    ).count()  # chips are fixed: 2020s, 2010s, 2000s, Before 2000
    page.locator("#year-chips .chip", has_text="Before 2000").click()
    assert page.locator("#year-to").input_value() == "1999"
    expect(page.locator("#filter-chips")).to_contain_text("To: 1999")
    expect(page.locator("#year-reset")).to_be_visible()
    # A chip's text opens its panel, its x removes only that filter.
    page.keyboard.press("Escape")
    page.locator("#filter-chips .chip-open", has_text="To: 1999").click()
    expect(page.locator("#year-pop")).to_have_attribute("open", "")
    page.locator("#filter-chips .filter-chip[data-filter-id='year-to'] .chip-remove").click()
    expect(page.locator("#year-to")).to_have_value("")
    page.locator("#rating-pop > summary").click()
    page.locator("#rating-pop input[value=tmdb]").check(force=True)
    page.locator("#rating-chips-tmdb .chip", has_text="7+").first.click()
    expect(page.locator("#rating-filter")).to_have_value("tmdb:7")
    assert "rating=tmdb%3A7" in page.url or "rating=tmdb:7" in page.url
    page.locator("#rating-reset").click()
    expect(page.locator("#rating-filter")).to_have_value("")
    # The services menu finds a service that is not one of the own ones.
    page.locator("#services-button").click()
    page.locator("#services-search").fill("zzzz")
    expect(page.locator("#services-list .services-group:visible")).to_have_count(0)


def test_card_menu_sets_a_film_aside_and_marks_it_watched_with_undo(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    titles = visible_titles(page)
    first = page.locator("article.film").first
    name = first.locator(".film-title").inner_text()
    # Watched: the poster says so, the toast offers Undo.
    first.hover()  # the action bar shows while the pointer is on the card
    first.get_by_role("button", name="Grey out").click()
    expect(page.locator("#toast-message")).to_contain_text("greyed out")
    expect(page.locator("article.film", has_text=name).locator(".poster-badge")).to_have_text("Greyed out")
    assert any(item["flag"] == "watched" for item in app_server["store"].list_flags())
    page.locator("#toast-undo").click()
    expect(page.locator("article.film", has_text=name).locator(".poster-badge")).to_have_count(0)
    assert app_server["store"].list_flags() == []
    # Not now: the film leaves the list until the filter asks for it.
    first = page.locator("article.film").first
    first.hover()
    first.get_by_role("button", name="Not now (30 days)").click()
    expect(page.locator("article.film")).to_have_count(len(titles) - 1)
    page.locator("#more-filters > summary").click()
    page.locator("#show-hidden").check()
    expect(page.locator("article.film")).to_have_count(len(titles))
    assert "hidden=1" in page.url


def test_arrow_keys_and_buttons_move_through_the_films_in_the_drawer(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    tick_all_services(page)
    expect(page.locator("article.film")).to_have_count(2)
    titles = page.locator("article.film .film-title").all_inner_texts()
    page.locator("article.film .film-open").first.click()
    expect(page.locator("#film-details-title")).to_have_text(titles[0])
    page.locator("#film-next").click()
    expect(page.locator("#film-details-title")).to_have_text(titles[1])
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#film-details-title")).to_have_text(titles[0])


def test_keyboard_shortcuts(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    page.keyboard.press("?")
    expect(page.locator("#shortcuts-dialog")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#shortcuts-dialog")).to_be_hidden()
    page.keyboard.press("/")
    expect(page.locator("#film-search")).to_be_focused()
    page.keyboard.type("s")  # typing in the search must not trigger a shortcut
    assert app_server["store"].list_flags() == []
    page.locator("#film-search").fill("")
    # "s" marks the card in focus as watched; "g" then "s" goes to the subscriptions.
    page.locator("article.film .film-open").first.focus()
    page.keyboard.press("s")
    expect(page.locator("article.film .poster-badge")).to_have_text("Greyed out")
    page.keyboard.press("g")
    page.keyboard.press("s")
    expect(page).to_have_url(re.compile(r"/subscriptions$"))


def test_deadline_banner_and_hidden_recommendation(app_server, page):
    expect = playwright_api.expect
    import datetime

    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    soon = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
    app_server["settings"].update({"costs": {"Netflix": {"price": 10, "remind_on": soon}}})
    page.goto(app_server["url"] + "/subscriptions")
    expect(page.locator("#deadline-banner")).to_contain_text(
        "Netflix: renewal or cancellation date in 2 days"
    )
    page.get_by_role("button", name="Dismiss").click()
    expect(page.locator("#deadline-banner")).to_be_hidden()
    page.reload()
    expect(page.locator("#deadline-banner")).to_be_hidden()  # dismissed in this browser
    page.goto(app_server["url"])  # Tonight shows the same banner unless dismissed
    expect(page.locator("#deadline-banner")).to_be_hidden()
    page.evaluate("localStorage.clear()")
    page.reload()
    expect(page.locator("#deadline-banner")).to_be_visible()
    expect(page.locator("#deadline-banner a")).to_have_attribute("href", "/subscriptions")


def test_service_drawer_saves_notes_and_splits_the_price(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    # A finished scan saved one history row for the own paid service.
    assert "Netflix" in app_server["store"].service_history("DE")
    page.goto(f"{app_server['url']}/subscriptions")
    netflix = page.locator('tr[data-service="Netflix"]')
    netflix.locator('[name="price"]').fill("12")
    netflix.locator('[name="price"]').blur()
    expect(page.locator("#save-state")).to_have_text("Saved")
    netflix.locator(".service-open").click()
    expect(page.locator("#service-drawer")).to_be_visible()
    expect(page.locator("#service-drawer-title")).to_have_text("Netflix")
    page.locator("#drawer-shared").fill("3")
    page.locator("#drawer-note").fill("family account")
    page.locator("#drawer-note").blur()
    expect(page.locator("#save-state")).to_have_text("Saved")
    saved = app_server["settings"].costs("DE")["Netflix"]
    assert (saved["price"], saved["shared"], saved["note"]) == (12.0, 3, "family account")
    page.keyboard.press("Escape")
    expect(page.locator("#service-drawer")).to_be_hidden()
    expect(netflix.locator(".service-open")).to_be_focused()
    page.reload()
    expect(page.locator("#total-month")).to_contain_text(re.compile(r"4[.,]00"))  # 12 split between 3


def test_planner_what_if_changes_nothing_that_is_saved(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    page.goto(f"{app_server['url']}/subscriptions")
    expect(page.locator("#planner")).to_be_visible()
    expect(page.locator("#whatif-result")).to_contain_text("As it is")
    page.locator('#whatif input[value="Netflix"]').uncheck()
    expect(page.locator("#whatif-result")).to_contain_text("What-if, nothing saved")
    assert app_server["settings"].subscriptions("DE") == ["Netflix"]
    page.locator('#whatif input[value="Netflix"]').check()
    expect(page.locator("#whatif-result")).to_contain_text("As it is")


def test_service_worker_saves_the_page_and_the_data_for_offline_use(app_server, browser):
    expect = playwright_api.expect
    context = browser.new_context()  # the shared page fixture blocks service workers on purpose
    page = context.new_page()
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=15000)
    page.reload()  # now the worker sees the requests
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    saved = page.evaluate(
        """async () => {
            const urls = async name => {
                const keys = await (await caches.open(name)).keys();
                return keys.map(request => new URL(request.url).pathname);
            };
            return {pages: await urls('pages-v1'), files: await urls('static-v1')};
        }"""
    )
    assert "/watchlist" in saved["pages"] and "/api/latest" in saved["pages"]
    assert "/static/js/app.js" in saved["files"] and "/static/css/app.css" in saved["files"]
    context.close()


def test_a_saved_view_comes_back_as_a_chip_on_tonight(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist?max=150")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    page.get_by_text("Save view", exact=True).click()  # the ghost button opens a small popover
    page.locator("#view-name").fill("Short before bed")
    page.locator(".save-pop").get_by_role("button", name="Save", exact=True).click()
    expect(page.locator("#views-menu .menu-item")).to_have_count(1)  # now it is in the Views dropdown
    page.goto(app_server["url"])
    link = page.locator("#tonight-views .saved-view a")
    expect(link).to_have_text("Short before bed")
    assert "max=150" in link.get_attribute("href") and "film=" not in link.get_attribute("href")
    page.get_by_role("button", name="Delete the view Short before bed").click()
    expect(page.locator("#tonight-views")).to_be_hidden()


def test_views_switch_between_grid_compact_and_table(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    page.locator("#view-switch label[title=Table]").click()
    expect(page.locator("#results table.film-table")).to_be_visible()
    expect(page.locator("#results table .film-open").first).to_have_text("Heat")
    page.reload()  # the choice stays
    expect(page.locator("#results table.film-table")).to_be_visible(timeout=15000)
    page.locator("#view-switch label[title=Compact]").click()
    expect(page.locator("#results.view-compact article.film").first).to_be_visible()
    page.locator("#view-switch label[title=Grid]").click()
    expect(page.locator("#results.view-compact")).to_have_count(0)


def test_details_have_one_main_button_and_people_are_search_links(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    page.locator("article.film .film-open").first.click()
    expect(page.locator("#film-details-title")).to_be_visible()
    assert page.locator("#film-details-content .btn-accent").count() <= 1  # only the main button is amber
    for link in page.locator("#film-details-content .film-modal-credits a").all():
        assert "/watchlist?q=" in link.get_attribute("href")


def test_compare_bar_appears_with_the_first_film_and_marks_the_best_value(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    tick_all_services(page)
    expect(page.locator("article.film")).to_have_count(2)
    expect(page.locator("#compare-bar")).to_be_hidden()
    for index in (0, 1):
        card = page.locator("article.film").nth(index)
        card.hover()
        card.get_by_role("button", name=re.compile("comparison")).click()
    expect(page.locator("#compare-count")).to_have_text("2 to compare")
    page.locator("#compare-go").click()
    expect(page.locator("#compare-table")).to_be_visible()
    expect(page.locator("#compare-table th", has_text="Runtime")).to_be_visible()
    page.keyboard.press("Escape")
    page.locator("#compare-bar-clear").click()
    expect(page.locator("#compare-bar")).to_be_hidden()


def test_a_failed_scan_says_what_is_wrong_and_offers_to_try_again(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    with patch(
        "watchlist_app.scan_service.load_watchlist",
        side_effect=letterboxd.LetterboxdError("Could not load the Letterboxd watchlist."),
    ):
        page.locator("#sync-toggle").click()
        page.locator("#retry-scan").click()
        banner = page.locator("#state-banner")
        expect(banner).to_be_visible(timeout=15000)
        expect(banner).to_contain_text("Letterboxd is not responding")
        expect(banner).to_contain_text("Showing the data from")
    # Try again with the stub working again: the banner goes away.
    expect(banner).to_be_visible()
    page.locator("#sync-toggle").click()  # close the sync panel: it covers the banner
    page.locator("#state-retry").click()
    expect(page.locator("#state-banner")).to_be_hidden(timeout=15000)


def test_details_actions_sit_in_one_row_with_a_clear_main_button(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    tick_all_services(page)
    page.locator('article.film[data-key="348"] .film-open').click()
    toolbar = page.locator("#film-details-content .film-modal-toolbar .tool")
    expect(toolbar).to_have_count(5)
    tops = toolbar.evaluate_all("buttons => buttons.map(b => Math.round(b.getBoundingClientRect().top))")
    assert len(set(tops)) == 1  # one row, nothing wraps
    expect(page.get_by_role("button", name="Grey out this film")).to_be_visible()


def test_header_says_synced_in_words_right_after_a_scan(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    # The new scan has arrived: never "Out of date" beside fresh data; the words show on a desktop.
    expect(page.locator("#sync-label")).to_have_text("Synced just now")
    expect(page.locator("#sync-label")).to_be_visible()


def test_cards_in_a_row_are_equally_high_and_say_where_to_watch_in_one_line(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    tick_all_services(page)
    cards = page.locator("article.film")
    expect(cards).to_have_count(2)
    heights = cards.evaluate_all(
        "cards => cards.map(card => Math.round(card.getBoundingClientRect().height))"
    )
    assert len(set(heights)) == 1  # no gaps in the grid from cards with more or fewer logos
    for index in (0, 1):
        assert cards.nth(index).locator(".best-way").count() == 1
        assert "€" not in cards.nth(index).locator(".card-foot").inner_text()  # no prices


def test_details_title_sits_in_the_hero_and_the_button_always_says_what_to_do(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    tick_all_services(page)
    page.locator('article.film[data-key="348"] .film-open').click()
    expect(page.locator("#film-details-content .film-hero-title")).to_have_text("Alien")
    expect(page.locator("#film-details-content .film-modal-primary")).to_have_text(
        re.compile(r"(Watch on|Rent on|Buy on|On .+ \(not your service\)|Not streaming)")
    )
    expect(page.locator("#film-details-content")).not_to_contain_text("Where to watch")
    expect(page.locator("#film-details-content")).not_to_contain_text(
        "Your service"
    )  # no badge in the top part


def test_flags_are_pictures_served_by_the_app(app_server, page):
    # Emoji flags show as letters on Windows, so the flags are SVG files of the app itself.
    for code in ("nl", "at", "us", "jp"):
        response = page.request.get(app_server["url"] + f"/static/flags/{code}.svg")
        assert response.ok and "svg" in response.headers["content-type"]


def test_details_never_scroll_sideways(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    tick_all_services(page)
    page.locator('article.film[data-key="348"] .film-open').click()
    content = page.locator("#film-details-content")
    expect(content).to_be_visible()
    page.evaluate("document.getElementById('film-more')?.setAttribute('open', '')")
    assert content.evaluate(
        "el => el.scrollWidth <= el.clientWidth"
    )  # a tooltip or a row must not widen the drawer


@pytest.mark.parametrize("width", [1400, 900, 500])
@pytest.mark.parametrize("view", ["Grid", "Compact", "Table"])
def test_arrow_keys_move_through_the_films_in_every_view_and_width(app_server, page, view, width):
    expect = playwright_api.expect
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    tick_all_services(page)
    page.locator(f"#view-switch label[title={view}]").click()
    page.set_viewport_size({"width": width, "height": 900})
    items = page.locator("#results tr[data-key]" if view == "Table" else "#results article.film")
    expect(items).to_have_count(2)
    keys = items.evaluate_all("rows => rows.map(row => row.dataset.key)")
    focused = "document.activeElement.closest('[data-key]')?.dataset.key"
    # Only the first film holds the tab stop; the arrows move it.
    assert items.nth(1).locator(".film-open").get_attribute("tabindex") == "-1"
    items.nth(0).locator(".film-open").focus()
    columns = page.evaluate(
        "() => { const tops = [...document.querySelectorAll('#results article.film, #results tr[data-key]')]"
        ".map(el => Math.round(el.getBoundingClientRect().top));"
        " return tops.filter(top => top === tops[0]).length; }"
    )
    page.keyboard.press("ArrowRight" if view != "Table" and columns > 1 else "ArrowDown")
    assert page.evaluate(focused) == keys[1]
    assert items.nth(1).locator(".film-open").get_attribute("tabindex") == "0"  # the tab stop moved with it
    assert items.nth(0).locator(".film-open").get_attribute("tabindex") == "-1"
    page.keyboard.press("Home")
    assert page.evaluate(focused) == keys[0]
    page.keyboard.press("End")
    assert page.evaluate(focused) == keys[1]
    # Enter opens the details; Escape returns the focus to that film; the arrows page through the drawer.
    page.keyboard.press("Enter")
    expect(page.locator("#film-details-modal")).to_have_class(re.compile("show"))
    page.wait_for_function("document.getElementById('film-details-modal').contains(document.activeElement)")
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#film-details-title")).to_have_text(items.nth(0).locator(".film-open").inner_text())
    page.keyboard.press("Escape")
    expect(page.locator("#film-details-modal")).to_be_hidden()
    page.wait_for_function(f"{focused} === '{keys[0]}'")  # back on the film the drawer showed last


def test_arrow_keys_move_through_the_tonight_rows(app_server, page):
    expect = playwright_api.expect
    # Two saved subscriptions give two rows (Free and On Netflix) that share a film.
    response = page.request.put(
        app_server["url"] + "/api/settings", data={"subscriptions": ["Netflix", "Arte"]}
    )
    assert response.ok
    page.goto(app_server["url"])
    expect(page.locator(".film-row").first).to_be_visible(timeout=15000)
    rows = page.locator(".film-row")
    assert rows.count() >= 2
    first_row = rows.nth(0).locator("article.film")
    second_row = rows.nth(1).locator("article.film")
    # One tab stop in all the rows: the first film.
    assert first_row.nth(0).locator(".film-open").get_attribute("tabindex") == "0"
    assert second_row.nth(0).locator(".film-open").get_attribute("tabindex") == "-1"
    first_row.nth(0).locator(".film-open").focus()
    page.keyboard.press("ArrowDown")
    assert second_row.nth(0).locator(".film-open").evaluate("el => el === document.activeElement")
    assert second_row.nth(0).locator(".film-open").get_attribute("tabindex") == "0"
    assert first_row.nth(0).locator(".film-open").get_attribute("tabindex") == "-1"
    page.keyboard.press("ArrowUp")
    assert first_row.nth(0).locator(".film-open").evaluate("el => el === document.activeElement")
    if first_row.count() > 1:
        page.keyboard.press("ArrowRight")
        assert first_row.nth(1).locator(".film-open").evaluate("el => el === document.activeElement")
        page.keyboard.press("Home")
        assert first_row.nth(0).locator(".film-open").evaluate("el => el === document.activeElement")


def test_on_a_phone_a_tap_on_the_cut_off_description_opens_it(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    tick_all_services(page)
    page.set_viewport_size({"width": 375, "height": 812})
    page.locator("article.film .film-open").first.click()
    box = page.locator("#film-details-content .overview-box")
    long_text = "A very long description. " * 20
    page.evaluate(
        "text => { const box = document.querySelector('#film-details-content .overview-box');"
        " box.classList.add('clamped'); box.querySelector('.film-modal-overview').textContent = text;"
        " if (!box.querySelector('.overview-more')) box.insertAdjacentHTML('beforeend',"
        ' \'<button class="overview-more" type="button">more</button>\'); }',
        long_text,
    )
    expect(box).to_have_class(re.compile("clamped"))
    box.locator(".film-modal-overview").click()
    expect(box).not_to_have_class(re.compile("clamped"))
    expect(box.locator(".overview-more")).to_have_text("less")


def test_a_long_poster_row_does_not_widen_the_details(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    tick_all_services(page)
    page.locator('article.film[data-key="348"] .film-open').click()
    expect(page.locator("#film-details-content .film-modal-body")).to_be_visible()
    # A series of many films (a wrapper around a scrolling row) used to widen the grid and clip text.
    row = (
        '<div class="film-modal-series"><ul class="mini-posters">'
        + '<li><button type="button">x</button></li>' * 20
    )
    page.evaluate(
        "html => document.querySelector('#film-details-content .film-modal-about')"
        ".insertAdjacentHTML('afterbegin', html)",
        row + "</ul></div>",
    )
    # Every block of the drawer ends inside it (the grid itself keeps its width even when its tracks grow).
    assert page.evaluate(
        "() => { const edge = document.getElementById('film-details-content').getBoundingClientRect().right;"
        " return [...document.querySelectorAll('.film-modal-body > *, .film-modal-about > *')]"
        ".every(el => el.getBoundingClientRect().right <= edge); }"
    )


def test_grey_outs_can_be_reset_on_the_data_page(app_server, page):
    expect = playwright_api.expect
    assert page.request.put(app_server["url"] + "/api/flags/348", data={"flag": "watched"}).ok
    page.goto(app_server["url"] + "/settings/data")
    expect(page.locator("#greyouts-text")).to_contain_text("1 film is greyed out")
    page.get_by_role("button", name="Reset grey-outs").click()
    expect(page.locator("#greyouts-text")).to_contain_text("1 grey-outs removed")
    expect(page.get_by_role("button", name="Reset grey-outs")).to_be_disabled()
    assert page.request.get(app_server["url"] + "/api/greyouts").json() == {"flags": 0, "favorites": 0}


def test_data_page_exports_and_previews_an_import_before_changing_anything(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/settings/data")
    with page.expect_download() as download:
        page.locator('[data-export="favorites-json"]').click()
    assert download.value.suggested_filename == "favorites.json"
    records = (
        '[{"key": "9001", "title": "Alien", "year": 1979}, {"key": "9002", "title": "Heat", "year": 1995}]'
    )
    page.locator("#import-favorites").set_input_files(
        files=[{"name": "favorites.json", "mimeType": "application/json", "buffer": records.encode()}]
    )
    expect(page.locator("#import-preview")).to_have_text("2 favorites found · 0 already set · 2 new")
    assert page.request.get(app_server["url"] + "/api/favorites").json() == []  # nothing changed yet
    page.get_by_role("button", name="Import", exact=True).click()
    expect(page.locator("#import-preview")).to_have_text("Imported 2 favorites.")
    assert len(page.request.get(app_server["url"] + "/api/favorites").json()) == 2


def test_the_abroad_switch_adds_films_your_services_have_in_other_countries(app_server, page):
    expect = playwright_api.expect
    store = app_server["store"]
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text(
        "Complete", timeout=15000
    )  # the scan stores the offers
    offers = store.offers_by_country(348)  # Alien: not on Netflix at home
    offers["AT"] = {"Netflix": ["flatrate"]}
    store.save_bundle(348, {"details": {}, "providers": offers})
    page.reload()
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    here = page.locator("article.film").count()
    toggle = page.locator("#abroad-toggle")
    expect(toggle).to_contain_text("+1")  # one more film would come in
    toggle.click()
    expect(page.locator("article.film")).to_have_count(here + 1)
    expect(page.locator("article.film .way-flag")).to_have_count(1)
    expect(page.locator("article.film", has=page.locator(".way-flag")).locator(".best-way")).to_contain_text(
        "Abroad"
    )
    expect(page.locator("#result-meta")).to_contain_text("1 via VPN")
    assert "where=both" in page.url
    expect(page.locator("#filter-chips")).to_contain_text("Where: Here and abroad")
    # "Only abroad" in the panel shows just that film; the switch and the field are one setting.
    page.locator("#more-filters > summary").click()
    page.locator("#where-filter").select_option("abroad")
    expect(page.locator("article.film")).to_have_count(1)
    expect(toggle).to_have_attribute("aria-pressed", "true")
    page.locator("#where-filter").select_option("all")
    expect(page.locator("article.film")).to_have_count(here)
    expect(toggle).to_have_attribute("aria-pressed", "false")


def test_a_card_shows_only_the_logo_and_the_words_come_on_hover(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    tick_all_services(page)
    card = page.locator("article.film").first
    words = card.locator(".best-way-link .way-text")
    expect(words).to_have_css("opacity", "0")  # only the logo (or the name) shows
    assert words.inner_text().strip()  # the words are there for screen readers all the time
    card.locator(".best-way-link").hover()
    expect(words).to_have_css("opacity", "1")
