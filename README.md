# Watchlist Availability

Vérifie quels films de votre watchlist **Letterboxd** sont disponibles en streaming
(Netflix, Canal+) en France, via l'API TMDB.

```
Fichier Letterboxd détecté : /Users/you/Downloads/watchlist-2024-06-01.csv
Recherche des disponibilités streaming: 100%|████████| 120/120 [01:23<00:00,  1.44film/s]

Films de votre watchlist disponibles en streaming :

| Titre                 | Année | Netflix | Canal+ |
|-----------------------|-------|---------|--------|
| Inception             |  2010 | X       |        |
| The Substance         |  2024 | X       | X      |
| Anatomy of a Fall     |  2023 |         | X      |
```

---

## Prérequis

- Python 3.9+
- Un compte [TMDB](https://www.themoviedb.org/) (gratuit) pour obtenir une clé API
- Une watchlist exportée depuis Letterboxd

## Installation

```bash
git clone https://github.com/votre-username/watchlist-availability.git
cd watchlist-availability
python3 -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

1. Copiez le fichier `.env.example` :
   ```bash
   cp .env.example .env
   ```
2. Éditez `.env` et renseignez votre clé API TMDB :
   ```
   TMDB_API_KEY=votre_cle_ici
   ```
   Obtenez une clé gratuite sur [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api).

## Exporter votre watchlist Letterboxd

1. Connectez-vous sur [letterboxd.com](https://letterboxd.com)
2. Allez dans **Profil → Importer & Exporter → Exporter vos données**
3. Décompressez l'archive et placez le fichier `watchlist.csv` dans votre dossier `Downloads`
   en le renommant au format `watchlist-YYYY-MM-DD.csv` (ex. `watchlist-2024-06-01.csv`)

Le script détecte automatiquement le fichier le plus récent correspondant à `watchlist-*.csv`.

## Usage

```bash
python watchlist_availability.py
```

## Personnalisation

Modifiez le dictionnaire `STREAMING_TARGETS` dans `watchlist_availability.py`
pour ajouter ou retirer des plateformes.
Les identifiants de fournisseurs sont disponibles via l'API TMDB :

```python
STREAMING_TARGETS = {
    "Netflix":   "nfx",
    "Canal+":    "cpl",
    "Disney+":   "dnp",
    "Amazon":    "amp",
    "Apple TV+": "atp",
}
```

Pour changer le pays, modifiez la variable `COUNTRY` (code ISO 3166-1 alpha-2, ex. `"BE"`, `"CH"`).

## Lancer les tests

```bash
pytest tests/ -v
```

Les tests sont entièrement mockés — aucune clé API réelle n'est requise.

## Structure du projet

```
watchlist-availability/
├── watchlist_availability.py   # Script principal
├── tests/
│   └── test_watchlist.py       # Suite de tests pytest (27 tests)
├── .env.example                # Template de configuration
├── .gitignore
├── requirements.txt
└── README.md
```

## Licence

MIT
