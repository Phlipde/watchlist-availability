"""Browser tests: settings, services, subscriptions, title matches and data pages."""

import datetime as dt
import json
import re
import threading
from unittest.mock import patch

import pytest
from flask import Flask
from werkzeug.serving import make_server

from tests.browser.helpers import pick_country, wait_until

playwright_api = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.browser


def test_settings_are_saved_and_checked(app_server, page):
    expect = playwright_api.expect
    page.goto(f"{app_server['url']}/settings")
    page.locator("#letterboxd-username").fill("bad name!")
    page.locator("#letterboxd-username").blur()  # saves on its own when the field is left
    expect(page.locator("#settings-message")).to_contain_text("may only contain")

    page.locator("#letterboxd-username").fill("someone_else")
    page.locator("#letterboxd-username").blur()
    expect(page.locator("#toast-text")).to_have_text("Saved · Rescan now?")
    expect(page.get_by_role("button", name="Rescan now")).to_be_visible()
    assert wait_until(lambda: app_server["settings"].letterboxd_username == "someone_else")
    page.locator("#weekly-hours").fill("12")
    page.locator("#weekly-hours").blur()
    expect(page.locator("#toast-text")).to_have_text("Saved")
    page.get_by_role("button", name="Undo").click()
    expect(page.locator("#toast-text")).to_have_text("Change undone")
    assert app_server["settings"].weekly_hours != 12


def test_settings_country_picker_saves_and_scans(app_server, page):
    expect = playwright_api.expect
    requests: list[str] = []
    page.on("request", lambda request: requests.append(f"{request.method} {request.url}"))
    page.goto(f"{app_server['url']}/settings")
    pick_country(page, "fr", picker="settings")
    # Saved, a scan started and the watchlist follows it.
    expect(page).to_have_url(re.compile(r"/watchlist\?scan="))
    assert app_server["settings"].country == "FR"
    assert [line for line in requests if line.startswith("PUT") and line.endswith("/api/settings")]
    assert [line for line in requests if line.startswith("POST") and line.endswith("/api/scan")]
    expect(page.locator("#header-country-pop .country-button .country-code")).to_have_text("FR")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)


