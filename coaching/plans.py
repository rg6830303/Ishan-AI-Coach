import json
import os
from datetime import datetime, timedelta
from engine.pace_calculator import calculate_pace_zones


# Persona-specific workout naming and descriptions
PERSONA_TEMPLATES = {
    "scientist": {
        "easy": {"name": "Zone 2 Aerobic", "desc": "Aerobic base development at 60-65% HRmax. Builds mitochondrial density."},
        "tempo": {"name": "Lactate Threshold", "desc": "LT2 stimulus at {pace}. Physiological target: shift threshold pace."},
        "interval": {"name": "VO2max Intervals", "desc": "4-6x {reps} at {pace} (95-100% VO2max). Full recovery between."},
        "long": {"name": "Long Aerobic Endurance", "desc": "Time on feet for capillarization and fat oxidation. Target: {dist}km at {pace}."},
        "recovery": {"name": "Active Recovery", "desc": "Sub-aerobic threshold movement for lactate clearance. HR < 120bpm."},
        "deload": "Planned deload: reduce volume 25%, maintain one quality session at reduced intensity.",
        "taper": "Taper protocol: volume -{pct}%, intensity maintained. Neural sharpening.",
    },
    "energizer": {
        "easy": {"name": "Adventure Run", "desc": "Easy and joyful! Pick a new route, enjoy the scenery. Just keep it conversational."},
        "tempo": {"name": "Speed Play", "desc": "Feel the POWER! Warm up, then hold {pace} — you'll feel amazing after this one!"},
        "interval": {"name": "Lightning Rounds", "desc": "Fast and fun! {reps} quick bursts at {pace} with easy jog between. Chase the wind!"},
        "long": {"name": "Explorer Run", "desc": "Your long run adventure! {dist}km of discovering how far your legs can take you."},
        "recovery": {"name": "Recharge Day", "desc": "Shake-out jog or fun cross-training. Your body EARNED this easy day!"},
        "deload": "Easy week! You've been crushing it — time to recharge so next week feels AMAZING.",
        "taper": "Race week energy! Keep it light, stay excited. You're ready for this!",
    },
    "warrior": {
        "easy": {"name": "Discipline Miles", "desc": "Execute at {pace}. No faster. Controlled effort builds the engine."},
        "tempo": {"name": "Threshold Mission", "desc": "Warm up. Then hold {pace} for the prescribed distance. No excuses. No shortcuts."},
        "interval": {"name": "Speed Drill", "desc": "{reps} at {pace}. Full effort. Full recovery. Execute each one like it's the last."},
        "long": {"name": "Endurance Test", "desc": "{dist}km. Prove you can sustain. Mental toughness is built here, not in the easy sessions."},
        "recovery": {"name": "Tactical Rest", "desc": "Recovery earned through hard work. Light movement only. Prepare for what's next."},
        "deload": "Strategic pullback. Warriors rest smart — you attack harder next block.",
        "taper": "Sharpening the blade. Volume drops, intensity stays. You're battle-ready.",
    },
    "sage": {
        "easy": {"name": "Easy Run", "desc": "Run at the pace your body chooses today. No watch pressure. Just movement."},
        "tempo": {"name": "Steady Effort", "desc": "Find a sustainable rhythm at {pace}. Not racing — practicing patience under effort."},
        "interval": {"name": "Quick Feet", "desc": "Brief faster efforts at {pace}. Then return to easy. Speed comes in its own time."},
        "long": {"name": "Long & Slow", "desc": "{dist}km. The long run teaches patience. Walk if you need to. The miles will come."},
        "recovery": {"name": "Rest", "desc": "Rest without guilt. The body heals in stillness. The miles will be there tomorrow."},
        "deload": "The seasons teach us: growth needs rest. Ease back. Trust the process.",
        "taper": "You've done the work. Now let the body absorb it. Less is more.",
    },
}


def get_persona_desc(persona: str, run_type: str, pace: str = "", dist: float = 0, reps: str = "400m") -> dict:
    """Get persona-flavored workout name and description."""
    templates = PERSONA_TEMPLATES.get(persona, PERSONA_TEMPLATES["scientist"])
    template = templates.get(run_type, templates.get("easy"))
    if isinstance(template, str):
        return {"name": run_type.title(), "desc": template}
    name = template["name"]
    desc = template["desc"].format(pace=pace, dist=f"{dist:.1f}", reps=reps)
    return {"name": name, "desc": desc}

