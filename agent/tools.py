import json
from engine.pace_calculator import calculate_pace_zones, format_pace
from engine.guardrails import check_guardrails
from knowledge.retriever import retriever
from database.auth import get_profile
from personalization.store import store as personalization_store


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_runner_profile",
            "description": "Retrieve the runner's complete profile including metrics, tier, goals, and injury history. Call this when you need to reference the user's specific data.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_knowledge",
            "description": "Search the coaching knowledge base for methodology, training principles, or scientific evidence. Use when the user asks about training approaches, recovery science, or you need to back up a recommendation with evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for the knowledge base",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_pace_zones",
            "description": "Calculate training pace zones from a 5K time in minutes. Returns easy, tempo, interval, and race paces. ALWAYS use this instead of making up numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "five_k_minutes": {
                        "type": "number",
                        "description": "5K time in minutes (e.g., 25.5 for 25:30). If unknown, pass 0 to use profile-based estimation.",
                    },
                },
                "required": ["five_k_minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_guardrails",
            "description": "Validate a coaching recommendation against safety guardrails for this runner's tier. Call BEFORE suggesting volume increases, new intensity sessions, or race recommendations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recommendation_type": {
                        "type": "string",
                        "enum": ["volume_increase", "intensity_session", "race_recommendation", "return_from_injury"],
                        "description": "Type of recommendation to validate",
                    },
                    "details": {
                        "type": "string",
                        "description": "Brief description of what you're about to recommend",
                    },
                },
                "required": ["recommendation_type", "details"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_training_run",
            "description": "Record a run the runner just reported so it is saved to their personal training log. Call this whenever the runner mentions completing a workout with any detail (distance, duration, type, or how it felt).",
            "parameters": {
                "type": "object",
                "properties": {
                    "distance_km": {"type": "number", "description": "Distance in km (estimate if given in miles or minutes)."},
                    "duration_minutes": {"type": "number", "description": "Duration in minutes if known."},
                    "type": {"type": "string", "description": "Run type, e.g. easy, long, tempo, intervals, race, recovery."},
                    "feel": {"type": "string", "description": "How it felt in a few words (e.g. 'strong', 'sore knee', 'tough but good')."},
                    "notes": {"type": "string", "description": "Any extra detail worth remembering."},
                },
                "required": [],
            },
        },
    },
]


def execute_tool(tool_name: str, arguments: dict, user_id: int) -> str:
    """Execute a tool call and return the result as a string."""
    try:
        if tool_name == "get_runner_profile":
            profile = get_profile(user_id)
            if profile is None:
                return json.dumps({"error": "No profile found for this user."})
            safe_profile = {k: v for k, v in profile.items() if k != "id"}
            return json.dumps(safe_profile, default=str)

        elif tool_name == "retrieve_knowledge":
            query = arguments.get("query", "")
            profile = get_profile(user_id)
            tier = profile.get("tier", "general") if profile else "general"
            results = retriever.retrieve(query, tier=tier)
            formatted = []
            for r in results:
                formatted.append({
                    "title": r["chunk"]["title"],
                    "content": r["chunk"]["content"][:500],
                    "source": r["chunk"]["source"],
                    "relevance_score": round(r["score"], 3),
                })
            return json.dumps(formatted, indent=2)

        elif tool_name == "calculate_pace_zones":
            five_k = arguments.get("five_k_minutes", 0)
            profile = get_profile(user_id)
            if five_k and five_k > 0:
                profile_with_5k = {**(profile or {}), "recent_5k_time": five_k}
            else:
                profile_with_5k = profile or {}
            zones = calculate_pace_zones(profile_with_5k)
            return json.dumps(zones)

        elif tool_name == "check_guardrails":
            rec_type = arguments.get("recommendation_type", "volume_increase")
            details = arguments.get("details", "")
            profile = get_profile(user_id)
            tier = profile.get("tier", "pace") if profile else "pace"
            result = check_guardrails(tier, rec_type, details)
            return json.dumps(result)

        elif tool_name == "log_training_run":
            entry = {
                "distance_km": arguments.get("distance_km"),
                "duration_minutes": arguments.get("duration_minutes"),
                "type": arguments.get("type", "run"),
                "feel": arguments.get("feel", ""),
                "notes": arguments.get("notes", ""),
            }
            entry = {k: v for k, v in entry.items() if v not in (None, "")}
            personalization_store.add_training_log(user_id, entry)
            return json.dumps({"logged": True, "entry": entry})

        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except Exception as e:
        return json.dumps({"error": str(e)})
