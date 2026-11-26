"""Browser tests: keyboard use (focus, skip link, arrow keys, shortcuts)."""

import re

import pytest

from tests.browser.helpers import tick_all_services

playwright_api = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.browser


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


def test_skip_link_and_three_stops_per_card(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text(
        "Complete", timeout=15000
    )  # a redraw after the scan would drop the focus
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
    assert "favorite" in stops and stops.count("card-action") == 3
    assert "lstack-toggle" in stops or "lstack-item" in stops
    # After the skip link, closing the details returns the focus to the title (no #results to go back to).
    first.locator(".film-open").focus()
    page.keyboard.press("Enter")
    page.wait_for_function("document.getElementById('film-details-modal').contains(document.activeElement)")
    page.keyboard.press("Escape")
    expect(first.locator(".film-open")).to_be_focused()


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
    assert app_server["store"].list_flags(profile_id=1) == []
    page.locator("#film-search").fill("")
    # "s" marks the card in focus as watched; "g" then "s" goes to the subscriptions.
    page.locator("article.film .film-open").first.focus()
    page.keyboard.press("s")
    expect(page.locator("article.film .poster-badge")).to_have_text("Hidden")
    page.keyboard.press("g")
    page.keyboard.press("s")
    expect(page).to_have_url(re.compile(r"/subscriptions$"))


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
