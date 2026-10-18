# Watchlist Availability

Checks which films from your **Letterboxd** watchlist are streamable via the TMDB API. Results are grouped into two sections — **Free** (free or free-with-ads)
and **Paid** (subscription or rental) — based on what TMDB reports for each film.

The watchlist is **fetched automatically** from your public Letterboxd page — no manual
export needed. An exported ZIP or CSV is still supported as a fallback.

```console
$ cd watchlist-availability
$ ./run.sh
Fetching Letterboxd watchlist: 100%|██████████| 12/12 [00:03<00:00,  3.6 film/s]
Watchlist fetched from Letterboxd: @yourname (12 films)
Checking streaming availability on TMDB: 100%|██████████| 12/12 [00:08<00:00,  1.45 film/s]

## Paid

|          Title |   Year |  Netflix  |  Canal+  |
|---------------:|-------:|:---------:|:--------:|
|           Heat |   1995 |     ✓     |    ✓     |
|      Gone Girl |   2014 |     ✓     |          |
| Ocean's Eleven |   2001 |           |    ✓     |

---
Netflix: 2 

Canal+: 2

Results saved: /Users/you/Downloads/watchlist_2026-06-06.md
```

---

## Requirements

- Python 3.11+ (uses `tomllib` from the stdlib)
- A free [TMDB](https://www.themoviedb.org/) account for an API key
- A Letterboxd username whose **watchlist is public** (or, failing that, an exported file)


## Installation

```bash
git clone https://github.com/CorbeusUltra/watchlist-availability.git
cd watchlist-availability
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```


## Configuration

1. Copy the `.env.example` file:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env`:
   ```
   TMDB_API_KEY=your_key_here
   LETTERBOXD_USERNAME=your_username
   COUNTRY=FR
   ```
   - Get a free TMDB key at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api).
   - `COUNTRY` is the ISO 3166-1 alpha-2 code (e.g. `FR`, `US`, `GB`) — it must match a section
     in `platforms.toml`.


## Getting the watchlist

**Automatic (recommended).** Set `LETTERBOXD_USERNAME` in `.env`. The script reads your
public watchlist directly (`letterboxd.com/<username>/watchlist/`), page by page, with a
**progress bar**. No manual download. Your watchlist must be **public**.

**Fallback — ZIP or CSV.** If scraping fails (private watchlist, outage) or
`LETTERBOXD_USERNAME` is empty, the script falls back to an exported file:

1. Sign in to [letterboxd.com](https://letterboxd.com) and go to:

       https://letterboxd.com/data/export

2. Drop the downloaded **ZIP** (or the extracted `watchlist.csv`) into `~/Downloads`.
3. Press **Enter** in the terminal — the script extracts `watchlist.csv` from the ZIP
   automatically and deletes the ZIP. No manual unzipping needed.

The script also auto-detects `watchlist*.csv` files (both `watchlist.csv` and
`watchlist-2024-06-01.csv` are accepted).

**What happens on failure?** If scraping fails *and* nothing is found in `Downloads`, the
script **does not crash**: it prints a one-step guide (copy-paste link), then **waits for
you to press Enter**. Press `Ctrl+C` to cancel.


## Saved result

On every run, a dated Markdown file is written to `Downloads`
(e.g. `watchlist_2026-06-06.md`) so you can keep the result and avoid re-running it too often.


## Usage

The canonical entry point is **`run.sh`**. Make sure you are **in the project folder**
first, then run it:

```bash
cd ~/path_to_project_folder
./run.sh
```

## Web app

Start the local web app to choose the streaming providers in the browser:

```bash
./run_web.sh
```

Unter Windows PowerShell:

```powershell
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). On the initial page load, the app
collects the availability data for all known providers once. Provider selection,
film search, Free/Paid, and year filters then only change the visible cards in the
browser. The scan runs in the background with a progress bar, and films appear as
soon as they are checked. Amazon Channels are grouped in a collapsible section.
The web app also supports country switching, cached repeat scans, one active scan at
a time, cancellation and retry, saved provider preferences, Any/All matching, sorting, statistics, film
details, and JSON/CSV export.
When rescanning, the current results stay visible until the new scan completes. You
can optionally grey out films reported as unavailable during that rescan.
The most recent successful result is restored immediately after a page reload while
the next scan runs. Completed results are written atomically, and a finished rescan
reports how many films became newly available or unavailable.
The availability filter can show available films only, unavailable films only, or
both. Completed rescans also list provider additions and removals on affected film
cards and in the expandable scan summary.
Inactive scans expire after 30 minutes so a stale background job cannot block the
single-scan guard forever. Browser polling backs off when no progress is reported,
and individual lookup failures are recorded while the rest of the watchlist
continues scanning.
The app uses the same Letterboxd fallback and TMDB logic as the CLI. The existing
`run.sh` command remains available for terminal output.

