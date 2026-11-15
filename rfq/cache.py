"""Response cache: cache/<key>.json. Committed to git so dev replays with no API key.

key = sha256(model + prompt_version + schema + request content). Only results that passed
schema validation are written, so a bad answer is never replayed.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from rfq.config import CACHE_DIR


def cache_key(model: str, prompt_version: str, schema: dict, content_digest: str) -> str:
    h = hashlib.sha256()
    for part in (model, prompt_version, json.dumps(schema, sort_keys=True), content_digest):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


class Cache:
    def __init__(self, root: Path = CACHE_DIR) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, key: str) -> dict | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None  # unreadable entry = miss; it will be overwritten by a good one

    def put(self, key: str, entry: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        p = self._path(key)
        tmp = p.with_name(p.name + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(entry, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(p)
