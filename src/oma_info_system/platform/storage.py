"""TinyDB-backed application storage."""

import threading
from pathlib import Path

from tinydb import TinyDB

_lock = threading.RLock()
_databases: dict[str, TinyDB] = {}


def get_database(path: Path) -> TinyDB:
    key = str(Path(path).resolve())
    with _lock:
        if key not in _databases:
            Path(key).parent.mkdir(parents=True, exist_ok=True)
            _databases[key] = TinyDB(key, ensure_ascii=False)
        return _databases[key]
