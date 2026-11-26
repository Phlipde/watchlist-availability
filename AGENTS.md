# Agent notes

## Project: watchlist-availability

Flask app (`app.py`, `web/routes.py`, `watchlist_app/`) with SQLite, Tabler/Bootstrap 5.3 and plain ES modules in `static/js/` (no build step). Plan and progress live in `PLAN.md` (German); design reviews in `reviews/`.

### Commands

- `.venv/Scripts/python.exe -m pytest -q` -- Python tests (browser tests are deselected by default)
- `.venv/Scripts/python.exe -m pytest -q -m browser tests/browser` -- Playwright browser tests against a fake TMDB/Letterboxd
- `node --test tests/js/*.mjs` -- tests for the pure JS modules (`filtering.js`, `filters.js`, `rendering.js`)
- `.venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format --check . && .venv/Scripts/python.exe -m mypy .` -- lint, format, types
- Preview with real data: `.claude/launch.json` config `web-copy` (port 5001, `WATCHLIST_DATA_DIR` = a copy of the data, `WATCHLIST_DISABLE_SCHEDULER=1`)

### Gotchas

- `CRLF line endings` -- most files use CRLF; scripted edits must match `\r\n` or the replace finds nothing
- `Stale templates in the preview` -- Flask caches templates; restart the preview server after template edits, or the old HTML loads the new JS and throws
- `Asset version` -- bump `v=` in `templates/*.html` (`url_for(..., v='YYYYMMDD-n')`) after CSS/JS changes, else browsers keep the old files
- `.btn beats display:none` -- a later `.btn { display: inline-flex }` overrides `.x { display: none }`; hide buttons with a more specific selector (`.header-buttons .provider-toggle`)
- `Disabled button loses focus` -- remember `document.activeElement` before `button.disabled = true` if focus must be restored
- `Bootstrap modal and Escape` -- Escape only works after the modal has faded in; tests wait until focus is inside the dialog
- `Bootstrap modal focus` -- Bootstrap does not return focus; use `openModal(id, opener)` in `app.js`, which also finds a redrawn card's button by `data-key`
- `ruff and ruflo` -- `pyproject.toml` excludes `.claude`, `.agents`, `.claude-flow`, else ruff formats code samples in the ruflo agent docs
- `Old saved scans` -- new film fields (`collection`, `watchlist_position`) are empty until the next scan refetches TMDB data

### Patterns

- Filters -- pure logic in `filtering.js`/`filters.js` (tested with a fake `doc`), DOM wiring in `app.js`; `FILTER_CONTROLS` drives chips, "Reset filters" and the "More filters (n active)" counter
- Visible filter row stays at five (search, availability, genre, runtime, rating); every new filter goes under "More filters"
- New film field -- add it in `models.Film`, `tmdb._details_from_movie`, `results.make_film` and `validation.clean_film` (backups and the client go through validation)
- Wording -- "service", not "provider", in the UI; one `.pill` class with tones ok/warn/danger/neutral; amber only for controls
- Font sizes -- `--fs-small/.75rem`, `--fs-body/.875rem`, `--fs-text/1rem`, `--fs-heading/2rem`; nothing under 12px

### Decisions

- "Where to watch" uses `tmdb_url + /watch?locale=XX` instead of storing TMDB's `link` field (same page, no DB/backup change)
- Subscriptions and prices live on `/subscriptions`; `PUT /api/settings` takes `subscriptions_country` so another country is edited without switching the app's country
- Letterboxd CSV is sorted by its `Date` column newest first, to match the website order (assumed newest first, not verified)
- 44px touch targets only under `pointer: coarse`, so the desktop stays dense

## Session Log

- 2026-11-16: [Decisions] Stages 9e-9j and most of 10 done (see PLAN.md); "Ähnliche Filme" left open because it needs extra TMDB requests per suggestion
- 2026-11-16: [Gotchas] Filter bugs found by comparing each filter's count against counts computed from `/api/latest` data; repeat this method after filter changes
- 2026-11-22: [Decisions] Fix plan `docs/PLAN-fehler-und-features.md` (A1-A6, then B); A1-A5 done, A6 open. Cards show all own services (max 4) with a corner type icon; the abroad (VPN) block alone has flag badges and type icons on its logos. Drawer "Other services" stays a compact logo row (tap shows the name), no provider list, no report link
- 2026-11-22: [Decisions] (superseded 2026-11-25) "Grey out" is now "Hide" (archive icon, mark "Hidden"); "Not now" stays 30 days. Stored values unchanged: `watched` / `not_now`. Settings -> Data lists hidden films with Unhide
- 2026-11-22: [Gotchas] Scripted edits: mixed CRLF/LF files, multi-line `old` strings fail; Python heredoc via stdin gives mojibake for non-ASCII (use script files); ruff E501 limit 110
- 2026-11-26: [Gotchas] Flask caches templates: after a template edit an old page links only the first CSS chunk and looks broken; restart the server, the CSS is fine
- 2026-11-26: [Patterns] CSS is six files `static/css/app*.css` linked in cascade order by `partials/styles.html` (one `css_v`); add rules at the end of the right file, never reorder
- 2026-11-26: [Architecture] Split modules re-export the old names: `drawer.js` (film-meta.js, places.js), `scan_service.py` (scan_run.py), `costs.py` (cost_settings.py), `store.py` (store_*.py mixins), `web/routes.py` (common, pages, api_scan, api_data, feeds). Tests patch module objects (`routes.time`, `tmdb.x`), so new code calls through the module
- 2026-11-26: [Decisions] No built-in service lists: "mostly free", rental shops and service groups come from scan offers + the TMDB catalog per country; `_ALIASES` keeps short display names ("Prime Video"); a new country starts with no services
- 2026-11-26: [Decisions] Any ISO country (`config.valid_country`: two letters with a flag file); list from TMDB `/watch/providers/regions` stored per scan; a country change saves the country and always starts a scan (fresh same-day scans are reused)
- 2026-11-26: [Decisions] One base set for all counts (`watchlist_app/base.py`, `baseCounts` in filtering.js): watchlist = released matched films; coming soon and to-check counted apart; coverage uses service groups like the stats page
- 2026-11-26: [Gotchas] Tests: browser tests are split by area under `tests/browser/` (fixtures in conftest.py, helpers.py); web tests live in package `tests/web/`; the regions call is stubbed in `tests/conftest.py`
