"""SQLite persistence for saved films."""

import sqlite3
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS favorites ("
        "movie_key TEXT PRIMARY KEY, title TEXT NOT NULL, year INTEGER, "
        "poster_path TEXT, tmdb_url TEXT, trailer_url TEXT, rating REAL)"
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(favorites)")}
    for name, definition in {
        "status": "TEXT NOT NULL DEFAULT 'plan'",
        "notes": "TEXT NOT NULL DEFAULT ''",
        "added_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    }.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE favorites ADD COLUMN {name} {definition}")
    connection.commit()
    return connection


def rows(path: Path) -> list[tuple]:
    with connect(path) as connection:
        return connection.execute(
            "SELECT movie_key, title, year, poster_path, tmdb_url, trailer_url, "
            "rating, status, notes, added_at FROM favorites ORDER BY title"
        ).fetchall()
