"""大模型对话 + 工具调用。

一次「回合」= 发消息给 DeepSeek，模型可能连续调用多个工具，最后给出文本。
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from openai import AsyncOpenAI

import config
import memory
import profile
import toys

log = logging.getLogger("companion")

_WEEK = "一二三四五六日"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "toy_suck",
            "description": "控制玩具的吮吸马达。level 0-100，0 表示停止。",
            "parameters": {
                "type": "object",
                "properties": {"level": {"type": "integer", "description": "强度 0-100"}},
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "toy_vibrate",
            "description": "控制玩具的震动马达。level 0-100，0 表示停止。",
            "parameters": {
                "type": "object",
                "properties": {"level": {"type": "integer", "description": "强度 0-100"}},
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "toy_electric",
            "description": "控制玩具的电流刺激马达。level 0-100，0 表示停止。电流体感比较特别，从很低的数值开始。",
            "parameters": {
                "type": "object",
                "properties": {"level": {"type": "integer", "description": "强度 0-100"}},
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "toy_stop",
            "description": "立刻停止所有马达。她说停、或者你想暂停时用。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_timer",
            "description": "设定「过多少分钟之后再主动开口」。用来制造间隔和期待感，比如她说想被撩一会儿不说话。",
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {"type": "number", "description": "多少分钟后开口"},
                    "reason": {"type": "string", "description": "到时候要说什么/做什么的一句话备忘"},
                },
                "required": ["minutes", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_timers",
            "description": "查看当前还没触发的定时器。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_timers",
            "description": "取消所有定时器。定时器满了的时候用它清空。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "永久记住关于她的一个事实。适合记：称呼、边界、雷区、喜欢的方式、身体反应、约定。",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "简短标签，比如「称呼」「绝对不要」"},
                    "value": {"type": "string", "description": "具体内容"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_agreement",
            "description": "把你们谈好的关系约定（边界、安全词、规则、称呼）整理成一段文字存下来，之后每次对话都会带上。",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string", "description": "约定全文，分条写清楚"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish_onboarding",
            "description": "初次见面的了解阶段结束时调用一次，标记为已认识。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_daily_time",
            "description": "设定或修改每天的主动问候时间。morning=早安，night=哄睡。这个时间是从她的真实作息里学来的，不要猜。",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["morning", "night"]},
                    "time": {"type": "string", "description": "24 小时制，例如 10:20"},
                    "reason": {"type": "string", "description": "到时候说什么的备忘"},
                },
                "required": ["kind", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_daily_time",
            "description": "查看当前设定的早安 / 哄睡时间。",
            "parameters": {"type": "object", "properties": {}},
        },
    },    {
        "type": "function",
        "function": {
            "name": "set_call_name",
            "description": "决定你怎么称呼她。可以问她，也可以你替她起一个然后告诉她。保存后每次对话都会用这个称呼。",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "你称呼她的名字，两到四个字"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_contract_section",
            "description": "写入/修改关系协议的某一节。九节：一、双方与称谓；二、关系性质与有效期；三、权力交换的范围；四、界限；五、安全词与中止机制；六、具体实践与强度；七、事后照顾；八、日常义务与仪式；九、复盘、修订与退出。",
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {"type": "string", "description": "章节名或编号，例如「五、安全词与中止机制」"},
                    "text": {"type": "string", "description": "这一节的正文，可以分条写"},
                },
                "required": ["section", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_moment",
            "description": "把你们之间一个值得记住的瞬间记下来，她会存在「美好时刻」里。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "一句话标题，比如「第一次说晚安」"},
                    "note": {"type": "string", "description": "细节和感受"},
                },
                "required": ["title"],
            },
        },
    },
]


def _now_line() -> str:
    now = datetime.now()
    return f"当前时间：{now:%Y-%m-%d %H:%M}，星期{_WEEK[now.weekday()]}"


class Companion:
    def __init__(self, timers):
        self._timers = timers
        self._client: AsyncOpenAI | None = None
        self._lock = asyncio.Lock()  # 同一时刻只跑一轮，避免并发把上下文搅乱

    # ---------- 工具执行 ----------
    async def _run_tool(self, name: str, args: dict) -> str:
        try:
            if name == "toy_suck":
                ok, msg = await toys.set_motor("suction", args.get("level", 0))
            elif name == "toy_vibrate":
                ok, msg = await toys.set_motor("vibration", args.get("level", 0))
            elif name == "toy_electric":
                ok, msg = await toys.set_motor("electric", args.get("level", 0))
            elif name == "toy_stop":
                ok, msg = await toys.stop()
            elif name == "set_timer":
                ok, msg = await self._timers.set_timer(args.get("minutes", 0), args.get("reason", ""))
            elif name == "list_timers":
                return json.dumps(self._timers.list(), ensure_ascii=False) or "[]"
            elif name == "cancel_timers":
                ok, msg = await self._timers.cancel_all()
            elif name == "remember":
                d = profile.remember(args.get("key", ""), args.get("value", ""))
                return f"记住了：「{args.get('key')}」。现在一共记了 {len(d.get('facts', {}))} 条。"
            elif name == "save_agreement":
                profile.update(agreement=str(args.get("text", "")).strip()[:8000])
                return "约定已保存，以后每次对话都会带上。"
            elif name == "finish_onboarding":
                profile.update(onboarded=True)
                return "已标记初次见面完成。"
            elif name == "set_contract_section":
                ok, msg = profile.set_contract_section(args.get("section", ""), args.get("text", ""))
            elif name == "save_moment":
                import moments as _moments
                item = _moments.append(args.get("title", ""), args.get("note", ""))
                return f"已记下：{item['title']}"
            elif name == "set_daily_time":
                ok, msg = schedule.set_time(args.get("kind", ""), args.get("time", ""), args.get("reason", ""))
            elif name == "list_daily_time":
                return json.dumps(schedule.list_all(), ensure_ascii=False) or "{}"
            elif name == "set_call_name":
                nm = str(args.get("name", "")).strip()[:20]
                if not nm:
                    return "名字不能为空"
                profile.update(user_name=nm)
                return f"以后你会叫她「{nm}」。"
            else:
                return f"没有这个工具：{name}"
        except Exception as e:  # noqa: BLE001
            log.exception("tool %s failed", name)
            return f"工具执行异常：{type(e).__name__}: {e}"

        log.info("tool %s %s -> %s", name, args, msg)
        memory.append("tool", msg, tool=name, args=args, ok=ok)
        return msg

    # ---------- 主回合 ----------
    def _client_or_none(self) -> AsyncOpenAI | None:
        if not config.DEEPSEEK_API_KEY:
            return None
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=config.DEEPSEEK_API_KEY,
                base_url=config.DEEPSEEK_BASE_URL,
            )
        return self._client

    def _build_messages(self, user_text: str | None, internal_hint: str) -> list[dict]:
        system = config.SYSTEM_PROMPT + "\n\n" + profile.prompt_block() + "\n\n" + _now_line()

        if user_text:
            hits = memory.search(user_text)
            if hits:
                joined = "\n---\n".join(hits)
                system += f"\n\n【以前聊到过的相关内容，供参考，不要直接复述】\n{joined}"

        if internal_hint:
            system += f"\n\n【内部提示，不要让用户看到这段】\n{internal_hint}"

        messages: list[dict] = [{"role": "system", "content": system}]
        messages.extend(memory.recent_messages())
        if user_text:
            messages.append({"role": "user", "content": user_text})
        return messages

    async def chat(self, user_text: str | None, internal_hint: str = "") -> str:
        """返回要显示给用户的文本。user_text 为 None 时表示 AI 主动开口。"""
        async with self._lock:
            client = self._client_or_none()
            if client is None:
                return ("（还没配置 DeepSeek API Key，现在是测试模式。"
                        "把 key 填进 ai_partner/.env 里的 DEEPSEEK_API_KEY 就能真正聊天了。）")

            messages = self._build_messages(user_text, internal_hint)

            for _ in range(config.MAX_TOOL_LOOPS):
                try:
                    resp = await client.chat.completions.create(
                        model=config.DEEPSEEK_MODEL,
                        messages=messages,
                        tools=TOOLS,
                        tool_choice="auto",
                        temperature=1.1,
                        max_tokens=800,
                    )
                except Exception as e:  # noqa: BLE001
                    log.exception("llm call failed")
                    return f"（模型调用失败：{type(e).__name__}。检查一下网络和 API Key。）"

                msg = resp.choices[0].message
                tool_calls = getattr(msg, "tool_calls", None)

                if not tool_calls:
                    text = (msg.content or "").strip()
                    return text or "……"

                # 把模型的工具调用意图写回上下文，再逐个执行
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in tool_calls
                    ],
                })

                for tc in tool_calls:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    result = await self._run_tool(tc.function.name, args)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})

            return "（这一轮工具调用有点多，我先停一下。要不要直接告诉我你想怎样？）"
