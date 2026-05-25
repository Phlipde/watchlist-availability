"""
watchlist_availability.py

Vérifie quels films de votre watchlist Letterboxd sont disponibles
en streaming (Netflix, Canal+) via l'API TMDB.

Usage : python watchlist_availability.py
"""

import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from tabulate import tabulate
from tqdm import tqdm

# =========================
# CONFIGURATION
# =========================

load_dotenv()

TMDB_API_KEY: str | None = os.getenv("TMDB_API_KEY")

COUNTRY = "FR"

STREAMING_TARGETS = {
    "Netflix": "nfx",
    "Canal+": "cpl",
}

DOWNLOADS_DIR = Path.home() / "Downloads"

# =========================
# FONCTIONS
# =========================


def find_watchlist_csv(downloads_dir: Path | None = None) -> Path:
    """Retourne le fichier watchlist-*.csv le plus récent du dossier Downloads.

    Raises:
        FileNotFoundError: si aucun fichier correspondant n'est trouvé.
    """
    directory = downloads_dir or DOWNLOADS_DIR
    candidates = list(directory.glob("watchlist-*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"Aucun fichier 'watchlist-*.csv' trouvé dans {directory}.\n"
            "Exportez votre watchlist depuis letterboxd.com > Profil > Importer & Exporter."
        )
    return max(candidates, key=lambda f: f.stat().st_mtime)


def load_watchlist(csv_path: Path) -> pd.DataFrame:
    """Charge et valide le CSV Letterboxd.

    Raises:
        ValueError: si les colonnes 'Name' ou 'Year' sont absentes.
    """
    df = pd.read_csv(csv_path)
    missing = [col for col in ("Name", "Year") if col not in df.columns]
    if missing:
        raise ValueError(
            f"Colonnes manquantes dans le CSV : {missing}. "
            "Vérifiez que le fichier provient bien de Letterboxd."
        )
    return df


def get_tmdb_id(title: str, year: int | str, api_key: str | None = None) -> int | None:
    """Recherche l'ID TMDB d'un film par titre et année.

    Effectue une seule tentative de retry si l'API répond 429 (rate limit).

    Returns:
        L'ID TMDB ou None si le film n'est pas trouvé / erreur réseau.
    """
    key = api_key or TMDB_API_KEY
    url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": key, "query": title, "year": year}

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
) -> set[str]:
    """Retourne l'ensemble des plateformes de streaming (flatrate) pour un film.

    Returns:
        Un set de noms de plateformes, vide si non disponible ou erreur réseau.
    """
    key = api_key or TMDB_API_KEY
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/watch/providers"
    params = {"api_key": key}

    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException:
        return set()

    flatrate = data.get("results", {}).get(country, {}).get("flatrate", [])
    return {p["provider_name"] for p in flatrate}


def build_results(
    df: pd.DataFrame,
    streaming_targets: dict[str, str] | None = None,
    country: str = "FR",
    api_key: str | None = None,
) -> list[dict]:
    """Parcourt le DataFrame et retourne les films disponibles sur les plateformes cibles.

    Args:
        df: DataFrame Letterboxd avec colonnes 'Name' et 'Year'.
        streaming_targets: dict {nom_affichage: provider_id}, utilise STREAMING_TARGETS par défaut.
        country: code pays ISO 3166-1 alpha-2.
        api_key: clé API TMDB, utilise la variable d'environnement par défaut.

    Returns:
        Liste de dicts avec les clés 'Titre', 'Année' et une clé par plateforme.
    """
    targets = streaming_targets or STREAMING_TARGETS
    results = []

    for _, row in tqdm(
        df.iterrows(),
        total=len(df),
        desc="Recherche des disponibilités streaming",
        unit="film",
    ):
        title = row["Name"]
        year = row["Year"]

        tmdb_id = get_tmdb_id(title, year, api_key=api_key)
        if tmdb_id is None:
            continue

        providers = get_streaming_platforms(tmdb_id, country=country, api_key=api_key)

        match = {name: name in providers for name in targets}
        if any(match.values()):
            results.append(
                {
                    "Titre": title,
                    "Année": year,
                    **{name: "X" if available else "" for name, available in match.items()},
                }
            )

        time.sleep(0.15)

    return results


def display_results(results: list[dict], streaming_targets: dict[str, str] | None = None) -> None:
    """Affiche les résultats triés dans le terminal (Netflix d'abord, puis Canal+).

    Si la liste est vide, affiche un message informatif.
    """
    targets = streaming_targets or STREAMING_TARGETS

    print()
    if not results:
        print("Aucun film de votre watchlist n'est disponible sur les plateformes cibles.")
        return

    df_result = pd.DataFrame(results)

    sort_cols = []
    sort_keys = []
    for name in targets:
        col = f"_sort_{name}"
        df_result[col] = df_result[name].map({"X": 1, "": 0})
        sort_cols.append(col)
        sort_keys.append(False)

    df_result = df_result.sort_values(by=sort_cols, ascending=sort_keys).drop(
        columns=sort_cols
    )

    print("Films de votre watchlist disponibles en streaming :\n")
    print(tabulate(df_result, headers="keys", tablefmt="github", showindex=False))


def main() -> None:
    """Point d'entrée principal du script."""
    if not TMDB_API_KEY:
        raise EnvironmentError(
            "Clé API TMDB manquante.\n"
            "Copiez .env.example → .env et renseignez votre clé TMDB_API_KEY."
        )

    csv_path = find_watchlist_csv()
    print(f"Fichier Letterboxd détecté : {csv_path}")

    df = load_watchlist(csv_path)
    results = build_results(df)
    display_results(results)


if __name__ == "__main__":
    main()
