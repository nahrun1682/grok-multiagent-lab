import os
from dotenv import load_dotenv

load_dotenv()

XAI_API_KEY: str = os.getenv("XAI_API_KEY", "")
BASE_URL: str = "https://api.x.ai/v1"
DEFAULT_MODEL: str = "grok-4.20-multi-agent-beta-0309"
AVAILABLE_TOOLS: list[str] = ["web_search", "x_search"]
LOG_DIR_EVENTS: str = "logs/events"
LOG_DIR_SESSIONS: str = "logs/sessions"
