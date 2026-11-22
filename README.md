# Watchlist Availability
> Still under development, mostly vibecoded :)
Automatically cross-references your **Letterboxd** watchlist with streaming provider availability via the **TMDB API** (data powered by JustWatch). Results are cleanly organized into **Free** (free or ad-supported) and **Paid** (subscription or rental) categories.

The script fetches your public Letterboxd watchlist page directly—no manual export required. If scraping is unavailable, local CSV or ZIP exports are supported as a fallback.

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

* **Python 3.11+** (uses standard library `tomllib`)
* A free [TMDB Account & API Key](https://www.themoviedb.org/)
* A Letterboxd account with a **public watchlist** (or an exported ZIP/CSV file)

---

## Installation

```bash
git clone https://github.com/CorbeusUltra/watchlist-availability.git
cd watchlist-availability
python3 -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

```

---

## Configuration

1. Copy the example environment file:
```bash
cp .env.example .env

```


2. Edit `.env` with your credentials and region:
```ini
TMDB_API_KEY=your_key_here
LETTERBOXD_USERNAME=your_username
COUNTRY=DE

```


* **TMDB Key:** Obtain a free API key at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api). The key stays in the environment and is never stored in the database or a backup.
* **Country:** Set your ISO 3166-1 alpha-2 code (e.g., `FR`, `US`, `DE`).
* **Start values only:** `LETTERBOXD_USERNAME`, `COUNTRY` and `platforms.toml` are only the start values. Once you save the **Settings** page of the web app (`/settings`), the saved values win, for the web app and the command line alike.



---

## Fetching the Watchlist

