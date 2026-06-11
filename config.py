import os
import re
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load a standard .env first (KEY=value format).
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _parse_env_like_file(path: str) -> dict:
    """Parse a loosely-formatted env file.

    Tolerates the malformed ``.env.txt`` shipped with the project where the
    key was stored as ``GROQ-API-KEY:gsk_...`` (dash + colon) instead of the
    standard ``GROQ_API_KEY=gsk_...``. Returns a dict of normalized keys.
    """
    values: dict[str, str] = {}
    if not os.path.exists(path):
        return values
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                # Split on the first '=' or ':' delimiter.
                m = re.match(r"^([A-Za-z0-9_\-\.]+)\s*[:=]\s*(.+)$", line)
                if not m:
                    continue
                key = m.group(1).strip().upper().replace("-", "_")
                val = m.group(2).strip().strip('"').strip("'")
                values[key] = val
    except Exception:
        pass
    return values


def _from_streamlit_secrets(name: str) -> str:
    """Read a secret from Streamlit Cloud's secrets, if running under Streamlit."""
    try:
        import streamlit as st  # local import; optional at runtime
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


def _resolve_groq_key() -> str:
    """Resolve the Groq API key from env, Streamlit secrets, then .env / .env.txt."""
    key = os.getenv("GROQ_API_KEY", "").strip()
    if key and key != "gsk_your_key_here":
        return key
    # Streamlit Cloud deployment: read from the Secrets panel.
    secret = _from_streamlit_secrets("GROQ_API_KEY")
    if secret and secret != "gsk_your_key_here":
        os.environ["GROQ_API_KEY"] = secret
        return secret
    # Local fallback to the legacy/loose file the user shipped.
    for fname in (".env", ".env.txt"):
        parsed = _parse_env_like_file(os.path.join(BASE_DIR, fname))
        candidate = parsed.get("GROQ_API_KEY", "").strip()
        if candidate and candidate != "gsk_your_key_here":
            os.environ["GROQ_API_KEY"] = candidate
            return candidate
    return key


GROQ_API_KEY = _resolve_groq_key()
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL_SMALL = os.getenv("GROQ_MODEL_SMALL", "llama-3.1-8b-instant")
GROQ_MODEL_LARGE = os.getenv("GROQ_MODEL_LARGE", "llama-3.3-70b-versatile")

DB_PATH = os.path.join(BASE_DIR, "data", "coach.db")
INDEX_PATH = os.path.join(BASE_DIR, "knowledge", "index")
CORPUS_PATH = os.path.join(BASE_DIR, "knowledge", "corpus")

# Local JSON / JSONL personalization store (one folder per user).
DATA_DIR = os.path.join(BASE_DIR, "data")
PERSONALIZATION_DIR = os.path.join(DATA_DIR, "personalization")

TIERS = {
    "spark": {
        "name": "Spark",
        "label": "Beginner",
        "model": GROQ_MODEL_SMALL,
        "max_rag_chunks": 3,
        "description": "New or returning runner, building habits",
    },
    "pace": {
        "name": "Pace",
        "label": "Intermediate",
        "model": GROQ_MODEL_SMALL,
        "max_rag_chunks": 4,
        "description": "Consistent runner, chasing 5K-10K goals",
    },
    "tempo": {
        "name": "Tempo",
        "label": "Advanced",
        "model": GROQ_MODEL_LARGE,
        "max_rag_chunks": 5,
        "description": "Half/full marathon, periodized training",
    },
    "apex": {
        "name": "Apex",
        "label": "Elite",
        "model": GROQ_MODEL_LARGE,
        "max_rag_chunks": 6,
        "description": "PR-chasing, competitive, data-driven",
    },
}

COACH_STYLES = {
    "scientist": {"name": "The Scientist", "db_key": "analyst"},
    "energizer": {"name": "The Energizer", "db_key": "motivator"},
    "warrior": {"name": "The Warrior", "db_key": "drill_sergeant"},
    "sage": {"name": "The Sage", "db_key": "zen"},
}

CLASSIFICATION_WEIGHTS = {
    "running_experience": 0.35,
    "fitness_level": 0.25,
    "five_k_time": 0.25,
    "training_days": 0.15,
}

TIER_THRESHOLDS = {
    "spark": (0, 25),
    "pace": (25, 50),
    "tempo": (50, 75),
    "apex": (75, 100),
}

MAX_AGENT_ITERATIONS = 4
MEMORY_DECAY_LAMBDA = 0.03
MEMORY_TOP_K_INSIGHTS = 8
CHAT_HISTORY_WINDOW = 12


def groq_key_is_configured() -> bool:
    return bool(GROQ_API_KEY) and GROQ_API_KEY != "gsk_your_key_here"
