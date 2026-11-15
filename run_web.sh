#!/usr/bin/env bash
# Start the local watchlist web app from any working directory.
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
exec "$PY" app.py "$@"
