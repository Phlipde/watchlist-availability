import importlib
import json
import sys
import threading
import time

import pytest

from watchlist_app.backups import KEEP, write_daily_backup
from watchlist_app.store import Store


def day(offset: int) -> float:
    return time.mktime((2026, 11, 1 + offset, 12, 0, 0, 0, 0, -1))


def test_one_backup_per_day_and_only_the_newest_are_kept(tmp_path):
    store = Store(":memory:")
    folder = tmp_path / "backups"
    first = write_daily_backup(store, folder, day(0))
    assert first is not None and json.loads(first.read_text(encoding="utf-8"))["version"]
    assert write_daily_backup(store, folder, day(0)) is None  # today's exists
    for offset in range(1, KEEP + 3):
        write_daily_backup(store, folder, day(offset))
    names = sorted(path.name for path in folder.glob("backup-*.json"))
    assert len(names) == KEEP
    assert names[-1] == "backup-2026-11-10.json" and "backup-2026-11-01.json" not in names
    assert not list(folder.glob("*.tmp"))


@pytest.fixture
def web_app(tmp_path, monkeypatch):
    monkeypatch.setenv("WATCHLIST_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WATCHLIST_DISABLE_SCHEDULER", "1")
    monkeypatch.delenv("WATCHLIST_DB", raising=False)
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    yield module
    sys.modules.pop("app", None)


def test_health_checks_database_and_schedule(web_app, monkeypatch):
    client = web_app.app.test_client()
    assert client.get("/health").status_code == 200  # schedule off: only the database counts
    stopped = threading.Thread(target=lambda: None)
    stopped.start()
    stopped.join()
    monkeypatch.setattr(web_app, "_SCHEDULER", stopped)
    assert client.get("/health").get_json() == {"status": "schedule stopped"}
    monkeypatch.setattr(web_app, "_SCHEDULER", None)

    def broken(limit=1):
        raise RuntimeError("locked")

    monkeypatch.setattr(web_app._STORE, "list_jobs", broken)
    assert client.get("/health").status_code == 503
