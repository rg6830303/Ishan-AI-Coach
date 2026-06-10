import json
import math
import re
from datetime import datetime
from database.models import get_connection
from config import MEMORY_DECAY_LAMBDA, MEMORY_TOP_K_INSIGHTS, CHAT_HISTORY_WINDOW


def store_message(user_id: int, role: str, content: str, tool_calls: list | None = None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO conversations (user_id, role, content, tool_calls) VALUES (?, ?, ?, ?)",
        (user_id, role, content, json.dumps(tool_calls) if tool_calls else None),
    )
    conn.commit()
    conn.close()


def get_chat_history(user_id: int, limit: int = CHAT_HISTORY_WINDOW) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT role, content, tool_calls, created_at FROM conversations
        WHERE user_id = ? ORDER BY created_at DESC LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    conn.close()
    messages = []
    for row in reversed(rows):
        msg = {"role": row["role"], "content": row["content"]}
        if row["tool_calls"]:
            msg["tool_calls"] = json.loads(row["tool_calls"])
        messages.append(msg)
    return messages


def clear_chat_history(user_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def extract_insights(user_id: int, content: str, role: str = "user"):
    patterns = {
        "goal": [
            r"(?:want to|going to|planning to|aiming for|target|goal is) (.{10,80})",
            r"(?:train(?:ing)? for|preparing for) (.{10,60})",
            r"(?:dream|bucket list).*?(?:is|:) (.{10,60})",
        ],
        "health_note": [
            r"(?:knee|ankle|hip|back|shin|hamstring|calf|achilles|plantar).*?(?:pain|hurt|sore|injury|issue)",
            r"(?:feeling|felt) (?:tired|exhausted|fatigued|sore|stiff)",
            r"(?:injury|injured|recovering from) (.{5,60})",
        ],
        "preference": [
            r"(?:I prefer|I like|I enjoy|I hate|I avoid) (.{5,60})",
            r"(?:morning|evening|afternoon|night) (?:runner|runs|person)",
        ],
        "achievement": [
            r"(?:just ran|completed|finished|did) (?:my|a) (.{5,60})",
            r"(?:PR|personal record|personal best|PB) (.{5,40})",
            r"(?:first time|first ever) (.{5,60})",
        ],
    }

    conn = get_connection()
    for category, pattern_list in patterns.items():
        for pattern in pattern_list:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                insight_text = match if isinstance(match, str) else content[:80]
                existing = conn.execute(
                    "SELECT id FROM insights WHERE user_id = ? AND category = ? AND content = ?",
                    (user_id, category, insight_text),
                ).fetchone()
                if not existing:
                    confidence = 1.0 if role == "user" else 0.8
                    conn.execute(
                        "INSERT INTO insights (user_id, category, content, confidence) VALUES (?, ?, ?, ?)",
                        (user_id, category, insight_text, confidence),
                    )

    conn.commit()
    conn.close()


def get_top_insights(user_id: int, top_k: int = MEMORY_TOP_K_INSIGHTS) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT category, content, confidence, created_at FROM insights WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()

    now = datetime.now()
    scored = []
    for row in rows:
        created = datetime.fromisoformat(row["created_at"])
        days_old = (now - created).days
        effective_weight = row["confidence"] * math.exp(-MEMORY_DECAY_LAMBDA * days_old)
        scored.append({
            "category": row["category"],
            "content": row["content"],
            "weight": effective_weight,
        })

    scored.sort(key=lambda x: x["weight"], reverse=True)
    return scored[:top_k]