def test_price_is_saved_when_you_leave_the_field(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    page.goto(f"{app_server['url']}/subscriptions")
    netflix = page.locator('tr[data-service="Netflix"]')
    netflix.locator('[name="price"]').fill("10,5")  # a comma is fine
    netflix.locator('[name="price"]').blur()
    expect(page.locator("#save-state")).to_have_text("Saved")
    assert app_server["settings"].costs("DE")["Netflix"]["price"] == 10.5
    # The total follows without a reload.
    expect(page.locator("#total-month")).to_contain_text(re.compile(r"10[.,]50"))
    page.reload()
    expect(netflix.locator('[name="price"]')).to_have_value("10.5")


def test_subscriptions_page_adds_a_service_and_cancels_it_to_an_end_date(app_server, page):
    expect = playwright_api.expect
    settings = app_server["settings"]
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    page.goto(f"{app_server['url']}/subscriptions")
    # Add: search, pick; the page reloads with the service saved.
    page.locator("#add-service").click()
    page.locator("#add-search").fill("MUBI")
    page.locator('#add-list .add-item[data-name="MUBI"]').click()
    expect(page.locator("#add-dialog")).to_be_hidden()
    assert sorted(settings.subscriptions("DE")) == ["MUBI", "Netflix"]
    # Cancel Netflix to a date: it stays on the list until then.
    netflix = page.locator('tr[data-service="Netflix"]')
    netflix.get_by_role("button", name="Cancel", exact=True).click()
    future = (dt.date.today() + dt.timedelta(days=20)).isoformat()
    page.locator("#cancel-date").fill(future)
    page.get_by_role("button", name="Cancel subscription").click()
    expect(netflix.locator(".pill-warn")).to_contain_text("Ends")
    expect(page.locator("#save-state")).to_have_text("Saved")
    assert settings.costs("DE")["Netflix"]["ends_on"] == future
    assert "Netflix" in settings.subscriptions("DE")  # runs to the end date
    page.reload()
    expect(netflix.locator(".pill-warn")).to_contain_text("Ends")
    # Undo takes the end date away again.
    netflix.get_by_role("button", name="Undo").click()
    expect(page.locator("#save-state")).to_have_text("Saved")
    assert "ends_on" not in settings.costs("DE").get("Netflix", {})


def test_services_are_saved_as_you_tick_and_can_be_undone(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    page.goto(f"{app_server['url']}/settings/services")
    # MUBI has no film in the scan, so it waits under the closed "More services".
    page.locator('details[data-section="More services"] summary').click()
    page.locator('#services-sections input[value="MUBI"]').check(force=True)
    expect(page.locator("#toast-text")).to_have_text("Saved")
    assert sorted(app_server["settings"].subscriptions("DE")) == ["MUBI", "Netflix"]
    page.locator("#toast-undo").click()
    expect(page.locator("#toast-text")).to_have_text("Undone")
    assert app_server["settings"].subscriptions("DE") == ["Netflix"]
    expect(page.locator('#services-sections input[value="MUBI"]')).not_to_be_checked()
    assert app_server["settings"].country == "DE"


def test_title_match_is_corrected_and_undone(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")  # the scan stores the matches
    expect(page.locator("article.film").first).to_be_visible(timeout=15000)

    page.goto(f"{app_server['url']}/settings/matches")
    rows = page.locator(".match-row")
    expect(rows).to_have_count(3)  # two title searches and one film TMDB does not know
    heat = rows.filter(has_text="Heat (1995)")
    heat.get_by_role("button", name="Correct").click()
    heat.locator(".candidate").filter(has_text="Heat 2").get_by_role("button", name="Use this").click()
    expect(page.locator("#matches-message")).to_contain_text("Heat (1995) → Heat 2 (2026)")
    expect(page.locator("#rescan")).to_be_visible()
    store = app_server["store"]
    assert store.get_id("title:heat|1995")["tmdb_id"] == 111
    expect(rows).to_have_count(2)  # a corrected match is certain

    page.locator("#show-all").check()
    page.locator(".match-row").filter(has_text="Heat (1995)").get_by_role(
        "button", name="Undo correction"
    ).click()
    expect(page.locator("#matches-message")).to_contain_text("looked up again")
    assert store.get_id("title:heat|1995") is None


ATTACK = '<img src=x onerror="window.attacked = true">'


HOSTILE_BACKUP = {
    "version": 1,
    "favorites": [{"key": "1", "title": "Evil favorite", "year": ATTACK}],
    "scans": [
        {
            "created": 1000.0,
            "country": "DE",
            "results": [
                {
                    "title": "Evil",
                    "tmdb_id": 5,
                    "year": ATTACK,
                    "runtime": ATTACK,
                    "providers": {"Netflix": ["flatrate"]},
                }
            ],
            "unavailable": [{"title": "Evil too", "key": "x", "year": ATTACK}],
        }
    ],
}


def test_hostile_backup_restored_on_the_settings_page_runs_no_script(app_server, page, tmp_path):
    expect = playwright_api.expect
    backup_file = tmp_path / "backup.json"
    backup_file.write_text(json.dumps(HOSTILE_BACKUP), encoding="utf-8")
    page.goto(f"{app_server['url']}/settings")
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#backup-file").set_input_files(str(backup_file))
    expect(page.locator("#backup-message")).to_contain_text("Restored: 1 favorites")

    # Open the page without a new scan replacing the restored one.
    with patch("watchlist_app.scan_service.load_watchlist", side_effect=FileNotFoundError("no list")):
        page.goto(app_server["url"] + "/watchlist")
        expect(page.locator('article.film[data-key="5"]')).to_have_count(1, timeout=15000)
    assert page.evaluate("() => window.attacked") is None
    assert page.locator("article.film img[src='x']").count() == 0
    expect(page.locator('article.film[data-key="5"] .year')).to_contain_text("Year unknown")


def test_another_web_site_cannot_restore_a_backup(app_server, page):
    """A page on another origin posts a backup to the app, as an attack would."""
    attacker = Flask("attacker")

    @attacker.get("/")
    def evil_page():
        return f"""<script>
        const body = new FormData();
        body.append('backup', new Blob([{json.dumps(json.dumps(HOSTILE_BACKUP))}]), 'backup.json');
        fetch('{app_server["url"]}/api/backup', {{method: 'POST', mode: 'no-cors', body}})
          .finally(() => {{ document.title = 'sent'; }});
        </script>"""

    server = make_server("127.0.0.1", 0, attacker)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        page.goto(f"http://127.0.0.1:{server.server_port}/")
        playwright_api.expect(page).to_have_title("sent")
    finally:
        server.shutdown()
    assert app_server["store"].list_favorites(profile_id=1) == []
    assert app_server["store"].latest_scan("DE", profile_id=1) is None


def test_service_drawer_saves_notes_and_splits_the_price(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    # A finished scan saved one history row for the own paid service.
    assert "Netflix" in app_server["store"].service_history("DE", profile_id=1)
    page.goto(f"{app_server['url']}/subscriptions")
    netflix = page.locator('tr[data-service="Netflix"]')
    netflix.locator('[name="price"]').fill("12")
    netflix.locator('[name="price"]').blur()
    expect(page.locator("#save-state")).to_have_text("Saved")
    netflix.locator(".service-open").click()
    expect(page.locator("#service-drawer")).to_be_visible()
    expect(page.locator("#service-drawer-title")).to_have_text("Netflix")
    page.locator("#drawer-shared").fill("3")
    page.locator("#drawer-note").fill("family account")
    page.locator("#drawer-note").blur()
    expect(page.locator("#save-state")).to_have_text("Saved")
    # "Saved" may still be showing from the price: wait until the note is really stored.
    for _ in range(30):
        saved = app_server["settings"].costs("DE")["Netflix"]
        if saved.get("note") == "family account":
            break
        page.wait_for_timeout(100)
    assert (saved["price"], saved["shared"], saved["note"]) == (12.0, 3, "family account")
    page.keyboard.press("Escape")
    expect(page.locator("#service-drawer")).to_be_hidden()
    expect(netflix.locator(".service-open")).to_be_focused()
    page.reload()
    expect(page.locator("#total-month")).to_contain_text(re.compile(r"4[.,]00"))  # 12 split between 3


def test_planner_what_if_changes_nothing_that_is_saved(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/watchlist")
    expect(page.locator("#progress-count")).to_have_text("Complete", timeout=15000)
    page.goto(f"{app_server['url']}/subscriptions")
    expect(page.locator("#planner")).to_be_visible()
    expect(page.locator("#whatif-result")).to_contain_text("As it is")
    page.locator('#whatif input[value="Netflix"]').uncheck()
    expect(page.locator("#whatif-result")).to_contain_text("What-if, nothing saved")
    assert app_server["settings"].subscriptions("DE") == ["Netflix"]
    page.locator('#whatif input[value="Netflix"]').check()
    expect(page.locator("#whatif-result")).to_contain_text("As it is")


def test_grey_outs_can_be_reset_on_the_data_page(app_server, page):
    expect = playwright_api.expect
    assert page.request.put(app_server["url"] + "/api/flags/348", data={"flag": "watched"}).ok
    page.goto(app_server["url"] + "/settings/data")
    expect(page.locator("#greyouts-text")).to_contain_text("1 film is hidden")
    page.get_by_role("button", name="Unhide all").click()
    expect(page.locator("#greyouts-text")).to_contain_text("1 films unhidden")
    expect(page.get_by_role("button", name="Unhide all")).to_be_disabled()
    assert page.request.get(app_server["url"] + "/api/greyouts").json() == {"flags": 0, "favorites": 0}


def test_data_page_exports_and_previews_an_import_before_changing_anything(app_server, page):
    expect = playwright_api.expect
    page.goto(app_server["url"] + "/settings/data")
    with page.expect_download() as download:
        page.locator('[data-export="favorites-json"]').click()
    assert download.value.suggested_filename == "favorites.json"
    records = (
        '[{"key": "9001", "title": "Alien", "year": 1979}, {"key": "9002", "title": "Heat", "year": 1995}]'
    )
    page.locator("#import-favorites").set_input_files(
        files=[{"name": "favorites.json", "mimeType": "application/json", "buffer": records.encode()}]
    )
    expect(page.locator("#import-preview")).to_have_text("2 favorites found · 0 already set · 2 new")
    assert page.request.get(app_server["url"] + "/api/favorites").json() == []  # nothing changed yet
    page.get_by_role("button", name="Import", exact=True).click()
    expect(page.locator("#import-preview")).to_have_text("Imported 2 favorites.")
    assert len(page.request.get(app_server["url"] + "/api/favorites").json()) == 2
