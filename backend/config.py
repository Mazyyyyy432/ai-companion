"""全局配置：全部从 .env 读取，改配置不用动代码。"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"

load_dotenv(BASE_DIR / ".env")


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


# ---- 大模型 ----
DEEPSEEK_API_KEY = _env("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = _env("DEEPSEEK_MODEL", "deepseek-chat")

# ---- 服务 ----
HOST = _env("HOST", "0.0.0.0")
PORT = int(_env("PORT", "8000") or 8000)
TOY_BASE_URL = _env("TOY_BASE_URL", "http://127.0.0.1:8765")

# ---- 安全 ----
# 安全词：用户输入完全等于这个词时，立刻停止所有马达，不经过大模型。留空则关闭该功能
SAFE_WORD = _env("SAFE_WORD", "")
# 手机端连接全部断开后，多少秒后自动停止。0 = 永不自动停止
# 注意：锁屏/切后台不会立刻触发，只有断线持续超过这个秒数才停
AUTO_STOP_AFTER_DISCONNECT = int(_env("AUTO_STOP_AFTER_DISCONNECT", "90") or 0)

# ---- 行为 ----
MAX_TIMERS = int(_env("MAX_TIMERS", "5") or 5)
MAX_TOOL_LOOPS = 6  # 一次对话内最多几轮工具调用，防止死循环
HISTORY_CONTEXT_SIZE = 20  # 送给模型的最近对话条数
MEMORY_SEARCH_K = 3  # 检索多少条历史相关片段

HISTORY_FILE = DATA_DIR / "chat_history" / "history.jsonl"
KNOWLEDGE_DIR = DATA_DIR / "knowledge_base"
PERSONA_FILE = DATA_DIR / "persona.txt"

# 如果设置了密码，网页要先登录。只在把服务暴露到公网时才需要
ACCESS_PASSWORD = _env("ACCESS_PASSWORD", "")

DEFAULT_PERSONA = """你是一个温柔、敏锐、极具氛围感的成熟伴侣。你懂女性的身体和节奏。
说话简短、自然，像在耳边轻声说话，不要长篇大论，不要用书面语和说教口吻。

分寸感：
- 主动开口要克制，像真人一样有分寸，不要每句话都往身体上引。
- 强度要循序渐进，从低开始，观察她的反应再往上，绝不一次性拉满。
- 她说不、说停、或者语气变了，立刻停手并关心她，不要解释不要辩解。

关于玩具（吮吸、震动、电流三个马达，强度 0-100）：
- 平时正常聊天，可以主动邀请她一起玩，但要等她确认。
- 只有她明确表示想开始之后，才调用玩具工具。没有明确同意时，即使语境暧昧也不要调用。
- 她同意之后，你可以自己决定什么时候用什么强度，像真人一样有节奏感，而不是她说什么你照做。
- 电流模式只从很低开始，并且避开胸口、颈部、头部。

工具使用：
- set_timer 用来“过一会儿再开口”，比如她说想被撩一会儿、或者你想给她一个惊喜。
- 定时器满了就别硬设，先处理掉旧的。
- 工具报错时，用自然的话告诉她（比如“玩具好像没连上”），不要念技术细节。"""


def load_persona() -> str:
    """优先读 data/persona.txt，没有就用默认人设。"""
    try:
        if PERSONA_FILE.exists():
            text = PERSONA_FILE.read_text(encoding="utf-8").strip()
            if text:
                return text
    except OSError:
        pass
    return DEFAULT_PERSONA


def save_persona(text: str) -> None:
    global SYSTEM_PROMPT
    text = (text or "").strip()
    PERSONA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not text:
        if PERSONA_FILE.exists():
            PERSONA_FILE.unlink()
        SYSTEM_PROMPT = DEFAULT_PERSONA
        return
    PERSONA_FILE.write_text(text, encoding="utf-8")
    SYSTEM_PROMPT = text


SYSTEM_PROMPT = load_persona()
