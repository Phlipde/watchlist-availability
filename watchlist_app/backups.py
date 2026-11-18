"""A daily backup file in the data folder; the last few are kept."""

import json
import logging
import time
from pathlib import Path

from .store import Store

KEEP = 7


def write_daily_backup(store: Store, directory: Path, now: float | None = None) -> Path | None:
    """Write today's backup file unless it exists; keep the newest KEEP files. Returns the new file."""
    now = now if now is not None else time.time()
    target = directory / f"backup-{time.strftime('%Y-%m-%d', time.localtime(now))}.json"
    created = None
    if not target.exists():
        directory.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(store.export_backup()), encoding="utf-8")
        temporary.replace(target)  # a half-written file never counts as today's backup
        created = target
    for old in sorted(directory.glob("backup-*.json"))[:-KEEP]:
        try:
            old.unlink()
        except OSError:
            logging.warning("Could not delete the old backup %s", old)
    return created
