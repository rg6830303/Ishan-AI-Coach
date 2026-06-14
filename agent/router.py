"""Adaptive model router with budget enforcement, caching, and circuit breaker.

Inspired by:
- Mohamed-Elguindy/Fitness-App: RouterQueryEngine pattern (route by query type)
- oscartiz/hermes-agent: Clean provider abstraction
- Sprint Society runbook: 1/3-of-plan-price budget rule

Routing hierarchy:
  1. Task classifier determines complexity level (0-4)
  2. Budget check: can user afford this model?
  3. Provider selection: Groq (free) -> Claude (premium) -> Rule-based (fallback)
  4. Circuit breaker: skip failed providers for 10 min
  5. Cache: return cached response for repeated corpus queries
"""

import time
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import config
from agent.providers import (
    get_provider, resolve_model, estimate_cost, LLMResponse,
    GroqProvider, AnthropicProvider,
)
from agent.cost_logger import cost_logger


# ============================================================
# TASK CLASSIFIER
# ============================================================

# Feature -> static complexity level
# Level 0: Math/Rules only (no LLM needed)
# Level 1: Simple LLM (8B, short output, near-zero cost)
# Level 2: Standard LLM (70B, moderate output)
# Level 3: Premium LLM (Claude Haiku/Sonnet for complex reasoning)
FEATURE_LEVELS = {
    "pace_zones": 0,       # Pure math
    "vo2max": 0,           # Pure math
    "race_predict": 0,     # Pure math + RAG context for explanation
    "readiness": 0,        # Pure formula (HR + soreness + sleep)
    "daily_insight": 1,    # Short, simple, low-stakes
    "pre_run": 1,          # Short brief, mostly RAG
    "challenge": 1,        # Simple generation
    "proactive": 1,        # Rule-triggered, simple output
    "post_run": 2,         # Analysis needs reasoning
    "weekly_summary": 2,   # Synthesis across days
    "injury_risk": 2,      # Important, needs good reasoning
    "chat": 2,             # Default for chat (can escalate)
    "profiling": 2,        # One-time, important to get right
    "plan": 3,             # Complex multi-week generation
}


def classify_chat_complexity(message: str) -> int:
    """Classify a free-form chat message into complexity level.

    Level 1: Simple factual ("what is tempo run", "how far is 10K")
    Level 2: Personalized advice ("should I run today", "analyze my week")
    Level 3: Complex planning ("create a plan", "periodize my training")
    """
    message_lower = message.lower()

    # Level 3 indicators: complex multi-step reasoning
    level_3_keywords = [
        "create a plan", "build a plan", "generate plan", "training plan",
        "periodiz", "12 week", "16 week", "marathon prep",
        "analyze my entire", "comprehensive review",
        "injury protocol", "return to run",
    ]
    if any(kw in message_lower for kw in level_3_keywords):
        return 3

    # Level 1 indicators: simple factual
    level_1_keywords = [
        "what is", "what are", "define", "explain",
        "how far", "how long", "how many",
        "tell me about", "difference between",
    ]
    if any(kw in message_lower for kw in level_1_keywords) and len(message) < 80:
        return 1

    # Default for chat: Level 2
    return 2


def get_task_level(feature: str, message: str = "") -> int:
    """Get the complexity level for a given feature + message."""
    base_level = FEATURE_LEVELS.get(feature, 2)

    # Chat can escalate based on message content
    if feature == "chat" and message:
        chat_level = classify_chat_complexity(message)
        return max(base_level, chat_level)

    return base_level


# ============================================================
# CIRCUIT BREAKER
# ============================================================

@dataclass
class CircuitState:
    failures: int = 0
    last_failure: float = 0.0
    open_until: float = 0.0  # timestamp when circuit closes again

    @property
    def is_open(self) -> bool:
        """True if circuit is open (provider should be skipped)."""
        if self.open_until == 0:
            return False
        return time.time() < self.open_until

    def record_failure(self):
        """Record a failure. Open circuit after 3 failures in 5 minutes."""
        now = time.time()
        # Reset if last failure was > 5 min ago
        if now - self.last_failure > 300:
            self.failures = 0
        self.failures += 1
        self.last_failure = now
        # Open circuit after 3 failures
        if self.failures >= 3:
            self.open_until = now + 600  # Skip for 10 minutes
            self.failures = 0

    def record_success(self):
        """Record success, reset failure count."""
        self.failures = 0
        self.open_until = 0.0


