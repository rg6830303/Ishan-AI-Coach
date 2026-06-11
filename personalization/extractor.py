"""Rule-based signal extraction from free-text chat messages.

Deterministic and zero-cost (no extra LLM calls) so the coaches can update
their personalization model on *every* message without added latency. The
extracted signals are merged into the per-user personalization profile by
:mod:`personalization.store`.
"""

import re

INJURY_AREAS = [
    "knee", "ankle", "hip", "back", "shin", "shins", "hamstring", "calf",
    "calves", "achilles", "plantar", "foot", "heel", "groin", "it band",
    "quad", "glute",
]

POSITIVE_WORDS = [
    "great", "amazing", "awesome", "love", "loved", "happy", "excited",
    "strong", "good", "fantastic", "proud", "crushed", "nailed", "pumped",
    "energized", "confident", "fun", "enjoyed", "best",
]

NEGATIVE_WORDS = [
    "tired", "exhausted", "sore", "pain", "hurt", "hurts", "injured", "sad",
    "frustrated", "struggling", "struggle", "hard", "awful", "terrible",
    "worst", "demotivated", "burned out", "burnt out", "anxious", "stressed",
    "discouraged", "quit", "giving up", "can't", "cant",
]

TOPIC_KEYWORDS = {
    "nutrition": ["eat", "fuel", "gel", "carb", "protein", "hydrat", "diet", "nutrition", "calorie"],
    "injury": INJURY_AREAS + ["injury", "injured", "pain", "physio", "rehab"],
    "racing": ["race", "marathon", "half", "10k", "5k", "pr", "personal best", "bib", "start line"],
    "pacing": ["pace", "splits", "tempo", "threshold", "zone", "heart rate", "hr "],
    "recovery": ["rest", "recover", "sleep", "foam roll", "stretch", "deload", "easy day"],
    "motivation": ["motivat", "give up", "quit", "discourag", "mindset", "consistent", "habit"],
    "training_plan": ["plan", "schedule", "week", "long run", "intervals", "workout", "program"],
    "strength": ["strength", "gym", "squat", "lunge", "core", "lift", "weights"],
    "mental": ["nervous", "anxious", "confidence", "fear", "doubt", "visualize", "focus"],
}

GOAL_PATTERNS = [
    r"(?:i\s+)?(?:want|hope|plan|planning|aim|aiming|going|trying|would like)\s+to\s+(.{6,90}?)(?:[\.,!?]|$)",
    r"(?:my\s+goal\s+is\s+(?:to\s+)?)(.{6,90}?)(?:[\.,!?]|$)",
    r"(?:training|prepping|preparing)\s+for\s+(?:a\s+|the\s+|my\s+)?(.{4,70}?)(?:[\.,!?]|$)",
    r"(?:i\s+(?:want|wanna)\s+to\s+(?:run|do|finish|complete|break))\s+(.{3,70}?)(?:[\.,!?]|$)",
]

ACHIEVEMENT_PATTERNS = [
    r"(?:i\s+)?(?:just\s+)?(?:ran|did|finished|completed|hit|smashed|crushed|nailed)\s+(?:my\s+|a\s+|an\s+)?(.{4,70}?)(?:[\.,!?]|$)",
    r"(?:new\s+)?(?:pr|personal\s+best|personal\s+record|pb)\b(.{0,50})",
    r"(?:first\s+(?:time|ever))\s+(.{4,60}?)(?:[\.,!?]|$)",
]

PREFERENCE_PATTERNS = [
    (r"i\s+(?:prefer|like|love|enjoy)\s+(.{4,60}?)(?:[\.,!?]|$)", "like"),
    (r"i\s+(?:hate|dislike|avoid|can't stand|cant stand|don't like|dont like)\s+(.{4,60}?)(?:[\.,!?]|$)", "dislike"),
]

# e.g. "ran 8km", "did 5 miles", "12 k easy"
MILEAGE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(km|kilometre|kilometer|k\b|mi\b|mile|miles)", re.IGNORECASE
)


_CLAUSE_BREAKS = re.compile(r"\s+(?:but|and|because|though|however|so|while|when)\s+", re.IGNORECASE)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" .,!?-")


def _first_clause(text: str) -> str:
    """Trim a captured phrase to its first clause so preferences stay tight."""
    parts = _CLAUSE_BREAKS.split(text, maxsplit=1)
    return _clean(parts[0]) if parts else _clean(text)


def detect_sentiment(text: str) -> str:
    lo = text.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in lo)
    neg = sum(1 for w in NEGATIVE_WORDS if w in lo)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def detect_topics(text: str) -> list[str]:
    lo = text.lower()
    found = []
    for topic, kws in TOPIC_KEYWORDS.items():
        if any(kw in lo for kw in kws):
            found.append(topic)
    return found


def detect_injuries(text: str) -> list[str]:
    lo = text.lower()
    hits = []
    for area in INJURY_AREAS:
        if re.search(rf"\b{re.escape(area)}\b", lo):
            # Only treat as injury signal if a pain word is nearby.
            if any(p in lo for p in ["pain", "hurt", "sore", "injur", "tight", "stiff", "niggle", "ache"]):
                hits.append(area.replace("shins", "shin").replace("calves", "calf"))
    return sorted(set(hits))


def extract_signals(text: str) -> dict:
    """Extract a bundle of structured signals from one message."""
    if not text:
        return {}

    signals: dict = {
        "goals": [],
        "achievements": [],
        "preferences": [],  # list of (kind, value)
        "injuries": detect_injuries(text),
        "topics": detect_topics(text),
        "sentiment": detect_sentiment(text),
        "mileage": [],
    }

    for pat in GOAL_PATTERNS:
        for m in re.findall(pat, text, re.IGNORECASE):
            val = _clean(m if isinstance(m, str) else m[0])
            if len(val) >= 4:
                signals["goals"].append(val)

    for pat in ACHIEVEMENT_PATTERNS:
        for m in re.findall(pat, text, re.IGNORECASE):
            val = _clean(m if isinstance(m, str) else m[0])
            if len(val) >= 3:
                signals["achievements"].append(val)

    for pat, kind in PREFERENCE_PATTERNS:
        for m in re.findall(pat, text, re.IGNORECASE):
            val = _first_clause(m if isinstance(m, str) else m[0])
            if len(val) >= 3:
                signals["preferences"].append((kind, val))

    for amount, unit in MILEAGE_PATTERN.findall(text):
        try:
            val = float(amount)
        except ValueError:
            continue
        unit = unit.lower()
        km = val * 1.60934 if unit.startswith("mi") else val
        if 0.5 <= km <= 100:
            signals["mileage"].append(round(km, 2))

    # De-duplicate list fields while preserving order.
    for key in ("goals", "achievements", "topics", "injuries"):
        seen = set()
        deduped = []
        for item in signals[key]:
            if item.lower() not in seen:
                seen.add(item.lower())
                deduped.append(item)
        signals[key] = deduped

    return signals
