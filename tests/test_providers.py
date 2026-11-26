from watchlist_app import providers
from watchlist_app.providers import load_platforms_config, mostly_free_from_scan, rental_from_scan


class TestLoadPlatformsConfig:
    def test_no_file_gives_no_services(self, tmp_path):
        assert load_platforms_config("FR", toml_path=tmp_path / "missing.toml") == {}

    def test_reads_enabled_only(self, tmp_path):
        toml = tmp_path / "platforms.toml"
        toml.write_text(
            '[FR]\nArte = true\nMolotov = false\nNetflix = true\n"Canal+" = false\n"TF1+" = true\n'
        )
        assert set(load_platforms_config("FR", toml_path=toml)) == {"Arte", "Netflix", "TF1+"}

    def test_values_are_tmdb_names(self, tmp_path):
        toml = tmp_path / "platforms.toml"
        toml.write_text('[FR]\n"Prime Video" = true\nNetflix = true\n')
        assert load_platforms_config("FR", toml_path=toml) == {
            "Prime Video": "Amazon Prime Video",
            "Netflix": "Netflix",
        }

    def test_a_country_without_a_section_starts_empty(self, tmp_path):
        toml = tmp_path / "platforms.toml"
        toml.write_text("[US]\nHulu = true\nNetflix = true\n[FR]\nArte = true\n")
        assert load_platforms_config("IT", toml_path=toml) == {}
        assert "Hulu" in load_platforms_config("US", toml_path=toml)
        assert "Hulu" not in load_platforms_config("FR", toml_path=toml)


def test_alias_display_names_still_map():
    assert providers.display_name("Amazon Prime Video") == "Prime Video"
    assert providers.display_name(" Disney Plus ") == "Disney+"
    assert providers.display_name("Wow Fiction Amazon Channel") == "WOW Fiction Amazon Channel"
    assert providers.display_name("Brand New Stream") == "Brand New Stream"
    assert providers.tmdb_names(["Prime Video", "Brand New Stream"]) == {
        "Prime Video": "Amazon Prime Video",
        "Brand New Stream": "Brand New Stream",
    }
    assert providers.known_names(["Netflix"]) >= {"Netflix", "Prime Video", "Apple TV+"}


def test_mostly_free_services_use_scan_data():
    results = [
        {"providers": {"BBC iPlayer": ["free"], "Molotov": ["free"]}},
        {"providers": {"BBC iPlayer": ["ads"]}},
        {"providers": {"Molotov": ["free"], "BBC iPlayer": ["free"]}},
    ]
    assert "BBC iPlayer" in mostly_free_from_scan(results, [])
    assert "Molotov" in mostly_free_from_scan(results, [])
    assert "Netflix" not in mostly_free_from_scan(results, [])


def test_mostly_free_counts_each_service_against_its_own_films():
    # A free service with few watchlist films is still free; a paid one with a few free films is not.
    paid = [{"providers": {"Netflix": ["flatrate"]}} for _ in range(20)]
    films = [*paid, {"providers": {"Joyn": ["free"], "Molotov": ["free"]}}]
    films += [{"providers": {"Molotov": ["flatrate"]}}, {"providers": {"Molotov": ["flatrate"]}}]
    free = mostly_free_from_scan(films, [])
    assert "Joyn" in free
    assert "Molotov" not in free
    assert "Arte" not in free  # not in the scan: no built-in list decides any more


def test_without_a_scan_no_service_is_free_or_a_rental_shop():
    assert mostly_free_from_scan([], []) == frozenset()
    assert rental_from_scan([], []) == frozenset()


def test_rental_shops_are_services_that_only_rent_or_buy():
    results = [
        {"providers": {"Apple TV Store": ["rent", "buy"], "Netflix": ["flatrate"]}},
        {"providers": {"Rakuten TV": ["rent"], "Amazon VOD": ["rent"]}},
        {"providers": {"Amazon VOD": ["flatrate"]}},
    ]
    unavailable = [{"providers": {"Videobuster": ["buy"]}}]
    assert rental_from_scan(results, unavailable) == {"Apple TV Store", "Rakuten TV", "Videobuster"}


def test_groups_come_from_the_scan_offers_in_catalog_order():
    results = [
        {"providers": {"Arte": ["free"], "Netflix": ["flatrate"], "Apple TV Store": ["rent"]}},
        {"providers": {"MUBI": ["flatrate"], "Zappn Amazon Channel": ["flatrate"]}},
    ]
    catalog = ["Netflix", "Apple TV Store", "Arte", "MUBI", "Zappn Amazon Channel", "Brand New Stream"]
    catalog.append("Netflix")  # TMDB can list a name twice
    groups = dict(providers.provider_groups(results, [], catalog))
    assert groups == {
        "Free and ad-supported": ["Arte"],
        "Subscriptions": ["Netflix", "MUBI"],  # TMDB's priority order, each name once
        "More services": ["Brand New Stream"],  # in the country, but not in the scan
        "Rental shops": ["Apple TV Store"],
        "Amazon Channels": ["Zappn Amazon Channel"],
    }
    # Only the country's services are listed: a scan provider missing from the catalog is left out.
    canal = [{"providers": {"Canal+": ["flatrate"]}}]
    assert "Canal+" not in str(providers.provider_groups(canal, [], ["Arte"]))


def test_groups_without_a_catalog_use_the_scan_providers():
    films = [{"providers": {"Netflix": ["flatrate"], "Arte": ["ads"]}}]
    groups = dict(providers.provider_groups(films, [], []))
    assert groups["Subscriptions"] == ["Netflix"] and groups["Free and ad-supported"] == ["Arte"]
    assert all(not names for names in dict(providers.provider_groups([], [], [])).values())
