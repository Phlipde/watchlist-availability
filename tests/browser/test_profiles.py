"""Browser tests: the profile switcher in the header and the page /settings/profiles."""

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.browser


def _switch_in_header(page, name: str) -> None:
    page.locator("#profile-pop > summary").click()
    page.locator("#profile-pop .menu-item", has_text=name).click()
    playwright_api.expect(page.locator("#profile-pop .profile-button")).to_have_text(name, timeout=15000)


def test_switching_the_profile_in_the_header_shows_its_own_favorites(app_server, page):
    expect = playwright_api.expect
    store = app_server["store"]
    store.add_profile("Anna")
    store.add_favorite({"key": "949", "title": "Heat", "year": 1995}, profile_id=1)
    page.goto(app_server["url"] + "/watchlist")  # app.js wires the header here
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    expect(page.locator('article.film[data-key="949"] button.favorite')).to_have_attribute(
        "data-favorite", "true"
    )
    _switch_in_header(page, "Anna")
    assert page.evaluate("fetch('/api/favorites').then(r => r.json())") == []

    page.goto(app_server["url"] + "/settings/data")  # header.js wires it here
    expect(page.locator("#profile-status")).to_contain_text("Favorites: 0")
    _switch_in_header(page, "Me")
    expect(page.locator("#profile-status")).to_contain_text("Favorites: 1")
    assert [f["key"] for f in page.evaluate("fetch('/api/favorites').then(r => r.json())")] == ["949"]
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator('article.film[data-key="949"] button.favorite')).to_have_attribute(
        "data-favorite", "true", timeout=15000
    )


def test_saved_views_belong_to_a_profile_and_an_old_one_goes_to_profile_1(app_server, page):
    expect = playwright_api.expect
    store = app_server["store"]
    anna = store.add_profile("Anna")
    heat = {"key": "949", "tmdb_id": 949, "title": "Heat", "providers": {"Netflix": ["flatrate"]}}
    store.save_scan("DE", "letterboxd", None, [heat], [], {}, profile_id=anna)
    page.goto(app_server["url"] + "/watchlist")  # lets the first scan of profile 1 finish
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    # A view saved before profiles had keys, and one Anna saved on this device.
    old, annas = (
        '[{"name": "Old night", "search": "?max=150"}]',
        '[{"name": "Anna night", "search": "?max=90"}]',
    )
    page.evaluate(
        "([key, a, b]) => { localStorage.setItem('savedViews', a); localStorage.setItem(key, b); }",
        [f"p{anna}:savedViews", old, annas],
    )
    page.goto(app_server["url"])
    expect(page.locator("#tonight-views .saved-view a")).to_have_text(["Old night"], timeout=15000)
    assert page.evaluate("localStorage.getItem('savedViews')") is None  # taken over by profile 1
    _switch_in_header(page, "Anna")
    expect(page.locator("body")).to_have_attribute("data-profile", str(anna))
    expect(page.locator("#tonight-views .saved-view a")).to_have_text(["Anna night"], timeout=15000)
    _switch_in_header(page, "Me")
    expect(page.locator("#tonight-views .saved-view a")).to_have_text(["Old night"], timeout=15000)


def test_profiles_page_adds_renames_and_deletes_with_the_keyboard(app_server, page):
    expect = playwright_api.expect
    store = app_server["store"]
    page.goto(app_server["url"] + "/settings/profiles")
    expect(page.get_by_role("button", name="Delete Me")).to_be_disabled()
    expect(page.locator("#profile-last-note")).to_be_visible()

    # Add: type into the fields, Enter submits.
    page.locator("#profile-add-name").focus()
    page.keyboard.type("Ben")
    page.keyboard.press("Tab")
    page.keyboard.type("ben@example.org")
    page.keyboard.press("Enter")
    expect(page.locator("#profiles-message")).to_have_text("Ben added.")
    expect(page.locator("#profiles-message")).to_be_focused()
    assert [p["name"] for p in store.list_profiles()] == ["Me", "Ben"]
    ben = store.list_profiles()[1]["id"]

    # A name that is taken: the server's message shows.
    page.locator("#profile-add-name").focus()
    page.keyboard.type("Me")
    page.keyboard.press("Enter")
    expect(page.locator("#profiles-message")).to_have_class("feedback text-danger")
    expect(page.locator("#profiles-message")).not_to_be_empty()

    # Rename: change the field, Enter saves.
    page.locator(f"#profile-name-{ben}").focus()
    page.keyboard.press("Control+A")
    page.keyboard.type("Benjamin")
    page.keyboard.press("Enter")
    expect(page.locator("#profiles-message")).to_have_text("Changes saved.")
    assert store.list_profiles()[1] == {"id": ben, "name": "Benjamin", "email": "ben@example.org"}

    # Delete: the first Enter asks, Escape takes it back, two presses delete.
    delete = page.get_by_role("button", name="Delete Benjamin")
    delete.focus()
    page.keyboard.press("Enter")
    expect(delete).to_have_text("Delete Benjamin?")
    page.keyboard.press("Escape")
    expect(delete).to_have_text("Delete")
    assert len(store.list_profiles()) == 2
    page.keyboard.press("Enter")
    page.keyboard.press("Enter")
    expect(page.locator("#profiles-message")).to_have_text("Benjamin deleted.")
    assert [p["name"] for p in store.list_profiles()] == ["Me"]


def test_deleting_the_active_profile_falls_back_to_another(app_server, page):
    expect = playwright_api.expect
    anna = app_server["store"].add_profile("Anna")
    page.goto(app_server["url"] + "/settings/profiles")
    page.get_by_role("button", name="Use this profile: Anna").click()
    expect(page.locator("#profile-pop .profile-button")).to_have_text("Anna", timeout=15000)
    expect(page.locator(f"#profile-{anna} .pill")).to_have_text("Active")
    page.get_by_role("button", name="Delete Anna").click()
    page.get_by_role("button", name="Delete Anna").click()
    expect(page.locator("#profiles-message")).to_have_text("Anna deleted.")
    expect(page.locator("#profile-pop .profile-button")).to_have_text("Me")
    # The next new profile gets Anna's id again; the old cookie must not open it.
    page.locator("#profile-add-name").fill("Ben")
    page.locator("#profile-add-name").press("Enter")
    expect(page.locator("#profiles-message")).to_have_text("Ben added.")
    assert app_server["store"].list_profiles()[1]["id"] == anna
    expect(page.locator("#profile-pop .profile-button")).to_have_text("Me")
