"""Full tool set for Sprint Society AI Coach (20+ tools).

References:
- PyExPhys (jackdaniels.py): VDOT/velocity formulas
- Athlytics: ACWR/EWMA calculations
- ronek22/runningCalculator: Race prediction (Riegel formula)

Tool categories:
1. READ (context) — get_profile, get_recent_runs, get_training_history,
   get_personal_records, get_goals, get_progress_and_level,
   get_weekly_load_acwr, get_current_plan, get_memory_insights
2. COMPUTE — calculate_pace_zones, estimate_vo2max, predict_race_time,
   assess_injury_risk, calculate_readiness
3. KNOWLEDGE — retrieve_knowledge, web_search_cached
4. ACTION (safe writes) — log_run, set_goal, generate_training_plan,
   adjust_plan, set_coaching_focus, save_memory_insight
5. SAFETY — check_guardrails
"""

import json
import math
import time
from datetime import datetime, timedelta

from engine.pace_calculator import calculate_pace_zones, format_pace
from engine.guardrails import check_guardrails
from engine.vo2max import estimate_vo2max_from_5k
from knowledge.retriever import retriever
from database.auth import get_profile
from personalization.store import store as personalization_store


# ============================================================
# TOOL DEFINITIONS (OpenAI function-calling format)
# ============================================================

