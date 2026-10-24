"""聊天记录持久化 + 极简关键词检索。

存储格式：data/chat_history/history.jsonl，一行一条，追加写入，不怕进程崩溃丢数据。
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from typing import Any

import config

_lock = threading.Lock()

# 中文按单字切、英文数字按词切。足够简单，不需要引入分词库
_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]")

# 这些词出现频率太高，没有检索价值
_STOPWORDS = {
    "的", "了", "是", "我", "你", "她", "他", "在", "有", "和", "就", "不", "也", "都", "吗",
    "呢", "吧", "啊", "呀", "这", "那", "个", "一", "上", "下", "很", "会", "要", "想",
    "the", "a", "an", "is", "are", "to", "of", "and", "i", "you", "it",
}


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS}


def append(role: str, content: str, **meta: Any) -> None:
    """追加一条记录。role: user / assistant / tool / system"""
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "role": role,
        "content": content,
        "meta": meta or {},
    }
    path = config.HISTORY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with _lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def _iter_records():
    path = config.HISTORY_FILE
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def recent_messages(limit: int | None = None) -> list[dict]:
    """取最近若干条 user/assistant 消息，用于拼上下文。"""
    limit = limit or config.HISTORY_CONTEXT_SIZE
    records = [r for r in _iter_records() if r.get("role") in ("user", "assistant")]
    records = records[-limit:]
    return [{"role": r["role"], "content": r["content"]} for r in records]


def recent_records(limit: int = 80) -> list[dict]:
    """给界面用的原始记录，包含工具调用。"""
    records = list(_iter_records())
    return records[-limit:]


def clear() -> int:
    """清空历史，返回清掉的条数。"""
    path = config.HISTORY_FILE
    if not path.exists():
        return 0
    n = sum(1 for _ in _iter_records())
    with _lock:
        path.write_text("", encoding="utf-8")
    return n


def search(query: str, k: int | None = None) -> list[str]:
    """按关键词重合度从历史里捞出最相关的几条（不含最近 6 条，避免和上下文重复）。"""
    k = k or config.MEMORY_SEARCH_K
    q = _tokens(query)
    if not q:
        return []

    records = [r for r in _iter_records() if r.get("role") in ("user", "assistant")]
    candidates = records[:-6] if len(records) > 6 else []

    scored: list[tuple[float, float, str]] = []
    for r in candidates:
        text = r.get("content", "")
        t = _tokens(text)
        if not t:
            continue
        overlap = len(q & t)
        if overlap == 0:
            continue
        # 重合词数为主，按文本长度做轻微惩罚，避免长段落霸榜
        score = overlap / (len(t) ** 0.5)
        scored.append((score, r.get("ts", ""), text))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [s[2][:300] for s in scored[:k]]
