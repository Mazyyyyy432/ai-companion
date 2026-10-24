"""Web Push：手机锁屏/App 关掉也能收到 AI 的消息。

前提是页面必须跑在 HTTPS 下（Tailscale 的证书或隧道都行），http 局域网地址浏览器不给推送权限。
没装 pywebpush 或没有 HTTPS 时，这里全部静默失败，不影响聊天。
"""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

import config

log = logging.getLogger("companion")

_SUB_FILE = config.DATA_DIR / "push_subscriptions.json"
_KEY_FILE = config.DATA_DIR / "vapid_private.pem"

try:
    from py_vapid import Vapid
    from pywebpush import WebPushException, webpush

    HAVE_PUSH = True
except Exception:  # noqa: BLE001
    HAVE_PUSH = False
    log.warning("pywebpush 不可用，推送功能关闭")


_vapid = None
_public_key_b64 = ""


def _load_or_create_keys() -> None:
    global _vapid, _public_key_b64
    if not HAVE_PUSH:
        return
    try:
        if _KEY_FILE.exists():
            _vapid = Vapid.from_file(str(_KEY_FILE))
        else:
            _vapid = Vapid()
            _vapid.generate_keys()
            _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
            _vapid.save_key(str(_KEY_FILE))
            log.info("已生成新的 VAPID 密钥：%s", _KEY_FILE)

        numbers = _vapid.public_key.public_numbers()
        raw = b"\x04" + numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")
        _public_key_b64 = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    except Exception:  # noqa: BLE001
        log.exception("VAPID 密钥初始化失败")


def public_key() -> str:
    return _public_key_b64


def init() -> None:
    _load_or_create_keys()


def _load_subs() -> list[dict]:
    if not _SUB_FILE.exists():
        return []
    try:
        return json.loads(_SUB_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def _save_subs(subs: list[dict]) -> None:
    _SUB_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SUB_FILE.write_text(json.dumps(subs, ensure_ascii=False, indent=1), encoding="utf-8")


def add_subscription(sub: dict) -> int:
    if not sub or not sub.get("endpoint"):
        return len(_load_subs())
    subs = _load_subs()
    endpoint = sub["endpoint"]
    subs = [s for s in subs if s.get("endpoint") != endpoint]
    subs.append(sub)
    _save_subs(subs)
    log.info("新增推送订阅，共 %d 个", len(subs))
    return len(subs)


def remove_subscription(endpoint: str) -> int:
    subs = [s for s in _load_subs() if s.get("endpoint") != endpoint]
    _save_subs(subs)
    return len(subs)


def count() -> int:
    return len(_load_subs())


def notify(body: str, title: str = "她") -> int:
    """给所有订阅端推送。返回成功条数。"""
    if not HAVE_PUSH or _vapid is None:
        return 0
    subs = _load_subs()
    if not subs:
        return 0

    payload = json.dumps({"title": title, "body": body[:180], "url": "/"}, ensure_ascii=False)
    dead: list[str] = []
    sent = 0

    for sub in subs:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=str(_KEY_FILE),
                vapid_claims={"sub": "mailto:me@localhost"},
                timeout=10,
            )
            sent += 1
        except WebPushException as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (404, 410):
                dead.append(sub.get("endpoint", ""))
            else:
                log.warning("推送失败：%s", e)
        except Exception as e:  # noqa: BLE001
            log.warning("推送异常：%s", e)

    if dead:
        kept = [s for s in subs if s.get("endpoint") not in dead]
        _save_subs(kept)
        log.info("清理失效订阅 %d 个", len(dead))

    return sent