# Global circuit states per provider
_circuits: dict[str, CircuitState] = {
    "groq": CircuitState(),
    "anthropic": CircuitState(),
}


def get_circuit(provider: str) -> CircuitState:
    if provider not in _circuits:
        _circuits[provider] = CircuitState()
    return _circuits[provider]


# ============================================================
# RESPONSE CACHE
# ============================================================

@dataclass
class CacheEntry:
    response: str
    timestamp: float
    ttl: float  # seconds

    @property
    def is_valid(self) -> bool:
        return (time.time() - self.timestamp) < self.ttl


# Simple in-memory cache (corpus-only answers, pace tables)
_cache: dict[str, CacheEntry] = {}
MAX_CACHE_SIZE = 500
CACHE_TTL_SHORT = 300    # 5 min for dynamic content
CACHE_TTL_LONG = 3600    # 1 hour for factual/corpus content


def _cache_key(feature: str, message: str, tier: str) -> str:
    """Generate cache key from request parameters."""
    raw = f"{feature}:{tier}:{message.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_cached(feature: str, message: str, tier: str) -> str | None:
    """Get cached response if available and valid."""
    key = _cache_key(feature, message, tier)
    entry = _cache.get(key)
    if entry and entry.is_valid:
        return entry.response
    return None


def set_cache(feature: str, message: str, tier: str, response: str, long_ttl: bool = False):
    """Cache a response."""
    if len(_cache) >= MAX_CACHE_SIZE:
        # Evict oldest entries
        oldest = sorted(_cache.items(), key=lambda x: x[1].timestamp)[:100]
        for k, _ in oldest:
            del _cache[k]

    key = _cache_key(feature, message, tier)
    ttl = CACHE_TTL_LONG if long_ttl else CACHE_TTL_SHORT
    _cache[key] = CacheEntry(response=response, timestamp=time.time(), ttl=ttl)


# Features where cache makes sense (factual, not personalized per-moment)
CACHEABLE_FEATURES = {"daily_insight", "challenge", "pre_run"}


# ============================================================
# MODEL SELECTOR
# ============================================================

@dataclass
class RouteDecision:
    """Result of the routing decision."""
    model: str
    provider: str
    level: int
    reason: str
    use_tools: bool = True
    max_tokens: int = 1024
    temperature: float = 0.7
    cached: bool = False
    cache_response: str | None = None


