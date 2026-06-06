"""
watchlist_availability.py

Checks which films from your Letterboxd watchlist are available to stream
via the TMDB API, grouped into two sections: Free and Paid.

The watchlist is fetched automatically from your public Letterboxd page
(via LETTERBOXD_USERNAME in .env). Otherwise, an exported ZIP or CSV is used
as a fallback.

Usage: python watchlist_availability.py
"""

import os
import re
import time
import tomllib
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tabulate import tabulate
from tqdm import tqdm

# =========================
# CONFIGURATION
# =========================

load_dotenv()

TMDB_API_KEY: str | None = os.getenv("TMDB_API_KEY")
LETTERBOXD_USERNAME: str | None = os.getenv("LETTERBOXD_USERNAME")
COUNTRY: str = os.getenv("COUNTRY", "FR")

DOWNLOADS_DIR = Path.home() / "Downloads"
PLATFORMS_TOML = Path(__file__).parent / "platforms.toml"

# Letterboxd scraping: 28 posters per page, grid rendered server-side.
FILMS_PER_PAGE = 28
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
# data-item-name is "Title (YYYY)"; the parenthesised year is optional.
_TITLE_YEAR_RE = re.compile(r"^(.*?)\s*\((\d{4})\)\s*$")

# Display name -> exact TMDB provider_name. Matching is by exact provider_name;
# these strings must match TMDB's own naming. Verified against
# GET /watch/providers/movie?watch_region=FR (and US/GB for international ones).
# Docs: https://developer.themoviedb.org/reference/watch-providers-movie-list
#
# The display section (Free / Paid) is NOT set here, nor in
# platforms.toml — it is detected per film from TMDB's real monetization. This
# mapping only links a display name to its exact TMDB provider_name. The comment
# groupings below are the *typical* nature of each provider, for readability only.
_ALL_PROVIDERS: dict[str, str] = {
    # --- Typically free / ad-supported ---
    "Arte":         "Arte",
    "Molotov":      "Molotov TV",
    "Pluto TV":     "Pluto TV",
    "Plex":         "Plex",
    # --- Typically subscription (flatrate) ---
    "Netflix":      "Netflix",
    "Canal+":       "Canal+",
    "TF1+":         "TF1+",
    "M6+":          "M6+",
    "Prime Video":  "Amazon Prime Video",
    "Disney+":      "Disney Plus",
    "Apple TV+":    "Apple TV",          # TMDB uses "Apple TV", not "Apple TV Plus"
    "Paramount+":   "Paramount Plus",
    "HBO Max":      "HBO Max",
    "Crunchyroll":  "Crunchyroll",
    "MUBI":         "MUBI",
    # --- Typically rental / VOD (France, verified against TMDB FR) ---
    "Canal VOD":    "Canal VOD",
    "Google Play":  "Google Play Movies",
    "Amazon VOD":   "Amazon Video",      # pay-per-rental, distinct from Prime Video
    "Pathé Home":   "Pathé Home",
    "Rakuten TV":   "Rakuten TV",
    "Orange VOD":   "Orange VOD",
    "YouTube":      "YouTube",
    "Sooner":       "Sooner",
    # --- International (change COUNTRY in .env) ---
    "BBC iPlayer":  "BBC iPlayer",
    "ITVX":         "ITVX",
    "Channel 4":    "Channel 4",
    "Hulu":         "Hulu",
    "Peacock":      "Peacock Premium",
    "Now":          "Now TV",
    "Discovery+":   "Discovery+",
    "Rakuten Viki": "Rakuten Viki",
    # Note: OCS merged into Canal+ (2024), no longer a separate TMDB provider.
    # Note: "france.tv" is not tracked by TMDB for movies (only TV shows).
    # Note: "Amazon Video" (rental) is distinct from "Amazon Prime Video" (subscription).
}


