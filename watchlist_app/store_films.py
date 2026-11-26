"""Store methods for watchlist entries, their TMDB ids, film data, offers and the provider catalog."""

import json
import time

from .store_base import StoreBase
from .store_schema import MATCH_FIELDS


class FilmStore(StoreBase):
    # ----- watchlist entry -> TMDB id -----

    def get_id(self, film_key: str) -> dict | None:
        rows = self._read(
            "SELECT tmdb_id, source, checked_at, lb_rating, lb_checked_at FROM film_ids WHERE film_key = ?",
            (film_key,),
        )
        if not rows:
            return None
        tmdb_id, source, checked_at, lb_rating, lb_checked_at = rows[0]
        return {
            "tmdb_id": tmdb_id,
            "source": source,
            "checked_at": checked_at,
            "lb_rating": lb_rating,
            "lb_checked_at": lb_checked_at,
        }

    def set_letterboxd_rating(self, film_key: str, rating: float | None, checked_at=None) -> None:
        """Remember the Letterboxd average of a watchlist entry (None: too few ratings)."""
        self._write(
            "UPDATE film_ids SET lb_rating = ?, lb_checked_at = ? WHERE film_key = ?",
            (rating, checked_at if checked_at is not None else time.time(), film_key),
        )

    def set_id(
        self,
        film_key: str,
        tmdb_id: int | None,
        source: str | None,
        checked_at=None,
        title: str | None = None,
        year: int | None = None,
    ) -> None:
        """Remember which TMDB id a watchlist entry maps to (None = not found).

        Sources: "letterboxd" (id from the film page), "search" (first TMDB title
        hit), "missing" (TMDB does not know the id) and "manual" (set by the user).
        """
        now = checked_at if checked_at is not None else time.time()
        self._write(
            "INSERT INTO film_ids (film_key, tmdb_id, source, checked_at, title, year, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(film_key) DO UPDATE SET tmdb_id = excluded.tmdb_id, "
            "source = excluded.source, checked_at = excluded.checked_at, "
            "title = coalesce(excluded.title, film_ids.title), year = coalesce(excluded.year, film_ids.year)",
            (film_key, tmdb_id, source, now, title, year, now),
        )

    def remove_id(self, film_key: str) -> None:
        self._write("DELETE FROM film_ids WHERE film_key = ?", (film_key,))

    def touch_ids(self, entries: list[tuple[str, str, int | None]], seen_at: float | None = None) -> None:
        """Mark watchlist entries (key, title, year) as seen in a scan; fills in missing titles."""
        moment = seen_at if seen_at is not None else time.time()
        with self._lock:
            self._db.executemany(
                "UPDATE film_ids SET last_seen = ?, title = coalesce(title, ?), year = coalesce(year, ?) "
                "WHERE film_key = ?",
                [(moment, title, year, key) for key, title, year in entries],
            )
            self._db.commit()

    def list_matches(self, seen_since: float = 0) -> list[dict]:
        """Watchlist entries and their TMDB id, with the stored TMDB data of the film."""
        rows = self._read(
            f"SELECT {', '.join('film_ids.' + name for name in MATCH_FIELDS)}, films.poster_path, "
            "films.details FROM film_ids LEFT JOIN films ON films.tmdb_id = film_ids.tmdb_id "
            "WHERE coalesce(film_ids.last_seen, film_ids.checked_at) >= ? ORDER BY film_ids.title",
            (seen_since,),
        )
        matches = []
        for row in rows:
            match = dict(zip(MATCH_FIELDS, row[: len(MATCH_FIELDS)], strict=True))
            match["poster_path"] = row[-2]
            match["details"] = json.loads(row[-1]) if row[-1] else None
            matches.append(match)
        return matches

    # ----- TMDB film data and offers -----

    def get_film(self, tmdb_id: int, country: str) -> dict | None:
        """Details and the offers for one country, or None if nothing is stored yet."""
        rows = self._read(
            "SELECT films.poster_path, films.details, films.fetched_at, offers.providers "
            "FROM films LEFT JOIN offers ON offers.tmdb_id = films.tmdb_id AND offers.country = ? "
            "WHERE films.tmdb_id = ?",
            (country, tmdb_id),
        )
        if not rows:
            return None
        poster_path, details, fetched_at, providers = rows[0]
        return {
            "poster_path": poster_path,
            "details": json.loads(details or "{}"),
            "providers": json.loads(providers) if providers else {},
            "fetched_at": fetched_at,
        }

    def offers_by_country(self, tmdb_id: int) -> dict[str, dict[str, list[str]]]:
        """The stored offers of every country: {country: {TMDB provider name: kinds}}."""
        rows = self._read("SELECT country, providers FROM offers WHERE tmdb_id = ?", (tmdb_id,))
        return {country: json.loads(providers) for country, providers in rows}

    def offers_for(self, tmdb_ids: list[int]) -> dict[str, dict[int, dict[str, list[str]]]]:
        """The stored offers of the given films in every country: {country: {tmdb_id: {provider: kinds}}}."""
        found: dict[str, dict[int, dict[str, list[str]]]] = {}
        for start in range(0, len(tmdb_ids), 500):  # SQLite limits the number of parameters
            chunk = tmdb_ids[start : start + 500]
            marks = ", ".join("?" for _ in chunk)
            for tmdb_id, country, providers in self._read(
                f"SELECT tmdb_id, country, providers FROM offers WHERE tmdb_id IN ({marks})", tuple(chunk)
            ):
                found.setdefault(country, {})[tmdb_id] = json.loads(providers)
        return found

    def save_bundle(self, tmdb_id: int, bundle: dict, fetched_at=None) -> None:
        """Store details and the offers of every country from one TMDB response."""
        self.offers_version += 1
        with self._lock:
            self._db.execute(
                "INSERT INTO films (tmdb_id, poster_path, details, fetched_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(tmdb_id) DO UPDATE SET poster_path = excluded.poster_path, "
                "details = excluded.details, fetched_at = excluded.fetched_at",
                (
                    tmdb_id,
                    bundle.get("poster_path"),
                    json.dumps(bundle.get("details") or {}),
                    fetched_at if fetched_at is not None else time.time(),
                ),
            )
            self._db.execute("DELETE FROM offers WHERE tmdb_id = ?", (tmdb_id,))
            self._db.executemany(
                "INSERT INTO offers (tmdb_id, country, providers) VALUES (?, ?, ?)",
                [
                    (tmdb_id, country, json.dumps(providers))
                    for country, providers in (bundle.get("providers") or {}).items()
                ],
            )
            self._db.commit()

    # ----- providers TMDB knows per country -----

    def save_provider_catalog(self, country: str, items: list[dict], fetched_at=None) -> None:
        """Replace the providers of a country ({"name", "logo_path", "priority"} each)."""
        moment = fetched_at if fetched_at is not None else time.time()
        with self._lock:
            self._db.execute("DELETE FROM provider_catalog WHERE country = ?", (country,))
            self._db.executemany(
                "INSERT OR REPLACE INTO provider_catalog "
                "(country, tmdb_name, logo_path, priority, fetched_at) VALUES (?, ?, ?, ?, ?)",
                [
                    (country, item["name"], item.get("logo_path"), item.get("priority"), moment)
                    for item in items
                ],
            )
            self._db.commit()

    def provider_catalog(self, country: str | None = None) -> list[dict]:
        """Stored providers, by country and TMDB display priority."""
        where, parameters = ("WHERE country = ?", (country,)) if country else ("", ())
        rows = self._read(
            "SELECT country, tmdb_name, logo_path, priority, fetched_at FROM provider_catalog "
            f"{where} ORDER BY country, coalesce(priority, 9999), tmdb_name",
            parameters,
        )
        names = ("country", "name", "logo_path", "priority", "fetched_at")
        return [dict(zip(names, row, strict=True)) for row in rows]

    def provider_catalog_age(self, country: str) -> float | None:
        """When the providers of a country were last fetched, or None."""
        return self._read("SELECT max(fetched_at) FROM provider_catalog WHERE country = ?", (country,))[0][0]
