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


# 协议的结构。刻意做成固定章节，这样读起来像一份文件，而不是一堆聊天记录。
CONTRACT_SECTIONS: list[tuple[str, str, str]] = [
    ("parties", "一、双方与称谓", "她怎么称呼你、你怎么称呼她，这段关系里各自的称呼"),
    ("nature", "二、关系性质与有效期", "这是什么样的关系，从什么时候开始，多久复盘一次"),
    ("power", "三、权力交换的范围", "哪些事情交给对方决定，哪些永远保留在自己手里"),
    ("limits", "四、界限", "可以做的、需要先问的、绝对不做的"),
    ("safety", "五、安全词与中止机制", "安全词是什么，说了之后怎么处理，谁可以随时喊停"),
    ("practice", "六、具体实践与强度", "涉及哪些方式，强度怎么递增，单次上限"),
    ("aftercare", "七、事后照顾", "结束之后需要什么，谁负责什么"),
    ("ritual", "八、日常义务与仪式", "日常里的问候、汇报、称呼、小规矩"),
    ("review", "九、复盘、修订与退出", "多久聊一次感受，怎么修改，怎么退出且不伤害彼此"),
]

_SECTION_KEYS = {k for k, _, _ in CONTRACT_SECTIONS}
_SECTION_BY_TITLE = {t: k for k, t, _ in CONTRACT_SECTIONS}


def contract() -> dict:
    """返回 {key: text}，缺失的补空串。"""
    d = load()
    raw = d.get("contract") or {}
    return {k: str(raw.get(k, "")) for k in _SECTION_KEYS}


def contract_filled() -> bool:
    return any(v.strip() for v in contract().values())


def set_contract_section(section: str, text: str) -> tuple[bool, str]:
    key = (section or "").strip()
    if key not in _SECTION_KEYS:
        key = _SECTION_BY_TITLE.get(key, "")
    if key not in _SECTION_KEYS:
        titles = "、".join(t for _, t, _ in CONTRACT_SECTIONS)
        return False, f"没有这一节。可用的有：{titles}"

    with _lock:
        d = load()
        cur = d.get("contract") or {}
        cur[key] = str(text).strip()[:4000]
        d["contract"] = cur
        save(d)
    title = next(t for k, t, _ in CONTRACT_SECTIONS if k == key)
    return True, f"「{title}」已保存"


def contract_lines() -> list[dict]:
    cur = contract()
    return [{"key": k, "title": t, "text": cur.get(k, "")} for k, t, _ in CONTRACT_SECTIONS]


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

    cur = contract()
    if any(v.strip() for v in cur.values()):
        lines.append("【你们签过的协议，聊天时自然遵守，不要逐条背】")
        for key, title, _ in CONTRACT_SECTIONS:
            if cur.get(key, "").strip():
                lines.append(f"{title}：{cur[key].strip()}")

    if not d.get("onboarded"):
        lines.append(
            "【这是你们的第一次见面。不要一上来就进入角色，先用几轮把彼此摸清楚："
            "问她希望你怎么称呼、今天想要什么样的感觉、哪些可以哪些绝对不行、"
            "安全词想用什么。关于称呼：可以问她想让你叫她什么；如果她说「你定」，"
            "就替她起一个，说出来，再用 set_call_name 记住。"
            "聊到差不多的时候，主动提出「我们把这些写成一份协议吧」。"
            "然后用 set_contract_section 一节一节写进去（九节，见工具说明），"
            "写完用 save_agreement 存一份简要版，再用 finish_onboarding 收尾。"
            "协议要写得像真的文件：清楚、具体、有边界，不要空话。"
            "整个过程要像聊天，不要像填表。】"
        )

    return "\n".join(lines)
