"""The HTML pages, the service worker and the manifest."""

import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from watchlist_app import base, costs, providers
from watchlist_app.scan_service import ScanService
from watchlist_app.settings import SCAN_INTERVALS_HOURS, AppSettings
from watchlist_app.store import Store
from watchlist_app.tmdb import _TMDB_IMAGE_BASE_URL, _TMDB_LOGO_BASE_URL
from web.common import SORTS, active_profile_id, active_settings, page, provider_logos, status_overview


def register(app: Flask, store: Store, settings: AppSettings, service: ScanService) -> None:
    @app.route("/")
    def tonight():
        return films_page("tonight")

    @app.get("/watchlist")
    def watchlist():
        return films_page("watchlist")

    def films_page(view: str):
        s = active_settings(settings)
        latest = store.latest_scan(s.country, profile_id=s.profile_id)
        films, unavailable = (latest["results"], latest["unavailable"]) if latest else ([], [])
        initial_filters = {"query": request.args.get("q", ""), "sort": request.args.get("sort", SORTS[0][0])}
        # Tonight names the cancel tip in one line, only when Subscriptions has one.
        hint = None
        if view == "tonight" and latest:
            hint = costs.cancel_hint(
                costs.overview(
                    films,
                    s.subscriptions(s.country),
                    s.costs(s.country),
                    base.base_counts(latest)["not_available"],
                    weekly_hours=s.weekly_hours,
                )["recommendations"]
            )
        needs_username = not s.letterboxd_username and not latest
        return page(
            "index.html",
            view=view,
            cancel_hint=hint,
            needs_username=needs_username,
            needs_tmdb=not s.tmdb_api_key,
            country=s.country,
            initial_filters=initial_filters,
            sorts=SORTS,
            client_config={
                "imageBaseUrl": _TMDB_IMAGE_BASE_URL,
                "view": view,
                # No name and no scan yet: the page shows the setup steps instead of a scan that must fail.
                "needsUsername": needs_username,
                "deadlines": costs.upcoming_deadlines(s.costs(s.country)),
                "initialFilters": initial_filters,
                "subscriptions": {country: s.subscriptions(country) for country in s.countries_in_use()},
                "rentalShops": sorted(providers.rental_from_scan(films, unavailable)),
                "freeServices": sorted(providers.mostly_free_from_scan(films, unavailable)),
                "logoBaseUrl": _TMDB_LOGO_BASE_URL,
                # Logos of the providers loaded from TMDB, for the services menu and the details.
                "providerLogos": provider_logos(store),
            },
        )

    @app.get("/settings")
    def settings_page():
        return page(
            "settings.html",
            settings=active_settings(settings).as_dict(),
            intervals=SCAN_INTERVALS_HOURS,
        )

    @app.get("/stats")
    def stats_page():
        s = active_settings(settings)
        return page(
            "stats.html",
            client_config={
                "country": s.country,
                "imageBaseUrl": _TMDB_IMAGE_BASE_URL,
                "subscriptions": s.subscriptions(),
                "prices": {
                    name: entry["price"]
                    for name, entry in s.costs().items()
                    if entry.get("price") is not None
                },
            },
        )

    @app.get("/settings/data")
    def status_page():
        return page("status.html", status=status_overview(store, active_settings(settings), service))

    other_cache: dict[tuple, list[dict]] = {}

    def _other_countries(scan: dict | None, own: list[str], country: str) -> list[dict]:
        """Countries where your services show more of the watchlist (stored offers, no TMDB request)."""
        if not scan:
            return []
        # It reads the offers of every country (about a second): the same scan, offers and services give the
        # same answer, so keep the last few, as /api/abroad does.
        key = (scan["id"], store.offers_version, tuple(sorted(own)), country)
        if key not in other_cache:
            if len(other_cache) >= 8:
                other_cache.pop(next(iter(other_cache)))
            other_cache[key] = _count_other_countries(scan, own, country)
        return other_cache[key]

    def _count_other_countries(scan: dict, own: list[str], country: str) -> list[dict]:
        ids = [film["tmdb_id"] for film in scan["results"] if isinstance(film.get("tmdb_id"), int)]
        raw = store.offers_for(ids)
        by_country = {
            code: {tmdb_id: providers.display_providers(offers) for tmdb_id, offers in films.items()}
            for code, films in raw.items()
        }
        return costs.other_countries(by_country, own, country, len(ids))

    def _country_groups(s: AppSettings) -> list[tuple[str, list[str]]]:
        """The services TMDB lists in the app's country (no Canal+ in DE), grouped by the latest scan."""
        scan = store.latest_scan(s.country, profile_id=s.profile_id)
        catalog = [providers.display_name(item["name"]) for item in store.provider_catalog(s.country)]
        return providers.provider_groups(
            scan["results"] if scan else [], scan["unavailable"] if scan else [], catalog
        )

    def _service_candidates(s: AppSettings, own: list[str]) -> list[dict]:
        """Services you could add: [{name, group}], the more usual groups first."""
        mine = set(own)
        return [
            {"name": name, "group": group}
            for group, names in _country_groups(s)
            for name in names
            if name not in mine
        ]

    @app.get("/subscriptions")
    def subscriptions_page():
        # The country is the app's own (header); the services are chosen under Settings -> My services.
        s, pid = active_settings(settings), active_profile_id()
        country = s.country
        scan = store.latest_scan(country, profile_id=pid)
        own = s.subscriptions(country)
        counts = base.base_counts(scan)
        return page(
            "subscriptions.html",
            country=country,
            last_scan_at=scan["created"] if scan else None,
            deadlines=costs.upcoming_deadlines(s.costs(country)),
            costs=costs.overview(
                scan["results"] if scan else [],
                own,
                s.costs(country),
                counts["not_available"],
                frozenset(favorite["key"] for favorite in store.list_favorites(profile_id=pid)),
                weekly_hours=s.weekly_hours,
            ),
            coming_soon=counts["coming_soon"],
            weekly_hours=s.weekly_hours,
            history=store.service_history(country, profile_id=pid),
            own=own,
            candidates=_service_candidates(s, own),
            other_countries=_other_countries(scan, own, country),
            image_base_url=_TMDB_IMAGE_BASE_URL,
            logos=provider_logos(store),
            logo_base_url=_TMDB_LOGO_BASE_URL,
        )

    @app.get("/settings/services")
    def services_page():
        s = active_settings(settings)
        scan = store.latest_scan(s.country, profile_id=s.profile_id)
        counts: dict[str, int] = {}
        for film in scan["results"] if scan else []:
            for name in film.get("providers", {}):
                counts[name] = counts.get(name, 0) + 1
        selected = set(s.subscriptions())
        groups = dict(_country_groups(s))
        sections = [("My subscriptions", sorted(selected, key=str.casefold), True)]
        for title, opened in (
            ("Free and ad-supported", True),
            ("Subscriptions", True),
            ("Rental shops", True),
            ("Amazon Channels", False),
            ("More services", False),
        ):
            sections.append((title, [name for name in groups.get(title, []) if name not in selected], opened))
        return page(
            "services.html",
            country=s.country,
            sections=[section for section in sections if section[1]],
            selected=selected,
            counts=counts,
            logos=provider_logos(store),
            logo_base_url=_TMDB_LOGO_BASE_URL,
        )

    @app.get("/settings/matches")
    def matches_page():
        s = active_settings(settings)
        return page(
            "matches.html",
            client_config={"imageBaseUrl": _TMDB_IMAGE_BASE_URL, "country": s.country},
            tmdb_api_key_set=bool(s.tmdb_api_key),
        )

    @app.get("/settings/profiles")
    def profiles_page():
        return page("profiles.html")  # the list comes from header_context

    @app.get("/sw.js")
    def service_worker():
        # At the root, so the worker controls every page; never cached by the browser itself.
        response = send_file(Path(__file__).parent.parent / "static" / "sw.js", mimetype="text/javascript")
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/manifest.webmanifest")
    def manifest():
        return send_file(
            Path(__file__).parent.parent / "manifest.webmanifest",
            mimetype="application/manifest+json",
        )

    @app.get("/dev/ui")
    def dev_ui():
        """Every button variant in its states, to check them by eye; only in development."""
        if not (app.debug or os.getenv("WATCHLIST_DEV") == "1"):
            return jsonify({"error": "Not found."}), 404
        return render_template("dev-ui.html")
