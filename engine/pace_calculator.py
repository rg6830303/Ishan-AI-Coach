from engine.vo2max import estimate_vo2max_from_5k, estimate_vo2max_from_profile


def get_age_factor(age: int, gender: str) -> float:
    """Age-grading factor: younger = closer to 1.0, older = lower."""
    base = 1.0
    if age > 30:
        decline_rate = 0.006 if gender == "male" else 0.007
        base -= (age - 30) * decline_rate
    return max(0.6, min(1.0, base))


def get_bmi_adjustment(weight_kg: float, height_cm: float) -> float:
    """BMI-based pace adjustment factor (>1 means slower)."""
    bmi = weight_kg / ((height_cm / 100) ** 2)
    if bmi < 18.5:
        return 1.02
    if bmi <= 24.9:
        return 1.0
    if bmi <= 29.9:
        return 1.08
    if bmi <= 34.9:
        return 1.18
    return 1.30


def get_fitness_multiplier(fitness_level: str) -> float:
    """Fitness level pace multiplier (>1 means slower)."""
    multipliers = {
        "sedentary": 1.25,
        "lightly_active": 1.12,
        "active": 1.0,
        "very_active": 0.92,
    }
    return multipliers.get(fitness_level, 1.0)


def calculate_pace_zones_from_profile(
    age: int,
    gender: str,
    weight_kg: float,
    height_cm: float,
    fitness_level: str,
    tier: str,
) -> dict:
    """Calculate pace zones from profile data (no race time available)."""
    tier_base_pace = {
        "spark": 420,
        "pace": 350,
        "tempo": 300,
        "apex": 260,
    }

    base_pace = tier_base_pace.get(tier, 350)
    age_factor = 1 / get_age_factor(age, gender)
    bmi_adjust = get_bmi_adjustment(weight_kg, height_cm)
    fitness_mult = get_fitness_multiplier(fitness_level)

    adjusted_pace = base_pace * age_factor * bmi_adjust * fitness_mult

    return {
        "easy_pace_per_km": round(adjusted_pace * 1.20),
        "tempo_pace_per_km": round(adjusted_pace),
        "interval_pace_per_km": round(adjusted_pace * 0.88),
        "race_pace_per_km": round(adjusted_pace * 0.95),
        "vo2max_estimate": estimate_vo2max_from_profile(age, gender, fitness_level, weight_kg, height_cm),
    }


def calculate_pace_zones_from_5k(five_k_minutes: float) -> dict:
    """Calculate pace zones from a known 5K time."""
    vo2max = estimate_vo2max_from_5k(five_k_minutes)
    five_k_seconds = five_k_minutes * 60
    race_pace = five_k_seconds / 5.0

    return {
        "easy_pace_per_km": round(race_pace * 1.30),
        "tempo_pace_per_km": round(race_pace * 1.10),
        "interval_pace_per_km": round(race_pace * 0.95),
        "race_pace_per_km": round(race_pace),
        "vo2max_estimate": round(vo2max, 1),
    }


def calculate_pace_zones(profile: dict) -> dict:
    """Main entry: uses 5K time if available, else profile-based estimation."""
    five_k = profile.get("recent_5k_time")
    if five_k and five_k > 0:
        zones = calculate_pace_zones_from_5k(five_k)
    else:
        zones = calculate_pace_zones_from_profile(
            profile.get("age", 25),
            profile.get("gender", "male"),
            profile.get("weight_kg", 70),
            profile.get("height_cm", 170),
            profile.get("fitness_level", "active"),
            profile.get("tier", "pace"),
        )

    zones["formatted"] = {
        "easy": format_pace(zones["easy_pace_per_km"]),
        "tempo": format_pace(zones["tempo_pace_per_km"]),
        "interval": format_pace(zones["interval_pace_per_km"]),
        "race": format_pace(zones["race_pace_per_km"]),
    }
    return zones


def format_pace(seconds_per_km: int) -> str:
    """Format seconds to mm:ss/km string."""
    mins = seconds_per_km // 60
    secs = seconds_per_km % 60
    return f"{mins}:{secs:02d}/km"
