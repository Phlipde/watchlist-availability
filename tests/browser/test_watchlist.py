"""Browser tests: the watchlist grid, scan, cards, favorites and views."""

import re
from unittest.mock import patch

import pytest

from tests.browser.helpers import (
    clear_services,
    free_tagged,
    pick_country,
    tick_all_services,
    visible_titles,
    wait_until,
)
from watchlist_app import letterboxd

playwright_api = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.browser


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
    assert wait_until(lambda: [favorite["key"] for favorite in store.list_favorites(profile_id=1)] == ["949"])

    # After a reload the favorite and the scan come back from the database.
    page.reload()
    expect(page.locator('article.film[data-key="949"] button.favorite')).to_have_attribute(
        "data-favorite", "true"
    )


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
    assert wait_until(lambda: "Arte" in free_tagged(page))  # the services list is drawn after load
    assert "BBC iPlayer" not in free_tagged(page)
    # A country switch saves the country and scans without reloading the page; the labels follow.
    requests: list[str] = []
    page.on("request", lambda request: requests.append(f"{request.method} {request.url}"))
    pick_country(page, "gb")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    assert wait_until(lambda: "BBC iPlayer" in free_tagged(page))
    assert "Arte" not in free_tagged(page)
    assert app_server["settings"].country == "GB"
    assert [line for line in requests if line.startswith("PUT") and line.endswith("/api/settings")]
    # Back to a country with a scan from today: a scan starts again, the server reuses the saved one.
    requests.clear()
    pick_country(page, "germany")
    expect(page.locator(".country-picker .country-code").first).to_have_text("DE")
    assert wait_until(lambda: "Arte" in free_tagged(page))
    assert wait_until(
        lambda: [line for line in requests if line.startswith("POST") and line.endswith("/api/scan")]
    )
    assert app_server["settings"].country == "DE"


