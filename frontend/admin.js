/* 电脑端控制台：状态、历史（含工具调用）、人设编辑。 */

const $ = (id) => document.getElementById(id);

const TOOL_LABEL = {
  toy_suck: "吮吸",
  toy_vibrate: "震动",
  toy_electric: "电流",
  toy_stop: "全部停止",
  set_timer: "设定定时",
  list_timers: "查看定时",
  cancel_timers: "取消定时",
};

let records = [];

function pad(n) { return String(n).padStart(2, "0"); }

function fmtTime(iso) {
  const d = new Date(iso);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fmtDur(sec) {
  if (sec < 60) return `${sec} 秒`;
  const m = Math.floor(sec / 60);
  if (m < 60) return `${m} 分钟`;
  return `${Math.floor(m / 60)} 小时 ${m % 60} 分`;
}

function toast(msg, bad = false) {
  const el = $("toast");
  el.textContent = msg;
  el.style.color = bad ? "#d5a2ab" : "#9fd0b4";
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.textContent = ""; }, 3500);
}

/* ---------------- 状态 ---------------- */
async function refresh() {
  try {
    const r = await fetch("/api/overview", { cache: "no-store" });
    if (r.status === 401) { location.href = "/login"; return; }
    const d = await r.json();
    const s = d.service;
    const m = d.motors || {};

    $("dot").dataset.s = s.ai ? "on" : "off";

    const pills = [
      { ok: s.ai, text: "AI 服务" },
      { ok: s.toy, text: s.toy ? "蓝牙已连接" : "蓝牙未连接" },
      { text: `页面 ${s.clients}` },
      { text: `推送 ${s.push_subs}` },
    ];
    $("pills").innerHTML = pills
      .map((p) => `<span class="pill ${p.ok === undefined ? "" : p.ok ? "ok" : "bad"}"><i></i>${p.text}</span>`)
      .join("");

    const rows = [
      ["模型", s.model, ""],
      ["API Key", s.api_key ? "已配置" : "未配置", s.api_key ? "ok" : "bad"],
      ["玩具连接", s.toy ? "已连接" : "未连接", s.toy ? "ok" : "bad"],
      ["在线页面", `${s.clients} 个${s.visible ? "（正在看）" : ""}`, ""],
      ["推送订阅", `${s.push_subs} 个`, s.push_subs ? "ok" : ""],
      ["安全词", s.safe_word ? "已启用" : "未设置", s.safe_word ? "ok" : "bad"],
      ["断线自停", s.auto_stop ? `${s.auto_stop} 秒` : "已关闭", ""],
      ["已运行", fmtDur(s.uptime), ""],
      ["历史条数", d.history_size, ""],
    ];
    $("status").innerHTML = rows
      .map(([k, v, cls]) => `<dt>${k}</dt><dd class="${cls}">${v}</dd>`)
      .join("");

    const motors = [
      ["吮吸", m.suction || 0],
      ["震动", m.vibration || 0],
      ["电流", m.electric || 0],
    ];
    $("motors").innerHTML = motors
      .map(
        ([name, v]) => `<div class="motor"><span>${name}</span>
        <span class="bar"><i style="width:${Math.min(100, v)}%"></i></span>
        <b>${v}</b></div>`
      )
      .join("");

    $("timerCount").textContent = d.timers.length ? `(${d.timers.length})` : "";
    $("timers").innerHTML = d.timers.length
      ? d.timers.map((t) => `<li>${t.fire_at} · ${t.reason}</li>`).join("")
      : `<li class="none">没有等待中的定时器</li>`;
  } catch (e) {
    console.warn(e);
  }
}

/* ---------------- 历史 ---------------- */
async function loadHistory() {
  try {
    const r = await fetch("/api/history?limit=300", { cache: "no-store" });
    if (r.status === 401) { location.href = "/login"; return; }
    const d = await r.json();
    records = d.records || [];
    renderHistory();
  } catch (e) {
    console.warn(e);
  }
}