The web UI uses locally served, pinned Tabler Core assets with the existing
Bootstrap-compatible component runtime. The custom theme and icon font are stored
under `static/`, so the Docker deployment does not depend on a CDN for its UI.
The frontend is split into Jinja partials under `templates/partials/`. Its browser
behavior is loaded through the native ES module entry point
`static/js/app.js`, with small `api.js`, `state.js`, `ui.js`, `filters.js`, and
`rendering.js` modules keeping
request handling, scan state, and presentation helpers separate. Template-only
configuration is passed through `window.WATCHLIST_CONFIG`, so the JavaScript
modules remain static and cacheable.
Scan feedback and favorite helpers are also isolated in `scans.js` and
`favorites.js`.
Film cards are keyboard-accessible and open a unified details popout when clicked.
The popout provides TMDB, trailer, and Letterboxd search actions. Provider filters
and result cards remain side by side on larger screens, while the page uses a
single document scroll instead of a nested provider scrollbar.
The header also provides a persisted Desktop layout toggle for narrow browser
windows or embedded previews. Offer-type badges, including their Tabler icons,
are shown both on cards and in the film details popout.
Each provider label also shows the number of unique available films for that
provider. A film with multiple offer types at one provider is counted once;
unavailable films are excluded. The provider panel is the primary filter: the
Filters button opens it on narrow screens, and the panel explains the Any/All
matching modes. Use **Reset defaults** to restore the providers enabled in the
country configuration after using Clear or a shared URL with a different
selection. Additional filters support trailers, posters, availability changes,
and minimum provider counts. Filter selections, provider selections, sorting,
and the favorites view are synchronized into the URL so filtered views can be
shared and restored after reload.

For Docker or Unraid, the included `Dockerfile` runs Gunicorn with one worker and
stores runtime data below `/data`. The included `docker-compose.yml` maps that
directory to `./data`; on Unraid, map it to a persistent appdata directory.
`WATCHLIST_DATA_DIR`, `WATCHLIST_CACHE_PATH`, `WATCHLIST_LATEST_PATH`, and
`WATCHLIST_FAVORITES_DB` can be overridden when separate persistent paths are
preferred.

`run.sh` activates the project's virtualenv and launches the script — no need to activate
`.venv` manually.


## How availability types are determined

There are just two sections, detected **automatically, per film**, from TMDB's real
monetization for that film on each provider (data sourced from JustWatch):

| Section | A ✓ appears when TMDB lists the film on the provider as… |
|---|---|
| **Free** | `free` or `ads` (watchable at no cost, possibly with ads) |
| **Paid** | `flatrate` (subscription) or `rent` (rental) |

The same provider can land in either section depending on the film, and a film can appear in
**both** at once — e.g. M6+ offering a film free-with-ads *and* by subscription puts it under
Free **and** Paid. The `buy` category (permanent purchase) is always excluded.

> **Note:** TMDB does not expose expiry dates (the data comes from JustWatch's private API).


## Customising the platforms

`platforms.toml` only chooses **which** platforms to check (`true`/`false`) — it does **not**
decide their section (that comes from TMDB, per film). The country is matched by the `COUNTRY`
setting in `.env`; each provider is a flat `true`/`false` toggle, grouped by comments for
readability only:

```toml
[FR]
# Typically free / ad-supported
Arte          = true
Molotov       = false
# Typically paid — subscription or rental
Netflix       = true
"Canal+"      = true
"TF1+"        = true
"M6+"         = false
"Canal VOD"   = false
"Google Play" = false

[US]
Netflix       = true
"Prime Video" = true
"Disney+"     = true
Hulu          = false
```

Provider names must match TMDB's own naming (verified against
`GET /watch/providers/movie?watch_region=<COUNTRY>`). To add a service not listed, extend
`_ALL_PROVIDERS` in `watchlist_availability.py`, then add it to the country section in
`platforms.toml`.


## Running the tests

```bash
.venv/bin/python -m pytest tests/ -v
```

The tests are fully mocked — no real API key required.


## Project structure

```
watchlist-availability/
├── watchlist_availability.py   # Compatibility facade and CLI entry point
├── watchlist_app/
│   ├── cli.py                   # Command-line orchestration
│   ├── rendering.py             # Terminal, Markdown, and HTML output
│   ├── config.py               # Environment and filesystem configuration
│   ├── providers.py            # Provider definitions and TOML loading
│   ├── letterboxd.py           # Letterboxd, CSV, and ZIP input loading
│   ├── tmdb.py                 # TMDB API access and metadata caches
│   └── results.py              # Availability result construction
├── web/
│   ├── routes.py                # Flask endpoint registration
│   ├── cache.py                # JSON scan-result cache
│   ├── favorites.py            # SQLite favorites persistence
│   ├── scans.py                # Background scan coordination
│   └── serialization.py        # Web API result/stat conversion
├── platforms.toml              # Streaming services selection (per country)
├── run.sh                      # Entry point (venv + script)
├── tests/
│   └── test_watchlist.py       # pytest suite (fully mocked)
├── .env.example                # Configuration template
├── .gitignore
├── requirements.txt
└── README.md
```


## Acknowledgements

Developed with the help of [Claude](https://claude.com/claude-code) (Anthropic).


## License

MIT
