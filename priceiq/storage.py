"""Persistence: append-only price history (CSV) + latest snapshot (JSON)."""
from __future__ import annotations

import csv
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
HISTORY_HEADER = ["timestamp", "sku", "competitor", "listing", "price"]


def _path(name: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, name)


def append_history(rows: list) -> None:
    if not rows:
        return
    path = _path("history.csv")
    is_new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(HISTORY_HEADER)
        w.writerows(rows)


def load_history() -> list:
    path = _path("history.csv")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_snapshot(obj: dict) -> None:
    with open(_path("snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)


def load_snapshot() -> dict:
    path = _path("snapshot.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)
