"""Persistent result cache for web scans."""

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


def load_cache(path: Path) -> dict[str, dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(path: Path, cache: dict[str, dict]) -> None:
    save_snapshot(path, cache)


def load_snapshot(path: Path) -> dict:
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return snapshot if isinstance(snapshot, dict) else {}


def save_snapshot(path: Path, snapshot: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        json.dump(snapshot, temporary)
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)
