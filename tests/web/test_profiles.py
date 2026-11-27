"""Route tests: the profiles API and the profile chosen for each request."""

import flask
import pytest

from web.common import active_settings

EMAIL = "Cf-Access-Authenticated-User-Email"


@pytest.fixture
def anna(store):
    return store.add_profile("Anna", "anna@example.org")


def _profile_of(client, path="/api/flags", method="get", **kwargs) -> int:
    with client:
        getattr(client, method)(path, **kwargs)
        return flask.g.profile_id


class TestProfilesApi:
    def test_list_add_rename_delete(self, client, store):
        answer = client.post("/api/profiles", json={"name": "Ben", "email": "ben@example.org"})
        assert answer.status_code == 201
        ben = answer.get_json()["id"]
        assert [p["name"] for p in client.get("/api/profiles").get_json()] == ["Me", "Ben"]

        answer = client.put(f"/api/profiles/{ben}", json={"name": "Benjamin"})
        assert answer.status_code == 200
        assert answer.get_json()["email"] == "ben@example.org"  # a missing e-mail is kept
        assert (
            client.put(f"/api/profiles/{ben}", json={"name": "Benjamin", "email": None}).get_json()["email"]
            is None
        )

        assert client.delete(f"/api/profiles/{ben}").status_code == 200
        assert [p["id"] for p in store.list_profiles()] == [1]

    def test_bad_requests_get_400(self, client, anna):
        for body in ({"name": "Anna"}, {"name": ""}, {}, {"name": "Ben", "email": "nope"}):
            answer = client.post("/api/profiles", json=body)
            assert answer.status_code == 400 and answer.get_json()["error"]
        assert client.put(f"/api/profiles/{anna}", json={"name": "Me"}).status_code == 400
        client.delete("/api/profiles/1")
        answer = client.delete(f"/api/profiles/{anna}")
        assert answer.status_code == 400 and "last profile" in answer.get_json()["error"]

    def test_unknown_profile_gets_404(self, client):
        assert client.put("/api/profiles/9", json={"name": "X"}).status_code == 404
        assert client.delete("/api/profiles/9").status_code == 404
        assert client.post("/api/profiles/active", json={"id": 9}).status_code == 404

    def test_cross_site_writes_are_refused(self, client, store, anna):
        evil = {"Origin": "https://evil.example"}
        assert client.post("/api/profiles", json={"name": "Eve"}, headers=evil).status_code == 403
        assert client.put(f"/api/profiles/{anna}", json={"name": "Eve"}, headers=evil).status_code == 403
        assert client.delete(f"/api/profiles/{anna}", headers=evil).status_code == 403
        assert client.post("/api/profiles/active", json={"id": anna}, headers=evil).status_code == 403
        assert len(store.list_profiles()) == 2


