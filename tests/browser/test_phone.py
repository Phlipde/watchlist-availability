"""Browser tests: the phone layout (sheets, header, compare bar)."""

import re

import pytest

from tests.browser.helpers import tick_all_services

playwright_api = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.browser


def test_phone_details_sheet_can_be_pulled_to_full_screen(app_server, page):
    expect = playwright_api.expect
    page.set_viewport_size({"width": 390, "height": 800})
    page.goto(f"{app_server['url']}/watchlist?film=949")
    modal = page.locator("#film-details-modal")
    expect(modal).to_be_visible(timeout=15000)
    dialog = page.locator("#film-details-modal .modal-dialog")
    # The slide-in must be over: dragging a moving sheet would hit the wrong spot.
    page.wait_for_function(
        "() => ['none', 'matrix(1, 0, 0, 1, 0, 0)'].includes(getComputedStyle(document.querySelector("
        "'#film-details-modal .modal-dialog')).transform)"
    )
    # Opened by a link (a new tab), the sheet is full screen at once; opened by a tap on a card it is 80 %.
    expect(modal).to_have_class(re.compile("is-full"))
    assert dialog.evaluate("el => el.getBoundingClientRect().height") > 700

    def drag(selector, dy):
        page.wait_for_timeout(450)  # the height change takes 0.2 s; the grip moves while it runs
        box = page.locator(selector).bounding_box()
        x, y = box["x"] + 30, box["y"] + box["height"] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x, y + dy, steps=5)
        page.mouse.up()

    drag("#sheet-grip", 80)  # pull the grip down: 80 %
    expect(modal).not_to_have_class(re.compile("is-full"))
    page.wait_for_timeout(450)
    assert dialog.evaluate("el => el.getBoundingClientRect().top") > 100  # 80 % shows
    drag("#sheet-grip", -80)  # pull the grip up
    expect(modal).to_have_class(re.compile("is-full"))
    drag("#sheet-grip", 80)  # and down again
    expect(modal).not_to_have_class(re.compile("is-full"))
    drag("#film-details-modal .modal-header", -80)  # the header works too, not only the thin grip
    expect(modal).to_have_class(re.compile("is-full"))
    page.wait_for_timeout(450)
    page.locator("#sheet-grip").click()  # a tap toggles
    expect(modal).not_to_have_class(re.compile("is-full"))
    page.wait_for_timeout(450)
    page.locator("#film-details-modal .modal-body").evaluate(
        "el => { el.style.paddingBottom = '1500px'; el.scrollTop = 200; }"
    )  # scrolling a long film expands it
    expect(modal).to_have_class(re.compile("is-full"))


def test_plus_n_on_a_card_opens_the_phone_sheet_full_screen(app_server, page):
    expect = playwright_api.expect
    page.set_viewport_size({"width": 390, "height": 800})
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    # No card in the fixture has a "+N"; the click rule is on the document, so a button with its marks works.
    button = (
        '<button id="fake-more" data-open-more data-key="949" '
        'style="position:fixed;top:0;left:0;z-index:9">+2</button>'
    )
    page.evaluate("html => document.body.insertAdjacentHTML('beforeend', html)", button)
    page.locator("#fake-more").click()
    expect(page.locator("#film-details-modal")).to_have_class(re.compile("is-full"))
    expect(page.locator("#film-more")).to_have_attribute("open", "")


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
    page.wait_for_timeout(450)  # it slides up first
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


def test_phone_head_is_two_rows_and_the_posters_start_high(app_server, page):
    expect = playwright_api.expect
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    # Row 1: search and Filters side by side; the first poster starts in the top quarter of the screen.
    search = page.locator("#film-search").bounding_box()
    filters = page.locator("#tools-toggle").bounding_box()
    assert abs(search["y"] - filters["y"]) < 12 and search["x"] < filters["x"]
    assert page.locator("article.film .poster").first.bounding_box()["y"] <= 844 * 0.25
    # The source name and the Letterboxd account are not in the count line.
    expect(page.locator("#source-name")).to_be_hidden()
    # The view switch sits in the tab row; heart and link live in the filter sheet.
    expect(page.locator("#tabs-view-slot #view-switch")).to_be_visible()
    expect(page.locator("#favorites-view")).to_be_hidden()
    page.locator("#tools-toggle").click()
    expect(page.locator("#favorites-view")).to_be_visible()
    expect(page.locator("#share-button")).to_be_visible()
    page.locator("#film-search").fill("zzzz-no-film")
    expect(page.locator("#tools-toggle")).to_contain_text("1")


def test_phone_compare_bar_sits_above_the_tab_bar_and_gives_way_to_sheets(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    tick_all_services(page)
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(500)
    for index in (0, 1):
        card = page.locator("article.film").nth(index)
        card.hover()
        card.get_by_role("button", name=re.compile("comparison")).click()
    bar = page.locator("#compare-bar")
    expect(bar).to_be_visible()
    box, nav = bar.bounding_box(), page.locator(".page-nav").bounding_box()
    assert box["x"] == 0 and box["width"] == 390 and box["height"] >= 56
    assert box["y"] + box["height"] <= nav["y"] + 1
    expect(page.locator("#compare-go")).to_be_enabled()
    page.locator("#tools-toggle").click()
    expect(bar).to_be_hidden()
    page.locator("#filter-sheet-close").click()
    expect(bar).to_be_visible()


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
