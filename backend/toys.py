"""玩具控制：把 sosexy-ble-control 的 HTTP 服务包装成几个 async 函数。

设计要点：
- 强度永远在本地再夹一次 0-100，不管模型传什么都不会越界。
- 连不上服务/设备时，把人类可读的错误返回给模型，而不是抛异常把整轮对话搞崩。
"""
from __future__ import annotations

import httpx

import config

LEVEL_MIN, LEVEL_MAX = 0, 100

_last_state: dict = {"suction": 0, "vibration": 0, "electric": 0}


def clamp(value) -> int:
    try:
        v = int(float(value))
    except (TypeError, ValueError):
        return 0
    return max(LEVEL_MIN, min(LEVEL_MAX, v))


async def _post(path: str, payload: dict | None = None, timeout: float = 16.0) -> tuple[bool, str]:
    """timeout 要大于玩具服务自身的 10 秒扫描时间，否则永远拿到“超时”而不是真实原因。"""
    url = config.TOY_BASE_URL.rstrip("/") + path
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, json=payload) if payload is not None else await client.post(url)
    except httpx.ConnectError:
        return False, "本地玩具服务没有运行（端口 8765 没有响应）。告诉用户需要先启动玩具服务。"
    except httpx.TimeoutException:
        return False, "玩具服务超时。玩具可能没开机，或者离电脑太远。"
    except Exception as e:  # noqa: BLE001
        return False, f"请求玩具服务失败：{type(e).__name__}"

    if r.status_code != 200:
        detail = ""
        try:
            detail = str(r.json().get("detail", ""))
        except Exception:  # noqa: BLE001
            detail = r.text[:200]
        if "not found" in detail.lower():
            return False, "没有扫描到玩具（SOSEXY）。确认玩具已开机、在电脑蓝牙范围内，并且手机上的官方 App 已经断开连接。"
        return False, f"玩具服务返回错误 {r.status_code}：{detail}"

    try:
        return True, str(r.json())
    except Exception:  # noqa: BLE001
        return True, "ok"


async def set_motor(kind: str, level) -> tuple[bool, str]:
    """kind: suction / vibration / electric"""
    if kind not in ("suction", "vibration", "electric"):
        return False, f"未知马达类型 {kind}"
    lv = clamp(level)
    ok, msg = await _post(f"/{kind}", {"level": lv})
    if ok:
        _last_state[kind] = lv
        return True, f"{kind} 已设为 {lv}"
    return False, msg


async def stop() -> tuple[bool, str]:
    # 停止不需要等扫描：设备没连上时本来也没东西可停
    ok, msg = await _post("/stop", timeout=5.0)
    if ok:
        for k in _last_state:
            _last_state[k] = 0
        return True, "所有马达已停止"
    return False, msg


async def status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(config.TOY_BASE_URL.rstrip("/") + "/status")
            return r.json()
    except Exception:  # noqa: BLE001
        return {"connected": False, "suction": 0, "vibration": 0, "electric": 0, "service": False}


def seed(state: dict) -> None:
    """进程刚启动时，用玩具服务的状态初始化本地缓存（避免界面显示“全 0”但其实还在转）。"""
    for k in _last_state:
        try:
            _last_state[k] = clamp(state.get(k, 0))
        except Exception:  # noqa: BLE001
            pass


def last_state() -> dict:
    return dict(_last_state)


def is_active() -> bool:
    return any(v > 0 for v in _last_state.values())