class TestActiveProfile:
    def test_choosing_sets_the_cookie(self, client, anna):
        answer = client.post("/api/profiles/active", json={"id": anna})
        assert answer.status_code == 200
        cookie = answer.headers["Set-Cookie"]
        assert cookie.startswith(f"wl_profile={anna};")
        for part in ("HttpOnly", "SameSite=Lax", "Path=/", "Max-Age=31536000"):
            assert part in cookie
        assert _profile_of(client) == anna  # the test client sends the cookie back

    def test_choosing_needs_an_integer_id(self, client, anna):
        for body in ({"id": True}, {"id": "2"}, {}, {"id": 1.5}):
            assert client.post("/api/profiles/active", json=body).status_code == 400

    def test_deleting_the_chosen_profile_forgets_the_cookie(self, client, store, anna):
        client.post("/api/profiles/active", json={"id": anna})
        assert client.delete(f"/api/profiles/{anna}").status_code == 200
        assert "wl_profile" not in {cookie.key for cookie in client._cookies.values()}
        assert _profile_of(client) == 1

    def test_default_is_profile_1(self, client, anna):
        assert _profile_of(client) == 1

    def test_query_beats_cookie(self, client, anna):
        client.set_cookie("wl_profile", "1")
        assert _profile_of(client, f"/api/flags?profile={anna}", headers={EMAIL: "anna@example.org"}) == anna

    def test_cookie_beats_header(self, client, store, anna):
        ben = store.add_profile("Ben", "ben@example.org")
        client.set_cookie("wl_profile", str(ben))
        assert _profile_of(client, headers={EMAIL: "anna@example.org"}) == ben

    def test_header_matches_the_email_case_insensitively(self, client, anna):
        assert _profile_of(client, headers={EMAIL: " ANNA@Example.org "}) == anna
        assert _profile_of(client, headers={EMAIL: "someone@example.org"}) == 1

    @pytest.mark.parametrize("value", ["abc", "", "9", "-1", "99999999999999999999", "²"])
    def test_invalid_values_fall_through(self, client, anna, value):
        assert _profile_of(client, f"/api/flags?profile={value}") == 1
        client.set_cookie("wl_profile", value)
        assert _profile_of(client, f"/api/flags?profile={value}", headers={EMAIL: "anna@example.org"}) == anna

    def test_query_is_ignored_on_writes(self, client, anna):
        assert _profile_of(client, f"/api/profiles?profile={anna}", "post", json={"name": "Ben"}) == 1

    def test_fallback_is_the_lowest_id_when_profile_1_is_gone(self, client, store, anna):
        store.add_profile("Ben")
        store.delete_profile(1)
        assert _profile_of(client) == anna

    def test_active_settings_belong_to_the_request_profile(self, client, store, settings, anna):
        store.set_profile_setting("country", "GB", profile_id=anna)
        with client:
            client.get(f"/api/flags?profile={anna}")
            assert (active_settings(settings).country, settings.country) == ("GB", "DE")


class TestProfilesInThePages:
    def test_header_shows_the_active_profile_and_offers_the_others(self, client, anna):
        client.set_cookie("wl_profile", str(anna))
        page = client.get("/settings").get_data(as_text=True)
        assert 'aria-label="Profile: Anna. Switch profile"' in page
        assert 'data-profile-id="1"' in page and f'data-profile-id="{anna}"' not in page
        assert 'href="/settings/profiles"' in page

    def test_header_with_one_profile_still_links_to_manage_profiles(self, client):
        page = client.get("/").get_data(as_text=True)
        assert 'aria-label="Profile: Me. Switch profile"' in page and "Manage profiles" in page
        assert "data-profile-id=" not in page

    def test_profiles_page_lists_every_profile_with_the_active_mark(self, client, anna):
        page = client.get("/settings/profiles").get_data(as_text=True)
        assert 'value="Me"' in page and 'value="Anna"' in page and 'value="anna@example.org"' in page
        assert page.count('class="pill pill-ok">Active<') == 1
        assert 'aria-label="Use this profile: Anna"' in page
        assert 'aria-label="Use this profile: Me"' not in page
        assert "Profiles are not private" in page and 'aria-current="page">Profiles<' in page
        assert "The last profile cannot be deleted." not in page

    def test_the_last_profile_cannot_be_deleted(self, client):
        page = client.get("/settings/profiles").get_data(as_text=True)
        assert "The last profile cannot be deleted." in page
        assert 'aria-label="Delete Me" disabled' in page

    def test_a_new_profile_without_a_name_is_not_scanned_by_the_page(self, client, store, anna):
        client.set_cookie("wl_profile", str(anna))
        assert '"needsUsername": true' in client.get("/watchlist").get_data(as_text=True)
        assert ">Not synced yet<" in client.get("/settings").get_data(as_text=True)  # not "Out of date"
        store.set_profile_setting("letterboxd_username", "anna", profile_id=anna)
        assert '"needsUsername": true' not in client.get("/watchlist").get_data(as_text=True)


def test_unknown_pages_get_the_app_404_and_the_api_json(client):
    answer = client.get("/no-such-page")
    assert answer.status_code == 404 and "Page not found" in answer.get_data(as_text=True)
    assert 'id="app-header"' in answer.get_data(as_text=True)
    answer = client.get("/api/no-such-thing")
    assert answer.status_code == 404 and answer.get_json() == {"error": "Not found."}


def test_ago_text_matches_the_page_script():
    from web.routes import ago_text

    assert [ago_text(s) for s in (30, 12 * 60, 3600, 47 * 3600, 3 * 86400)] == [
        "just now",
        "12 min ago",
        "1 h ago",
        "47 h ago",
        "3 days ago",
    ]
