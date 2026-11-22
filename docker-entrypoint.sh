#!/bin/sh
# Runs as root only to set up the data folder, then drops to PUID/PGID (Unraid: 99/100).
set -e
if [ "$(id -u)" = "0" ]; then
  PUID="${PUID:-99}"
  PGID="${PGID:-100}"
  getent group "$PGID" >/dev/null || groupadd -g "$PGID" app
  getent passwd "$PUID" >/dev/null || useradd -u "$PUID" -g "$PGID" -M -s /usr/sbin/nologin app
  mkdir -p "${WATCHLIST_DATA_DIR:-/data}"
  chown -R "$PUID:$PGID" "${WATCHLIST_DATA_DIR:-/data}"
  exec gosu "$PUID:$PGID" "$@"
fi
exec "$@"
