import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL_SMALL = os.getenv("GROQ_MODEL_SMALL", "llama-3.1-8b-instant")
GROQ_MODEL_LARGE = os.getenv("GROQ_MODEL_LARGE", "llama-3.3-70b-versatile")

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "coach.db")
INDEX_PATH = os.path.join(os.path.dirname(__file__), "knowledge", "index")
CORPUS_PATH = os.path.join(os.path.dirname(__file__), "knowledge", "corpus")

TIERS = {
    "spark": {
        "name": "Spark",
        "label": "Beginner",
        "model": GROQ_MODEL_SMALL,
        "max_rag_chunks": 2,
        "description": "New or returning runner, building habits",
    },
    "pace": {
        "name": "Pace",
        "label": "Intermediate",
        "model": GROQ_MODEL_SMALL,
        "max_rag_chunks": 3,
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
        "max_rag_chunks": 5,
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

MAX_AGENT_ITERATIONS = 3
MEMORY_DECAY_LAMBDA = 0.03
MEMORY_TOP_K_INSIGHTS = 5
CHAT_HISTORY_WINDOW = 10
