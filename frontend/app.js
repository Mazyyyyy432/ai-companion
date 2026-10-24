/* 手机端：历史记录、时间戳、实时消息、断线重连、推送。
   原则：界面只显示后端确认过的事实，不猜状态。 */

const $ = (id) => document.getElementById(id);
const stream = $("stream");
const input = $("input");
const sendBtn = $("send");
const dot = $("dot");
const chips = $("chips");
const offline = $("offline");
const emptyEl = $("empty");

const state = { ws: null, retry: 0, typingEl: null, lastStampTs: 0, lastDay: "" };

const TOOL_LABEL = {
  toy_suck: "吮吸",
  toy_vibrate: "震动",
  toy_electric: "电流",
  toy_stop: "停止",
  set_timer: "设定定时",
  list_timers: "查看定时",
  cancel_timers: "取消定时",
};

/* ---------------- 时间格式 ---------------- */
function pad(n) { return String(n).padStart(2, "0"); }
function fmtTime(iso) {
  const d = new Date(iso);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function dayKey(d) {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}
function dayLabel(iso) {
  const d = new Date(iso);
  const now = new Date();
  if (dayKey(d) === dayKey(now)) return "今天";
  const y = new Date(now);
  y.setDate(now.getDate() - 1);
  if (dayKey(d) === dayKey(y)) return "昨天";
  return `${d.getMonth() + 1} 月 ${d.getDate()} 日`;
}

/* ---------------- 渲染 ---------------- */
function addDay(iso) {
  const k = dayKey(new Date(iso));
  if (k === state.lastDay) return;
  state.lastDay = k;
  const el = document.createElement("div");
  el.className = "day";
  el.textContent = dayLabel(iso);
  stream.appendChild(el);
}

function addMsg(text, who, iso, image) {
  const ts = iso || new Date().toISOString();
  addDay(ts);
  const el = document.createElement("div");
  el.className = `msg ${who}${image ? " hasimg" : ""}`;
  if (image) {
    const img = document.createElement("img");
    img.src = image;
    img.loading = "lazy";
    img.alt = "";
    el.appendChild(img);
    if (text && text !== "[图片]") {
      const cap = document.createElement("div");
      cap.textContent = text;
      el.appendChild(cap);
    }
  } else {
    el.textContent = text;
  }
  stream.appendChild(el);

  // 时间戳只在间隔较久时出现，避免每条都挂一个
  const t = new Date(ts).getTime();
  if (!state.lastStampTs || t - state.lastStampTs > 4 * 60 * 1000) {
    const s = document.createElement("div");
    s.className = "stamp" + (who === "me" ? " right" : "");
    s.textContent = fmtTime(ts);
    stream.appendChild(s);
    state.lastStampTs = t;
  }
  scrollDown();
}

function addTool(rec) {
  const name = (rec.meta && rec.meta.tool) || "工具";
  const el = document.createElement("div");
  el.className = "toolnote";
  el.innerHTML = `⚙ <b>${TOOL_LABEL[name] || name}</b>`;
  el.title = rec.content || "";
  stream.appendChild(el);
  state.lastStampTs = 0;
}

function toggleEmpty() {
  const has = stream.querySelector(".msg");
  if (emptyEl) emptyEl.style.display = has ? "none" : "block";
}

function scrollDown() {
  stream.scrollTo({ top: stream.scrollHeight, behavior: "smooth" });
}

function setTyping(on) {
  if (on && !state.typingEl) {
    const el = document.createElement("div");
    el.className = "msg her typing";
    el.innerHTML = "<i></i><i></i><i></i>";
    stream.appendChild(el);
    state.typingEl = el;
    scrollDown();
  } else if (!on && state.typingEl) {
    state.typingEl.remove();
    state.typingEl = null;
  }
}

function renderChips(toy) {
  const map = { suction: "吮", vibration: "震", electric: "电" };
  const parts = [];
  for (const [k, label] of Object.entries(map)) {
    const v = Number((toy && toy[k]) || 0);
    if (v > 0) parts.push(`${label}${v}`);
  }
  chips.innerHTML = "";
  for (const p of parts) {
    const c = document.createElement("span");
    c.className = "chip";
    c.textContent = p;
    chips.appendChild(c);
  }
}

/* ---------------- 历史 ---------------- */
async function syncHistory() {
  try {
    const r = await fetch("/api/history?limit=150", { cache: "no-store" });
    if (r.status === 401) { location.href = "/login"; return; }
    const d = await r.json();

    stream.querySelectorAll(".msg, .day, .stamp, .toolnote, .sysnote").forEach((e) => e.remove());
    state.lastStampTs = 0;
    state.lastDay = "";

    for (const rec of d.records || []) {
      if (rec.role === "user") addMsg(rec.content, "me", rec.ts, rec.meta && rec.meta.image);
      else if (rec.role === "assistant") addMsg(rec.content, "her", rec.ts);
      else if (rec.role === "tool") addTool(rec);
      else if (rec.role === "system") {
        const el = document.createElement("div");
        el.className = "sysnote";
        el.textContent = rec.content;
        stream.appendChild(el);
      }
    }
    toggleEmpty();
    scrollDown();
  } catch (e) {
    console.warn("history failed", e);
  }
}

async function refreshState() {
  try {
    const r = await fetch("/api/state", { cache: "no-store" });
    if (r.status === 401) { location.href = "/login"; return; }
    const d = await r.json();
    renderChips(d.toy || d.local || {});
    applyName(d.name);
  } catch {}
}

let currentName = "";
function applyName(name) {
  if (!name || name === currentName) return;
  currentName = name;
  document.title = name;
  const el = document.querySelector(".name");
  if (el) el.textContent = name;
  const apple = document.querySelector('meta[name="apple-mobile-web-app-title"]');
  if (apple) apple.setAttribute("content", name);
}

/* ---------------- 连接 ---------------- */
function wsUrl() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/ws`;
}

function connect() {
  try {
    state.ws = new WebSocket(wsUrl());
  } catch {
    scheduleRe
/* ---------------- 图片 ---------------- */
let pendingImage = "";

function clearPreview() {
  pendingImage = "";
  $("preview").hidden = true;
  $("previewImg").removeAttribute("src");
  $("file").value = "";
}

$("attachBtn").addEventListener("click", () => $("file").click());

$("previewClear").addEventListener("click", clearPreview);

$("file").addEventListener("change", async () => {
  const f = $("file").files && $("file").files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append("file", f);
  try {
    const r = await fetch("/api/upload", { method: "POST", body: fd });
    const d = await r.json();
    if (d.url) {
      pendingImage = d.url;
      $("previewImg").src = d.url;
      $("preview").hidden = false;
    }
  } catch (e) {
    console.warn("upload failed", e);
  }
});

/* ---------------- 菜单 ---------------- */
$("menuBtn").addEventListener("click", () => {
  $("menu").hidden = !$("menu").hidden;
});

document.addEventListener("click", (e) => {
  const m = $("menu");
  if (!m.hidden && !m.contains(e.target) && e.target.id !== "menuBtn") m.hidden = true;
});

$("menuPush").addEventListener("click", () => {
  $("menu").hidden = true;
  $("bell").click();
});

connect();
    return;
  }

  state.ws.onopen = () => {
    state.retry = 0;
    dot.dataset.s = "on";
    offline.classList.remove("show");
    sendBtn.disabled = false;
    sendFocus(true);
    syncHistory();
    refreshState();
  };

  state.ws.onmessage = (ev) => {
    let d;
    try { d = JSON.parse(ev.data); } catch { return; }
    handle(d);
  };

  state.ws.onclose = () => {
    dot.dataset.s = "off";
    sendBtn.disabled = true;
    offline.textContent = "和电脑断开了，正在重连…";
    offline.classList.add("show");
    scheduleReconnect();
  };

  state.ws.onerror = () => { try { state.ws.close(); } catch {} };
}

function scheduleReconnect() {
  state.retry = Math.min(state.retry + 1, 6);
  setTimeout(connect, Math.min(500 * 2 ** (state.retry - 1), 8000));
}

function handle(d) {
  switch (d.type) {
    case "message":
      if (d.echo) {
        addMsg(d.text, "me", null, d.image);
      } else {
        setTyping(false);
        addMsg(d.text, "her");
      }
      toggleEmpty();
      break;
    case "typing":
      setTyping(!!d.on);
      break;
    case "state":
      renderChips(d.toy || {});
      break;
  }
}

/* ---------------- 发送 / 停止 ---------------- */
function send() {
  const text = input.value.trim();
  if (pendingImage) {
    if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
    state.ws.send(JSON.stringify({ type: "image", url: pendingImage, caption: text }));
    clearPreview();
    input.value = "";
    autosize();
    return;
  }
  if (!text) return;
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    offline.textContent = "还没连上电脑，等一下再发";
    offline.classList.add("show");
    return;
  }
  state.ws.send(JSON.stringify({ type: "text", text }));
  input.value = "";
  autosize();
}

function autosize() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 128) + "px";
}

sendBtn.addEventListener("click", send);

input.addEventListener("input", autosize);

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    send();
  }
});

$("stopBtn").addEventListener("click", async () => {
  try { await fetch("/api/stop", { method: "POST" }); } catch {}
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify({ type: "stop" }));
  }
  chips.innerHTML = "";
  const el = document.createElement("div");
  el.className = "sysnote";
  el.textContent = "已停止";
  stream.appendChild(el);
  scrollDown();
});

/* ---------------- 前台/后台 ---------------- */
function sendFocus(visible) {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify({ type: "focus", visible }));
  }
}

document.addEventListener("visibilitychange", () => {
  const visible = document.visibilityState === "visible";
  sendFocus(visible);
  if (visible) {
    if (!state.ws || state.ws.readyState === WebSocket.CLOSED) {
      state.retry = 0;
      connect();
    } else {
      refreshState();
    }
  }
});

window.addEventListener("online", () => {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    state.retry = 0;
    connect();
  }
});

/* ---------------- 推送 ---------------- */
const bell = $("bell");
const secureOK =
  location.protocol === "https:" ||
  location.hostname === "localhost" ||
  location.hostname === "127.0.0.1";

function b64ToU8(s) {
  const pad = "=".repeat((4 - (s.length % 4)) % 4);
  const raw = atob((s + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

async function initPush({ interactive = false } = {}) {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    if (interactive) addMsg("这个浏览器不支持网页通知。", "her");
    return;
  }
  if (!secureOK) {
    if (interactive) {
      addMsg("通知只能在 HTTPS 下开启。现在用的是局域网 http 地址，浏览器不给授权。", "her");
    }
    return;
  }
  try {
    const reg = await navigator.serviceWorker.register("/sw.js");
    await navigator.serviceWorker.ready;

    let perm = Notification.permission;
    if (perm === "default" && interactive) perm = await Notification.requestPermission();
    if (perm !== "granted") {
      if (interactive) addMsg("没拿到通知权限，去系统设置里给它打开。", "her");
      return;
    }

    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      const { key } = await (await fetch("/api/push/key")).json();
      if (!key) return;
      sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToU8(key) });
    }
    await fetch("/api/push/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sub),
    });
    bell.dataset.on = "1";
    bell.title = "通知已开启";
    if (interactive) {
      addMsg("通知开好了。锁屏也能收到。", "her");
      await fetch("/api/push/test", { method: "POST" });
    }
  } catch (e) {
    console.error(e);
    if (interactive) addMsg("开通知失败：" + (e && e.message ? e.message : e), "her");
  }
}

bell.addEventListener("click", () => initPush({ interactive: true }));

if (secureOK && typeof Notification !== "undefined" && Notification.permission === "granted") {
  initPush();
}

connect();