def select_route(
    feature: str,
    message: str,
    tier: str,
    plan: str,
    user_id: int,
) -> RouteDecision:
    """Select the optimal model/provider based on all factors.

    Decision chain:
    1. Determine task level
    2. Check cache
    3. Check budget
    4. Check circuit breakers
    5. Select model based on level + tier + plan + budget
    """
    level = get_task_level(feature, message)

    # Level 0: No LLM needed
    if level == 0:
        return RouteDecision(
            model="none", provider="rules",
            level=0, reason="Pure math/rules — no LLM needed",
            use_tools=False, max_tokens=0,
        )

    # Check cache
    if feature in CACHEABLE_FEATURES:
        cached = get_cached(feature, message, tier)
        if cached:
            return RouteDecision(
                model="cache", provider="cache",
                level=level, reason="Cached response",
                cached=True, cache_response=cached,
            )

    # Check budget
    budget = cost_logger.get_budget(user_id, plan)
    if not budget.can_make_call():
        return RouteDecision(
            model="none", provider="fallback",
            level=level, reason="Budget exhausted — using rule-based fallback",
            use_tools=False,
        )

    # Determine target model based on level + tier + plan
    groq_circuit = get_circuit("groq")
    claude_circuit = get_circuit("anthropic")

    # Level 1: Always use cheapest (Groq 8B)
    if level == 1:
        if not groq_circuit.is_open and config.groq_key_is_configured():
            return RouteDecision(
                model=config.GROQ_MODEL_SMALL,
                provider="groq", level=level,
                reason="Level 1 (simple) -> Groq 8B",
                use_tools=False,  # Simple tasks don't need tools
                max_tokens=512,
            )
        # Fallback to Claude Haiku if Groq is down
        if not claude_circuit.is_open:
            return RouteDecision(
                model="claude-haiku-4-5-20251001",
                provider="anthropic", level=level,
                reason="Level 1 fallback -> Claude Haiku (Groq circuit open)",
                use_tools=False, max_tokens=512,
            )
        # All providers down
        return RouteDecision(
            model="none", provider="fallback",
            level=level, reason="All providers down — rule-based fallback",
            use_tools=False,
        )

    # Level 2: Use tier-appropriate model on Groq (70B for tempo/apex, 8B for spark/pace)
    if level == 2:
        tier_model = config.TIERS.get(tier, config.TIERS["pace"])["model"]

        # Pro users with budget can get Claude Haiku for better quality
        if plan == "pro" and budget.remaining_usd > 0.005 and not claude_circuit.is_open:
            # Only escalate to Claude if it's a meaningful conversation
            if feature == "chat" and len(message) > 50:
                return RouteDecision(
                    model="claude-haiku-4-5-20251001",
                    provider="anthropic", level=level,
                    reason="Level 2 Pro user -> Claude Haiku (better reasoning)",
                    use_tools=True, max_tokens=1024,
                )

        if not groq_circuit.is_open and config.groq_key_is_configured():
            return RouteDecision(
                model=tier_model,
                provider="groq", level=level,
                reason=f"Level 2 -> Groq {tier_model.split('-')[1]} (tier: {tier})",
                use_tools=True, max_tokens=1024,
            )
        if not claude_circuit.is_open:
            return RouteDecision(
                model="claude-haiku-4-5-20251001",
                provider="anthropic", level=level,
                reason="Level 2 fallback -> Claude Haiku",
                use_tools=True, max_tokens=1024,
            )
        return RouteDecision(
            model="none", provider="fallback",
            level=level, reason="All providers down",
            use_tools=False,
        )

    # Level 3: Premium — use best available within budget
    if level >= 3:
        # Check if budget allows Claude Sonnet
        sonnet_cost = estimate_cost("sonnet", 2000, 1000)
        haiku_cost = estimate_cost("haiku", 2000, 1000)

        if plan == "pro" and budget.remaining_usd > sonnet_cost and not claude_circuit.is_open:
            return RouteDecision(
                model="claude-sonnet-4-6",
                provider="anthropic", level=level,
                reason="Level 3 Pro -> Claude Sonnet (complex task, budget allows)",
                use_tools=True, max_tokens=2048, temperature=0.6,
            )
        if budget.remaining_usd > haiku_cost and not claude_circuit.is_open:
            return RouteDecision(
                model="claude-haiku-4-5-20251001",
                provider="anthropic", level=level,
                reason="Level 3 -> Claude Haiku (budget-conscious premium)",
                use_tools=True, max_tokens=1536,
            )
        # Fall back to Groq 70B
        if not groq_circuit.is_open and config.groq_key_is_configured():
            return RouteDecision(
                model=config.GROQ_MODEL_LARGE,
                provider="groq", level=level,
                reason="Level 3 fallback -> Groq 70B (Claude over budget or down)",
                use_tools=True, max_tokens=1024,
            )
        return RouteDecision(
            model="none", provider="fallback",
            level=level, reason="All providers down or over budget",
            use_tools=False,
        )

    # Should never reach here
    return RouteDecision(model="none", provider="fallback", level=level, reason="Unknown")


def report_result(provider: str, success: bool):
    """Report call result to circuit breaker."""
    circuit = get_circuit(provider)
    if success:
        circuit.record_success()
    else:
        circuit.record_failure()


def get_router_status() -> dict:
    """Get current router status for debug panel."""
    return {
        "groq_circuit": "OPEN (skipping)" if get_circuit("groq").is_open else "CLOSED (active)",
        "anthropic_circuit": "OPEN (skipping)" if get_circuit("anthropic").is_open else "CLOSED (active)",
        "cache_size": len(_cache),
        "groq_failures": get_circuit("groq").failures,
        "anthropic_failures": get_circuit("anthropic").failures,
    }
