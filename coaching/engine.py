"""Headless coach engine — the single entry point for all AI features.

Usage:
    from coaching.engine import coach

    result = coach.handle("chat", {
        "user_id": 901,
        "message": "What should I do today?",
        "tier": "pace",
        "persona": "scientist",
        "plan": "base",
    })

    # result = {
    #     "text": "...",
    #     "tools_used": [...],
    #     "citations": [...],
    #     "insights": [...],
    #     "tokens": {"input": N, "output": N},
    #     "est_cost": 0.00123,
    #     "model": "llama-3.3-70b-versatile",
    #     "provider": "groq",
    # }

Features supported:
    chat, profiling, plan, daily_insight, pre_run, post_run,
    challenge, weekly_summary, proactive, race_predict, injury_risk
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

from agent.providers import (
    get_provider, get_best_available_provider,
    resolve_model, estimate_cost, LLMResponse,
)
from agent.cost_logger import cost_logger, UsageEntry
from agent.system_prompts import build_system_prompt
from agent.tools import TOOL_DEFINITIONS, execute_tool
from knowledge.retriever import retriever
from engine.guardrails import check_guardrails
from database.auth import get_profile
from database.memory import get_chat_history, get_top_insights, store_message, extract_insights
from personalization.store import store as personalization_store
from coaching.cycles import estimate_starting_level, level_block_for_prompt
import config


@dataclass
class CoachResult:
    text: str = ""
    tools_used: list[str] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    tokens: dict = field(default_factory=lambda: {"input": 0, "output": 0})
    est_cost: float = 0.0
    model: str = ""
    provider: str = ""
    level: int = 0
    feature: str = ""
    guardrail_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# Feature → default model tier mapping
# "classify" = use 8B just for task classification
# "default" = use the tier's default model (70B for tempo/apex, 8B for spark/pace)
# "premium" = use Claude when budget allows
FEATURE_MODEL_MAP = {
    "chat": "default",
    "profiling": "default",
    "plan": "premium",  # Plans benefit from better reasoning
    "daily_insight": "classify",  # Simple, short output
    "pre_run": "classify",
    "post_run": "default",
    "challenge": "classify",
    "weekly_summary": "default",
    "proactive": "classify",
    "race_predict": "classify",  # Mostly formula-based
    "injury_risk": "default",
}


def _select_model(feature: str, tier: str, plan: str, budget_remaining: float) -> tuple[str, str]:
    """Select model and provider based on feature, tier, plan, and budget.

    Returns (model_name, provider_name).
    """
    model_class = FEATURE_MODEL_MAP.get(feature, "default")

    if model_class == "classify":
        # Always cheap — 8B on Groq
        return config.GROQ_MODEL_SMALL, "groq"

    if model_class == "premium" and plan == "pro" and budget_remaining > 0.01:
        # Pro users with budget get Claude Haiku for premium features
        return "claude-haiku-4-5-20251001", "anthropic"

    # Default: use tier's model on Groq
    tier_model = config.TIERS.get(tier, config.TIERS["pace"])["model"]
    return tier_model, "groq"


def _retrieve_context(query: str, tier: str, coach: str | None, feature: str) -> list[dict]:
    """Retrieve relevant knowledge for the query."""
    try:
        results = retriever.retrieve(query, tier=tier, coach=coach)
        return results
    except Exception:
        return []


class CoachEngine:
    """The adaptive coaching engine. One entry point for all AI features."""

    def handle(self, feature: str, context: dict) -> CoachResult:
        """Process a coaching request.

        Args:
            feature: One of chat|profiling|plan|daily_insight|pre_run|post_run|
                     challenge|weekly_summary|proactive|race_predict|injury_risk
            context: {
                user_id: int,
                message: str (for chat) or query context,
                tier: str,
                persona: str,
                plan: str ("free"|"base"|"pro"),
                thread_id: int | None,
                locale: str ("en"|"hi"|"hinglish"),
            }

        Returns:
            CoachResult with text, tools_used, citations, cost, etc.
        """
        user_id = context.get("user_id")
        message = context.get("message", "")
        tier = context.get("tier", "pace")
        persona = context.get("persona", "energizer")
        plan = context.get("plan", "base")
        thread_id = context.get("thread_id")
        locale = context.get("locale", "en")

        result = CoachResult(feature=feature)

        # 1. Check budget
        budget = cost_logger.get_budget(user_id, plan)
        if not budget.can_make_call():
            result.text = self._budget_exhausted_response(feature, locale)
            result.guardrail_flags.append("budget_exhausted")
            return result

        # 2. Select model
        model, provider_name = _select_model(feature, tier, plan, budget.remaining_usd)
        result.model = model
        result.provider = provider_name

        # 3. Retrieve knowledge (RAG)
        rag_query = message if feature == "chat" else self._build_rag_query(feature, context)
        rag_results = _retrieve_context(rag_query, tier, persona, feature)
        if rag_results:
            result.citations = [
                {"title": r["chunk"]["title"], "source": r["chunk"]["source"]}
                for r in rag_results
            ]

        # 4. Build context
        profile = get_profile(user_id) if user_id else {}
        insights = get_top_insights(user_id) if user_id else []

        # Personalization
        if profile:
            personalization_store.sync_profile(user_id, profile)
        personalization_block = personalization_store.build_prompt_block(user_id) if user_id else ""

        # Training cycle level
        start_level = estimate_starting_level(persona, profile) if profile else 1
        current_level = personalization_store.get_training_level(user_id, persona, default=start_level) if user_id else start_level
        cycle_block = level_block_for_prompt(persona, current_level)
        personalization_block = (cycle_block + "\n\n" + personalization_block).strip()
        result.level = current_level

        # Profile summary
        profile_summary = self._format_profile(profile) if profile else "No profile data."

        # 5. Build system prompt
        system_prompt = build_system_prompt(
            tier, persona, profile_summary, insights, personalization_block
        )

        # Inject RAG context into system prompt
        if rag_results:
            rag_text = "\n\nRELEVANT KNOWLEDGE (cite when using):\n"
            for r in rag_results:
                rag_text += f"- [{r['chunk']['title']}]: {r['chunk']['content'][:500]}\n"
            system_prompt += rag_text

        # Inject locale instruction
        if locale == "hi":
            system_prompt += "\n\nREPLY IN HINDI (Devanagari script). Keep technical terms in English."
        elif locale == "hinglish":
            system_prompt += "\n\nREPLY IN HINGLISH (Roman Hindi mixed with English). Natural, conversational."

        # Inject feature-specific instruction
        system_prompt += self._feature_instruction(feature, context)

        # 6. Build messages
        messages = [{"role": "system", "content": system_prompt}]

        if feature == "chat" and user_id:
            history = get_chat_history(user_id, thread_id=thread_id)
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": message})

        # 7. Call LLM (agent loop with tools)
        provider = get_provider(provider_name)
        tools = TOOL_DEFINITIONS if feature in ("chat", "plan", "injury_risk", "post_run") else None

        iterations = 0
        max_iter = config.MAX_AGENT_ITERATIONS if tools else 1
        total_input = 0
        total_output = 0

        while iterations < max_iter:
            iterations += 1
            llm_result = provider.chat(messages, model=model, tools=tools, max_tokens=1024)
            total_input += llm_result.input_tokens
            total_output += llm_result.output_tokens

            if llm_result.finish_reason == "error":
                # Fallback: try without tools
                if tools:
                    llm_result = provider.chat(messages, model=model, tools=None, max_tokens=1024)
                    total_input += llm_result.input_tokens
                    total_output += llm_result.output_tokens
                if llm_result.finish_reason == "error":
                    result.text = "I'm having trouble right now. Please try again in a moment."
                    result.guardrail_flags.append("provider_error")
                    return result
                break

            if llm_result.tool_calls:
                # Execute tools
                # Build assistant message for conversation
                assistant_msg = {"role": "assistant", "content": llm_result.content or ""}
                messages.append(assistant_msg)

                for tc in llm_result.tool_calls:
                    tool_result = execute_tool(tc["name"], tc["arguments"], user_id, thread_id=thread_id)
                    result.tools_used.append(tc["name"])
                    messages.append({
                        "role": "tool" if provider_name == "groq" else "user",
                        "tool_call_id": tc["id"],
                        "content": tool_result,
                    })
                    # For Anthropic, wrap tool results properly
                    if provider_name == "anthropic":
                        messages[-1] = {
                            "role": "user",
                            "content": [{"type": "tool_result", "tool_use_id": tc["id"], "content": tool_result}],
                        }
            else:
                # Final response
                result.text = llm_result.content or ""
                break

        # 8. Post-processing
        result.tokens = {"input": total_input, "output": total_output}
        result.est_cost = estimate_cost(model, total_input, total_output)

        # Store chat message
        if feature == "chat" and user_id:
            store_message(user_id, "user", message, thread_id=thread_id)
            store_message(user_id, "assistant", result.text, result.tools_used or None, thread_id=thread_id)
            extract_insights(user_id, message, role="user")
            extract_insights(user_id, result.text, role="assistant")

        # Log usage
        cost_logger.log_usage(UsageEntry(
            timestamp=datetime.now().isoformat(),
            user_id=user_id or 0,
            feature=feature,
            provider=provider_name,
            model=model,
            input_tokens=total_input,
            output_tokens=total_output,
            latency_ms=0,
            estimated_cost_usd=result.est_cost,
            tools_used=result.tools_used,
        ))

        return result

    def _budget_exhausted_response(self, feature: str, locale: str) -> str:
        if locale == "hi":
            return "आपका आज का AI बजट समाप्त हो गया है। कल फिर मिलते हैं!"
        elif locale == "hinglish":
            return "Aaj ka AI budget khatam ho gaya hai boss. Kal phir baat karte hain!"
        return "You've reached today's coaching limit. See you tomorrow! Keep running."

    def _format_profile(self, profile: dict) -> str:
        five_k = profile.get("recent_5k_time")
        five_k_str = f"{five_k:.1f} min" if five_k else "not recorded"
        return (
            f"Tier: {profile.get('tier', 'unknown').upper()}\n"
            f"Age: {profile.get('age', '?')} | Gender: {profile.get('gender', '?')}\n"
            f"Fitness: {profile.get('fitness_level', '?')} | Experience: {profile.get('running_experience', '?')}\n"
            f"5K time: {five_k_str}\n"
            f"Dream race: {profile.get('dream_race', '?')}\n"
            f"Training days/week: {profile.get('training_days', '?')}\n"
            f"Injuries: {profile.get('injury_history', [])}"
        )

    def _build_rag_query(self, feature: str, context: dict) -> str:
        """Build a RAG query appropriate for the feature."""
        tier = context.get("tier", "pace")
        queries = {
            "daily_insight": f"daily coaching tip for {tier} runner",
            "pre_run": f"pre-run warmup and preparation for {tier} runner",
            "post_run": f"post-run recovery and analysis for {tier} runner",
            "challenge": f"training challenge ideas for {tier} runner",
            "weekly_summary": f"weekly training review for {tier} runner",
            "proactive": f"proactive coaching alerts for {tier} runner",
            "race_predict": f"race prediction methodology",
            "injury_risk": f"injury risk assessment and prevention",
            "profiling": f"runner classification and profiling methodology",
            "plan": f"training plan periodization for {tier} runner {context.get('message', '')}",
        }
        return queries.get(feature, context.get("message", f"{feature} for {tier}"))

    def _feature_instruction(self, feature: str, context: dict) -> str:
        """Add feature-specific instruction to the system prompt."""
        instructions = {
            "daily_insight": "\n\nGENERATE A DAILY INSIGHT: One actionable tip for today (2-3 sentences). Consider their recent training, goals, and current fitness level.",
            "pre_run": "\n\nGENERATE A PRE-RUN BRIEF: What to do before today's run. Include warmup, hydration, and pacing guidance. Keep it concise (3-4 sentences).",
            "post_run": "\n\nANALYZE THE RUN: Score it, identify patterns, suggest recovery. Use the tools to check data. Be specific about what went well and what to adjust.",
            "challenge": "\n\nGENERATE A CHALLENGE: One specific, achievable challenge for this week. Categories: bodyweight, nutrition, hydration, technique, breathing, mental. Make it personal to their level.",
            "weekly_summary": "\n\nGENERATE WEEKLY SUMMARY: Review the past 7 days of training. Volume, consistency, key achievements, and one focus for next week. Be data-driven.",
            "proactive": "\n\nPROACTIVE CHECK: Look for warning signs (overtraining, inconsistency, approaching injury risk). If nothing to flag, give an encouraging nudge.",
            "plan": "\n\nGENERATE OR ADJUST TRAINING PLAN: Use periodization principles appropriate for their tier. Every session must have a purpose. Use calculate_pace_zones for all paces.",
            "profiling": "\n\nPROFILE THE RUNNER: Based on their inputs, classify their tier, estimate VO2max, assign pace zones, and suggest a coach personality. Explain your reasoning.",
        }
        return instructions.get(feature, "")


# Singleton
coach = CoachEngine()
