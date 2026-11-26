"""GET /api/together: the active profile's list merged with other profiles' lists."""

import time

import pytest

HEAT = {"key": "949", "tmdb_id": 949, "title": "Heat", "year": 1995, "providers": {"Netflix": ["flatrate"]}}
ALIEN = {"key": "348", "tmdb_id": 348, "title": "Alien", "year": 1979, "providers": {"MUBI": ["flatrate"]}}
UP = {"key": "14160", "tmdb_id": 14160, "title": "Up", "year": 2009, "providers": {"MUBI": ["flatrate"]}}


@pytest.fixture
def anna(store, settings):
    anna = store.add_profile("Anna")
    settings.for_profile(anna).update({"subscriptions": ["MUBI"]})
    store.save_scan("DE", "letterboxd", None, [HEAT, UP], [], {}, profile_id=anna)
    return anna


@pytest.fixture
def ben(store):
    ben = store.add_profile("Ben")
    store.save_scan("DE", "letterboxd", None, [HEAT, ALIEN], [], {}, profile_id=ben)
    return ben


@pytest.fixture
def mine(store, settings):
    settings.update({"subscriptions": ["Netflix"]})
    store.save_scan("DE", "letterboxd", None, [HEAT, ALIEN], [], {}, profile_id=1)


@pytest.mark.usefixtures("mine")
class TestTogether:
    def test_two_profiles(self, client, anna):
        answer = client.get(f"/api/together?with={anna}").get_json()
        assert answer["available"] is True and answer["country"] == "DE" and answer["missing"] == []
        assert [film["key"] for film in answer["results"]] == ["949", "348", "14160"]
        assert answer["together"] == {
            "members": [{"id": 1, "name": "Me"}, {"id": anna, "name": "Anna"}],
            "groups": {"both": ["949"], "one": ["348", "14160"]},
            "service_owners": {"Netflix": [1], "MUBI": [anna]},
        }
        assert answer["subscriptions"] == ["Netflix", "MUBI"]
        heat = answer["results"][0]
        assert heat["on_lists"] == [1, anna] and heat["group"] == "both"
        assert "only_on_my_services" in heat  # marked with the services of both, like /api/latest

    def test_three_profiles_watched_and_hidden_films_drop_out(self, client, store, anna, ben):
        store.set_id("lb:alien", 348, "letterboxd")  # matched by an earlier scan
        store.replace_watched(["lb:alien"], profile_id=ben)
        store.set_flag("14160", "not_now", time.time() + 3600, profile_id=anna)
        answer = client.get(f"/api/together?with={anna},{ben}").get_json()
        assert [film["key"] for film in answer["results"]] == ["949"]
        assert answer["together"]["groups"] == {"both": ["949"], "one": []}
        assert [member["id"] for member in answer["together"]["members"]] == [1, anna, ben]

    def test_the_active_profile_and_its_country_lead(self, client, store, settings, anna):
        settings.for_profile(anna).update({"country": "GB"})
        store.save_scan("GB", "letterboxd", None, [UP], [], {}, profile_id=anna)
        # Anna is active: her country, her scan first; profile 1 has no scan in GB.
        answer = client.get(f"/api/together?with=1,{anna}&profile={anna}").get_json()
        assert answer["country"] == "GB" and answer["missing"] == [1]
        assert [film["key"] for film in answer["results"]] == ["14160"]
        assert answer["together"]["members"][0] == {"id": anna, "name": "Anna"}  # self in ?with is ignored

    def test_a_partner_with_an_old_or_no_scan_is_missing(self, client, store):
        old = store.add_profile("Old")
        store.save_scan(
            "DE", "letterboxd", None, [UP], [], {}, created=time.time() - 3 * 86400, profile_id=old
        )
        nobody = store.add_profile("Nobody")
        answer = client.get(f"/api/together?with={old},{nobody}").get_json()
        assert answer["missing"] == [old, nobody]
        # The old list still counts; without a scan Nobody has no list to be on.
        assert answer["together"]["groups"] == {"both": [], "one": ["949", "348", "14160"]}

    @pytest.mark.parametrize("partners", ["", "abc", "1", "99", "2,x"])
    def test_invalid_partners_are_refused(self, client, anna, partners):
        assert client.get(f"/api/together?with={partners}").status_code == 400


def test_without_an_own_scan_nothing_is_available(client, store, anna):
    answer = client.get(f"/api/together?with={anna}").get_json()
    assert answer["available"] is False and answer["missing"] == []
    assert answer["together"]["members"][1]["name"] == "Anna"
