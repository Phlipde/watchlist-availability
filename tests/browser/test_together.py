"""Browser tests: Together on Tonight (two profiles' lists merged, whose service each logo is)."""

import json

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.browser

HEAT = {"key": "949", "tmdb_id": 949, "title": "Heat", "year": 1995, "providers": {"Netflix": ["flatrate"]}}
UP = {"key": "14160", "tmdb_id": 14160, "title": "Up", "year": 2009, "providers": {"MUBI": ["flatrate"]}}


def _wait_for_my_scan(app_server, page) -> None:
    page.goto(app_server["url"] + "/watchlist")
    playwright_api.expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)


def _open_drawer(page, key: str) -> None:
    page.locator(f'#tonight-rows article.film[data-key="{key}"] .film-open').click()
    page.wait_for_function("document.getElementById('film-details-modal').contains(document.activeElement)")


def test_together_shows_both_lists_with_owner_badges_and_turns_off(app_server, page):
    expect = playwright_api.expect
    store, settings = app_server["store"], app_server["settings"]
    anna = store.add_profile("Anna")
    settings.for_profile(anna).update({"subscriptions": ["MUBI"]})
    store.save_scan("DE", "letterboxd", None, [HEAT, UP], [], {}, profile_id=anna)
    _wait_for_my_scan(app_server, page)
    page.goto(app_server["url"])
    expect(page.locator(".film-row h2").first).to_have_text("On Netflix 1", timeout=15000)

    page.locator("#together-pop > summary").click()
    page.get_by_role("checkbox", name="Anna").check()
    expect(page.locator("#row-both")).to_have_text("On both lists 1")
    expect(page.locator("#row-one")).to_have_text("One of you, unseen 1")
    expect(page.locator("#together-label")).to_have_text("Together with Anna")
    expect(page.locator("#context-text")).to_have_text(
        "2 films available on the 2 services you have between you"
    )
    expect(page.locator("#together-note")).to_be_hidden()  # Anna's scan is fresh
    heat = page.locator('#tonight-rows article.film[data-key="949"]')
    up = page.locator('#tonight-rows article.film[data-key="14160"]')
    expect(page.locator("#tonight-rows section").first.locator(".film-title")).to_have_text(["Heat"])
    expect(heat.locator(".way-badge-owner")).to_have_text("M")
    expect(heat.locator(".lstack-item").first).to_have_attribute(
        "aria-label", "Netflix · Subscription · your service"
    )
    expect(up.locator(".way-badge-owner")).to_have_text("A")
    expect(up.locator(".lstack-item").first).to_have_attribute(
        "data-tip", "MUBI · Subscription · Anna's service"
    )

    # The drawer says whose service the best way is; Anna's film opens though it is not on my list.
    page.locator("#together-pop > summary").click()  # close the menu
    _open_drawer(page, "14160")
    expect(page.locator("#film-details-content .film-modal-primary")).to_have_text(
        "Watch on Anna's MUBI · Subscription"
    )
    page.keyboard.press("Escape")
    expect(page.locator("#film-details-modal")).to_be_hidden()
    _open_drawer(page, "949")
    expect(page.locator("#film-details-content .film-modal-primary")).to_have_text(
        "Watch on your Netflix · Subscription"
    )
    page.keyboard.press("Escape")
    expect(page.locator("#film-details-modal")).to_be_hidden()

    # Remembered in this browser.
    assert json.loads(page.evaluate("localStorage.getItem('p1:togetherWith')")) == [anna]
    page.goto(app_server["url"])
    expect(page.locator("#row-both")).to_have_text("On both lists 1", timeout=15000)

    # One click back to my own rows.
    page.get_by_role("button", name="Back to my list").click()
    expect(page.locator(".film-row h2").first).to_have_text("On Netflix 1")
    expect(page.locator("#together-off")).to_be_hidden()
    expect(page.locator("#tonight-rows .way-badge-owner")).to_have_count(0)
    expect(page.locator("#together-pop > summary")).to_be_focused()
    assert json.loads(page.evaluate("localStorage.getItem('p1:togetherWith')")) == []


def test_together_names_a_partner_without_a_scan_and_says_when_nothing_is_shared(app_server, page):
    expect = playwright_api.expect
    store = app_server["store"]
    store.add_profile("Ben")
    cleo = store.add_profile("Cleo")
    store.save_scan("DE", "letterboxd", None, [UP], [], {}, profile_id=cleo)
    _wait_for_my_scan(app_server, page)
    page.goto(app_server["url"])
    expect(page.locator(".film-row h2").first).to_have_text("On Netflix 1", timeout=15000)
    page.locator("#together-pop > summary").click()
    page.get_by_role("checkbox", name="Ben").check()
    expect(page.locator("#together-note")).to_have_text(
        "Ben has no recent scan for DE — their list may be out of date."
    )
    page.get_by_role("checkbox", name="Ben").uncheck()
    page.get_by_role("checkbox", name="Cleo").check()
    expect(page.locator("#together-note")).to_be_hidden()
    expect(page.locator("#tonight-rows .together-empty")).to_have_text("No film is on both lists.")


def test_together_is_not_offered_with_one_profile(app_server, page):
    page.goto(app_server["url"])
    playwright_api.expect(page.locator(".film-row h2").first).to_have_text("On Netflix 1", timeout=15000)
    assert page.locator("#together-pop").count() == 0


def test_the_grid_in_together_shows_both_lists_and_goes_back_to_mine(app_server, page):
    expect = playwright_api.expect
    store, settings = app_server["store"], app_server["settings"]
    anna = store.add_profile("Anna")
    settings.for_profile(anna).update({"subscriptions": ["MUBI"]})
    store.save_scan("DE", "letterboxd", None, [HEAT, UP], [], {}, profile_id=anna)
    _wait_for_my_scan(app_server, page)
    expect(page.locator('#results article.film[data-key="14160"]')).to_have_count(0)

    # Tonight's Together rows link to the grid.
    page.goto(app_server["url"])
    page.locator("#together-pop > summary").click()
    page.get_by_role("checkbox", name="Anna").check()
    expect(page.locator("#tonight-rows .film-row-head a").first).to_have_attribute(
        "href", f"/watchlist?together={anna}"
    )
    page.goto(app_server["url"] + f"/watchlist?together={anna}")
    expect(page.locator("#together-grid-note")).to_contain_text("Together with Anna", timeout=15000)
    up = page.locator('#results article.film[data-key="14160"]')
    expect(up.locator(".way-badge-owner")).to_have_text("A")
    expect(page.locator('#results article.film[data-key="949"] .way-badge-owner')).to_have_text("M")
    assert "MUBI" in page.url  # Anna's service is ticked too

    page.get_by_role("link", name="Back to my list").click()
    expect(page.locator('#results article.film[data-key="949"]')).to_have_count(1, timeout=15000)
    expect(page.locator('#results article.film[data-key="14160"]')).to_have_count(0)
    expect(page.locator("#together-grid-note")).to_have_count(0)
