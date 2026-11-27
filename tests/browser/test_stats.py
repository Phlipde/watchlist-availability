"""Browser tests: the stats page."""

import re

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.browser


def test_stats_page_shows_the_numbers_of_the_last_scan(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    page.get_by_role("link", name="Stats").first.click()
    expect(page.locator("#stats-root")).to_have_attribute("aria-busy", "false")
    expect(page.locator(".stat-tile").first).to_contain_text("films on your services")
    expect(page.locator(".stat-tile", has_text="films on the watchlist")).to_be_visible()
    expect(page.locator(".avail-bar .avail-seg").first).to_be_visible()
    expect(page.locator(".stats-card", has_text="Genres").locator(".bars li").first).to_be_visible()
    expect(page.locator("#people-list")).to_be_visible()
    page.get_by_role("tab", name="Series").click()
    expect(page.locator("#people-tab-collections")).to_have_attribute("aria-selected", "true")
    page.locator("#people-tab-collections").press("ArrowRight")
    expect(page.locator("#people-tab-directors")).to_have_attribute("aria-selected", "true")
    expect(page.locator("#people-tab-directors")).to_be_focused()
    expect(page.locator(".avail-seg").first).to_have_attribute("aria-label", re.compile("films"))
    expect(page.locator(".stats-table").last).to_contain_text("Netflix")
    expect(page.locator(".stats-card a[href^='/watchlist?genre=']").first).to_be_visible()


def test_stats_service_table_filters_sorts_and_keeps_its_state_in_the_address(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    page.goto(app_server["url"] + "/stats")
    expect(page.locator("#svc-table .svc-row").first).to_be_visible()
    expect(page.locator("#svc-count")).to_contain_text("services")
    page.locator("#svc-q").fill("netflix")
    expect(page.locator("#svc-table .svc-row")).to_have_count(1)
    page.locator("[data-sort=films]").click()
    assert "svcq=netflix" in page.url
    assert "sort=films%3Aasc" in page.url
    page.reload()
    expect(page.locator("#svc-q")).to_have_value("netflix")
    expect(page.locator("#svc-table .svc-row")).to_have_count(1)
    expect(page.locator("th[aria-sort=ascending]")).to_have_count(1)
    page.locator("#svc-table .svc-name").click()
    expect(page.locator("#svc-table .svc-detail")).to_be_visible()
    page.locator("#svc-q").fill("zzzz")
    expect(page.locator(".svc-empty")).to_contain_text("No service matches")
    page.get_by_role("button", name="Reset filters").last.click()
    expect(page.locator("#svc-table .svc-row").first).to_be_visible()


def test_links_from_the_stats_page_filter_the_watchlist_and_show_removable_chips(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    page.goto(app_server["url"] + "/watchlist?availability=rent_buy&runtimeMin=60&sort=oldest")
    chip = page.locator("#filter-chips .filter-chip", has_text="Best way: Rent or buy only")
    expect(chip).to_be_visible()
    expect(page.locator("#filter-chips .filter-chip", has_text="Runtime: 60 min and longer")).to_be_visible()
    assert "availability=rent_buy" in page.url
    chip.locator(".chip-remove").click()
    expect(chip).to_have_count(0)
    assert "availability=" not in page.url
    page.get_by_role("button", name="Clear filters").click()
    assert "runtimeMin" not in page.url
