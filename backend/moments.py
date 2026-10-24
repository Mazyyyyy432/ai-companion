"""「美好时刻」：她想留住的小事。

一行一条，追加写入 data/moments.jsonl，可以带一张图片。
"""
from __future__ import annotations

import json
import threading
from datetime import datetime

import config

_FILE = config.DATA_DIR / "moments.jsonl"
_lock = threading.Lock()


def append(title: str, note: str = "", image: str = "") -> dict:
    item = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "title": (title or "").strip()[:80] or "无题",
        "note": (note or "").strip()[:2000],
        "image": (image or "").strip(),
    }
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with _FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return item


def load(limit: int = 200) -> list[dict]:
    if not _FILE.exists():
        return []
    items: list[dict] = []
    with _FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items[-limit:][::-1]  # 新的在前


def delete(ts: str) -> bool:
    items = load(100000)
    keep = [i for i in items if i.get("ts") != ts]
    if len(keep) == len(items):
        return False
    _FILE.write_text(
        "\n".join(json.dumps(i, ensure_ascii=False) for i in keep) + "\n",
        encoding="utf-8",
    )
    return True
