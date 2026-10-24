"""定时器：AI 自己决定的“过多久再开口”。

用 asyncio task 而不是 threading.Timer —— 推消息、调模型都在同一个事件循环里，不会有跨线程竞态。
"""
from __future__ import annotations

import asyncio
import itertools
from datetime import datetime, timedelta
from typing import Awaitable, Callable

import config


class TimerManager:
    def __init__(self, on_fire: Callable[[str], Awaitable[None]]):
        self._on_fire = on_fire
        self._tasks: dict[str, asyncio.Task] = {}
        self._meta: dict[str, dict] = {}
        self._ids = itertools.count(1)

    def __len__(self) -> int:
        return len(self._tasks)

    def list(self) -> list[dict]:
        return [
            {
                "id": tid,
                "reason": self._meta[tid]["reason"],
                "fire_at": self._meta[tid]["fire_at"].isoformat(timespec="minutes"),
            }
            for tid in self._tasks
            if tid in self._meta
        ]

    async def set_timer(self, minutes, reason: str) -> tuple[bool, str]:
        if len(self._tasks) >= config.MAX_TIMERS:
            pending = "、".join(f"{m['reason']}({m['fire_at']})" for m in self.list())
            return False, f"定时器已满（上限 {config.MAX_TIMERS} 个），当前有：{pending}。请先取消或等待。"
        try:
            minutes = float(minutes)
        except (TypeError, ValueError):
            return False, "minutes 参数必须是数字"
        if minutes <= 0:
            return False, "minutes 必须大于 0"
        if minutes > 24 * 60:
            return False, "最长只能设 24 小时以内的定时器"

        tid = f"t{next(self._ids)}"
        fire_at = datetime.now() + timedelta(minutes=minutes)
        task = asyncio.create_task(self._run(tid, minutes, reason))
        self._tasks[tid] = task
        self._meta[tid] = {"reason": reason, "fire_at": fire_at}
        return True, f"已设定 {minutes:g} 分钟后开口（{fire_at.strftime('%H:%M')}），原因：{reason}"

    async def _run(self, tid: str, minutes: float, reason: str) -> None:
        try:
            await asyncio.sleep(minutes * 60)
            await self._on_fire(reason)
        except asyncio.CancelledError:
            pass
        finally:
            self._tasks.pop(tid, None)
            self._meta.pop(tid, None)

    async def cancel_all(self) -> tuple[bool, str]:
        n = len(self._tasks)
        for task in list(self._tasks.values()):
            task.cancel()
        self._tasks.clear()
        self._meta.clear()
        return True, f"已取消 {n} 个定时器" if n else "当前没有定时器"

    async def cancel(self, tid: str) -> tuple[bool, str]:
        task = self._tasks.pop(tid, None)
        self._meta.pop(tid, None)
        if not task:
            return False, f"没有找到定时器 {tid}"
        task.cancel()
        return True, f"已取消 {tid}"

    def shutdown(self) -> None:
        for task in list(self._tasks.values()):
            task.cancel()
        self._tasks.clear()
        self._meta.clear()