* **Automatic (Recommended):** Set `LETTERBOXD_USERNAME` in `.env`. The application reads your public watchlist directly (`letterboxd.com/<username>/watchlist/`).
* **Fallback (ZIP or CSV):** If `LETTERBOXD_USERNAME` is empty or scraping fails, place your exported `watchlist.csv` or `watchlist.zip` (from [letterboxd.com/data/export](https://letterboxd.com/data/export)) into `~/Downloads`. The script auto-detects `watchlist*.csv` and extracts ZIP files automatically.
* **Failure Handling:** If scraping fails and no local export is detected, the script displays a direct download link and waits for manual input without crashing.

---

## Usage

### 1. Terminal Interface (CLI)

Execute `run.sh` inside the project folder. It activates the virtual environment automatically:

```bash
cd watchlist-availability
./run.sh

```

*A dated HTML report (e.g., `watchlist_2026-06-06.html`) is saved to your `Downloads` folder upon completion. The command line uses the same database, settings and scan as the web app.*

---

### 2. Interactive Web Application

Launch the Flask web app to filter, search, and manage your watchlist visually:

```bash
# macOS / Linux
./run_web.sh

# Windows (PowerShell)
python app.py

```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

#### Web Features

* **Tonight (`/`):** The start page: rows of films on your ticked services (new in the last 14 days, free, one row per subscription), quick filters, "Pick for me" (key `r`) and what recently left your services and where it runs now.
* **Watchlist (`/watchlist`):** All films with one filter bar in a single row: search, services, cost (*Available / Free / Subscription / Rent* with counts), genre, ♥ favorites, **Abroad**, **More filters** and sort. Grid, compact and table views, a **Changes** tab with every change of the last 30 days, and a link icon that copies the current view. When the bar does not fit one row, *Year*, *Runtime* and *Rating* move into the *More filters* panel (same controls, shown inline). Old links to `/` with filters redirect here.
* **Film cards:** A card shows the poster with a small heart, the title, the meta line and one row of logo tiles for **your own services** (a small € badge marks a shop that only rents or sells; the words come on hover, focus or a first tap on a phone). A card without any of your services shows its one best way. Hover or long-press the poster for *Compare*, *Not now* and *Grey out*. No prices are shown anywhere: the data source has none.
* **Abroad:** The *Abroad* chip also lists films that your ticked services have in another country but not at home (a VPN is needed). It shows how many films would be added; the card names the country with a flag, and the details list all countries, the nearest and same-language ones first. *More filters → Where* can show only here, here and abroad, or only abroad.
* **Film details:** A side drawer (a bottom sheet on phones) with one main button (the best way to watch), the services grouped by offer, abroad countries, the collection, similar films and links (Letterboxd first, with a direct link, then TMDB, JustWatch and others). `l` opens Letterboxd, `s` greys out, `n` sets aside for 30 days.
* **Keyboard:** The arrow keys move through films in the grid, compact view, table and the Tonight rows; only one film holds the tab stop.
* **Saved views:** *Save view* appears when filters are active; saved views show up as a *Views* menu and as chips on Tonight.
* **Progressive Scans & Caching:** Scans execute in the background with progressive card loading. The app caches results locally and restores previous state on reload.
* **Filtering & Search:** Services, cost, genres (alt-click excludes), runtime, year, rating (Letterboxd or TMDB), age rating, original language, country, keyword, trailer, number of services and availability changes. Everything that is set shows as a chip; each dropdown in *More filters* has a small × and the panel has *Reset*.
* **Any / All Provider Modes:** Toggle between showing films available on *any* selected service vs. *all* selected services.
* **Change History:** Every scan is compared with the earlier ones. "New on …" is stored with its date; "gone" needs two scans in a row without the service, so a one-day TMDB hiccup is not reported. Changes are kept for 30 days.
* **Export and import:** Under *Settings → Data*: films and favorites as CSV or JSON, and a favorites import with a preview ("12 found · 3 already set · 9 new") before anything is changed.
* **Grey out:** A film you do not want to see any more can be greyed out; *Settings → Data* lists the greyed-out films and resets them. The app never writes to Letterboxd: log or rate a film there, and it leaves the watchlist at the next sync.
* **Settings (`/settings`):** Letterboxd username, country, the automatic scan interval, and backup download / restore (settings, favorites, change history, last scan per country). *My services* (`/settings/services`) is the list of services you pay for or use for free; ticking saves at once, with Undo.
* **Subscriptions (`/subscriptions`):** One table of your paid services sorted by what cancelling would cost you (films only there, hours), prices and renewal dates that save when you leave the field, totals per month and year, your free services as a block, and a hint what to cancel or book next.
* **Automatic Scans:** Optionally every 6, 12, 24 or 48 hours or once a week, while the app runs. A scan interrupted by a restart is started again.
* **Stats (`/stats`):** Numbers for the last scan: films per service and offer type, what each subscription adds, genres, decades, runtime, ratings, languages, countries, people, series, keywords, changes per week and the films waiting longest.
* **Settings → Data & status (`/settings/data`, formerly `/status`):** Last and next scan, and the recent scan runs with duration, failed lookups and the number of TMDB requests.
* **Settings → Unmatched films (`/settings/matches`, formerly `/matches`):** Films matched by a TMDB title search, not found, or with a release year more than a year apart are listed for checking. Search TMDB or paste a TMDB link to correct a match; corrections are kept for good and are part of the backup.
* **Provider list from TMDB:** Once a week, a scan loads every streaming service TMDB knows in your country. New services appear in the filters and in the settings without a code change.
* **Favorites & Deep Links:** Persistent SQLite favorites, detailed modal popouts (trailers, TMDB links, Letterboxd search), and URL-synced search filter states.
* **Bundled Assets:** Native Tabler Core UI components hosted under `static/` with zero CDN dependencies.

---

### 3. Docker & Self-Hosting (Unraid)

Deploy the application using the included Docker configuration:

```bash
cp .env.example .env   # then put TMDB_API_KEY and LETTERBOXD_USERNAME into it
docker compose up -d --build
```

The container starts as root only to set up `/data`, then runs as `PUID`/`PGID` (default 99/100, Unraid's *nobody*/*users*). `/health` checks the database and the schedule; Docker uses it as the healthcheck. A backup of settings, favorites, history and the last scan is written once a day to `/data/backups/` (the newest 7 stay). To restore one, use *Settings → Restore backup* with the file.

**Unraid:** build the image on the server (`docker build -t watchlist-availability .` from a clone of this repository, or add the repository as a build context), then add `unraid-template.xml` under *Docker → Add Container → Template*. Map `/data` to `/mnt/user/appdata/watchlist-availability`. Update: pull the repository, build again, recreate the container; the data stays in `/data`. GitHub builds and starts the image on every push (`.github/workflows/docker.yml`), so a broken image shows up there.

**There is no login.** Run it in the home network only, or behind a reverse proxy that asks for a login; the proxy also gives you HTTPS, which installing the app as a PWA needs.

#### Persistent Path Environment Variables

Data is stored inside `/data` in the container. Map this directory to an appdata folder on host environments (like Unraid):

| Variable | Default Path | Purpose |
| --- | --- | --- |
| `WATCHLIST_DATA_DIR` | App root directory | Base directory for the database |
| `WATCHLIST_DB` | `<DATA_DIR>/.watchlist.sqlite3` | One SQLite database for film data, offers per country, scans, favorites and settings |
| `WATCHLIST_SCAN_WORKERS` | `6` | Films looked up at the same time |
| `WATCHLIST_DISABLE_SCHEDULER` | not set | Set to `1` to switch off automatic scans in this process |
| `WATCHLIST_DEV` | not set | Set to `1` to open `/dev/ui`, a page with every button, menu and chip in every state (also open in debug mode) |
| `WATCHLIST_TRUSTED_HOSTS` | not set | Host names the app is reached under behind a reverse proxy that changes the `Host` header, comma-separated (e.g. `watch.example.org`) |

#### Install and offline

The app is a PWA: over https (or on localhost) your browser offers to install it, and it opens offline with the data it saved last ("Offline: showing the data from …"). Behind a reverse proxy with https this works in the home network too. `GET /calendar.ics` is a calendar feed of the renewal dates you enter on the subscriptions page.

#### Notifications and Home Assistant

*Settings → Notifications* sends messages to ntfy, Gotify or a webhook: a favorite left your services, a renewal date is 3 and 1 day away, a Friday summary, optionally every new film. At most one message a day, none between 22:00 and 08:00. `GET /api/sensors` returns numbers for a Home Assistant REST sensor (`new_on_my_services`, `gone_from_my_services`, `next_subscription_deadline`, `watchlist_coverage`, `films_available`).

Flag images in `static/flags/` come from the npm package [flag-icons](https://github.com/lipis/flag-icons) (MIT, see `static/flags/LICENSE`).

#### Start-page tile, RSS and the small API

- `GET /tile`: a small page for Homepage or Homarr (iframe): new this week on your services and a pick of the day (a well-rated film on your services that is not marked watched or "not now"; the same all day).
- `GET /feed.xml`: RSS feed of films that became watchable on your services in the last 30 days.
- `GET /api/latest` the last scan, `GET /api/sensors` numbers for Home Assistant, `GET /calendar.ics` renewal dates, `GET /api/flags` greyed-out and "not now" marks, `GET /api/abroad` films your services have in other countries, `GET /api/greyouts` and `POST /api/greyouts/reset`, `GET /api/backup` a full backup, `GET /health` for a container check. Writing calls (`PUT /api/settings`, `PUT /api/flags/<key>`) refuse requests from other sites.

#### Security

The app has no login; run it only in your home network or behind a reverse proxy with authentication. Changing requests (scan, settings, favorites, backup restore, match corrections) are refused when another web site makes the browser send them, so a page you visit cannot change your data. Tools without a browser (command line, `curl`, Home Assistant) are not affected. A restored backup is checked field by field; entries that do not fit are skipped and counted.

On the first start, data from older versions (`.watchlist_favorites.sqlite3`, `.watchlist_latest.json`, `.watchlist_films.sqlite3`) is copied into the database once. The old files are left untouched and can be deleted afterwards. Favorites saved under `Title|Year` move to the film's TMDB id after the next scan.

---

## Provider Classification Logic

Monetization categories are mapped dynamically per film based on TMDB / JustWatch data:

| Section | A checkmark (✓) appears when TMDB reports the offer as… |
| --- | --- |
| **Free** | `free` or `ads` (free streaming, ad-supported streaming) |
| **Paid** | `flatrate` (subscription) or `rent` (rental purchase) |

* **Note:** Permanent purchases (`buy`) are excluded. If a service offers a film under both free-with-ads and subscription models, it appears in both sections.

---

## Customizing Platforms (`platforms.toml`)

`platforms.toml` configures which providers to check for your active region:

```toml
[FR]
# Free / Ad-supported
Arte         = true
Molotov      = false

# Paid / Subscription
Netflix      = true
"Canal+"     = true
"TF1+"       = true

[US]
Netflix      = true
"Prime Video" = true
"Disney+"    = true
Hulu         = false

```

> **Note:** `platforms.toml` only knows the built-in provider names (`watchlist_app/providers.py`). Every other service TMDB lists for your country can be chosen on the Settings page once the first scan has loaded the provider list.

---

## Running Tests

Install the development tools once, then run the checks:

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium   # only for the browser tests; an installed Chrome or Edge also works

pytest -q                # unit tests
pytest -q -m browser     # end-to-end tests in a real browser (Playwright)
node --test tests/js/    # filter logic of the page
ruff check . && ruff format --check .
mypy                     # type check
```

*All API calls and network requests in the test suite are fully mocked.* There is one test file per module. The browser tests start the app on a free local port with an empty database and fixed answers for Letterboxd and TMDB. GitHub Actions runs all of these on every push.

---

## Project Structure

```text
watchlist-availability/
├── watchlist_availability.py   # CLI entry point
├── app.py                      # Flask web application entry point
├── watchlist_app/              # Core application logic & ingestion
│   ├── cli.py                  # CLI orchestration
│   ├── config.py               # Path and environment settings
│   ├── legacy_import.py        # One-time import of files from older versions
│   ├── history.py              # Changes between scans
│   ├── letterboxd.py           # Web scraping, CSV, and ZIP loading
│   ├── lookup.py               # Cached film lookup (Letterboxd id, then TMDB)
│   ├── matches.py              # Uncertain title matches and manual corrections
│   ├── models.py               # Film and WatchlistEntry data classes
│   ├── providers.py            # Provider catalogue, groups and platforms.toml
│   ├── rendering.py            # Console, Markdown, and HTML formatters
│   ├── results.py              # Parallel availability check
│   ├── scan_service.py         # One scan for page, schedule and CLI; job state
│   ├── scheduler.py            # Automatic scans
│   ├── settings.py             # Settings from the database, .env as start values
│   ├── store.py                # Shared SQLite database
│   ├── validation.py           # Checks for restored backups and other outside data
│   └── tmdb.py                 # TMDB API access
├── web/                        # Web app modules
│   └── routes.py               # Pages and API endpoints
├── static/                     # Bundled frontend (plain ES modules, no build step), flags
│   └── js/                     # filtering, filterbar, bestway (card and drawer), drawer, abroad, gridnav...
├── templates/                  # Jinja2 templates and UI partials
├── platforms.toml              # Regional streaming provider toggles
├── run.sh                      # CLI launch script
├── run_web.sh                  # Web server launch script
├── Dockerfile                  # Production container build definition
├── docker-compose.yml          # Docker Compose orchestration
└── tests/                      # Automated unit test suite

```

---

## Acknowledgements

Developed with the assistance of [Claude Code](https://claude.com/claude-code) (Anthropic) and [GitHub Copilot](https://github.com/features/copilot) (GitHub / Microsoft).

---

## License

[MIT](LICENSE)

```

```