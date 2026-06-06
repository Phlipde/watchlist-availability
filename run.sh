#!/usr/bin/env bash
# Lance watchlist_availability. Fonctionne depuis n'importe quel dossier.
cd "$(dirname "$0")" || exit 1
exec .venv/bin/python3.14 watchlist_availability.py "$@"
