# Copilot instructions

## Repository map

- `watchlist_availability.py` is the compatibility facade and CLI entry point.
- `watchlist_app/cli.py` contains command-line orchestration.
- `watchlist_app/rendering.py` contains terminal, Markdown, and HTML output.
- `watchlist_app/config.py` contains environment and filesystem configuration.
- `watchlist_app/providers.py` contains provider definitions and TOML loading.
- `watchlist_app/letterboxd.py` contains Letterboxd, CSV, and ZIP input loading.
- `watchlist_app/tmdb.py` contains TMDB API access and metadata caches.
- `watchlist_app/results.py` contains availability result construction.
- `app.py` contains Flask route registration and web startup.
- `web/cache.py` contains the JSON scan-result cache.
- `web/favorites.py` contains SQLite favorites persistence.
- `web/scans.py` contains background scan coordination.
- `web/serialization.py` contains web API result and statistics conversion.
- `web/routes.py` contains Flask endpoint registration.
- `templates/`, `manifest.webmanifest`, and `sw.js` contain the web UI and
  browser shell.
- `platforms.toml` selects providers by country; it does not determine whether a
  result is free or paid.
- `tests/test_watchlist.py` contains the mocked pytest suite for the core
  functionality.
- `README.md` documents setup and user-facing behavior.

## Context discipline

- Start with targeted searches and the smallest relevant file or symbol range.
- For CLI work, prefer the owning `watchlist_app` module and the related test class.
- For web work, prefer `web/routes.py`, `web/scans.py`, the relevant template, and focused tests.
- Do not load the entire repository, test suite, or main modules unless the task
  requires cross-cutting changes.
- Ignore `.venv/`, `__pycache__/`, `.pytest_cache/`, local cache files, the
  favorites database, and `.env` unless the task explicitly concerns them.
- Treat TMDB API usage and Copilot prompt-token usage as separate concerns.

## Change and validation rules

- Preserve unrelated staged and unstaged worktree changes.
- Follow existing Python style and keep changes surgical.
- Add or update focused tests for behavior changes.
- On Windows, run the smallest applicable command with
  `.venv\Scripts\python.exe -m pytest`.
- For the full suite, use:

  ```powershell
  .venv\Scripts\python.exe -m pytest tests\ -v
  ```

- Summarize changed files, validation performed, and any remaining issue
  concisely.