# Display sections, in order, with the TMDB monetization types each one covers.
# A film's section is decided per (film, provider) from TMDB's real monetization,
# NOT from platforms.toml. Only two buckets: Free (no cost) vs Paid (subscription
# or rental). A film available on a provider under both kinds appears in both
# sections (e.g. M6+ as ads + flatrate → Free AND Paid). "buy" is always excluded.
_SECTION_ORDER: list[tuple[str, frozenset[str]]] = [
    ("Free", frozenset({"free", "ads"})),
    ("Paid", frozenset({"flatrate", "rent"})),
]

# Default selection when platforms.toml is missing or has no section for COUNTRY.
_DEFAULT_ENABLED: frozenset[str] = frozenset(
    {"Arte", "Netflix", "Canal+", "TF1+", "M6+"}
)

MONTHS_EN = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# =========================
# FUNCTIONS
# =========================


class LetterboxdError(Exception):
    """Raised when the watchlist cannot be fetched from Letterboxd."""


def _date_en(d: date) -> str:
    return f"{MONTHS_EN[d.month - 1]} {d.day}, {d.year}"


def _parse_watchlist_page(html: str) -> list[dict]:
    """Extract (title, year) for each film on a Letterboxd watchlist page.

    Each poster exposes its title via the `data-item-name` attribute in the
    "Title (YYYY)" format. The year is optional (films with no known release date).

    Returns:
        List of dicts {'Name': str, 'Year': int | None} in page order.
    """
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("div.poster-grid") or soup
    rows: list[dict] = []

    for poster in container.select("[data-item-slug]"):
        raw = poster.get("data-item-name") or poster.get("data-item-full-display-name") or ""
        title: str = raw
        year: int | None = None

        match = _TITLE_YEAR_RE.match(raw)
        if match:
            title, year = match.group(1), int(match.group(2))

        if not title:
            img = poster.find("img")
            if img and img.get("alt"):
                title = img.get("alt")

        if title:
            rows.append({"Name": title, "Year": year})

    return rows


def _extract_num_entries(html: str) -> int | None:
    """Read the watchlist's total film count from the data-num-entries attribute.

    Returns:
        The total (for a determinate progress bar), or None if absent/unreadable.
    """
    el = BeautifulSoup(html, "html.parser").select_one("[data-num-entries]")
    if el is None:
        return None
    try:
        return int(el["data-num-entries"])
    except (ValueError, TypeError, KeyError):
        return None


def fetch_watchlist_from_letterboxd(
    username: str,
    max_pages: int = 100,
    session: requests.Session | None = None,
    show_progress: bool = True,
) -> pd.DataFrame:
    """Fetch a user's public Letterboxd watchlist by scraping.

    Walks through the `/<username>/watchlist/page/N/` pages until an incomplete
    page (fewer than 28 films) or an empty one. The grid is rendered server-side:
    no browser needed, just a believable User-Agent. A tqdm progress bar tracks
    progress (exact total read from data-num-entries).

    Args:
        username: Letterboxd username (the watchlist must be public).
        max_pages: safeguard against an infinite loop.
        session: reusable requests session (injected for tests).
        show_progress: show the progress bar (can be disabled for tests).

    Returns:
        DataFrame with columns 'Name' and 'Year' (Year may be None), same
        schema as load_watchlist().

    Raises:
        LetterboxdError: username not found (404) or network / HTTP error.
    """
    sess = session or requests.Session()
    headers = {"User-Agent": _USER_AGENT}
    rows: list[dict] = []
    progress: tqdm | None = None

    try:
        for page in range(1, max_pages + 1):
            url = f"https://letterboxd.com/{username}/watchlist/page/{page}/"

            for attempt in range(2):
                try:
                    r = sess.get(url, headers=headers, timeout=10)
                except requests.RequestException as exc:
                    raise LetterboxdError(f"Network error reaching Letterboxd: {exc}") from exc
                if r.status_code == 429 and attempt == 0:
                    time.sleep(2)
                    continue
                break

            if r.status_code == 404:
                raise LetterboxdError(
                    f'Watchlist not found for "{username}" '
                    "(wrong username or private watchlist)."
                )
            if not r.ok:
                raise LetterboxdError(f"Letterboxd returned {r.status_code} for {url}.")

            if progress is None:
                progress = tqdm(
                    total=_extract_num_entries(r.text),
                    desc="Fetching Letterboxd watchlist",
                    unit="film",
                    disable=not show_progress,
                )

            page_rows = _parse_watchlist_page(r.text)
            if not page_rows:
                break
            rows.extend(page_rows)
            progress.update(len(page_rows))
            if len(page_rows) < FILMS_PER_PAGE:
                break
    finally:
        if progress is not None:
            progress.close()

    return pd.DataFrame(rows, columns=["Name", "Year"])


