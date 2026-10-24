"""AI 伴侣主服务：一个端口同时提供手机网页 + WebSocket + 控制接口。

启动：  .venv\\Scripts\\python.exe backend\\main.py
手机访问：http://<电脑局域网IP>:8000
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from logging.handlers import RotatingFileHandler

import uvicorn
from fastapi import FastAPI, File, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

import config
import memory
import moments
import profile
import push
import schedule
import toys
from llm import Companion
from timers import TimerManager

# ---------------- 日志 ----------------
log = logging.getLogger("companion")
log.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
_sh = logging.StreamHandler()
_sh.setFormatter(_fmt)
log.addHandler(_sh)
try:
    (config.BASE_DIR / "logs").mkdir(exist_ok=True)
    _fh = RotatingFileHandler(config.BASE_DIR / "logs" / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    _fh.setFormatter(_fmt)
    log.addHandler(_fh)
except Exception:  # noqa: BLE001
    pass


# ---------------- 连接管理 ----------------
class Hub:
    """手机端连接 + 离线消息队列。

    锁屏时浏览器会挂掉 WebSocket，这期间 AI 主动说的话先存起来，亮屏重连后补发。
    """

    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self.visible: set[WebSocket] = set()
        self.pending: list[dict] = []
        self._stop_task: asyncio.Task | None = None

    def has_visible(self) -> bool:
        """有没有正在亮屏看着的页面。没有就说明人不在看，该发推送了。"""
        return bool(self.visible)

    def set_visible(self, ws: WebSocket, visible: bool) -> None:
        if visible:
            self.visible.add(ws)
        else:
            self.visible.discard(ws)

    async def add(self, ws: WebSocket) -> None:
        self.clients.add(ws)
        self.cancel_stop()
        if self.pending:
            queued = self.pending[:]
            self.pending.clear()
            for item in queued:
                await self._safe_send(ws, item)

    def remove(self, ws: WebSocket) -> None:
        self.clients.discard(ws)
        self.visible.discard(ws)

    async def _safe_send(self, ws: WebSocket, payload: dict) -> bool:
        try:
            await ws.send_json(payload)
            return True
        except Exception:  # noqa: BLE001
            self.clients.discard(ws)
            return False

    async def broadcast(self, payload: dict) -> None:
        if not self.clients:
            if payload.get("type") == "message":
                self.pending.append(payload)
                del self.pending[:-50]  # 最多留 50 条
            return
        for ws in list(self.clients):
            await self._safe_send(ws, payload)

    # 断线兜底：全部断开持续 N 秒且玩具还在转，才停止
    def schedule_stop(self) -> None:
        if config.AUTO_STOP_AFTER_DISCONNECT <= 0:
            return
        if self._stop_task and not self._stop_task.done():
            return
        self._stop_task = asyncio.create_task(self._delayed_stop())

    async def _delayed_stop(self) -> None:
        try:
            await asyncio.sleep(config.AUTO_STOP_AFTER_DISCONNECT)
            if self.clients:
                return
            if toys.is_active():
                ok, msg = await toys.stop()
                log.warning("all clients gone %ss, auto-stop -> %s", config.AUTO_STOP_AFTER_DISCONNECT, msg)
                memory.append("system", f"手机端断开超时，已自动停止：{msg}")
        except asyncio.CancelledError:
            pass

    def cancel_stop(self) -> None:
        if self._stop_task and not self._stop_task.done():
            self._stop_task.cancel()
        self._stop_task = None


hub = Hub()


# ---------------- 定时器 → 主动开口 ----------------
async def on_timer_fire(reason: str, source: str = "timer") -> None:
    log.info("%s fired: %s", source, reason)
    await hub.broadcast({"type": "typing", "on": True})
    if source == "daily":
        hint = (
            f"到了每天的固定时间。你的意图：{reason}。"
            "现在主动开口，一两句话，自然一点，不要说「系统提醒」「定时器」这种话。"
            "结合你对她的了解，说一句只属于你们的话。"
        )
    else:
        hint = (
            f"你之前设的闹钟响了。原因：{reason}。"
            "现在请主动开口，一两句话，自然一点，别解释这是闹钟，也别提系统提示。"
            "如果合适，可以配合工具给她一个惊喜。"
        )
    text = await companion.chat(None, internal_hint=hint)
    memory.append("assistant", text, proactive=True, reason=reason, source=source)
    await hub.broadcast({"type": "typing", "on": False})
    await hub.broadcast({"type": "message", "role": "assistant", "text": text, "proactive": True})
    if not hub.has_visible():
        push.notify(text, profile.name())


# ---------------- 早安 / 哄睡（时间是她自己学来的） ----------------
async def daily_loop() -> None:
    log.info("作息表：%s", schedule.list_all() or "（空的，等她自己学）")
    fired: set[tuple] = set()
    while True:
        try:
            now = datetime.now()
            for kind, reason in schedule.due(now):
                key = (now.date(), kind, now.strftime("%H:%M"))
                if key in fired:
                    continue
                fired.add(key)
                log.info("到点：%s", kind)
                asyncio.create_task(on_timer_fire(reason, "daily"))
            if len(fired) > 40:
                fired = {k for k in fired if k[0] == now.date()}
        except Exception:  # noqa: BLE001
            log.exception("daily loop error")
        await asyncio.sleep(20)

timers = TimerManager(on_fire=on_timer_fire)
companion = Companion(timers)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("service up on %s:%s", config.HOST, config.PORT)
    push.init()
    if not config.DEEPSEEK_API_KEY:
        log.warning("DEEPSEEK_API_KEY 未配置，当前是测试回复模式")
    if not config.SAFE_WORD:
        log.warning("SAFE_WORD 为空，安全词功能未启用")
    log.info("推送订阅数：%d", push.count())
    try:
        st = await asyncio.wait_for(toys.status(), timeout=3)
        if st.get("connected"):
            toys.seed(st)
            log.info("已同步玩具当前状态：%s", toys.last_state())
    except Exception:  # noqa: BLE001
        log.info("玩具服务未就绪（不影响启动）")

    daily_task = asyncio.create_task(daily_loop())

    yield
    daily_task.cancel()
    timers.shutdown()
    try:
        await toys.stop()
    except Exception:  # noqa: BLE001
        pass


app = FastAPI(lifespan=lifespan)


# ---------------- 可选密码保护（只有把服务暴露到公网时才需要） ----------------
def _auth_token() -> str:
    return hashlib.sha256(("aipartner:" + config.ACCESS_PASSWORD).encode()).hexdigest()[:32]


_LOGIN_HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>她</title><style>
html,body{margin:0;height:100%;background:#0e070c;color:#f2e9ee;
font:16px/1.5 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;display:flex;
align-items:center;justify-content:center}
form{background:#160d14;border:1px solid #2a1c26;border-radius:18px;padding:26px 22px;width:260px}
h1{font-size:15px;font-weight:400;letter-spacing:.1em;color:#9b8794;margin:0 0 18px}
input{width:100%;box-sizing:border-box;background:#1a1018;border:1px solid #2a1c26;border-radius:12px;
color:#f2e9ee;padding:11px 13px;font:inherit;outline:0}
input:focus{border-color:#7d4a63}
button{margin-top:12px;width:100%;padding:11px;border:0;border-radius:12px;background:#d986a6;
color:#2a0f18;font:inherit;font-weight:600}
.err{color:#d18a99;font-size:13px;margin-top:10px;min-height:18px}
</style></head><body><form method="post" action="/login">
<h1>她</h1>
<input type="password" name="p" placeholder="密码" autofocus autocomplete="current-password">
<button type="submit">进去</button>
<div class="err">%s</div></form></body></html>"""


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if not config.ACCESS_PASSWORD:
        return await call_next(request)

    path = request.url.path
    if path == "/login" or path.startswith("/icon") or path == "/favicon.ico":
        return await call_next(request)
    if request.cookies.get("k") == _auth_token():
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    return RedirectResponse("/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(e: int = 0):
    return HTMLResponse(_LOGIN_HTML % ("密码不对" if e else ""))


@app.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    if str(form.get("p", "")) == config.ACCESS_PASSWORD:
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie("k", _auth_token(), max_age=30 * 86400, httponly=True, samesite="lax")
        return resp
    return RedirectResponse("/login?e=1", status_code=303)


# ---------------- HTTP 接口 ----------------
@app.get("/api/health")
async def health():
    return {"ok": True, "model": config.DEEPSEEK_MODEL, "api_key": bool(config.DEEPSEEK_API_KEY)}


@app.get("/api/state")
async def state():
    try:
        svc = await asyncio.wait_for(toys.status(), timeout=2.5)
    except Exception:  # noqa: BLE001
        svc = {"connected": False, "service": False}
    # 马达档位以本地“写成功过”的值为准：玩具服务的 /status 在写入失败时也会返回新值，不可信
    toy = {"connected": bool(svc.get("connected")), **toys.last_state()}
    return {
        "toy": toy,
        "service": bool(svc.get("connected")),
        "local": toys.last_state(),
        "timers": timers.list(),
        "safe_word_enabled": bool(config.SAFE_WORD),
        "auto_stop": config.AUTO_STOP_AFTER_DISCONNECT,
        "name": profile.name(),
    }


@app.post("/api/stop")
async def api_stop():
    """网页上的红色按钮走这里，不依赖 WebSocket 是否还活着。"""
    ok, msg = await toys.stop()
    await timers.cancel_all()
    log.info("manual stop -> %s", msg)
    await hub.broadcast({"type": "state", "toy": {"connected": ok, **toys.last_state()}, "stopped": True})
    return JSONResponse({"ok": ok, "message": msg})


# ---------------- 推送 ----------------
@app.get("/api/push/key")
async def push_key():
    return {"key": push.public_key(), "enabled": bool(push.public_key())}


@app.post("/api/push/subscribe")
async def push_subscribe(sub: dict):
    n = push.add_subscription(sub)
    return {"ok": True, "count": n}


@app.post("/api/push/unsubscribe")
async def push_unsubscribe(body: dict):
    n = push.remove_subscription(body.get("endpoint", ""))
    return {"ok": True, "count": n}


@app.post("/api/push/test")
async def push_test():
    sent = push.notify("这是一条测试通知，看到就说明推送通了。", profile.name())
    return {"ok": sent > 0, "sent": sent}


# ---------------- 界面数据 ----------------
_STARTED_AT = time.time()


@app.get("/api/history")
async def api_history(limit: int = 80):
    return {"records": memory.recent_records(max(1, min(limit, 500)))}


@app.post("/api/history/clear")
async def api_history_clear():
    return {"ok": True, "cleared": memory.clear()}


@app.get("/api/persona")
async def api_persona_get():
    return {
        "text": config.SYSTEM_PROMPT,
        "default_text": config.DEFAULT_PERSONA,
        "is_custom": config.PERSONA_FILE.exists(),
    }


@app.get("/api/profile")
async def api_profile_get():
    return profile.load()


@app.post("/api/profile")
async def api_profile_set(body: dict):
    allowed = {k: v for k, v in body.items() if k in ("name", "user_name", "agreement", "onboarded")}
    if "name" in allowed:
        allowed["name"] = str(allowed["name"]).strip()[:24] or "她"
    profile.update(**allowed)
    return profile.load()


@app.delete("/api/profile/facts/{key}")
async def api_profile_forget(key: str):
    profile.forget(key)
    return profile.load()


@app.post("/api/persona")
async def api_persona_set(body: dict):
    config.save_persona(body.get("text", ""))
    return {"ok": True, "is_custom": config.PERSONA_FILE.exists()}


UPLOAD_DIR = config.DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "img.jpg")[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        ext = ".jpg"
    data = await file.read()
    if len(data) > 12 * 1024 * 1024:
        return JSONResponse({"ok": False, "error": "图片太大（上限 12MB）"}, status_code=413)
    name = f"{int(time.time())}_{uuid.uuid4().hex[:6]}{ext}"
    (UPLOAD_DIR / name).write_bytes(data)
    return {"ok": True, "url": f"/uploads/{name}"}


@app.get("/api/contract")
async def api_contract():
    return {
        "sections": profile.contract_lines(),
        "name": profile.name(),
        "user_name": profile.load().get("user_name", ""),
        "updated": profile.load().get("updated", ""),
    }


@app.post("/api/contract")
async def api_contract_set(body: dict):
    ok, msg = profile.set_contract_section(body.get("section", ""), body.get("text", ""))
    return {"ok": ok, "message": msg, "sections": profile.contract_lines()}


@app.get("/api/moments")
async def api_moments():
    return {"items": moments.load(300)}


@app.post("/api/moments")
async def api_moment_add(body: dict):
    item = moments.append(body.get("title", ""), body.get("note", ""), body.get("image", ""))
    return {"ok": True, "item": item}


@app.delete("/api/moments/{ts}")
async def api_moment_del(ts: str):
    return {"ok": moments.delete(ts)}


@app.get("/api/overview")
async def api_overview():
    try:
        svc = await asyncio.wait_for(toys.status(), timeout=2.5)
    except Exception:  # noqa: BLE001
        svc = {"connected": False}
    return {
        "service": {
            "ai": True,
            "toy": bool(svc.get("connected")),
            "uptime": int(time.time() - _STARTED_AT),
            "api_key": bool(config.DEEPSEEK_API_KEY),
            "model": config.DEEPSEEK_MODEL,
            "clients": len(hub.clients),
            "visible": hub.has_visible(),
            "push_subs": push.count(),
            "safe_word": bool(config.SAFE_WORD),
            "auto_stop": config.AUTO_STOP_AFTER_DISCONNECT,
        },
        "name": profile.name(),
        "onboarded": bool(profile.load().get("onboarded")),
        "motors": toys.last_state(),
        "timers": timers.list(),
        "daily": schedule.list_all(),
        "history_size": len(memory.recent_records(100000)),
    }


# ---------------- WebSocket ----------------
_WS_RE = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS_RE.sub("", text or "").strip().lower()


def is_safe_word(text: str) -> bool:
    if not config.SAFE_WORD:
        return False
    return _norm(text) == _norm(config.SAFE_WORD)


# 她说要离开一会儿 → 强制提醒模型安排定时消息，不完全依赖它自觉
_LEAVE_RE = re.compile(
    r"(去洗澡|洗个澡|洗澡去|去冲个澡|去洗漱|我去忙|先忙|忙一下|出门了|我出门|要出门|"
    r"去开会|上班了|要去睡|先睡了|先躺|去收拾|下楼|去上班)"
)


def _leave_hint(text: str) -> str:
    if not _LEAVE_RE.search(text):
        return ""
    return (
        "她刚刚说她要去忙、要离开一会儿。"
        "你现在就应该用 set_timer 安排 1-2 条稍后发出的消息（例如 8 分钟、15 分钟各一条），"
        "内容要具体、像只有你们懂的话。不要告诉她自己设了定时。"
    )


# 敷衍的两个字、深夜不睡 —— 这类情况要她「有脾气」，不能第一句就软
_LAZY = {"嗯", "嗯嗯", "哦", "哦哦", "随便", "随便吧", "都行", "都行吧", "知道了", "行吧", "好吧", "哦好", "你定"}
_LATE_RE = re.compile(r"(熬夜|还没睡|没睡|睡不着|又刷|三点|两点|四点|一点)")


def _style_hint(text: str) -> str:
    hints: list[str] = []
    t = _norm(text)

    if t in _LAZY:
        hints.append(
            "她只回了很敷衍的两个字。这一轮不要哄，回一句短的、有点冷的话"
            "（比如「我不喜欢这个字。」「嗯。」「想清楚再跟我说。」），"
            "说完就停，不要追问，不要接着安慰。把话头留给她。"
        )

    now = datetime.now()
    if now.hour in (0, 1, 2, 3, 4, 5) and _LATE_RE.search(text):
        hints.append(
            "这个点她还没睡。不要温柔哄，语气冷一点，一句话说完就停，不要追着劝。"
            "（这是提醒过之后的反应，不是第一次。）"
        )

    return " ".join(hints)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    if config.ACCESS_PASSWORD and ws.cookies.get("k") != _auth_token():
        await ws.close(code=4401)
        return
    await ws.accept()
    await hub.add(ws)
    log.info("client connected (%d online)", len(hub.clients))

    await ws.send_json({"type": "ready", "safe_word_enabled": bool(config.SAFE_WORD)})

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {"type": "text", "text": raw}

            kind = data.get("type", "text")

            if kind == "ping":
                await ws.send_json({"type": "pong"})
                continue

            if kind == "focus":
                hub.set_visible(ws, bool(data.get("visible")))
                continue

            if kind == "stop":
                await toys.stop()
                await timers.cancel_all()
                await hub.broadcast({"type": "state", "toy": toys.last_state(), "stopped": True})
                continue

            if kind == "image":
                url = (data.get("url") or "").strip()
                caption = (data.get("caption") or "").strip()
                if not url.startswith("/uploads/"):
                    continue
                shown = caption or "[发来一张图片]"
                memory.append("user", caption or "[图片]", image=url)
                await hub.broadcast({"type": "message", "role": "user", "text": shown, "image": url, "echo": True})
                await hub.broadcast({"type": "typing", "on": True})
                reply = await companion.chat(
                    f"她给你发了一张图片。她配的文字是：{caption or '（没有配文字）'}。"
                    "你看不到图片内容，但可以回应她发图这件事本身，不要假装看见了细节。",
                    internal_hint="",
                )
                memory.append("assistant", reply)
                await hub.broadcast({"type": "typing", "on": False})
                await hub.broadcast({"type": "message", "role": "assistant", "text": reply})
                if not hub.has_visible():
                    push.notify(reply, profile.name())
                continue

            text = (data.get("text") or "").strip()
            if not text:
                continue

            # 安全词：绕过模型直接停
            if is_safe_word(text):
                await toys.stop()
                await timers.cancel_all()
                memory.append("user", text, safe_word=True)
                reply = "已经停了，我在。"
                memory.append("assistant", reply, safe_word_reply=True)
                await hub.broadcast({"type": "message", "role": "assistant", "text": reply})
                log.warning("safe word triggered")
                continue

            memory.append("user", text)
            await hub.broadcast({"type": "message", "role": "user", "text": text, "echo": True})
            await hub.broadcast({"type": "typing", "on": True})

            reply = await companion.chat(text, internal_hint=(_leave_hint(text) + " " + _style_hint(text)).strip())

            memory.append("assistant", reply)
            await hub.broadcast({"type": "typing", "on": False})
            await hub.broadcast({"type": "message", "role": "assistant", "text": reply})

            # 人不在看（锁屏 / 切走了），补一条手机通知
            if not hub.has_visible():
                push.notify(reply, profile.name())

    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        log.exception("websocket error")
    finally:
        hub.remove(ws)
        log.info("client disconnected (%d online)", len(hub.clients))
        if not hub.clients:
            hub.schedule_stop()


# 静态页面放最后挂载，前面的 /api 和 /ws 优先匹配
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info", access_log=False)
