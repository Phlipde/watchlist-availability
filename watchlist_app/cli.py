"""Command-line orchestration for watchlist availability."""

import time
from pathlib import Path

import pandas as pd
from tqdm import tqdm


def prompt_for_csv(wa, downloads_dir: Path | None = None, username: str | None = None) -> Path:
    directory = downloads_dir or wa.DOWNLOADS_DIR
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
        try:
            return wa.find_watchlist_csv(downloads_dir=directory)
        except FileNotFoundError:
            pass
        zip_path = wa._find_letterboxd_zip(directory)
        if zip_path:
            csv_path = wa._extract_watchlist_from_zip(zip_path, directory)
            print(f"  → Extracted watchlist.csv (ZIP {zip_path.name} deleted).")
            return csv_path
        print(f"  → Still no watchlist*.csv or Letterboxd ZIP found in {directory}. Try again.")


def load_watchlist_source(wa) -> tuple[pd.DataFrame, str, Path]:
    if wa.LETTERBOXD_USERNAME:
        try:
            dataframe = wa.fetch_watchlist_from_letterboxd(wa.LETTERBOXD_USERNAME)
            if len(dataframe):
                print(
                    f"Watchlist fetched from Letterboxd: "
                    f"@{wa.LETTERBOXD_USERNAME} ({len(dataframe)} films)"
                )
                return (
                    dataframe,
                    f"Letterboxd @{wa.LETTERBOXD_USERNAME}",
                    wa.DOWNLOADS_DIR,
                )
            print("Letterboxd watchlist empty or private — falling back to the exported CSV.")
        except wa.LetterboxdError as exc:
            print(f"Could not fetch from Letterboxd ({exc})\n→ falling back to the exported CSV.")
    try:
        csv_path = wa.find_watchlist_csv()
    except FileNotFoundError:
        csv_path = prompt_for_csv(wa, username=wa.LETTERBOXD_USERNAME)
    print(f"Using watchlist CSV: {csv_path}")
    return wa.load_watchlist(csv_path), csv_path.name, csv_path.parent


def test_unknown_providers(wa, df: pd.DataFrame, country: str = "DE", api_key: str | None = None) -> None:
    known_providers = set(wa._ALL_PROVIDERS.values())
    unknown_providers: set[str] = set()
    for _, row in tqdm(
        df.iterrows(),
        total=len(df),
        desc=f"Finding unknown TMDB providers ({country})",
        unit="film",
    ):
        tmdb_id = wa.get_tmdb_id(row["Name"], row["Year"], api_key=api_key)
        if tmdb_id is None:
            continue
        providers = wa.get_streaming_platforms(tmdb_id, country=country, api_key=api_key)
        unknown_providers.update(
            provider for provider in providers if provider not in known_providers
        )
        time.sleep(0.15)
    print("\n=== UNKNOWN TMDB PROVIDERS ===")
    if unknown_providers:
        for provider in sorted(unknown_providers):
            print(f'"{provider}"')
    else:
        print("None")
    print("==============================\n")


def main(wa) -> None:
    if not wa.TMDB_API_KEY:
        raise EnvironmentError(
            "Missing TMDB API key.\n"
            "Copy .env.example → .env and set your TMDB_API_KEY."
        )
    targets = wa.load_platforms_config(wa.COUNTRY)
    dataframe, source_name, output_dir = wa.load_watchlist_source()
    results = wa.build_results(dataframe, targets, country=wa.COUNTRY)
    wa.display_results(results, targets)
    output_path = wa.save_results(results, source_name, targets, output_dir)
    print(f"\nResults saved: {output_path}")