def test_any_country_can_be_picked_and_stays_after_a_reload(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    page.locator("#header-country-pop > summary").click()
    expect(page.locator("#header-country-search")).to_be_focused()
    page.keyboard.type("pola")
    expect(page.locator(".country-option:visible")).to_have_count(1)
    expect(page.locator(".country-option:visible")).to_contain_text("Poland")
    page.keyboard.press("Enter")
    expect(page.locator("#header-country-pop")).not_to_have_attribute("open", "")
    expect(page.locator("#header-country-pop > summary")).to_be_focused()
    assert wait_until(lambda: app_server["settings"].country == "PL")
    # The new country's scan runs and is saved.
    assert wait_until(lambda: app_server["store"].latest_scan("PL", profile_id=1) is not None, timeout=15)
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    # Poland has no own services yet (and the fake TMDB no offers there): none are ticked, nothing breaks.
    assert app_server["settings"].subscriptions("PL") == []
    expect(page).not_to_have_url(re.compile(r"providers="))  # the address follows once the films are drawn
    assert page.locator("#services-list input:checked").count() == 0
    assert page.locator("#country-select").input_value() == "PL"
    page.goto(app_server["url"] + "/watchlist")  # a fresh load, without the scan in the address
    expect(page.locator("#header-country-pop .country-button .country-code")).to_have_text("PL")
    expect(page.locator("#status-message")).to_have_text(re.compile(r"^Saved results from "))
    # Escape closes the menu and gives the focus back to its button.
    page.locator("#header-country-pop > summary").click()
    page.keyboard.press("Escape")
    expect(page.locator("#header-country-pop > summary")).to_be_focused()


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
    expect(page.locator("#filter-chips")).to_contain_text("TMDB votes: 1k+")
    page.goto(app_server["url"] + "/watchlist?ages=16")
    expect(page.locator("#more-filters > summary")).to_have_text("More filters · 1")


def test_no_match_offers_a_way_out(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    page.locator("#film-search").fill("nothing like this")
    expect(page.locator("#filters-empty")).to_be_visible()
    expect(page.locator("#filter-chips")).to_contain_text("Clear filters")
    # The way out names each filter that keeps films away, with how many come back.
    expect(page.locator("#empty-ways")).to_have_text("Remove Search: nothing like this to see 1 film")
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
    assert wait_until(lambda: store.list_favorites(profile_id=1)[0].get("notes") == "with Lisa")
    page.locator("#favorites-view").click()
    star.click()
    assert wait_until(lambda: store.list_favorites(profile_id=1) == [])
    page.locator("#toast-undo").click()
    assert wait_until(lambda: [f.get("notes") for f in store.list_favorites(profile_id=1)] == ["with Lisa"])
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
    assert app_server["store"].list_favorites(profile_id=1)[0].get("notes", "") == "Watch with"


def test_card_menu_sets_a_film_aside_and_marks_it_watched_with_undo(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    titles = visible_titles(page)
    first = page.locator("article.film").first
    name = first.locator(".film-title").inner_text()
    # Watched: the poster says so, the toast offers Undo.
    first.hover()  # the action bar shows while the pointer is on the card
    first.get_by_role("button", name="Hide: stays hidden until you unhide it").click()
    expect(page.locator("#toast-message")).to_contain_text("hidden away")
    expect(page.locator("article.film", has_text=name).locator(".poster-badge")).to_have_text("Hidden")
    assert any(item["flag"] == "watched" for item in app_server["store"].list_flags(profile_id=1))
    page.locator("#toast-undo").click()
    expect(page.locator("article.film", has_text=name).locator(".poster-badge")).to_have_count(0)
    assert app_server["store"].list_flags(profile_id=1) == []
    # Not now: the film leaves the list until the filter asks for it.
    first = page.locator("article.film").first
    first.hover()
    first.get_by_role("button", name="Not now: off Tonight and suggestions for 30 days").click()
    expect(page.locator("article.film")).to_have_count(len(titles) - 1)
    page.locator("#more-filters > summary").click()
    page.locator("#show-hidden").check()
    expect(page.locator("article.film")).to_have_count(len(titles))
    assert "hidden=1" in page.url


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
    # A profile switch asks the worker to forget the saved pages and data; scripts and styles stay.
    left = page.evaluate(
        """async () => {
            const {clearPages} = await import('/static/js/register-sw.js');
            await clearPages(5000);
            const count = async name => (await (await caches.open(name)).keys()).length;
            return {pages: await count('pages-v1'), files: await count('static-v1')};
        }"""
    )
    assert left["pages"] == 0 and left["files"] > 0
    context.close()


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
    expect(page.locator("#compare-bar")).to_be_hidden()  # the bar gives way to the open comparison
    page.wait_for_function("document.getElementById('compare-modal').contains(document.activeElement)")
    page.keyboard.press("Escape")
    expect(page.locator("#compare-modal")).to_be_hidden()
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


def test_flags_are_pictures_served_by_the_app(app_server, page):
    # Emoji flags show as letters on Windows, so the flags are SVG files of the app itself.
    for code in ("nl", "at", "us", "jp"):
        response = page.request.get(app_server["url"] + f"/static/flags/{code}.svg")
        assert response.ok and "svg" in response.headers["content-type"]


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
    expect(page.locator("article.film .way-badge-flag")).to_have_count(1)
    abroad_card = page.locator("article.film", has=page.locator(".way-badge-flag"))
    expect(abroad_card.locator(".lstack-item").first).to_have_attribute(
        "data-tip", re.compile(r"Subscription · ")
    )
    expect(page.locator("#result-meta")).to_contain_text("1 via VPN")
    assert "where=both" in page.url
    expect(page.locator("#filter-chips")).to_contain_text("Where: Here and abroad")
    # "Only abroad" comes from a link (Tonight's row); the switch is the one control and turns it off.
    page.goto(app_server["url"] + "/watchlist?where=abroad")
    expect(page.locator("article.film")).to_have_count(1)
    expect(toggle).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#filter-chips")).to_contain_text("Where: Only abroad")
    toggle.click()
    expect(page.locator("article.film")).to_have_count(here)
    expect(toggle).to_have_attribute("aria-pressed", "false")


def test_a_card_shows_only_the_logo_and_the_words_come_on_hover(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)
    tick_all_services(page)
    card = page.locator("article.film").first
    stack = card.locator(".lstack")
    assert "service" in stack.locator(".lstack-toggle").get_attribute("aria-label")
    first = card.locator(".lstack-item").first
    assert first.get_attribute("data-tip").strip()  # the words come as a bubble
    expect(first).to_have_css("margin-left", "0px")  # the best logo is never overlapped
    assert (
        card.locator(".lstack-item .way-badge").count() == card.locator(".lstack-item").count()
    )  # a type icon on each
    first.hover()  # the name comes as a bubble
    expect(page.locator(".tip")).to_have_text(first.get_attribute("data-tip"))
    first.click()  # a click on a logo opens nothing
    expect(page.locator("#film-details-modal")).to_be_hidden()
    stack.locator(".lstack-toggle").focus()  # the stack's button opens the details
    page.keyboard.press("Enter")
    expect(page.locator("#film-details-modal")).to_be_visible(timeout=5000)


def test_an_empty_list_names_every_filter_and_clear_resets_all(app_server, page):
    expect = playwright_api.expect
    # Heat (1995, on Netflix only) is the one film; only "Services: 2+" keeps it out,
    # and its chip hides behind "+2 more".
    page.goto(app_server["url"] + "/watchlist?from=1990&to=2000&media=trailer&minproviders=2&hidden=1")
    expect(page.locator("#filters-empty")).to_be_visible(timeout=15000)
    expect(page.locator("[data-chips-more]")).to_have_text("+2 more")
    expect(page.locator("#empty-ways")).to_have_text("Remove Services: 2+ to see 1 film")
    page.locator("#empty-ways button").click()
    expect(page.locator("#visible-count")).to_have_text("1")
    # "Only favorites" is a chip like every other filter, and the empty list names it too.
    page.locator("#favorites-view").click()
    expect(page.locator("#filter-chips [data-favorites]")).to_contain_text("Only favorites")
    expect(page.locator("#empty-ways")).to_contain_text("Remove Only favorites to see 1 film")
    page.locator("[data-reset-filters]").click()
    expect(page.locator("#filter-chips")).to_be_hidden()
    expect(page.locator("#favorites-view")).to_have_attribute("aria-pressed", "false")
    expect(page.locator('#age-chips .chip[aria-pressed="true"]')).to_have_count(0)
    for name in ("favorites=", "media=", "minproviders=", "from=", "to=", "hidden="):
        assert name not in page.url
