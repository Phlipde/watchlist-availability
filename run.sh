#!/usr/bin/env bash
# Run watchlist_availability from any working directory.
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
exec "$PY" watchlist_availability.py "$@"
