"""Browser tests: the Tonight page."""

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.browser


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
