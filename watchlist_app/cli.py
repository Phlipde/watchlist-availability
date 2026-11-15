"""Command-line entry point: check the watchlist and write an HTML report."""

from pathlib import Path

from . import config, letterboxd, rendering
from .models import WatchlistEntry
from .scan_service import perform_scan
from .settings import AppSettings
from .store import Store


def prompt_for_csv(downloads_dir: Path | None = None, username: str | None = None) -> Path:
    directory = downloads_dir or config.DOWNLOADS_DIR
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
            raise SystemExit("\nCancelled.") from None
        try:
            return letterboxd.find_watchlist_csv(downloads_dir=directory)
        except FileNotFoundError:
            pass
        zip_path = letterboxd.find_letterboxd_zip(directory)
        if zip_path:
            csv_path = letterboxd.extract_watchlist_from_zip(zip_path, directory)
            print(f"  → Extracted watchlist.csv (ZIP {zip_path.name} deleted).")
            return csv_path
        print(f"  → Still no watchlist*.csv or Letterboxd ZIP found in {directory}. Try again.")


_FROM_ENVIRONMENT = object()


def load_watchlist_source(username=_FROM_ENVIRONMENT) -> tuple[list[WatchlistEntry], str, Path]:
    if username is _FROM_ENVIRONMENT:
        username = config.LETTERBOXD_USERNAME
    if username:
        try:
            entries = letterboxd.fetch_watchlist_from_letterboxd(username)
            if entries:
                print(f"Watchlist fetched from Letterboxd: @{username} ({len(entries)} films)")
                return entries, f"Letterboxd @{username}", config.DOWNLOADS_DIR
            print("Letterboxd watchlist empty or private — falling back to the exported CSV.")
        except letterboxd.LetterboxdError as exc:
            print(f"Could not fetch from Letterboxd ({exc})\n→ falling back to the exported CSV.")
    try:
        csv_path = letterboxd.find_watchlist_csv()
    except FileNotFoundError:
        csv_path = prompt_for_csv(username=username)
    print(f"Using watchlist CSV: {csv_path}")
    return letterboxd.load_watchlist(csv_path), csv_path.name, csv_path.parent


def main() -> None:
    if not config.TMDB_API_KEY:
        raise OSError("Missing TMDB API key.\nCopy .env.example → .env and set your TMDB_API_KEY.")
    store = Store(config.database_path())
    try:
        # The same settings and the same scan as the web app: saved settings win over .env.
        settings = AppSettings(store)
        targets = settings.targets()
        entries, source_name, output_dir = load_watchlist_source(settings.letterboxd_username)
        outcome = perform_scan(store, entries, source_name, settings.country, settings.tmdb_api_key)
    finally:
        store.close()
    assert outcome is not None  # only a cancelled scan has no outcome
    if outcome.reused:
        print("Using the scan from the last 24 hours.")
    rendering.display_results(outcome.films, targets)
    if outcome.failed:
        print(f"\n{len(outcome.failed)} lookup(s) failed:")
        for failure in outcome.failed:
            print(f"  {failure['title']}: {failure['message']}")
    output_path = rendering.save_results(outcome.films, source_name, targets, output_dir)
    print(f"\nResults saved: {output_path}")
