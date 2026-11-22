from watchlist_app.providers import MOSTLY_FREE, load_platforms_config, mostly_free_from_scan


class TestLoadPlatformsConfig:
    def test_returns_defaults_when_no_file(self, tmp_path):
        targets = load_platforms_config("FR", toml_path=tmp_path / "missing.toml")
        assert "Arte" in targets
        assert "Netflix" in targets

    def test_reads_enabled_only(self, tmp_path):
        toml = tmp_path / "platforms.toml"
        toml.write_text(
            '[FR]\nArte = true\nMolotov = false\nNetflix = true\n"Canal+" = false\n"TF1+" = true\n'
        )
        targets = load_platforms_config("FR", toml_path=toml)
        assert "Arte" in targets
        assert "Molotov" not in targets
        assert "Netflix" in targets
        assert "Canal+" not in targets
        assert "TF1+" in targets

    def test_unknown_key_ignored(self, tmp_path):
        toml = tmp_path / "platforms.toml"
        toml.write_text("[FR]\nInconnu = true\nNetflix = true\n")
        targets = load_platforms_config("FR", toml_path=toml)
        assert "Inconnu" not in targets
        assert "Netflix" in targets

    def test_values_are_tmdb_names(self, tmp_path):
        toml = tmp_path / "platforms.toml"
        toml.write_text('[FR]\n"Prime Video" = true\n')
        targets = load_platforms_config("FR", toml_path=toml)
        assert targets["Prime Video"] == "Amazon Prime Video"

    def test_falls_back_to_defaults_when_country_section_missing(self, tmp_path):
        toml = tmp_path / "platforms.toml"
        toml.write_text("[US]\nNetflix = true\n")
        targets = load_platforms_config("FR", toml_path=toml)
        assert "Arte" in targets  # no [FR] → fallback to defaults

    def test_different_country_section(self, tmp_path):
        toml = tmp_path / "platforms.toml"
        toml.write_text("[US]\nHulu = true\nNetflix = true\n[FR]\nArte = true\n")
        us = load_platforms_config("US", toml_path=toml)
        fr = load_platforms_config("FR", toml_path=toml)
        assert "Hulu" in us and "Hulu" not in fr
        assert "Arte" in fr and "Arte" not in us


def test_display_names_and_loaded_providers():
    from watchlist_app import providers

    assert providers.display_name("Amazon Prime Video") == "Prime Video"
    assert providers.display_name("Brand New Stream") == "Brand New Stream"
    assert providers.tmdb_names(["Prime Video", "Brand New Stream"]) == {
        "Prime Video": "Amazon Prime Video",
        "Brand New Stream": "Brand New Stream",
    }
    groups = dict(providers.provider_groups(["Brand New Stream", "Zappn amazon channel", "Netflix"]))
    more = dict(groups["Services"])["More services"]
    assert more[-1] == "Brand New Stream" and more.count("Netflix") == 0
    assert "Zappn amazon channel" in groups["Amazon Channels"][0][1]
    names = [
        name
        for _, subgroups in providers.provider_groups(["Netflix"])
        for _, group in subgroups
        for name in group
    ]
    assert names.count("Netflix") == 1


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
    assert "Arte" in free  # not in the scan: the list decides


def test_mostly_free_services_fall_back_without_scan():
    assert mostly_free_from_scan([], []) == MOSTLY_FREE
