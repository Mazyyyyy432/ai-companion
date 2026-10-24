"""搭子的资料与「关系协议」。

存在 data/profile.json，模型可以通过工具写入，电脑端也能直接编辑。
这份东西会拼进 System Prompt，所以换聊天记录、换设备都不会丢。
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any

import config

_FILE = config.DATA_DIR / "profile.json"
_lock = threading.Lock()

_DEFAULT = {
    "name": "她",
    "user_name": "",
    "agreement": "",
    "facts": {},
    "onboarded": False,
    "created": "",
    "updated": "",
}


def load() -> dict:
    if not _FILE.exists():
        d = dict(_DEFAULT)
        d["created"] = datetime.now().isoformat(timespec="seconds")
        return d
    try:
        d = json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        d = dict(_DEFAULT)
    for k, v in _DEFAULT.items():
        d.setdefault(k, v)
    return d


def save(data: dict) -> dict:
    data["updated"] = datetime.now().isoformat(timespec="seconds")
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def name() -> str:
    return (load().get("name") or "她").strip() or "她"


def update(**kw: Any) -> dict:
    with _lock:
        d = load()
        for k, v in kw.items():
            if k in _DEFAULT:
                d[k] = v
        return save(d)


def remember(key: str, value: str) -> dict:
    with _lock:
        d = load()
        d["facts"][str(key).strip()[:40]] = str(value).strip()[:2000]
        return save(d)


def forget(key: str) -> bool:
    with _lock:
        d = load()
        ok = d["facts"].pop(key, None) is not None
        save(d)
        return ok


def prompt_block() -> str:
    """拼进 System Prompt 的那一段。"""
    d = load()
    nm = d.get("name") or "她"
    lines = [f"【你的名字是「{nm}」。她这样叫你，你也这样称呼自己。】"]

    if d.get("user_name"):
        lines.append(f"【你称呼她「{d['user_name']}」。】")

    facts = d.get("facts") or {}
    if facts:
        lines.append("【你记得关于她的事】")
        for k, v in list(facts.items())[:30]:
            lines.append(f"- {k}：{v}")

    if d.get("agreement"):
        lines.append("【你们之前一起定下的约定，聊天时自然遵守，不要逐条背诵】")
        lines.append(d["agreement"])

    if not d.get("onboarded"):
        lines.append(
            "【这是你们的第一次见面。不要一上来就进入角色，先用几轮把彼此摸清楚："
            "问她希望你怎么称呼、今天想要什么样的感觉、哪些可以哪些绝对不行、"
            "安全词想用什么。聊到差不多的时候，主动提出「我们把刚才说的写成一份约定吧」，"
            "然后用 save_agreement 把它们存下来，再用 finish_onboarding 收尾。"
            "整个过程要像聊天，不要像填表。】"
        )

    return "\n".join(lines)
