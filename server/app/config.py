import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]  # server/
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"
SANDBOX_DIR = DATA_DIR / "sandbox"
DB_DIR = DATA_DIR / "db"
VSTORE_PATH = DB_DIR / "vstore.json"

LLM_MODE = os.getenv("AGENT_LLM_MODE", "auto")  # auto | openai | stub
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("AGENT_MODEL", "gpt-4o-mini")
EMBED_BACKEND = os.getenv("AGENT_EMBED_BACKEND", "hash")  # hash | openai
EMBED_MODEL = os.getenv("AGENT_EMBED_MODEL", "text-embedding-3-small")
STEP_TIMEOUT_S = float(os.getenv("AGENT_TIMEOUT_S", "120"))
APPROVAL_TIMEOUT_S = float(os.getenv("AGENT_APPROVAL_TIMEOUT_S", "900"))
SANDBOX_MAX_FILE_BYTES = 1024 * 1024
SANDBOX_MAX_FILES = 50

MCP_MODE = os.getenv("AGENT_MCP_MODE", "off")  # off | demo | stdio:<command>
MCP_TIMEOUT_S = float(os.getenv("AGENT_MCP_TIMEOUT_S", "60"))


def ensure_dirs() -> None:
    for d in (DATA_DIR, DOCS_DIR, SANDBOX_DIR, DB_DIR):
        d.mkdir(parents=True, exist_ok=True)