def generate_periodized_plan(profile: dict, goal: str, weeks: int = 12, days_per_week: int = 3, persona: str = "scientist") -> dict:
    """
    Generates a structured, periodized training plan based on Daniels VDOT paces,
    the runner's profile, training volume tier, and persona coaching style.
    """
    # 1. Calculate training paces
    zones = calculate_pace_zones(profile)
    formatted_paces = zones["formatted"]
    
    easy_pace = formatted_paces["easy"]
    tempo_pace = formatted_paces["tempo"]
    interval_pace = formatted_paces["interval"]
    
    easy_sec = zones["easy_pace_per_km"]
    tempo_sec = zones["tempo_pace_per_km"]
    interval_sec = zones["interval_pace_per_km"]
    
    # 2. Determine base weekly volume depending on tier & goal
    tier = profile.get("tier", "pace")
    base_volumes = {
        "spark": 12.0,
        "pace": 25.0,
        "tempo": 45.0,
        "apex": 65.0,
    }
    start_volume = base_volumes.get(tier, 20.0)
    
    # Adjust starting volume for the selected goal
    goal_modifiers = {
        "5k": 1.0,
        "10k": 1.2,
        "half": 1.5,
        "marathon": 1.8,
        "base": 0.9,
    }
    start_volume = start_volume * goal_modifiers.get(goal.lower(), 1.0)
    
    # Caps based on tier safety rules
    tier_caps = {
        "spark": 15.0,
        "pace": 40.0,
        "tempo": 80.0,
        "apex": 120.0,
    }
    max_volume_cap = tier_caps.get(tier, 40.0)
    
    plan_weeks = []
    current_volume = start_volume
    
    # 3. Generate weeks with periodization (build, deload every 4th, taper last 1-2)
    for w in range(1, weeks + 1):
        is_deload = (w % 4 == 0) and (w < weeks - 1)
        is_taper = w >= weeks - 1
        
        # Calculate weekly volume
        if is_taper:
            # Drop volume by 30% for second-to-last week, 50% for last week
            taper_factor = 0.7 if w == weeks - 1 else 0.5
            weekly_volume = start_volume * taper_factor
        elif is_deload:
            # 25% deload for recovery
            weekly_volume = current_volume * 0.75
        else:
            # Standard build week, increase by 8% (safety check)
            if w > 1:
                current_volume = min(current_volume * 1.08, max_volume_cap)
            weekly_volume = current_volume
            
        weekly_volume = round(weekly_volume, 1)
        
        # Distribute volume among days
        workouts = []
        
        # Allocate run days (e.g. Tues, Thurs, Sat for 3 days; Wed, Fri, Sun for 4/5 days)
        if days_per_week == 3:
            days = [("Tuesday", "quality"), ("Thursday", "easy"), ("Saturday", "long")]
        elif days_per_week == 4:
            days = [("Tuesday", "quality"), ("Wednesday", "easy"), ("Friday", "easy"), ("Sunday", "long")]
        else:  # 5 days
            days = [("Tuesday", "quality"), ("Wednesday", "easy"), ("Thursday", "recovery"), ("Friday", "easy"), ("Saturday", "long")]
            
        # Distribute percentages: Quality 25%, Long 40%, Easy/Recovery divided
        # For deload / taper weeks, modify descriptions to specify lower intensity
        
        for idx, (day_name, run_category) in enumerate(days):
            workout_id = f"W{w}D{idx+1}"
            run_type = "easy"
            dist = 0.0
            pace = easy_pace
            pace_sec = easy_sec

            if run_category == "quality":
                if w % 2 == 1:
                    run_type = "tempo"
                    dist = round(weekly_volume * 0.25, 1)
                    pace = tempo_pace
                    pace_sec = tempo_sec
                else:
                    run_type = "interval"
                    dist = round(weekly_volume * 0.20, 1)
                    pace = interval_pace
                    pace_sec = interval_sec
            elif run_category == "long":
                run_type = "long"
                dist = round(weekly_volume * 0.45, 1)
                pace = easy_pace
                pace_sec = easy_sec
            elif run_category == "recovery":
                run_type = "recovery"
                dist = round(weekly_volume * 0.10, 1)
                pace = easy_pace
                pace_sec = easy_sec
            else:
                run_type = "easy"
                dist = round(weekly_volume * (0.35 if days_per_week == 3 else 0.20), 1)
                pace = easy_pace
                pace_sec = easy_sec

            persona_info = get_persona_desc(persona, run_type, pace=pace, dist=dist)
            desc = persona_info["desc"]
            workout_name = persona_info["name"]
                
            if dist < 1.0:
                dist = 1.0
                
            dur_mins = round((dist * pace_sec) / 60.0)
            
            workouts.append({
                "id": workout_id,
                "day": day_name,
                "name": workout_name,
                "type": run_type,
                "distance_km": dist,
                "duration_minutes": dur_mins,
                "target_pace": pace,
                "description": desc,
                "status": "scheduled",
                "logged_run": None
            })
            
        # Add rest days for non-run days
        all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        filled_days = {w["day"]: w for w in workouts}
        
        complete_week_schedule = []
        for d in all_days:
            if d in filled_days:
                complete_week_schedule.append(filled_days[d])
            else:
                complete_week_schedule.append({
                    "id": f"W{w}{d[:3]}",
                    "day": d,
                    "type": "rest",
                    "distance_km": 0.0,
                    "duration_minutes": 0,
                    "target_pace": "-",
                    "description": "Rest day. Recovery is where adaptations happen.",
                    "status": "rest",
                    "logged_run": None
                })
                
        plan_weeks.append({
            "week_number": w,
            "target_volume_km": weekly_volume,
            "is_deload": is_deload,
            "is_taper": is_taper,
            "schedule": complete_week_schedule
        })
        
    return {
        "goal": goal.upper(),
        "total_weeks": weeks,
        "days_per_week": days_per_week,
        "paces": formatted_paces,
        "vdot": zones["vdot"],
        "generated_at": datetime.now().isoformat(),
        "weeks": plan_weeks
    }
