from watchlist_app import history


def film(key, title, providers, year=2000):
    return {"key": key, "title": title, "year": year, "providers": {name: ["flatrate"] for name in providers}}


def previous(results, unavailable=()):
    return {"results": list(results), "unavailable": list(unavailable)}


class TestDiffScans:
    def test_no_previous_scan_means_no_changes(self):
        assert history.diff_scans(None, [film("1", "Heat", ["Netflix"])], []) == []

    def test_added_and_removed_providers(self):
        before = previous([film("1", "Heat", ["Netflix", "MUBI"])])
        changes = history.diff_scans(before, [film("1", "Heat", ["Netflix", "Arte"])], [])
        assert [(change["provider"], change["change"]) for change in changes] == [
            ("Arte", "added"),
            ("MUBI", "removed"),
        ]
        assert changes[0]["film_key"] == "1" and changes[0]["title"] == "Heat"

    def test_film_becoming_available_or_unavailable(self):
        before = previous([film("1", "Heat", ["Netflix"])], [film("2", "Alien", [])])
        changes = history.diff_scans(before, [film("2", "Alien", ["Arte"])], [film("1", "Heat", [])])
        assert {(change["title"], change["provider"], change["change"]) for change in changes} == {
            ("Alien", "Arte", "added"),
            ("Heat", "Netflix", "removed"),
        }

    def test_film_new_on_the_watchlist_is_not_a_change(self):
        before = previous([film("1", "Heat", ["Netflix"])])
        assert (
            history.diff_scans(before, [film("1", "Heat", ["Netflix"]), film("2", "Alien", ["Arte"])], [])
            == []
        )

    def test_old_scan_without_tmdb_keys_is_matched_by_title_and_year(self):
        before = previous([{"title": "Heat", "year": 1995, "providers": {"Netflix": ["rent"]}}])
        changes = history.diff_scans(before, [film("949", "Heat", ["Arte"], year=1995)], [])
        assert {(change["provider"], change["change"]) for change in changes} == {
            ("Arte", "added"),
            ("Netflix", "removed"),
        }
        assert {change["film_key"] for change in changes} == {"949"}


def change(key, provider, kind, created):
    return {
        "film_key": key,
        "title": "x",
        "year": 2000,
        "provider": provider,
        "change": kind,
        "created": created,
    }


class TestApplyChanges:
    def test_changes_are_attached_to_copies(self):
        original = film("1", "Heat", ["Arte"])
        annotated = history.apply_changes(
            [original], [change("1", "Arte", "added", 20), change("1", "MUBI", "removed", 10)]
        )
        assert annotated[0]["provider_changes"] == {"added": ["Arte"], "removed": ["MUBI"], "since": 20}
        assert "provider_changes" not in original

    def test_newest_change_per_provider_wins(self):
        # Added last week, removed yesterday: only "removed" is shown.
        annotated = history.apply_changes(
            [film("1", "Heat", [])], [change("1", "Arte", "removed", 20), change("1", "Arte", "added", 10)]
        )
        assert annotated[0]["provider_changes"] == {"added": [], "removed": ["Arte"], "since": 20}

    def test_change_that_no_longer_matches_is_dropped(self):
        annotated = history.apply_changes([film("1", "Heat", ["Arte"])], [change("1", "Arte", "removed", 5)])
        assert "provider_changes" not in annotated[0]

    def test_films_without_changes_are_untouched(self):
        assert history.apply_changes([film("2", "Alien", ["Arte"])], [change("1", "Arte", "added", 5)]) == [
            film("2", "Alien", ["Arte"])
        ]


def test_compare_only_ignores_providers_the_old_scan_did_not_know():
    from watchlist_app.history import diff_scans

    previous = {"results": [{"key": "1", "title": "A", "year": 2000, "providers": {"Netflix": ["flatrate"]}}]}
    results = [
        {"key": "1", "title": "A", "year": 2000, "providers": {"Netflix": ["flatrate"], "New": ["ads"]}}
    ]
    assert diff_scans(previous, results, [], compare_only={"Netflix"}) == []
    assert [change["provider"] for change in diff_scans(previous, results, [])] == ["New"]
