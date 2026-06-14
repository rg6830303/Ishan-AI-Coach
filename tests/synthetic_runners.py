"""Synthetic runner fixtures for testing all tiers.

Each runner has a complete profile, run history, goals, and injury context
so every AI feature can be tested against realistic data.
"""

SYNTHETIC_RUNNERS = [
    {
        "id": 901,
        "name": "Spark Sara",
        "email": "sara@test.sprint",
        "tier": "spark",
        "coach_style": "energizer",
        "plan": "base",
        "profile": {
            "gender": "female",
            "age": 28,
            "height_cm": 162,
            "weight_kg": 68,
            "fitness_level": "lightly_active",
            "running_experience": "beginner",
            "recent_5k_time": None,
            "dream_race": "5K",
            "running_why": "Weight loss, stress relief",
            "training_days": 3,
            "preferred_time": "morning",
            "bad_run_response": "feel_guilty",
            "injury_history": [],
        },
        "runs": [
            {"distance_km": 2.1, "duration_min": 18, "type": "easy", "pace_sec_km": 514, "days_ago": 1},
            {"distance_km": 1.8, "duration_min": 16, "type": "walk_run", "pace_sec_km": 533, "days_ago": 3},
            {"distance_km": 2.5, "duration_min": 21, "type": "easy", "pace_sec_km": 504, "days_ago": 5},
            {"distance_km": 1.5, "duration_min": 14, "type": "walk_run", "pace_sec_km": 560, "days_ago": 7},
            {"distance_km": 2.0, "duration_min": 17, "type": "easy", "pace_sec_km": 510, "days_ago": 9},
            {"distance_km": 1.2, "duration_min": 12, "type": "walk_run", "pace_sec_km": 600, "days_ago": 12},
            {"distance_km": 2.3, "duration_min": 20, "type": "easy", "pace_sec_km": 522, "days_ago": 14},
            {"distance_km": 1.0, "duration_min": 10, "type": "walk_run", "pace_sec_km": 600, "days_ago": 16},
        ],
        "goals": [{"type": "race", "distance": "5K", "target_time": None, "weeks": 8}],
        "weekly_km": 6.4,
        "streak_days": 3,
        "context": "Complete beginner. Started running 2 weeks ago to lose weight before her college reunion. Very motivated but has zero running knowledge. Gets confused by jargon. Needs encouragement and simple instructions.",
    },
    {
        "id": 902,
        "name": "Pace Priya",
        "email": "priya@test.sprint",
        "tier": "pace",
        "coach_style": "scientist",
        "plan": "base",
        "profile": {
            "gender": "female",
            "age": 32,
            "height_cm": 165,
            "weight_kg": 58,
            "fitness_level": "active",
            "running_experience": "intermediate",
            "recent_5k_time": 28.5,
            "dream_race": "10K",
            "running_why": "Personal challenge, race goals",
            "training_days": 4,
            "preferred_time": "evening",
            "bad_run_response": "analyze_it",
            "injury_history": ["shin splints (6 months ago, resolved)"],
        },
        "runs": [
            {"distance_km": 6.0, "duration_min": 36, "type": "easy", "pace_sec_km": 360, "days_ago": 1},
            {"distance_km": 8.0, "duration_min": 46, "type": "long", "pace_sec_km": 345, "days_ago": 3},
            {"distance_km": 5.0, "duration_min": 27, "type": "tempo", "pace_sec_km": 324, "days_ago": 5},
            {"distance_km": 6.5, "duration_min": 39, "type": "easy", "pace_sec_km": 360, "days_ago": 7},
            {"distance_km": 5.0, "duration_min": 30, "type": "easy", "pace_sec_km": 360, "days_ago": 9},
            {"distance_km": 7.0, "duration_min": 40, "type": "long", "pace_sec_km": 343, "days_ago": 10},
            {"distance_km": 4.0, "duration_min": 24, "type": "recovery", "pace_sec_km": 360, "days_ago": 12},
            {"distance_km": 6.0, "duration_min": 34, "type": "easy", "pace_sec_km": 340, "days_ago": 14},
            {"distance_km": 5.5, "duration_min": 30, "type": "tempo", "pace_sec_km": 327, "days_ago": 16},
            {"distance_km": 7.5, "duration_min": 44, "type": "long", "pace_sec_km": 352, "days_ago": 18},
            {"distance_km": 5.0, "duration_min": 30, "type": "easy", "pace_sec_km": 360, "days_ago": 20},
            {"distance_km": 6.0, "duration_min": 36, "type": "easy", "pace_sec_km": 360, "days_ago": 22},
            {"distance_km": 4.5, "duration_min": 25, "type": "intervals", "pace_sec_km": 333, "days_ago": 24},
            {"distance_km": 6.0, "duration_min": 36, "type": "easy", "pace_sec_km": 360, "days_ago": 26},
            {"distance_km": 8.5, "duration_min": 50, "type": "long", "pace_sec_km": 353, "days_ago": 28},
        ],
        "goals": [{"type": "race", "distance": "10K", "target_time": "55:00", "weeks": 12}],
        "weekly_km": 25.0,
        "streak_days": 14,
        "context": "Consistent intermediate runner. Data-driven (she's a data scientist). Recovered from shin splints. Wants a sub-55 10K. Respects evidence-based advice. Gets frustrated by generic coaching.",
    },
    {
        "id": 903,
        "name": "Tempo Tanmay",
        "email": "tanmay@test.sprint",
        "tier": "tempo",
        "coach_style": "warrior",
        "plan": "pro",
        "profile": {
            "gender": "male",
            "age": 35,
            "height_cm": 175,
            "weight_kg": 72,
            "fitness_level": "very_active",
            "running_experience": "advanced",
            "recent_5k_time": 21.0,
            "dream_race": "Half Marathon",
            "running_why": "Competition, personal records",
            "training_days": 5,
            "preferred_time": "morning",
            "bad_run_response": "push_harder_next",
            "injury_history": ["plantar fasciitis (1 year ago, managed)", "IT band (2 years ago, resolved)"],
        },
        "runs": [
            {"distance_km": 12.0, "duration_min": 60, "type": "long", "pace_sec_km": 300, "days_ago": 1},
            {"distance_km": 8.0, "duration_min": 38, "type": "tempo", "pace_sec_km": 285, "days_ago": 2},
            {"distance_km": 6.0, "duration_min": 33, "type": "recovery", "pace_sec_km": 330, "days_ago": 3},
            {"distance_km": 10.0, "duration_min": 48, "type": "easy", "pace_sec_km": 288, "days_ago": 5},
            {"distance_km": 7.0, "duration_min": 30, "type": "intervals", "pace_sec_km": 257, "days_ago": 6},
            {"distance_km": 5.0, "duration_min": 28, "type": "recovery", "pace_sec_km": 336, "days_ago": 7},
            {"distance_km": 15.0, "duration_min": 75, "type": "long", "pace_sec_km": 300, "days_ago": 8},
            {"distance_km": 8.0, "duration_min": 37, "type": "tempo", "pace_sec_km": 278, "days_ago": 9},
            {"distance_km": 6.0, "duration_min": 33, "type": "recovery", "pace_sec_km": 330, "days_ago": 10},
            {"distance_km": 10.0, "duration_min": 50, "type": "easy", "pace_sec_km": 300, "days_ago": 12},
            {"distance_km": 6.0, "duration_min": 26, "type": "intervals", "pace_sec_km": 260, "days_ago": 13},
            {"distance_km": 5.0, "duration_min": 28, "type": "recovery", "pace_sec_km": 336, "days_ago": 14},
            {"distance_km": 18.0, "duration_min": 93, "type": "long", "pace_sec_km": 310, "days_ago": 15},
        ],
        "goals": [{"type": "race", "distance": "Half Marathon", "target_time": "1:32:00", "weeks": 14}],
        "weekly_km": 55.0,
        "streak_days": 42,
        "context": "Serious competitive runner. 42-day streak. Training for sub-1:32 half marathon. Has managed injuries before. Responds well to tough coaching. Wants to be pushed but needs to respect his plantar fasciitis history.",
    },
    {
        "id": 904,
        "name": "Apex Arjun",
        "email": "arjun@test.sprint",
        "tier": "apex",
        "coach_style": "sage",
        "plan": "pro",
        "profile": {
            "gender": "male",
            "age": 29,
            "height_cm": 178,
            "weight_kg": 65,
            "fitness_level": "very_active",
            "running_experience": "advanced",
            "recent_5k_time": 17.5,
            "dream_race": "Marathon",
            "running_why": "Qualify for international races, personal mastery",
            "training_days": 6,
            "preferred_time": "morning",
            "bad_run_response": "analyze_it",
            "injury_history": ["achilles tendinopathy (18 months ago, managed with eccentric loading)"],
        },
        "runs": [
            {"distance_km": 16.0, "duration_min": 72, "type": "easy", "pace_sec_km": 270, "days_ago": 1},
            {"distance_km": 12.0, "duration_min": 50, "type": "tempo", "pace_sec_km": 250, "days_ago": 2},
            {"distance_km": 8.0, "duration_min": 38, "type": "recovery", "pace_sec_km": 285, "days_ago": 3},
            {"distance_km": 14.0, "duration_min": 63, "type": "easy", "pace_sec_km": 270, "days_ago": 4},
            {"distance_km": 10.0, "duration_min": 40, "type": "intervals", "pace_sec_km": 240, "days_ago": 5},
            {"distance_km": 6.0, "duration_min": 30, "type": "recovery", "pace_sec_km": 300, "days_ago": 6},
            {"distance_km": 30.0, "duration_min": 150, "type": "long", "pace_sec_km": 300, "days_ago": 8},
            {"distance_km": 14.0, "duration_min": 63, "type": "easy", "pace_sec_km": 270, "days_ago": 9},
            {"distance_km": 12.0, "duration_min": 49, "type": "tempo", "pace_sec_km": 245, "days_ago": 10},
            {"distance_km": 8.0, "duration_min": 38, "type": "recovery", "pace_sec_km": 285, "days_ago": 11},
            {"distance_km": 16.0, "duration_min": 72, "type": "easy", "pace_sec_km": 270, "days_ago": 12},
            {"distance_km": 8.0, "duration_min": 32, "type": "intervals", "pace_sec_km": 240, "days_ago": 13},
            {"distance_km": 6.0, "duration_min": 30, "type": "recovery", "pace_sec_km": 300, "days_ago": 14},
            {"distance_km": 32.0, "duration_min": 160, "type": "long", "pace_sec_km": 300, "days_ago": 15},
            {"distance_km": 10.0, "duration_min": 45, "type": "easy", "pace_sec_km": 270, "days_ago": 16},
        ],
        "goals": [{"type": "race", "distance": "Marathon", "target_time": "2:55:00", "weeks": 16}],
        "weekly_km": 95.0,
        "streak_days": 180,
        "context": "Elite competitive runner chasing sub-3 marathon. 180-day streak, 95km/wk. Has managed Achilles with eccentric loading. Very analytical. Needs advanced periodization, ACWR monitoring, and marginal gains talk. Values patience and long-term perspective.",
    },
]


def get_runner(tier: str) -> dict:
    """Get a synthetic runner by tier name."""
    for r in SYNTHETIC_RUNNERS:
        if r["tier"] == tier:
            return r
    raise ValueError(f"No synthetic runner for tier: {tier}")


def get_all_runners() -> list[dict]:
    """Get all synthetic runners."""
    return SYNTHETIC_RUNNERS


def runner_as_profile(runner: dict) -> dict:
    """Convert synthetic runner to the format get_profile() returns."""
    profile = dict(runner["profile"])
    profile["id"] = runner["id"]
    profile["tier"] = runner["tier"]
    profile["coach_style"] = runner["coach_style"]
    return profile