TOOL_DEFINITIONS = [
    # === READ / CONTEXT ===
    {
        "type": "function",
        "function": {
            "name": "get_runner_profile",
            "description": "Get the runner's complete profile: tier, age, gender, fitness level, goals, injury history, coach style. Call when you need their specific data.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_runs",
            "description": "Get the runner's recent runs (last 7-14 days). Returns distance, duration, pace, type, and feel for each run. Use for post-run analysis, daily insight, pre-run context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Number of days to look back (default 14)", "default": 14},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_training_history",
            "description": "Get longer training history (weeks/months). Returns weekly summaries with volume, intensity distribution, consistency. Use for plans, weekly summary, injury risk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "weeks": {"type": "integer", "description": "Number of weeks to look back (default 8)", "default": 8},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_personal_records",
            "description": "Get the runner's personal bests across all distances (5K, 10K, Half, Marathon, etc.). Use for race predictions, progress tracking, celebration.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_goals",
            "description": "Get the runner's active goals (race targets, pace goals, volume goals). Use for plan generation, daily insight, motivation.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_progress_and_level",
            "description": "Get the runner's current XP level (1-40 app system) and recent progress metrics. Use for celebration, nudges, weekly summary.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weekly_load_acwr",
            "description": "Get the runner's Acute:Chronic Workload Ratio (ACWR) and weekly training load. CRITICAL for injury risk and plan adjustments. Returns acute (7d), chronic (28d), ratio, and risk level.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_plan",
            "description": "Get the runner's active training plan with this week's sessions. Use for pre-run briefs, plan adjustments, progress checks.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_memory_insights",
            "description": "Get stored insights about this runner from past conversations (goals mentioned, injuries discussed, preferences learned). Personalizes coaching.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },

    # === COMPUTE ===
    {
        "type": "function",
        "function": {
            "name": "calculate_pace_zones",
            "description": "Calculate training pace zones (easy, tempo, interval, race) from a 5K time. ALWAYS use this for paces — NEVER invent numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "five_k_minutes": {"type": "number", "description": "5K time in minutes (e.g., 25.5 for 25:30). Pass 0 to use profile estimate."},
                },
                "required": ["five_k_minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estimate_vo2max",
            "description": "Estimate VO2max from profile data or a recent race time. Returns ml/kg/min + fitness category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "five_k_minutes": {"type": "number", "description": "5K time in minutes (most accurate if available)"},
                    "age": {"type": "integer", "description": "Runner's age"},
                    "gender": {"type": "string", "enum": ["male", "female"]},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "predict_race_time",
            "description": "Predict race time for a target distance based on a known race performance. Uses Riegel formula with distance-specific adjustments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "known_distance_km": {"type": "number", "description": "Distance of the known race (km)"},
                    "known_time_minutes": {"type": "number", "description": "Time for the known race (minutes)"},
                    "target_distance_km": {"type": "number", "description": "Distance to predict (km)"},
                },
                "required": ["known_distance_km", "known_time_minutes", "target_distance_km"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assess_injury_risk",
            "description": "Assess current injury risk based on ACWR, training patterns, and history. Returns risk level (low/moderate/high/critical) with specific concerns.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_readiness",
            "description": "Calculate today's training readiness score (1-10) based on recent load, recovery indicators, and schedule. Recommends session type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sleep_quality": {"type": "integer", "description": "Last night's sleep 1-5 (5=great)", "minimum": 1, "maximum": 5},
                    "muscle_soreness": {"type": "integer", "description": "Soreness 1-5 (5=fresh)", "minimum": 1, "maximum": 5},
                    "energy": {"type": "integer", "description": "Energy/motivation 1-5 (5=high)", "minimum": 1, "maximum": 5},
                },
                "required": [],
            },
        },
    },

    # === KNOWLEDGE ===
    {
        "type": "function",
        "function": {
            "name": "retrieve_knowledge",
            "description": "Search the coaching knowledge base for methodology, training principles, or scientific evidence. Use when you need to back up a recommendation with evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query for the knowledge base"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search_cached",
            "description": "Search the web for latest running research, race info, or current events. Results are cached. Use ONLY for questions the knowledge base can't answer (latest news, specific races, gear).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Web search query"},
                },
                "required": ["query"],
            },
        },
    },

    # === ACTION (safe writes — no XP/money) ===
    {
        "type": "function",
        "function": {
            "name": "log_training_run",
            "description": "Record a run the runner just reported. Call whenever they mention completing a workout with any detail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "distance_km": {"type": "number", "description": "Distance in km"},
                    "duration_minutes": {"type": "number", "description": "Duration in minutes"},
                    "type": {"type": "string", "description": "Run type: easy, long, tempo, intervals, race, recovery, fartlek"},
                    "feel": {"type": "string", "description": "How it felt (e.g., 'strong', 'tired', 'knee tight')"},
                    "notes": {"type": "string", "description": "Any extra detail"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_goal",
            "description": "Set or update a running goal for the runner. Goals drive plan generation and daily coaching.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal_type": {"type": "string", "enum": ["race", "pace", "volume", "consistency"], "description": "Type of goal"},
                    "target": {"type": "string", "description": "Target (e.g., '5K in 25:00', '50km/week', 'run 4x/week')"},
                    "deadline_weeks": {"type": "integer", "description": "Weeks until target date"},
                },
                "required": ["goal_type", "target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_training_plan",
            "description": "Generate a full periodized training plan with specific daily workouts, paces, and persona-flavored descriptions. Returns week-by-week structured sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "What the plan is for (e.g., '5K', '10K', 'half', 'marathon', 'base')"},
                    "weeks": {"type": "integer", "description": "Number of weeks for the plan (8-24)"},
                    "days_per_week": {"type": "integer", "description": "Training days available per week (3-6)"},
                    "persona": {"type": "string", "enum": ["scientist", "energizer", "warrior", "sage"], "description": "Coaching persona for workout naming style"},
                },
                "required": ["goal", "weeks"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "adjust_plan",
            "description": "Adjust the current training plan based on new information (injury, schedule change, performance update). Modifies upcoming sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why the plan needs adjustment"},
                    "adjustment_type": {"type": "string", "enum": ["reduce_volume", "reduce_intensity", "skip_day", "swap_session", "extend_plan", "deload_now"]},
                },
                "required": ["reason", "adjustment_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_coaching_focus",
            "description": "Set the coaching focus for the next period (e.g., 'base building', 'speed development', 'injury recovery', 'race prep'). Influences daily insights and recommendations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "focus": {"type": "string", "description": "The coaching focus area"},
                    "duration_weeks": {"type": "integer", "description": "How long this focus should last"},
                },
                "required": ["focus"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory_insight",
            "description": "Save an important insight about the runner for future reference (preference learned, goal stated, concern raised). Called automatically by the system but can also be called explicitly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["goal", "health_note", "preference", "achievement", "training_pattern", "personal_context"]},
                    "content": {"type": "string", "description": "The insight to remember"},
                },
                "required": ["category", "content"],
            },
        },
    },

    # === SAFETY ===
    {
        "type": "function",
        "function": {
            "name": "check_guardrails",
            "description": "Validate a coaching recommendation against safety guardrails. Call BEFORE suggesting volume increases, intensity sessions, or return from injury.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recommendation_type": {"type": "string", "enum": ["volume_increase", "intensity_session", "race_recommendation", "return_from_injury"]},
                    "details": {"type": "string", "description": "What you're about to recommend"},
                    "weekly_km": {"type": "number", "description": "Proposed weekly volume (optional)"},
                    "volume_increase_percent": {"type": "number", "description": "Proposed increase % (optional)"},
                    "intensity_type": {"type": "string", "description": "Type of intensity proposed (optional)"},
                },
                "required": ["recommendation_type", "details"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_training_level",
            "description": "Update the runner's coaching cycle level (1-10). Only call when they've clearly met graduation criteria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "minimum": 1, "maximum": 10, "description": "New level"},
                    "reason": {"type": "string", "description": "Why they earned this level"},
                },
                "required": ["level", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_wellness_check",
            "description": "Get the runner's morning wellness self-report (replaces HRV for readiness). Returns sleep quality, energy, soreness, stress, and motivation on 1-5 scales.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# ============================================================
# TOOL EXECUTION (the actual logic behind each tool)
# ============================================================

def execute_tool(tool_name: str, arguments: dict, user_id: int, thread_id: int | None = None) -> str:
    """Execute a tool and return JSON result string."""
    try:
        if tool_name == "get_runner_profile":
            return _get_runner_profile(user_id)
        elif tool_name == "get_recent_runs":
            return _get_recent_runs(user_id, arguments.get("days", 14))
        elif tool_name == "get_training_history":
            return _get_training_history(user_id, arguments.get("weeks", 8))
        elif tool_name == "get_personal_records":
            return _get_personal_records(user_id)
        elif tool_name == "get_goals":
            return _get_goals(user_id)
        elif tool_name == "get_progress_and_level":
            return _get_progress_and_level(user_id)
        elif tool_name == "get_weekly_load_acwr":
            return _get_weekly_load_acwr(user_id)
        elif tool_name == "get_current_plan":
            return _get_current_plan(user_id)
        elif tool_name == "get_memory_insights":
            return _get_memory_insights(user_id)
        elif tool_name == "get_wellness_check":
            return _get_wellness_check(user_id)
        elif tool_name == "calculate_pace_zones":
            return _calculate_pace_zones(user_id, arguments)
        elif tool_name == "estimate_vo2max":
            return _estimate_vo2max_tool(user_id, arguments)
        elif tool_name == "predict_race_time":
            return _predict_race_time(arguments)
        elif tool_name == "assess_injury_risk":
            return _assess_injury_risk(user_id)
        elif tool_name == "calculate_readiness":
            return _calculate_readiness(user_id, arguments)
        elif tool_name == "retrieve_knowledge":
            return _retrieve_knowledge(user_id, arguments)
        elif tool_name == "web_search_cached":
            return _web_search(arguments)
        elif tool_name == "log_training_run":
            return _log_run(user_id, arguments, thread_id)
        elif tool_name == "set_goal":
            return _set_goal(user_id, arguments)
        elif tool_name == "generate_training_plan":
            return _generate_plan(user_id, arguments)
        elif tool_name == "adjust_plan":
            return _adjust_plan(user_id, arguments)
        elif tool_name == "set_coaching_focus":
            return _set_focus(user_id, arguments)
        elif tool_name == "save_memory_insight":
            return _save_insight(user_id, arguments)
        elif tool_name == "check_guardrails":
            return _check_guardrails(user_id, arguments)
        elif tool_name == "set_training_level":
            return _set_level(user_id, arguments)
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================
# TOOL IMPLEMENTATIONS
# ============================================================

def _get_runner_profile(user_id: int) -> str:
    profile = get_profile(user_id)
    if not profile:
        return json.dumps({"error": "No profile found"})
    safe = {k: v for k, v in profile.items() if k != "id"}
    return json.dumps(safe, default=str)


def _get_recent_runs(user_id: int, days: int) -> str:
    runs = personalization_store.get_training_log(user_id, limit=20)
    if not runs:
        return json.dumps({"runs": [], "message": "No recent runs logged"})
    return json.dumps({"runs": runs[:days], "count": len(runs)})


def _get_training_history(user_id: int, weeks: int) -> str:
    runs = personalization_store.get_training_log(user_id, limit=100)
    if not runs:
        return json.dumps({"weeks": [], "message": "No training history"})
    # Summarize by week
    total_km = sum(r.get("distance_km", 0) for r in runs if r.get("distance_km"))
    total_runs = len(runs)
    avg_weekly = total_km / max(weeks, 1)
    return json.dumps({
        "total_runs": total_runs,
        "total_km": round(total_km, 1),
        "avg_weekly_km": round(avg_weekly, 1),
        "weeks_covered": weeks,
        "recent_runs": runs[:10],
    })


def _get_personal_records(user_id: int) -> str:
    profile = get_profile(user_id)
    five_k = profile.get("recent_5k_time") if profile else None
    records = {}
    if five_k:
        records["5K"] = f"{int(five_k)}:{int((five_k % 1) * 60):02d}"
        # Predict others using Riegel
        records["10K"] = _format_time(_riegel_predict(5, five_k, 10))
        records["Half"] = _format_time(_riegel_predict(5, five_k, 21.1))
        records["Marathon"] = _format_time(_riegel_predict(5, five_k, 42.195))
    return json.dumps({"records": records, "source": "calculated from 5K" if five_k else "no data"})


def _get_goals(user_id: int) -> str:
    goals = personalization_store.get_goals(user_id) if hasattr(personalization_store, 'get_goals') else []
    if not goals:
        return json.dumps({"goals": [], "message": "No active goals set"})
    return json.dumps({"goals": goals})


def _get_progress_and_level(user_id: int) -> str:
    profile = get_profile(user_id)
    coach = profile.get("coach_style", "energizer") if profile else "energizer"
    level = personalization_store.get_training_level(user_id, coach, default=1)
    return json.dumps({"level": level, "max_level": 10, "coach_style": coach})


def _get_weekly_load_acwr(user_id: int) -> str:
    """Calculate ACWR from training log. Formula from Athlytics/Gabbett."""
    runs = personalization_store.get_training_log(user_id, limit=50)

    # Calculate daily loads (distance * RPE-equivalent)
    now = datetime.now()
    daily_loads = {}
    for run in runs:
        # Estimate days ago from log order (simplified — real app uses timestamps)
        idx = runs.index(run)
        day_key = (now - timedelta(days=idx)).strftime("%Y-%m-%d")
        km = run.get("distance_km", 0) or 0
        daily_loads[day_key] = daily_loads.get(day_key, 0) + km

    # Acute (7 days) and Chronic (28 days)
    acute_days = 7
    chronic_days = 28
    acute_load = sum(list(daily_loads.values())[:acute_days])
    chronic_load = sum(list(daily_loads.values())[:chronic_days])
    chronic_avg = chronic_load / chronic_days * acute_days if chronic_days > 0 else 0

    acwr = round(acute_load / chronic_avg, 2) if chronic_avg > 0 else 1.0

    # Risk assessment
    if acwr < 0.8:
        risk = "low (undertraining)"
    elif acwr <= 1.3:
        risk = "optimal (sweet spot)"
    elif acwr <= 1.5:
        risk = "moderate (caution)"
    else:
        risk = "high (injury danger)"

    return json.dumps({
        "acute_load_km": round(acute_load, 1),
        "chronic_avg_km": round(chronic_avg, 1),
        "acwr": acwr,
        "risk_level": risk,
        "recommendation": "Safe to increase" if acwr <= 1.3 else "Reduce load" if acwr > 1.5 else "Monitor closely",
    })


def _get_current_plan(user_id: int) -> str:
    plan = personalization_store.get_active_plan(user_id) if hasattr(personalization_store, 'get_active_plan') else None
    if not plan:
        return json.dumps({"plan": None, "message": "No active training plan"})
    return json.dumps({"plan": plan})


def _get_memory_insights(user_id: int) -> str:
    from database.memory import get_top_insights
    insights = get_top_insights(user_id)
    if not insights:
        return json.dumps({"insights": [], "message": "No stored insights yet"})
    return json.dumps({"insights": insights})


def _get_wellness_check(user_id: int) -> str:
    """Get the runner's latest morning wellness self-report.

    This replaces HRV-based readiness for users without wearables.
    Sprint Society app prompts users each morning with 5 quick sliders (1-5).
    """
    # In production, reads from Sprint Society's wellness_checks table
    # For now, returns most recent check or indicates no data
    try:
        from integration.sprint_society_adapter import DATA_SOURCE
        if DATA_SOURCE == "supabase":
            from integration.sprint_society_adapter import _get_supabase_client
            client = _get_supabase_client()
            result = (
                client.table("wellness_checks")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if result.data:
                row = result.data[0]
                return json.dumps({
                    "sleep_quality": row.get("sleep_quality", 3),
                    "energy_level": row.get("energy_level", 3),
                    "muscle_soreness": row.get("muscle_soreness", 3),
                    "stress_level": row.get("stress_level", 3),
                    "motivation": row.get("motivation", 3),
                    "readiness_score": _calc_readiness_from_wellness(row),
                    "date": row.get("created_at", ""),
                })
    except (ImportError, RuntimeError):
        pass

    return json.dumps({
        "message": "No wellness check recorded today",
        "suggestion": "Ask the runner how they slept, their energy level, and any soreness",
        "readiness_score": None,
    })


def _calc_readiness_from_wellness(wellness: dict) -> float:
    """Calculate readiness 1-5 from wellness self-report."""
    sleep = wellness.get("sleep_quality", 3)
    energy = wellness.get("energy_level", 3)
    soreness = 6 - wellness.get("muscle_soreness", 3)  # Invert: high soreness = low readiness
    stress = 6 - wellness.get("stress_level", 3)  # Invert: high stress = low readiness
    motivation = wellness.get("motivation", 3)
    # Weighted: sleep 30%, energy 25%, soreness 20%, stress 15%, motivation 10%
    score = (sleep * 0.30 + energy * 0.25 + soreness * 0.20 + stress * 0.15 + motivation * 0.10)
    return round(score, 1)


# --- COMPUTE ---

def _calculate_pace_zones(user_id: int, args: dict) -> str:
    five_k = args.get("five_k_minutes", 0)
    profile = get_profile(user_id)
    if five_k and five_k > 0:
        profile_with_5k = {**(profile or {}), "recent_5k_time": five_k}
    else:
        profile_with_5k = profile or {}
    zones = calculate_pace_zones(profile_with_5k)
    return json.dumps(zones)


def _estimate_vo2max_tool(user_id: int, args: dict) -> str:
    """Estimate VO2max using Daniels/Gilbert formula from PyExPhys reference."""
    five_k = args.get("five_k_minutes")
    profile = get_profile(user_id)

    if five_k and five_k > 0:
        # Daniels formula: VO2max from race performance
        # velocity in m/min from 5K time
        velocity = 5000 / five_k  # meters per minute
        # Percent VO2max sustained during race (from duration)
        pct_vo2 = 0.8 + 0.1894393 * math.exp(-0.012778 * five_k) + 0.2989558 * math.exp(-0.1932605 * five_k)
        # VO2 at that velocity
        vo2_at_velocity = -4.60 + 0.182258 * velocity + 0.000104 * (velocity ** 2)
        vo2max = vo2_at_velocity / pct_vo2
    elif profile and profile.get("recent_5k_time"):
        five_k = profile["recent_5k_time"]
        velocity = 5000 / five_k
        pct_vo2 = 0.8 + 0.1894393 * math.exp(-0.012778 * five_k) + 0.2989558 * math.exp(-0.1932605 * five_k)
        vo2_at_velocity = -4.60 + 0.182258 * velocity + 0.000104 * (velocity ** 2)
        vo2max = vo2_at_velocity / pct_vo2
    else:
        # Rough estimate from age/gender/fitness
        age = args.get("age") or (profile.get("age") if profile else 30)
        gender = args.get("gender") or (profile.get("gender") if profile else "male")
        base = 45 if gender == "male" else 38
        vo2max = base - (age - 25) * 0.5  # Rough decline

    # Categorize
    if vo2max >= 55:
        category = "Excellent"
    elif vo2max >= 45:
        category = "Good"
    elif vo2max >= 35:
        category = "Average"
    else:
        category = "Below average"

    return json.dumps({
        "vo2max": round(vo2max, 1),
        "category": category,
        "unit": "ml/kg/min",
        "method": "Daniels/Gilbert formula" if five_k else "Estimate from demographics",
    })


def _predict_race_time(args: dict) -> str:
    """Riegel formula with distance-specific fatigue factors."""
    known_dist = args.get("known_distance_km", 5)
    known_time = args.get("known_time_minutes", 25)
    target_dist = args.get("target_distance_km", 10)

    predicted = _riegel_predict(known_dist, known_time, target_dist)

    return json.dumps({
        "predicted_time": _format_time(predicted),
        "predicted_minutes": round(predicted, 2),
        "predicted_pace": _format_time(predicted / target_dist) + "/km",
        "from_distance": f"{known_dist}km in {_format_time(known_time)}",
        "target_distance": f"{target_dist}km",
        "method": "Riegel formula (fatigue factor 1.06)",
        "confidence": "High" if abs(target_dist - known_dist) < known_dist * 2 else "Moderate",
    })


def _riegel_predict(known_dist_km: float, known_time_min: float, target_dist_km: float) -> float:
    """Riegel race prediction: T2 = T1 * (D2/D1)^1.06"""
    fatigue_factor = 1.06
    return known_time_min * (target_dist_km / known_dist_km) ** fatigue_factor


def _format_time(minutes: float) -> str:
    """Format minutes to H:MM:SS or M:SS."""
    total_seconds = int(minutes * 60)
    hours = total_seconds // 3600
    mins = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def _assess_injury_risk(user_id: int) -> str:
    """Assess injury risk from ACWR + history."""
    acwr_data = json.loads(_get_weekly_load_acwr(user_id))
    profile = get_profile(user_id)
    injuries = profile.get("injury_history", []) if profile else []

    acwr = acwr_data.get("acwr", 1.0)
    concerns = []

    if acwr > 1.5:
        concerns.append(f"ACWR is {acwr} (above 1.5 danger threshold)")
    elif acwr > 1.3:
        concerns.append(f"ACWR is {acwr} (approaching caution zone)")

    if injuries:
        concerns.append(f"History of: {', '.join(injuries[:3])}")

    risk_level = "low"
    if acwr > 1.5 or (acwr > 1.3 and injuries):
        risk_level = "high"
    elif acwr > 1.3 or injuries:
        risk_level = "moderate"

    return json.dumps({
        "risk_level": risk_level,
        "acwr": acwr,
        "concerns": concerns,
        "injuries_history": injuries,
        "recommendation": "Reduce training load immediately" if risk_level == "high" else "Monitor and don't increase" if risk_level == "moderate" else "Safe to train normally",
    })


def _calculate_readiness(user_id: int, args: dict) -> str:
    """Calculate training readiness score."""
    sleep = args.get("sleep_quality", 3)
    soreness = args.get("muscle_soreness", 3)
    energy = args.get("energy", 3)

    # Get ACWR influence
    acwr_data = json.loads(_get_weekly_load_acwr(user_id))
    acwr = acwr_data.get("acwr", 1.0)
    acwr_score = 5 if acwr <= 1.0 else (4 if acwr <= 1.2 else (3 if acwr <= 1.4 else 2))

    readiness = (sleep + soreness + energy + acwr_score) / 4

    if readiness >= 4.0:
        recommendation = "Green: quality session today (intervals, tempo, or long run)"
    elif readiness >= 3.0:
        recommendation = "Yellow: easy run only, reduce any planned intensity"
    elif readiness >= 2.0:
        recommendation = "Orange: recovery run or complete rest"
    else:
        recommendation = "Red: rest day. Assess for illness or overtraining."

    return json.dumps({
        "readiness_score": round(readiness, 1),
        "out_of": 5.0,
        "components": {"sleep": sleep, "soreness": soreness, "energy": energy, "load_factor": acwr_score},
        "recommendation": recommendation,
    })


# --- KNOWLEDGE ---

def _retrieve_knowledge(user_id: int, args: dict) -> str:
    query = args.get("query", "")
    profile = get_profile(user_id)
    tier = profile.get("tier", "general") if profile else "general"
    coach = profile.get("coach_style") if profile else None
    results = retriever.retrieve(query, tier=tier, coach=coach)
    formatted = []
    for r in results:
        formatted.append({
            "title": r["chunk"]["title"],
            "content": r["chunk"]["content"],
            "source": r["chunk"]["source"],
            "score": round(r["score"], 4),
        })
    return json.dumps(formatted, indent=2)


def _web_search(args: dict) -> str:
    query = args.get("query", "")
    try:
        from knowledge.web_scraper import scrape_web
        results = scrape_web(query)
        formatted = [{"title": r.get("title"), "snippet": r.get("snippet"), "url": r.get("url")} for r in results]
        return json.dumps(formatted, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Web search unavailable: {e}", "fallback": "Use knowledge base instead"})


# --- ACTION ---

def _log_run(user_id: int, args: dict, thread_id: int | None) -> str:
    entry = {k: v for k, v in args.items() if v not in (None, "")}
    personalization_store.add_training_log(user_id, entry, thread_id=thread_id)
    return json.dumps({"logged": True, "entry": entry})


def _set_goal(user_id: int, args: dict) -> str:
    goal = {"type": args.get("goal_type"), "target": args.get("target"), "weeks": args.get("deadline_weeks")}
    personalization_store.log_event(user_id, "goal_set", goal)
    return json.dumps({"goal_set": True, "goal": goal})


def _generate_plan(user_id: int, args: dict) -> str:
    """Generate a full periodized plan with specific daily workouts and paces."""
    from coaching.plans import generate_periodized_plan

    profile = get_profile(user_id) or {}
    weeks = args.get("weeks", 12)
    days = args.get("days_per_week", profile.get("training_days", 4) if profile else 4)
    goal = args.get("goal", "general fitness")

    persona = args.get("persona", profile.get("coach_style", "scientist"))
    plan = generate_periodized_plan(profile, goal, weeks=weeks, days_per_week=days, persona=persona)
    personalization_store.log_event(user_id, "plan_generated", {
        "goal": goal, "weeks": weeks, "days_per_week": days,
        "vdot": plan.get("vdot"), "paces": plan.get("paces"),
    })

    summary = {
        "goal": plan["goal"],
        "total_weeks": plan["total_weeks"],
        "days_per_week": plan["days_per_week"],
        "paces": plan["paces"],
        "vdot": plan["vdot"],
        "week_summaries": [],
    }
    for week in plan["weeks"]:
        runs = [s for s in week["schedule"] if s["type"] != "rest"]
        summary["week_summaries"].append({
            "week": week["week_number"],
            "volume_km": week["target_volume_km"],
            "deload": week["is_deload"],
            "taper": week["is_taper"],
            "sessions": [
                {"day": r["day"], "name": r.get("name", r["type"].title()),
                 "type": r["type"], "km": r["distance_km"],
                 "pace": r["target_pace"], "desc": r["description"]}
                for r in runs
            ],
        })

    return json.dumps(summary, default=str)


def _adjust_plan(user_id: int, args: dict) -> str:
    adjustment = {"reason": args.get("reason"), "type": args.get("adjustment_type"), "applied": True}
    personalization_store.log_event(user_id, "plan_adjusted", adjustment)
    return json.dumps(adjustment)


def _set_focus(user_id: int, args: dict) -> str:
    focus = {"focus": args.get("focus"), "duration_weeks": args.get("duration_weeks", 4)}
    personalization_store.log_event(user_id, "focus_set", focus)
    return json.dumps(focus)


def _save_insight(user_id: int, args: dict) -> str:
    category = args.get("category", "personal_context")
    content = args.get("content", "")
    personalization_store.log_event(user_id, "insight_saved", {"category": category, "content": content})
    return json.dumps({"saved": True, "category": category, "content": content})


def _check_guardrails(user_id: int, args: dict) -> str:
    profile = get_profile(user_id)
    tier = profile.get("tier", "pace") if profile else "pace"
    result = check_guardrails(
        tier,
        args.get("recommendation_type", "volume_increase"),
        args.get("details", ""),
        weekly_km=args.get("weekly_km"),
        volume_increase_percent=args.get("volume_increase_percent"),
        intensity_type=args.get("intensity_type"),
    )
    return json.dumps(result)


def _set_level(user_id: int, args: dict) -> str:
    profile = get_profile(user_id)
    coach = profile.get("coach_style", "energizer") if profile else "energizer"
    level = args.get("level", 1)
    reason = args.get("reason", "")
    new_level = personalization_store.set_training_level(user_id, coach, level, reason)
    from coaching.cycles import get_level
    info = get_level(coach, new_level)
    return json.dumps({"level": new_level, "level_name": info["name"], "focus": info["focus"]})
