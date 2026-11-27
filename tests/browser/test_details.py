"""Browser tests: the film details drawer."""

import re

import pytest

from tests.browser.helpers import tick_all_services

playwright_api = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.browser


def test_trailer_from_the_details_window_is_in_front(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    page.locator('article.film[data-key="949"] .film-open').click()
    # Bootstrap ignores hide() while a dialog is still fading in; a person never clicks that fast.
    page.wait_for_function("document.getElementById('film-details-modal').contains(document.activeElement)")
    page.locator("#film-details-content .trailer-link").click()
    expect(page.locator("#trailer-modal")).to_be_visible()
    expect(page.locator("#film-details-modal")).to_be_hidden()


def test_a_film_of_the_series_opens_in_the_details_with_a_way_back(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    tick_all_services(page)
    page.locator('article.film[data-key="348"] .film-open').click()
    # Heat is in the same series: it shows there, not again under "Similar" (which needs 3 matches).
    expect(page.locator("#film-details-content .film-modal-similar")).to_have_count(0)
    page.locator("#film-details-content .series-pick", has_text="1995").click()
    expect(page.locator("#film-details-title")).to_have_text("Heat")
    # The new film starts at the top, with a way back to the one before.
    assert page.locator("#film-details-content").evaluate("body => body.scrollTop") == 0
    back = page.locator("#film-details-content [data-back]")
    expect(back).to_have_text("Back to Alien")
    expect(back).to_be_focused()
    back.click()
    expect(page.locator("#film-details-title")).to_have_text("Alien")
    expect(page.locator("#film-details-content [data-back]")).to_have_count(0)


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


def test_details_have_one_main_button_and_people_are_search_links(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    page.locator("article.film .film-open").first.click()
    expect(page.locator("#film-details-title")).to_be_visible()
    assert page.locator("#film-details-content .btn-accent").count() <= 1  # only the main button is amber
    for link in page.locator("#film-details-content .film-modal-credits a").all():
        assert "/watchlist?q=" in link.get_attribute("href")


def test_service_logos_name_themselves_only_in_a_tooltip(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist?film=949")
    expect(page.locator("#film-details-title")).to_be_visible(timeout=15000)
    page.evaluate("const more = document.getElementById('film-more'); more.hidden = false; more.open = true")
    logos = page.locator("#film-more .svc")
    name = logos.first.get_attribute("aria-label")
    assert name and name.split(" · ")[0] not in logos.first.inner_text()  # no name written out
    # Bootstrap moves the focus to the dialog once it has faded in (late on a slow machine):
    # focus the logo until it sticks.
    shown = "() => { const s = document.querySelector('#film-more .svc');"
    shown += " if (document.activeElement !== s) s.focus();"
    shown += " const t = document.querySelector('.tip'); return t && !t.hidden; }"
    page.wait_for_function(shown, polling=500, timeout=8000)  # keyboard focus shows the name
    expect(page.locator(".tip")).to_have_text(name)
    expect(page.locator(".tip")).to_have_text(name)
    if logos.count() > 1:
        logos.nth(1).focus()
        expect(page.locator(".tip")).to_have_text(logos.nth(1).get_attribute("aria-label"), timeout=200)


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
    expect(
        page.get_by_role("button", name="Hide this film: stays hidden until you unhide it")
    ).to_be_visible()


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
