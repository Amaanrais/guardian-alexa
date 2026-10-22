"""Small key-value storage behind an interface: JSON files in server/data/ now, DynamoDB later.

Each collection is one JSON object on disk ({key: record}), e.g. server/data/family.json.
"""

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Protocol

from . import config


class Store(Protocol):
    def get(self, collection: str, key: str) -> dict | None: ...
    def put(self, collection: str, key: str, value: dict) -> None: ...
    def all(self, collection: str) -> dict[str, dict]: ...


class JsonFileStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self._lock = threading.Lock()

    def _path(self, collection: str) -> Path:
        return self.directory / f"{collection}.json"

    def all(self, collection: str) -> dict[str, dict]:
        try:
            return json.loads(self._path(collection).read_text())
        except (OSError, ValueError):
            return {}

    def get(self, collection: str, key: str) -> dict | None:
        return self.all(collection).get(key)

    def put(self, collection: str, key: str, value: dict) -> None:
        with self._lock:
            data = self.all(collection)
            data[key] = value
            self.directory.mkdir(parents=True, exist_ok=True)
            # write-then-rename, so a crash never leaves half a file
            fd, tmp = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self._path(collection))


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = JsonFileStore(config.DATA_DIR)
    return _store


def set_store(store: Store | None) -> None:
    """Swap the backend (tests, or DynamoDB later). None goes back to the default."""
    global _store
    _store = store
