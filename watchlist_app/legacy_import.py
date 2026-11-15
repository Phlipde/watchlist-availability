"""Copy data from the files used before the shared database, once.

Older versions kept favorites, the last scan and the film cache in separate
files. They are read on the first start and left in place untouched.
"""

import json
import sqlite3
from pathlib import Path

from .store import Store

DONE_SETTING = "legacy_import_done"


def _read_sqlite(path: Path, sql: str) -> list[tuple]:
    if not path.is_file():
        return []
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return connection.execute(sql).fetchall()
    except sqlite3.Error:
        return []
    finally:
        connection.close()


def _import_favorites(store: Store, path: Path) -> int:
    rows = _read_sqlite(
        path,
        "SELECT movie_key, title, year, poster_path, tmdb_url, trailer_url, rating, status, notes "
        "FROM favorites",
    )
    for key, title, year, poster_path, tmdb_url, trailer_url, rating, status, notes in rows:
        store.add_favorite(
            {
                "key": key,
                "title": title,
                "year": year,
                "poster_path": poster_path,
                "tmdb_url": tmdb_url,
                "trailer_url": trailer_url,
                "rating": rating,
                "status": status or "plan",
                "notes": notes or "",
            }
        )
    return len(rows)


def _import_latest_scan(store: Store, path: Path) -> int:
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return 0
    if not isinstance(snapshot, dict) or "results" not in snapshot:
        return 0
    store.save_scan(
        country=snapshot.get("country") or "",
        source_name=snapshot.get("source_name") or "",
        watchlist_key=None,
        results=snapshot.get("results") or [],
        unavailable=snapshot.get("unavailable") or [],
        stats=snapshot.get("stats") or {},
        created=snapshot.get("created"),
    )
    return 1


def _import_film_cache(store: Store, path: Path) -> int:
    rows = _read_sqlite(
        path,
        "SELECT film_key, tmdb_id, id_source, id_checked_at, poster_path, details, providers, fetched_at "
        "FROM films",
    )
    for film_key, tmdb_id, source, checked_at, poster_path, details, providers, fetched_at in rows:
        store.set_id(film_key, tmdb_id, source, checked_at=checked_at)
        if tmdb_id is not None and details and providers:
            store.save_bundle(
                tmdb_id,
                {
                    "poster_path": poster_path,
                    "details": json.loads(details),
                    "providers": json.loads(providers),
                },
                fetched_at=fetched_at,
            )
    return len(rows)


def import_legacy_data(
    store: Store,
    *,
    favorites_db: Path,
    latest_json: Path,
    film_cache_db: Path,
) -> dict[str, int] | None:
    """Import the old files into the store. Runs only once; returns None afterwards."""
    if store.get_setting(DONE_SETTING):
        return None
    counts = {
        "favorites": _import_favorites(store, favorites_db),
        "scans": _import_latest_scan(store, latest_json),
        "films": _import_film_cache(store, film_cache_db),
    }
    store.set_setting(DONE_SETTING, json.dumps(counts))
    return counts
