"""Test all 24 tools against synthetic runners."""

import sys
import os
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.makedirs('data/usage_logs', exist_ok=True)
os.makedirs('data/personalization', exist_ok=True)

from agent.tools_full import TOOL_DEFINITIONS, execute_tool
from tests.synthetic_runners import get_all_runners, runner_as_profile
from database.models import init_db
from database.auth import get_profile

init_db()

# Seed a synthetic runner into DB for tool testing
runner = get_all_runners()[1]  # Pace Priya
profile = runner_as_profile(runner)

# Create user if not exists (simplified)
try:
    from database.auth import signup
    signup("Pace Priya", "priya@test.sprint", "test123")
except Exception:
    pass

print("SPRINT 3: TOOL EXECUTION TEST")
print("=" * 65)
print(f"Runner: {runner['name']} (tier={runner['tier']}, 5K={profile.get('recent_5k_time')}min)")
print(f"Tools: {len(TOOL_DEFINITIONS)}")
print("=" * 65)

# Test each tool
test_calls = [
    ("get_runner_profile", {}),
    ("get_recent_runs", {"days": 7}),
    ("get_training_history", {"weeks": 4}),
    ("get_personal_records", {}),
    ("get_goals", {}),
    ("get_progress_and_level", {}),
    ("get_weekly_load_acwr", {}),
    ("get_current_plan", {}),
    ("get_memory_insights", {}),
    ("calculate_pace_zones", {"five_k_minutes": 28.5}),
    ("estimate_vo2max", {"five_k_minutes": 28.5, "age": 32, "gender": "female"}),
    ("predict_race_time", {"known_distance_km": 5, "known_time_minutes": 28.5, "target_distance_km": 21.1}),
    ("assess_injury_risk", {}),
    ("calculate_readiness", {"sleep_quality": 4, "muscle_soreness": 3, "energy": 4}),
    ("retrieve_knowledge", {"query": "tempo run for intermediate runner"}),
    ("log_training_run", {"distance_km": 6.0, "duration_minutes": 36, "type": "easy", "feel": "good"}),
    ("set_goal", {"goal_type": "race", "target": "10K in 55:00", "deadline_weeks": 12}),
    ("generate_training_plan", {"goal": "10K in 55 min", "weeks": 12, "days_per_week": 4}),
    ("adjust_plan", {"reason": "shin tightness after long run", "adjustment_type": "reduce_volume"}),
    ("set_coaching_focus", {"focus": "base building", "duration_weeks": 4}),
    ("save_memory_insight", {"category": "goal", "content": "Wants sub-55 10K by December"}),
    ("check_guardrails", {"recommendation_type": "volume_increase", "details": "Increase to 30km/week", "weekly_km": 30}),
    ("set_training_level", {"level": 3, "reason": "Completed 4 weeks of consistent training"}),
]

passed = 0
failed = 0

for tool_name, args in test_calls:
    result_str = execute_tool(tool_name, args, runner["id"])
    try:
        result = json.loads(result_str)
        has_error = "error" in result and result["error"]
        if has_error:
            print(f"  [!] {tool_name:30s} ERROR: {result['error'][:60]}")
            failed += 1
        else:
            # Show a preview of the result
            preview = result_str[:80].replace("\n", " ")
            print(f"  [OK] {tool_name:30s} {preview}...")
            passed += 1
    except json.JSONDecodeError:
        print(f"  [!] {tool_name:30s} INVALID JSON: {result_str[:60]}")
        failed += 1

# Skip web_search (needs network)
print(f"\n  [--] web_search_cached              SKIPPED (needs network)")

print(f"\n{'=' * 65}")
print(f"RESULTS: {passed} passed | {failed} failed | 1 skipped")
print(f"TOTAL TOOLS: {len(TOOL_DEFINITIONS)}")
print(f"{'=' * 65}")

# Show key computed outputs
print("\nKEY OUTPUTS:")
pace_result = json.loads(execute_tool("calculate_pace_zones", {"five_k_minutes": 28.5}, runner["id"]))
print(f"  Pace zones (5K=28:30): {pace_result.get('formatted', {})}")

vo2_result = json.loads(execute_tool("estimate_vo2max", {"five_k_minutes": 28.5}, runner["id"]))
print(f"  VO2max: {vo2_result.get('vo2max')} ml/kg/min ({vo2_result.get('category')})")

race_result = json.loads(execute_tool("predict_race_time", {"known_distance_km": 5, "known_time_minutes": 28.5, "target_distance_km": 42.195}, runner["id"]))
print(f"  Marathon prediction (from 5K 28:30): {race_result.get('predicted_time')}")

acwr_result = json.loads(execute_tool("get_weekly_load_acwr", {}, runner["id"]))
print(f"  ACWR: {acwr_result.get('acwr')} ({acwr_result.get('risk_level')})")

readiness_result = json.loads(execute_tool("calculate_readiness", {"sleep_quality": 4, "muscle_soreness": 3, "energy": 4}, runner["id"]))
print(f"  Readiness: {readiness_result.get('readiness_score')}/5 ({readiness_result.get('recommendation')[:40]})")