def load_platforms_config(
    country: str = "FR",
    toml_path: Path | None = None,
) -> dict[str, str]:
    """Load platforms.toml and return the enabled platforms for the given country.

    Reads the flat [<country>] section (display_name = true/false) and returns a
    dict mapping display_name -> TMDB provider_name for the enabled, known ones.
    The section does NOT decide where a platform is displayed — that comes from
    TMDB per film. Falls back to the default selection when the file is missing
    or has no section for the requested country.
    """
    path = toml_path or PLATFORMS_TOML

    def _defaults() -> dict[str, str]:
        return {k: v for k, v in _ALL_PROVIDERS.items() if k in _DEFAULT_ENABLED}

    if not path.exists():
        return _defaults()

    with open(path, "rb") as f:
        config = tomllib.load(f)

    section = config.get(country, {})
    if not section:
        return _defaults()

    return {
        display: _ALL_PROVIDERS[display]
        for display, enabled in section.items()
        if enabled and display in _ALL_PROVIDERS
    }


def find_watchlist_csv(downloads_dir: Path | None = None) -> Path:
    """Return the most recent watchlist*.csv file in the Downloads folder.

    Raises:
        FileNotFoundError: if no matching file is found.
    """
    directory = downloads_dir or DOWNLOADS_DIR
    # Accepts 'watchlist.csv' (the Letterboxd export name) and 'watchlist-YYYY-MM-DD.csv'.
    candidates = list(directory.glob("watchlist*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"No 'watchlist*.csv' file found in {directory}.\n"
            "Export your watchlist from letterboxd.com > Settings > Import & Export."
        )
    return max(candidates, key=lambda f: f.stat().st_mtime)


def load_watchlist(csv_path: Path) -> pd.DataFrame:
    """Load and validate the Letterboxd CSV.

    Raises:
        ValueError: if the 'Name' or 'Year' columns are missing.
    """
    df = pd.read_csv(csv_path)
    missing = [col for col in ("Name", "Year") if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing columns in the CSV: {missing}. "
            "Make sure the file comes from Letterboxd."
        )
    return df


def _clean_year(year: int | str | float | None) -> int | None:
    """Normalise a year to int, or None if absent/invalid (NaN, empty, etc.)."""
    if year is None:
        return None
    if not isinstance(year, str) and pd.isna(year):
        return None
    try:
        return int(year)
    except (ValueError, TypeError):
        return None


def get_tmdb_id(
    title: str, year: int | str | float | None, api_key: str | None = None
) -> int | None:
    """Look up a film's TMDB ID by title, refining by year when available.

    Retries once if the API responds 429 (rate limit).

    Returns:
        The TMDB ID, or None if the film is not found / on a network error.
    """
    key = api_key or TMDB_API_KEY
    url = "https://api.themoviedb.org/3/search/movie"
    params: dict = {"api_key": key, "query": title}

    clean_year = _clean_year(year)
    if clean_year is not None:
        params["year"] = clean_year

    for attempt in range(2):
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 429:
                if attempt == 0:
                    time.sleep(2)
                    continue
                return None
            r.raise_for_status()
            data = r.json()
            results = data.get("results", [])
            return results[0]["id"] if results else None
        except requests.RequestException:
            return None

    return None


def get_streaming_platforms(
    tmdb_id: int, country: str = "FR", api_key: str | None = None
) -> dict[str, set[str]]:
    """Return the streaming availability for a film, keyed by provider_name.

    Queries TMDB's watch/providers endpoint (data sourced from JustWatch) and
    returns, for each provider_name, the set of monetization types it offers the
    film under, among free / ads / flatrate / rent. The 'buy' category (permanent
    purchase) is excluded.

    Returns:
        {provider_name: {category, ...}} dict, empty on network error or no data.
    """
    key = api_key or TMDB_API_KEY
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/watch/providers"

    try:
        r = requests.get(url, params={"api_key": key}, timeout=10)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException:
        return {}

    country_data = data.get("results", {}).get(country, {})
    result: dict[str, set[str]] = {}
    for category in ("free", "ads", "flatrate", "rent"):
        for p in country_data.get(category, []):
            result.setdefault(p["provider_name"], set()).add(category)
    return result


def build_results(
    df: pd.DataFrame,
    targets: dict[str, str],
    country: str = "FR",
    api_key: str | None = None,
) -> list[dict]:
    """Walk the DataFrame and return one result dict per available film.

    Makes a single TMDB API call per film. Each platform column holds the SET of
    TMDB monetization types the film is available under on that provider (a subset
    of free / ads / flatrate / rent), or an empty set. Sectioning (Free / Paid)
    is derived from these sets later.

    Returns:
        List of dicts with keys 'Title', 'Year', and one set per platform.
        Only films available on at least one target are included.
    """
    results: list[dict] = []

    for _, row in tqdm(
        df.iterrows(),
        total=len(df),
        desc="Checking streaming availability on TMDB",
        unit="film",
    ):
        title = row["Name"]
        year = row["Year"]

        tmdb_id = get_tmdb_id(title, year, api_key=api_key)
        if tmdb_id is None:
            time.sleep(0.15)
            continue

        providers = get_streaming_platforms(tmdb_id, country=country, api_key=api_key)

        row_data: dict = {"Title": title, "Year": year}
        for display, tmdb_name in targets.items():
            row_data[display] = providers.get(tmdb_name, set())

        if any(row_data[display] for display in targets):
            results.append(row_data)

        time.sleep(0.15)

    return results


def _split_by_section(
    results: list[dict],
    targets: dict[str, str],
) -> list[tuple[str, list[dict], dict[str, str]]]:
    """Split results into sections by each (film, provider)'s real monetization.

    A film is "✓" in a section when TMDB lists it on the provider under one of the
    section's monetization types. The same provider can appear in several sections,
    and a film available under several types appears in each matching section
    (e.g. M6+ as ads + flatrate → Free AND Paid).

    Returns:
        List of (section_label, view_results, view_targets) for non-empty sections.
    """
    sections = []
    for label, mon_set in _SECTION_ORDER:
        # Keep only columns with at least one film matching this section's types.
        active = [
            display for display in targets
            if any(mon_set & r.get(display, set()) for r in results)
        ]
        if not active:
            continue

        view_results = []
        for r in results:
            checks = {n: ("✓" if (mon_set & r.get(n, set())) else "") for n in active}
            if any(checks.values()):
                view_results.append({"Title": r["Title"], "Year": r["Year"], **checks})

        view_targets = {display: targets[display] for display in active}
        sections.append((label, view_results, view_targets))

    return sections


def _sort_results(results: list[dict], targets: dict[str, str]) -> pd.DataFrame:
    """Sort films for display, by priority:

    1. number of available platforms (descending) — most available first;
    2. by platform, in column order (✓ before blank) — groups films by service;
    3. title alphabetical.
    """
    df = pd.DataFrame(results)
    platform_cols = list(targets.keys())

    df["_score"] = df[platform_cols].apply(lambda row: (row == "✓").sum(), axis=1)
    rank_cols: list[str] = []
    for col in platform_cols:
        rank = f"_rank_{col}"
        df[rank] = (df[col] == "✓").astype(int)
        rank_cols.append(rank)

    sort_cols = ["_score", *rank_cols, "Title"]
    ascending = [False, *([False] * len(rank_cols)), True]
    df = df.sort_values(by=sort_cols, ascending=ascending).drop(columns=["_score", *rank_cols])
    return df


def _summary_line(results: list[dict], targets: dict[str, str]) -> str:
    """One-line count per platform: number of watchlist films available on it
    (in any tracked tier), in targets order. Avoids per-section duplicates."""
    parts = []
    for display in targets:
        count = sum(1 for r in results if r.get(display))
        if count:
            parts.append(f"{display}: {count}")
    return "\n\n".join(parts)


def _render_section(title: str, results: list[dict], targets: dict[str, str]) -> str:
    """Return the Markdown text of a section (heading + table, or empty message).

    Formatting: Title column right-aligned, Year right-aligned, platform columns
    (✓) centered.
    """
    lines = [f"## {title}\n"]
    if not results:
        lines.append("_No films available._\n")
    else:
        df = _sort_results(results, targets)
        colalign = ["right", "right", *(["center"] * len(targets))]
        # "pipe" format carries the alignment markers (:---:) so the rendered
        # Markdown actually aligns (title right, ✓ centered), not just as text.
        lines.append(
            tabulate(
                df, headers="keys", tablefmt="pipe", showindex=False, colalign=colalign
            )
        )
        lines.append("")
    return "\n".join(lines)


def display_results(
    results: list[dict],
    targets: dict[str, str] | None = None,
) -> None:
    """Print the results grouped by section (Free / Paid)."""
    _targets = (
        targets if targets is not None
        else {k: v for k, v in _ALL_PROVIDERS.items() if k in _DEFAULT_ENABLED}
    )

    print()

    if not results:
        print("No film from your watchlist is available on the selected platforms.")
        return

    sections = _split_by_section(results, _targets)

    if not sections:
        print("No film from your watchlist is available on the selected platforms.")
        return

    for label, view_results, view_targets in sections:
        print(_render_section(label, view_results, view_targets))

    print("---")
    print(_summary_line(results, _targets))


def save_results(
    results: list[dict],
    source_name: str,
    targets: dict[str, str],
    output_dir: Path | None = None,
) -> Path:
    """Save the results to a dated Markdown file.

    Args:
        source_name: where the watchlist came from (Letterboxd username or CSV name).
        output_dir: destination folder (Downloads by default).

    Returns:
        The path of the created file.
    """
    out_dir = output_dir or DOWNLOADS_DIR
    today = date.today()
    out_path = out_dir / f"watchlist_{today.isoformat()}.md"

    sections = _split_by_section(results, targets)
    rendered_sections = [
        _render_section(label, view_results, view_targets)
        for label, view_results, view_targets in sections
    ]
    summary = _summary_line(results, targets)

    content = "\n".join([
        f"# Watchlist streaming availability — {_date_en(today)}\n",
        f"**Source:** {source_name}  ",
        f"**Generated:** {today.isoformat()}\n",
        "---\n",
        *rendered_sections,
        "---\n",
        summary,
    ])
    out_path.write_text(content, encoding="utf-8")
    return out_path


def _find_letterboxd_zip(downloads_dir: Path) -> Path | None:
    """Search Downloads for a ZIP file containing a watchlist.csv entry.

    Returns:
        The path of the first matching ZIP, or None if not found.
    """
    for zip_path in sorted(downloads_dir.glob("*.zip"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            with zipfile.ZipFile(zip_path) as zf:
                if any(name.endswith("watchlist.csv") for name in zf.namelist()):
                    return zip_path
        except zipfile.BadZipFile:
            continue
    return None


def _extract_watchlist_from_zip(zip_path: Path, downloads_dir: Path) -> Path:
    """Extract watchlist.csv from a Letterboxd ZIP, then delete the ZIP.

    Returns:
        Path to the extracted watchlist.csv in downloads_dir.
    """
    with zipfile.ZipFile(zip_path) as zf:
        # The file may be at root or inside a subdirectory within the ZIP.
        entry = next(name for name in zf.namelist() if name.endswith("watchlist.csv"))
        zf.extract(entry, downloads_dir)
        extracted = downloads_dir / entry

    zip_path.unlink()

    # If extracted inside a subfolder, move it to downloads_dir root.
    dest = downloads_dir / "watchlist.csv"
    if extracted != dest:
        extracted.replace(dest)
        # Remove the now-empty subdirectory if possible.
        try:
            extracted.parent.rmdir()
        except OSError:
            pass

    return dest


def _prompt_for_csv(
    downloads_dir: Path | None = None, username: str | None = None
) -> Path:
    """Guide the user to export their watchlist, wait for Enter, then locate the CSV.

    Accepts either a watchlist*.csv or a Letterboxd export ZIP (auto-extracted,
    ZIP deleted afterwards). Loops until a file is found.

    Raises:
        FileNotFoundError: if stdin is not interactive (EOFError), to degrade
            cleanly in non-interactive contexts (cron, pipe).
        SystemExit: if the user cancels with Ctrl+C.
    """
    directory = downloads_dir or DOWNLOADS_DIR

    print(
        f"\nCould not fetch the watchlist automatically, and no watchlist*.csv file "
        f"was found in:\n    {directory}\n\n"
        "Download your Letterboxd data (login required) and drop the file in the folder above:\n\n"
        "    https://letterboxd.com/data/export\n\n"
        "The ZIP will be extracted automatically — no need to unzip it manually.\n"
    )
    if username:
        print(f"  Your watchlist online: https://letterboxd.com/{username}/watchlist/\n")

    while True:
        try:
            input("Press Enter once the file is in Downloads (Ctrl+C to cancel)… ")
        except EOFError as exc:
            raise FileNotFoundError(
                f"No watchlist*.csv in {directory} and stdin is not interactive."
            ) from exc
        except KeyboardInterrupt:
            raise SystemExit("\nCancelled.")

        # 1. Try existing CSV.
        try:
            return find_watchlist_csv(downloads_dir=directory)
        except FileNotFoundError:
            pass

        # 2. Try ZIP auto-extraction.
        zip_path = _find_letterboxd_zip(directory)
        if zip_path:
            csv_path = _extract_watchlist_from_zip(zip_path, directory)
            print(f"  → Extracted watchlist.csv (ZIP {zip_path.name} deleted).")
            return csv_path

        print(f"  → Still no watchlist*.csv or Letterboxd ZIP found in {directory}. Try again.")


def load_watchlist_source() -> tuple[pd.DataFrame, str, Path]:
    """Get the watchlist: Letterboxd scraping first, CSV as a fallback.

    Returns:
        (df, source_name, output_dir) where df has columns 'Name' and 'Year'.
    """
    if LETTERBOXD_USERNAME:
        try:
            df = fetch_watchlist_from_letterboxd(LETTERBOXD_USERNAME)
            if len(df):
                print(
                    f"Watchlist fetched from Letterboxd: "
                    f"@{LETTERBOXD_USERNAME} ({len(df)} films)"
                )
                return df, f"Letterboxd @{LETTERBOXD_USERNAME}", DOWNLOADS_DIR
            print("Letterboxd watchlist empty or private — falling back to the exported CSV.")
        except LetterboxdError as exc:
            print(f"Could not fetch from Letterboxd ({exc})\n→ falling back to the exported CSV.")

    try:
        csv_path = find_watchlist_csv()
    except FileNotFoundError:
        csv_path = _prompt_for_csv(username=LETTERBOXD_USERNAME)
    print(f"Using watchlist CSV: {csv_path}")
    return load_watchlist(csv_path), csv_path.name, csv_path.parent


def main() -> None:
    """Main entry point."""
    if not TMDB_API_KEY:
        raise EnvironmentError(
            "Missing TMDB API key.\n"
            "Copy .env.example → .env and set your TMDB_API_KEY."
        )

    targets = load_platforms_config(COUNTRY)

    df, source_name, output_dir = load_watchlist_source()

    results = build_results(df, targets, country=COUNTRY)
    display_results(results, targets)

    out_path = save_results(results, source_name, targets, output_dir)
    print(f"\nResults saved: {out_path}")


if __name__ == "__main__":
    main()
