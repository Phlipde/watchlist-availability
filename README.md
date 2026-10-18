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
git clone [https://github.com/CorbeusUltra/watchlist-availability.git](https://github.com/CorbeusUltra/watchlist-availability.git)
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


* **TMDB Key:** Obtain a free API key at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api).
* **Country:** Set your ISO 3166-1 alpha-2 code (e.g., `FR`, `US`, `DE`). This must match a defined section in `platforms.toml`.



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

*A dated Markdown report (e.g., `watchlist_2026-06-06.md`) is saved to your `Downloads` folder upon completion.*

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

* **Progressive Scans & Caching:** Scans execute in the background with progressive card loading. The app caches results locally and restores previous state on reload.
* **Filtering & Search:** Dynamic filtering by Provider, Free/Paid offer types, release year, trailer availability, poster availability, and minimum provider counts.
* **Any / All Provider Modes:** Toggle between showing films available on *any* selected service vs. *all* selected services.
* **Delta Tracking:** Rescans highlight provider additions and removals on film cards and summary panels.
* **Favorites & Deep Links:** Persistent SQLite favorites, detailed modal popouts (trailers, TMDB links, Letterboxd search), and URL-synced search filter states.
* **Bundled Assets:** Native Tabler Core UI components hosted under `static/` with zero CDN dependencies.

---

### 3. Docker & Self-Hosting (Unraid)

Deploy the application using the included Docker configuration:

```bash
docker-compose up -d

```

#### Persistent Path Environment Variables

Data is stored inside `/data` in the container. Map this directory to an appdata folder on host environments (like Unraid):

| Variable | Default Path | Purpose |
| --- | --- | --- |
| `WATCHLIST_DATA_DIR` | App root directory | Base directory for runtime databases and caches |
| `WATCHLIST_CACHE_PATH` | `<DATA_DIR>/.watchlist_cache.json` | Persistent TMDB lookup cache |
| `WATCHLIST_LATEST_PATH` | `<DATA_DIR>/.watchlist_latest.json` | State of the most recent completed scan |
| `WATCHLIST_FAVORITES_DB` | `<DATA_DIR>/.watchlist_favorites.sqlite3` | SQLite database storing favorited movies |

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

> **Note:** Provider names must match TMDB's exact regional provider names (`GET /watch/providers/movie?watch_region=<COUNTRY>`).

---

## Running Tests

Execute the automated `pytest` test suite:

```bash
# macOS / Linux
.venv/bin/python -m pytest tests/ -v

# Windows (PowerShell)
.venv\Scripts\python.exe -m pytest tests\ -v

```

*All API calls and network requests in the test suite are fully mocked.*

---

## Project Structure

```text
watchlist-availability/
├── watchlist_availability.py   # Compatibility facade and CLI entry point
├── app.py                      # Flask web application entry point
├── watchlist_app/              # Core application logic & ingestion
│   ├── cli.py                  # CLI orchestration
│   ├── config.py               # Path and environment settings
│   ├── letterboxd.py           # Web scraping, CSV, and ZIP loading
│   ├── providers.py            # TOML provider definition loader
│   ├── rendering.py            # Console, Markdown, and HTML formatters
│   ├── results.py              # Streaming availability builder
│   └── tmdb.py                 # TMDB API access and caching
├── web/                        # Web app modules
│   ├── cache.py                # JSON scan cache management
│   ├── favorites.py            # SQLite favorites database
│   ├── routes.py               # Flask endpoint definitions
│   ├── scans.py                # Background scan coordination
│   └── serialization.py        # Web API response converters
├── static/                     # Bundled frontend scripts and stylesheets
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

[MIT](https://www.google.com/search?q=LICENSE)

```

```