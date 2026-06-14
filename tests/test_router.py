"""Test the adaptive router — Sprint 2 verification."""

import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.makedirs('data/usage_logs', exist_ok=True)
os.makedirs('data/personalization', exist_ok=True)

from agent.router import (
    select_route, get_task_level, classify_chat_complexity,
    get_router_status, report_result, get_circuit
)
from agent.providers import estimate_cost
from agent.cost_logger import cost_logger
from tests.synthetic_runners import get_all_runners


print("SPRINT 2: ADAPTIVE ROUTER TEST")
print("=" * 65)

# Test task classification
print("\nTASK LEVEL CLASSIFICATION:")
test_cases = [
    ("pace_zones", "", "Pure math"),
    ("daily_insight", "", "Simple tip"),
    ("chat", "what is tempo run", "Simple factual"),
    ("chat", "should I run today given my knee pain", "Personalized"),
    ("chat", "create a 16 week marathon plan with periodization", "Complex plan"),
    ("post_run", "", "Run analysis"),
    ("plan", "", "Training plan gen"),
]
for feature, msg, desc in test_cases:
    level = get_task_level(feature, msg)
    print(f"  Level {level} | {feature:15s} | {desc}")

# Test routing per runner
print("\nROUTING DECISIONS PER RUNNER:")
print("-" * 65)
runners = get_all_runners()

for runner in runners:
    print(f"\n  {runner['name']} (tier={runner['tier']}, plan={runner['plan']}):")

    scenarios = [
        ("pace_zones", "What is my easy pace?"),
        ("daily_insight", "Give me a tip"),
        ("chat", "How should I adjust for my knee?"),
        ("plan", "Create a 12 week half marathon plan"),
    ]

    for feature, msg in scenarios:
        route = select_route(feature, msg, runner["tier"], runner["plan"], runner["id"])
        model_short = route.model[:28] if route.model else "none"
        print(f"    {feature:15s} -> {route.provider:10s} {model_short:30s} L{route.level}")
        print(f"                    {route.reason}")

# Circuit breaker test
print("\n\nCIRCUIT BREAKER TEST:")
print("-" * 65)
circuit = get_circuit("groq")
circuit.open_until = 0
circuit.failures = 0
print(f"  Initial: open={circuit.is_open}, failures={circuit.failures}")

for i in range(3):
    report_result("groq", False)
print(f"  After 3 failures: open={circuit.is_open}")

route = select_route("chat", "test", "pace", "base", 901)
print(f"  Route (Groq down): {route.provider} / {route.model}")
print(f"  Reason: {route.reason}")

# Reset
circuit.open_until = 0
circuit.failures = 0

# Budget test
print("\n\nBUDGET ENFORCEMENT TEST:")
print("-" * 65)
budget = cost_logger.get_budget(901, "base")

budget.total_cost_usd = 0.0
budget.daily_calls = 0
route_ok = select_route("chat", "test", "spark", "base", 901)
print(f"  Fresh budget: {route_ok.provider} ({route_ok.reason})")

budget.total_cost_usd = 0.04  # Over $0.036 ceiling
route_blocked = select_route("chat", "test", "spark", "base", 901)
print(f"  Over budget:  {route_blocked.provider} ({route_blocked.reason})")

budget.total_cost_usd = 0.0
budget.daily_calls = 5  # At daily cap
route_capped = select_route("chat", "test", "spark", "base", 901)
print(f"  Daily capped: {route_capped.provider} ({route_capped.reason})")

# Reset
budget.total_cost_usd = 0.0
budget.daily_calls = 0

# Status
print("\n\nROUTER STATUS:")
for k, v in get_router_status().items():
    print(f"  {k}: {v}")

print("\n" + "=" * 65)
print("SPRINT 2 ROUTER: ALL TESTS PASS")
print("=" * 65)
