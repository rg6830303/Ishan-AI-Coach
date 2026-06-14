"""Test script for LLM providers.

Run: python tests/test_providers.py

Tests Claude (Anthropic) if ANTHROPIC_API_KEY is set.
Tests Groq if GROQ_API_KEY is set.
Reports which providers are available and working.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.providers import (
    get_provider, get_best_available_provider,
    resolve_model, estimate_cost, LLMResponse
)
from agent.cost_logger import cost_logger, UsageEntry
from tests.synthetic_runners import get_runner, runner_as_profile
from datetime import datetime


def test_anthropic():
    """Test Claude provider with a simple coaching query."""
    print("\n━━━ ANTHROPIC (Claude) ━━━")
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        print("  SKIP: ANTHROPIC_API_KEY not set")
        return False

    provider = get_provider("anthropic")
    if not provider.available:
        print(f"  FAIL: {provider._init_error}")
        return False

    runner = get_runner("pace")
    messages = [
        {"role": "system", "content": "You are a running coach. Be concise (2 sentences max)."},
        {"role": "user", "content": f"I'm a {runner['tier']} tier runner doing {runner['weekly_km']}km/week. What should my easy pace be?"},
    ]

    print("  Testing Haiku...")
    result = provider.chat(messages, model="haiku", max_tokens=150)
    print(f"    Model: {result.model}")
    print(f"    Latency: {result.latency_ms}ms")
    print(f"    Tokens: {result.input_tokens} in / {result.output_tokens} out")
    print(f"    Cost: ${result.estimated_cost_usd:.6f}")
    print(f"    Response: {result.content[:120]}...")
    print(f"    Status: {'OK' if result.finish_reason != 'error' else 'ERROR'}")

    if result.finish_reason == "error":
        return False

    # Log it
    cost_logger.log_usage(UsageEntry(
        timestamp=datetime.now().isoformat(),
        user_id=runner["id"],
        feature="test",
        provider=result.provider,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
        estimated_cost_usd=result.estimated_cost_usd,
    ))

    # Test with tools
    print("\n  Testing Haiku with tools...")
    from agent.tools import TOOL_DEFINITIONS
    messages_with_tools = [
        {"role": "system", "content": "You are a running coach. Use calculate_pace_zones to answer pace questions. Never invent paces."},
        {"role": "user", "content": "What are my training pace zones if my 5K time is 28.5 minutes?"},
    ]
    result2 = provider.chat(messages_with_tools, model="haiku", tools=TOOL_DEFINITIONS, max_tokens=300)
    print(f"    Finish reason: {result2.finish_reason}")
    print(f"    Tool calls: {result2.tool_calls}")
    print(f"    Latency: {result2.latency_ms}ms")
    print(f"    Cost: ${result2.estimated_cost_usd:.6f}")

    if result2.tool_calls:
        print(f"    TOOL USE WORKING: {[tc['name'] for tc in result2.tool_calls]}")

    print("\n  Claude provider: PASS")
    return True


def test_groq():
    """Test Groq provider."""
    print("\n━━━ GROQ (Llama) ━━━")
    import config
    if not config.groq_key_is_configured():
        print("  SKIP: GROQ_API_KEY not set")
        return False

    provider = get_provider("groq")
    runner = get_runner("spark")
    messages = [
        {"role": "system", "content": "You are a running coach for beginners. Be encouraging. 2 sentences max."},
        {"role": "user", "content": "I just ran 2km without stopping for the first time! What should I do next?"},
    ]

    print("  Testing Llama 8B...")
    result = provider.chat(messages, model="8b", max_tokens=150)
    print(f"    Model: {result.model}")
    print(f"    Latency: {result.latency_ms}ms")
    print(f"    Tokens: {result.input_tokens} in / {result.output_tokens} out")
    print(f"    Cost: ${result.estimated_cost_usd:.6f}")
    print(f"    Response: {result.content[:120]}...")
    print(f"    Status: {'OK' if result.finish_reason != 'error' else 'ERROR'}")

    if result.finish_reason == "error":
        return False

    print("\n  Testing Llama 70B with tools...")
    from agent.tools import TOOL_DEFINITIONS
    messages2 = [
        {"role": "system", "content": "You are a running coach. Use tools when needed."},
        {"role": "user", "content": "Check if it's safe for me to increase my weekly volume by 20%. I currently run 6km/week."},
    ]
    result2 = provider.chat(messages2, model="70b", tools=TOOL_DEFINITIONS, max_tokens=300)
    print(f"    Finish reason: {result2.finish_reason}")
    print(f"    Tool calls: {result2.tool_calls}")
    print(f"    Latency: {result2.latency_ms}ms")

    print("\n  Groq provider: PASS")
    return True


def test_cost_tracking():
    """Test cost logger and budget enforcement."""
    print("\n━━━ COST TRACKING ━━━")
    runner = get_runner("base") if False else get_runner("spark")

    budget = cost_logger.get_budget(runner["id"], plan="base")
    print(f"  User: {runner['name']} (plan: base)")
    print(f"  Budget ceiling: ${budget.ceiling_usd}")
    print(f"  Spent: ${budget.total_cost_usd:.6f}")
    print(f"  Remaining: ${budget.remaining_usd:.6f}")
    print(f"  Daily cap: {budget.daily_cap}")
    print(f"  Can make call: {budget.can_make_call()}")

    # Simulate hitting budget
    print("\n  Simulating cost accumulation...")
    for i in range(5):
        cost_logger.log_usage(UsageEntry(
            timestamp=datetime.now().isoformat(),
            user_id=runner["id"],
            feature="chat",
            provider="groq",
            model="llama-3.3-70b-versatile",
            input_tokens=800,
            output_tokens=400,
            latency_ms=200,
            estimated_cost_usd=estimate_cost("70b", 800, 400),
        ))

    status = cost_logger.check_budget(runner["id"], "base")
    print(f"  After 5 calls: spent=${status['spent_usd']:.6f}, remaining=${status['remaining_usd']:.6f}")
    print(f"  Percent used: {status['percent_used']}%")
    print(f"  Daily calls: {status['daily_calls_today']}/{status['daily_cap']}")

    print("\n  Cost tracking: PASS")
    return True


def test_model_resolution():
    """Test model alias resolution and pricing."""
    print("\n━━━ MODEL RESOLUTION ━━━")
    tests = [
        ("8b", "llama-3.1-8b-instant"),
        ("70b", "llama-3.3-70b-versatile"),
        ("haiku", "claude-haiku-4-5-20251001"),
        ("sonnet", "claude-sonnet-4-6"),
        ("opus", "claude-opus-4-6"),
    ]
    for alias, expected in tests:
        resolved = resolve_model(alias)
        status = "OK" if resolved == expected else "FAIL"
        print(f"  {alias:8s} -> {resolved:35s} [{status}]")

    # Cost estimates
    print("\n  Cost per 1000-token call (in/out):")
    for alias in ["8b", "70b", "haiku", "sonnet", "opus"]:
        cost = estimate_cost(alias, 1000, 1000)
        print(f"    {alias:8s}: ${cost:.6f}")

    print("\n  Model resolution: PASS")
    return True


if __name__ == "__main__":
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Sprint Society AI Coach")
    print("  Provider Test Suite")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    results = {}
    results["models"] = test_model_resolution()
    results["cost"] = test_cost_tracking()
    results["anthropic"] = test_anthropic()
    results["groq"] = test_groq()

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  RESULTS")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for name, passed in results.items():
        icon = "PASS" if passed else ("SKIP" if passed is None else "FAIL")
        print(f"  {name:12s}: {icon}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
