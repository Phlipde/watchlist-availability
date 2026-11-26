"""Helpers for the browser tests."""

import time


def wait_until(condition, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        if condition():
            return True
        time.sleep(0.05)
    return False


def tick_all_services(page) -> None:
    """Tick every service in the services menu, group by group, as a person would."""
    from playwright.sync_api import expect

    page.locator("#services-button").click()
    # The list is drawn after the menu opens; on a slow machine .all() would find nothing yet.
    expect(page.locator("#services-menu [data-group-toggle]").first).to_be_visible()
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
    # text_content: cards outside the window skip rendering (content-visibility), so innerText can be empty.
    titles = page.locator("article.film:visible .film-title").all_text_contents()
    return sorted(title.strip() for title in titles)


def free_tagged(page) -> list[str]:
    return sorted(
        page.locator("label:has(.free-tag)").evaluate_all(
            "labels => labels.map(l => l.dataset.providerLabel)"
        )
    )


def pick_country(page, search: str, picker: str = "header") -> None:
    """Choose a country with the keyboard: open the picker, type, arrow down to the first hit, Enter."""
    from playwright.sync_api import expect

    page.locator(f"#{picker}-country-pop > summary").click()
    # Opening clears the search field and focuses it; typing before that would be wiped.
    expect(page.locator(f"#{picker}-country-search")).to_be_focused()
    page.locator(f"#{picker}-country-search").fill(search)
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
