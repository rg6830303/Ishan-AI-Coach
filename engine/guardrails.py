TIER_GUARDRAILS = {
    "spark": {
        "max_weekly_km": 15,
        "max_consecutive_run_days": 3,
        "min_rest_days_per_week": 3,
        "max_run_duration_minutes": 40,
        "max_volume_increase_percent": 10,
        "allowed_intensity": ["easy", "walk_run"],
        "never_recommend": ["intervals", "tempo_runs", "hill_sprints", "fasted_runs", "doubles"],
        "injury_response": "always_rest_first",
        "notes": "Focus on habit-building and consistency. Never push volume.",
    },
    "pace": {
        "max_weekly_km": 40,
        "max_consecutive_run_days": 4,
        "min_rest_days_per_week": 2,
        "max_run_duration_minutes": 75,
        "max_volume_increase_percent": 10,
        "allowed_intensity": ["easy", "tempo", "fartlek", "strides"],
        "never_recommend": ["VO2max_intervals_over_1km", "doubles", "altitude_training"],
        "injury_response": "reduce_and_assess",
        "notes": "10% rule is sacred. Quality over quantity. 48h between hard sessions.",
    },
    "tempo": {
        "max_weekly_km": 80,
        "max_consecutive_run_days": 5,
        "min_rest_days_per_week": 1,
        "max_run_duration_minutes": 150,
        "max_volume_increase_percent": 10,
        "allowed_intensity": ["easy", "tempo", "threshold", "interval", "long_run", "fartlek", "hills"],
        "never_recommend": ["no_rest_week", "race_during_build_phase"],
        "injury_response": "modify_and_cross_train",
        "deload_frequency_weeks": 4,
        "notes": "Periodization is key. Deload every 4th week. Never skip taper.",
    },
    "apex": {
        "max_weekly_km": 150,
        "max_consecutive_run_days": 6,
        "min_rest_days_per_week": 1,
        "max_run_duration_minutes": 210,
        "max_volume_increase_percent": 10,
        "max_acwr": 1.5,
        "strain_ceiling": 800,
        "allowed_intensity": ["all"],
        "never_recommend": ["ignore_hrv_signals", "skip_taper", "race_when_overreached"],
        "injury_response": "data_driven_modification",
        "notes": "ACWR must stay below 1.5. HRV guides intensity. Taper is non-negotiable.",
    },
}


def check_guardrails(tier: str, recommendation_type: str, details: str) -> dict:
    """
    Validate a coaching recommendation against tier-specific guardrails.
    Returns pass/fail with explanation.
    """
    rules = TIER_GUARDRAILS.get(tier, TIER_GUARDRAILS["pace"])

    result = {"passed": True, "warnings": [], "blocked": False, "reason": ""}

    if recommendation_type == "volume_increase":
        max_pct = rules["max_volume_increase_percent"]
        result["warnings"].append(
            f"Volume increases must not exceed {max_pct}% per week."
        )
        if "20%" in details or "30%" in details or "double" in details.lower():
            result["passed"] = False
            result["blocked"] = True
            result["reason"] = f"Volume increase exceeds {max_pct}% weekly cap for {tier} tier."

    elif recommendation_type == "intensity_session":
        never = rules.get("never_recommend", [])
        for forbidden in never:
            if forbidden.lower().replace("_", " ") in details.lower():
                result["passed"] = False
                result["blocked"] = True
                result["reason"] = f"'{forbidden}' is not recommended for {tier} tier runners."
                break

        allowed = rules.get("allowed_intensity", [])
        if "all" not in allowed:
            result["warnings"].append(
                f"Allowed intensities for {tier}: {', '.join(allowed)}"
            )

    elif recommendation_type == "race_recommendation":
        if tier == "spark":
            result["warnings"].append(
                "Spark runners should only race 5K or fun runs. No half/full marathon."
            )
        if tier == "tempo" and "during build" in details.lower():
            result["passed"] = False
            result["reason"] = "Racing during build phase is not recommended for Tempo tier."

    elif recommendation_type == "return_from_injury":
        response = rules["injury_response"]
        result["warnings"].append(f"Injury protocol for {tier}: {response}")
        if tier == "spark":
            result["warnings"].append("Always recommend rest first. Never push through pain.")

    if tier == "apex" and "acwr" in details.lower():
        result["warnings"].append(f"ACWR must remain below {rules.get('max_acwr', 1.5)}")

    return result


def get_guardrails_summary(tier: str) -> str:
    """Get a brief guardrails summary for system prompt injection."""
    rules = TIER_GUARDRAILS.get(tier, TIER_GUARDRAILS["pace"])
    never = rules.get("never_recommend", [])
    never_str = ", ".join(never) if never else "none"

    return (
        f"GUARDRAILS ({tier.upper()} tier):\n"
        f"- Max weekly volume: {rules['max_weekly_km']}km\n"
        f"- Max consecutive run days: {rules['max_consecutive_run_days']}\n"
        f"- Volume increase cap: {rules['max_volume_increase_percent']}%/week\n"
        f"- Never recommend: {never_str}\n"
        f"- Injury response: {rules['injury_response']}\n"
        f"- Notes: {rules['notes']}"
    )
