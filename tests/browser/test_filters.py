"""Browser tests: the filter bar, its menus, chips and the address."""

import re

import pytest

from tests.browser.helpers import tick_all_services, visible_titles

playwright_api = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.browser


def test_filters_from_a_link_survive_the_scan(app_server, page):
    expect = playwright_api.expect
    # The genre list is filled only when films arrive; the genre from the link must wait for it.
    page.goto(app_server["url"] + "/watchlist?genre=Action&rating=tmdb:7&providers=Netflix,Arte")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    expect(page.locator('#genre-list input[value="Action"]')).to_be_checked()
    expect(page.locator("#visible-count")).to_have_text("1")
    assert visible_titles(page) == ["Heat"]
    # The same link again, now from the saved scan.
    page.reload()
    expect(page.locator('#genre-list input[value="Action"]')).to_be_checked()
    # The rating from the link shows as a chip; the chip clears it.
    expect(page.locator("#tmdb-filter")).to_have_value("7")  # the old ?rating=tmdb:7 link still works
    page.locator('.filter-chip[data-filter-id="tmdb-filter"] .chip-remove').click()
    expect(page.locator("#tmdb-filter")).to_have_value("")
    # The genre chip clears the genre.
    page.locator('.filter-chip[data-genre-include="Action"] .chip-remove').click()
    expect(page.locator('#genre-list input[value="Action"]')).not_to_be_checked()
    # The favorite status only belongs to the favorites view.
    expect(page.locator("#favorite-status-filter")).to_be_hidden()
    page.locator("#favorites-view").click()
    expect(page.locator("#favorite-status-filter")).to_be_visible()


def test_runtime_and_rating_filters_show_unit_and_source(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    page.locator("#runtime-pop summary").click()
    page.locator("#runtime-slider").evaluate(
        "e => { e.value = 225; e.dispatchEvent(new Event('input', {bubbles: true})); }"
    )
    expect(page.locator("#runtime-slider-value")).to_have_text("Up to 3 h 45")
    # The label is one line, not a column of letters.
    assert page.locator("#runtime-slider-value").bounding_box()["height"] < 30
    expect(page.locator("#runtime-summary")).to_have_text("≤ 3 h 45")
    page.keyboard.press("Escape")
    page.locator("#rating-pop summary").click()
    page.locator('[data-rating="tmdb:7"]').click()
    expect(page.locator("#rating-summary")).to_have_text("TMDB 7+")
    expect(page.locator('.filter-chip[data-filter-id="tmdb-filter"]')).to_have_text("TMDB: 7+")
    expect(page.locator("#tmdb-note")).to_be_visible()
    # The two minimums are independent: setting Letterboxd keeps TMDB.
    page.evaluate(
        "document.querySelectorAll('#rating-chips-lb .chip, #rating-slider-lb')"
        ".forEach(e => { e.disabled = false; })"
    )
    page.locator('[data-rating="lb:3.5"]').click()
    expect(page.locator("#rating-summary")).to_have_text("LB 3.5+ · TMDB 7+")
    assert "lb=3.5" in page.url and "tmdb=7" in page.url
    page.locator("#tmdb-reset").click()
    expect(page.locator("#rating-summary")).to_have_text("LB 3.5+")


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
    expect(runtime_chip).to_have_text("Runtime: Up to 2 h")


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
    expect(page.locator("#moved-slot > #rating-pop.is-moved")).to_have_count(1)  # Rating gives way last
    page.locator("#moved-slot #rating-chips-tmdb .chip", has_text="7+").first.click()
    expect(page.locator("#tmdb-filter")).to_have_value("7")
    expect(page.locator("#more-filters-count")).to_have_text("· 2")
    expect(page.locator("#more-filters")).to_have_attribute("open", "")  # still open
    page.keyboard.press("Escape")
    page.set_viewport_size({"width": 2400, "height": 900})
    expect(page.locator("#moved-slot > .filter-pop")).not_to_have_count(2)  # with room, one moves back
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
    page.locator("#rating-chips-tmdb .chip", has_text="7+").first.click()
    expect(page.locator("#tmdb-filter")).to_have_value("7")
    assert "tmdb=7" in page.url and "rating=" not in page.url
    page.locator("#tmdb-reset").click()
    expect(page.locator("#tmdb-filter")).to_have_value("")
    # The services menu finds a service that is not one of the own ones.
    page.locator("#services-button").click()
    page.locator("#services-search").fill("zzzz")
    expect(page.locator("#services-list .services-group:visible")).to_have_count(0)


def test_many_filter_chips_collapse_behind_a_more_button(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist?votes=1000&ages=16&max=120&rating=tmdb:7&cost=free")
    chips = page.locator("#filter-chips .filter-chip:not(.chips-more):not(.filter-reset)")
    expect(page.locator("#filter-chips .chips-more")).to_have_text(re.compile(r"^\+\d+ more$"), timeout=15000)
    assert chips.count() == 3
    page.locator("#filter-chips .chips-more").click()
    assert chips.count() >= 5
    expect(page.locator("#filter-chips .chips-more")).to_have_text("Fewer")