function renderHistory() {
  const q = $("search").value.trim().toLowerCase();
  const showTools = $("showTools").checked;

  const filtered = records.filter((rec) => {
    if (!showTools && rec.role === "tool") return false;
    if (!showTools && rec.role === "system") return false;
    if (!q) return true;
    const hay = `${rec.content || ""} ${JSON.stringify(rec.meta || {})}`.toLowerCase();
    return hay.includes(q);
  });

  $("hcount").textContent = `(${filtered.length})`;

  if (!filtered.length) {
    $("list").innerHTML = `<div class="empty">还没有记录</div>`;
    return;
  }

  const roleLabel = { user: "我", assistant: "她", tool: "工具", system: "系统" };

  $("list").innerHTML = filtered
    .map((rec) => {
      const role = rec.role || "system";
      let text = rec.content || "";
      let extra = "";

      if (role === "tool") {
        const name = (rec.meta && rec.meta.tool) || "tool";
        const args = rec.meta && rec.meta.args ? JSON.stringify(rec.meta.args) : "";
        extra = `<div class="args">${TOOL_LABEL[name] || name} ${args}</div>`;
        text = `<span class="args">→ </span>${escapeHtml(text)}`;
        return `<div class="rec" data-role="${role}">
          <span class="t">${fmtTime(rec.ts)}</span>
          <span class="role">${roleLabel[role] || role}</span>
          <span class="txt">${text}${extra}</span>
        </div>`;
      }

      return `<div class="rec" data-role="${role}">
        <span class="t">${fmtTime(rec.ts)}</span>
        <span class="role">${roleLabel[role] || role}</span>
        <span class="txt">${escapeHtml(text)}</span>
      </div>`;
    })
    .join("");
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/* ---------------- 人设 ---------------- */
async function loadPersona() {
  try {
    const r = await fetch("/api/persona", { cache: "no-store" });
    if (r.status === 401) { location.href = "/login"; return; }
    const d = await r.json();
    $("personaText").value = d.text;
    $("personaState").textContent = d.is_custom
      ? "当前使用自定义人设（data/persona.txt）"
      : "当前使用内置默认人设";
  } catch (e) {
    console.warn(e);
  }
}

async function savePersona(text) {
  const r = await fetch("/api/persona", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const d = await r.json();
  $("personaState").textContent = d.is_custom
    ? "已保存，下一次对话生效"
    : "已恢复默认人设，下一次对话生效";
  toast("保存成功");
}

/* ---------------- 事件 ---------------- */
$("refresh").addEventListener("click", () => { refresh(); loadHistory(); loadPersona(); });

$("stopAll").addEventListener("click", async () => {
  const r = await fetch("/api/stop", { method: "POST" });
  const d = await r.json();
  toast(d.ok ? "已全部停止" : "停止失败：" + (d.message || ""), !d.ok);
  refresh();
});

$("testPush").addEventListener("click", async () => {
  const r = await fetch("/api/push/test", { method: "POST" });
  const d = await r.json();
  toast(d.sent ? `已推送 ${d.sent} 条` : "没有可用的推送订阅（需要 HTTPS + 在手机上开通知）", !d.sent);
});

$("clearHistory").addEventListener("click", async () => {
  if (!confirm("确定清空全部聊天记录？这个不能撤销。")) return;
  const r = await fetch("/api/history/clear", { method: "POST" });
  const d = await r.json();
  toast(`已清空 ${d.cleared} 条`);
  loadHistory();
  refresh();
});

$("savePersona").addEventListener("click", () => savePersona($("personaText").value));

$("resetPersona").addEventListener("click", async () => {
  if (!confirm("恢复成内置默认人设？当前的自定义内容会被删除。")) return;
  await savePersona("");
  loadPersona();
});

$("search").addEventListener("input", renderHistory);
$("showTools").addEventListener("change", renderHistory);

/* ---------------- 资料 ---------------- */
async function loadProfile() {
  try {
    const r = await fetch("/api/profile", { cache: "no-store" });
    if (r.status === 401) { location.href = "/login"; return; }
    const d = await r.json();

    $("pName").value = d.name || "";
    $("pUser").value = d.user_name || "";
    $("pAgreement").value = d.agreement || "";
    $("onboardState").textContent = d.onboarded
      ? "已完成初次认识"
      : "还没进行初次见面（她会主动了解你）";

    if (d.name) {
      $("brandName").textContent = d.name;
      document.title = `${d.name} · 控制台`;
    }

    const facts = d.facts || {};
    const keys = Object.keys(facts);
    $("pFacts").innerHTML = keys.length
      ? keys
          .map(
            (k) =>
              `<span class="fact" data-k="${escapeHtml(k)}" title="点一下删除"><b>${escapeHtml(k)}</b> ${escapeHtml(
                String(facts[k]).slice(0, 20)
              )}</span>`
          )
          .join("")
      : `<span class="hint">还没有记下任何事</span>`;
  } catch (e) {
    console.warn(e);
  }
}

async function saveProfile() {
  await fetch("/api/profile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: $("pName").value.trim() || "她",
      user_name: $("pUser").value.trim(),
      agreement: $("pAgreement").value,
    }),
  });
  toast("资料已保存");
  loadProfile();
  refresh();
}

$("saveProfile").addEventListener("click", saveProfile);

$("pFacts").addEventListener("click", async (e) => {
  const chip = e.target.closest(".fact");
  if (!chip) return;
  const key = chip.dataset.k;
  if (!confirm(`忘掉「${key}」？`)) return;
  await fetch(`/api/profile/facts/${encodeURIComponent(key)}`, { method: "DELETE" });
  loadProfile();
});

/* ---------------- 启动 ---------------- */
refresh();
loadHistory();
loadPersona();
loadProfile();
setInterval(refresh, 5000);
setInterval(loadHistory, 20000);
