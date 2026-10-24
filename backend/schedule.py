"""她的“作息表”：什么时候说早安、什么时候哄睡。

关键设计：**这里没有默认时间**。所有时间都是她在聊天里察觉到的，
通过 set_daily_time 写进来；你作息变了，她再改。

存在 data/schedule.json，后台每分钟检查一次，改了立即生效，不用重启。
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime

import config

_FILE = config.DATA_DIR / "schedule.json"
_lock = threading.Lock()

_VALID_KINDS = {"morning", "night"}


def load() -> dict:
    if not _FILE.exists():
        return {}
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save(data: dict) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def set_time(kind: str, hhmm: str, reason: str = "") -> tuple[bool, str]:
    kind = (kind or "").strip().lower()
    if kind not in _VALID_KINDS:
        return False, "kind 只能是 morning 或 night"
    if not re.fullmatch(r"\d{1,2}:\d{2}", (hhmm or "").strip()):
        return False, "时间格式要像 09:10 或 23:30"

    hh, mm = (int(x) for x in hhmm.strip().split(":"))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return False, "时间超出范围"

    with _lock:
        d = load()
        d[kind] = {
            "time": f"{hh:02d}:{mm:02d}",
            "reason": (reason or "").strip()[:300],
            "updated": datetime.now().isoformat(timespec="seconds"),
        }
        _save(d)

    label = "早安" if kind == "morning" else "哄睡"
    return True, f"已把{label}时间设为 {hh:02d}:{mm:02d}"


def clear(kind: str) -> tuple[bool, str]:
    kind = (kind or "").strip().lower()
    with _lock:
        d = load()
        if kind not in d:
            return False, f"本来就没有设置 {kind}"
        d.pop(kind)
        _save(d)
    return True, f"已取消 {kind}"


def list_all() -> dict:
    d = load()
    out = {}
    for k in _VALID_KINDS:
        if k in d:
            out[k] = d[k]
    return out


def due(now: datetime) -> list[tuple[str, str]]:
    """当前这一分钟该发哪些。返回 [(kind, 意图)]"""
    d = load()
    hits: list[tuple[str, str]] = []
    for kind, item in d.items():
        t = item.get("time", "")
        if t == f"{now.hour:02d}:{now.minute:02d}":
            hits.append((kind, item.get("reason") or ("说早安" if kind == "morning" else "哄她睡觉")))
    return hits
