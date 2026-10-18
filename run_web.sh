#!/usr/bin/env bash
# Start the local watchlist web app from any working directory.
cd "$(dirname "$0")" || exit 1
exec .venv/bin/python3.14 app.py "$@"