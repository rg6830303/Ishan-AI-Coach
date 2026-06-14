"""Sprint Society AI Coach Engine v2 — Full integration.

Wires together:
- Router (agent/router.py): Adaptive model selection + budget + circuit breaker
- Tools (agent/tools_full.py): 24 tools for all features
- Guardrails (engine/guardrails_full.py): 8-category safety system
- RAG (knowledge/retriever.py): Hybrid knowledge retrieval
- Providers (agent/providers.py): Groq + Claude + fallback
- Memory (personalization/store.py): Insight extraction + decay
- Personas (agent/system_prompts.py): 4 coaching voices

Entry point: coach.handle(feature, context) -> CoachResult
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

from agent.router import select_route, report_result, set_cache, RouteDecision
from agent.providers import get_provider, LLMResponse
from agent.cost_logger import cost_logger, UsageEntry
from agent.tools_full import TOOL_DEFINITIONS, execute_tool
from agent.system_prompts import build_system_prompt
from engine.guardrails_full import check_all_guardrails, DISCLAIMER
from knowledge.retriever import retriever
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
    tokens: dict = field(default_factory=lambda: {"input": 0, "output": 0})
    est_cost: float = 0.0
    model: str = ""
    provider: str = ""
    level: int = 0
    feature: str = ""
    guardrail_flags: list[str] = field(default_factory=list)
    route_reason: str = ""
    cached: bool = False
    locale: str = "en"

    def to_dict(self) -> dict:
        return asdict(self)


class CoachEngine:
    """The adaptive coaching engine v2. Integrates router + tools + guardrails."""

    def handle(self, feature: str, context: dict) -> CoachResult:
        """Process any coaching request through the full pipeline.

        Pipeline:
        1. Pre-guardrails (check user message for red flags)
        2. Route (select model + provider based on task level + budget)
        3. If cached/rules-only, return immediately
        4. Build context (profile + RAG + memory + persona + guardrails)
        5. Agent loop (LLM + tool calls, max 3 iterations)
        6. Post-guardrails (validate output integrity + bias + IP)
        7. Cost tracking + memory extraction
        8. Return result
        """
        user_id = context.get("user_id", 0)
        message = context.get("message", "")
        tier = context.get("tier", "pace")
        persona = context.get("persona", "energizer")
        plan = context.get("plan", "base")
        thread_id = context.get("thread_id")
        locale = context.get("locale", "en")

        result = CoachResult(feature=feature, locale=locale)

        # ============================
        # 1. PRE-GUARDRAILS
        # ============================
        pre_check = check_all_guardrails(
            tier=tier,
            user_message=message,
            user_id=user_id,
            plan=plan,
        )
        if pre_check["blocked"]:
            result.text = pre_check["replacement_text"] or "I can't help with that. Let's focus on your running."
            result.guardrail_flags = pre_check["all_warnings"]
            return result

        # ============================
        # 2. ROUTE
        # ============================
        route = select_route(feature, message, tier, plan, user_id)
        result.model = route.model
        result.provider = route.provider
        result.level = route.level
        result.route_reason = route.reason

        # Level 0: pure math/rules — no LLM
        if route.provider == "rules":
            result.text = self._rules_only(feature, context)
            return result

        # Cached response
        if route.cached and route.cache_response:
            result.text = route.cache_response
            result.cached = True
            return result

        # Budget exhausted fallback
        if route.provider == "fallback":
            result.text = self._fallback_response(feature, tier, locale)
            result.guardrail_flags.append("budget_or_provider_fallback")
            return result

        # ============================
        # 3. BUILD CONTEXT
        # ============================
        profile = get_profile(user_id) if user_id else {}
        insights = get_top_insights(user_id) if user_id else []

        # Personalization
        if profile and user_id:
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

        # System prompt
        system_prompt = build_system_prompt(tier, persona, profile_summary, insights, personalization_block)

        # RAG context
        rag_query = message if feature == "chat" else self._rag_query_for_feature(feature, context)
        rag_results = retriever.retrieve(rag_query, tier=tier, coach=persona)
        if rag_results:
            result.citations = [{"title": r["chunk"]["title"], "source": r["chunk"]["source"]} for r in rag_results]
            rag_text = "\n\nRELEVANT KNOWLEDGE (cite when using):\n"
            for r in rag_results:
                rag_text += f"- [{r['chunk']['title']}]: {r['chunk']['content'][:500]}\n"
            system_prompt += rag_text

        # Locale instruction
        if locale == "hi":
            system_prompt += "\n\nREPLY IN HINDI (Devanagari script). Keep technical terms in English."
        elif locale == "hinglish":
            system_prompt += "\n\nREPLY IN HINGLISH (Roman Hindi mixed with English). Natural, conversational."

        # Feature-specific instruction
        system_prompt += self._feature_instruction(feature, context)

        # ============================
        # 4. AGENT LOOP
        # ============================
        messages = [{"role": "system", "content": system_prompt}]

        # Add chat history for conversation continuity
        if feature == "chat" and user_id:
            history = get_chat_history(user_id, thread_id=thread_id)
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": message})

        # Get provider and run agent loop
        try:
            provider = get_provider(route.provider)
        except Exception:
            result.text = self._fallback_response(feature, tier, locale)
            result.guardrail_flags.append("provider_init_failed")
            return result

        tools = TOOL_DEFINITIONS if route.use_tools else None
        max_iter = config.MAX_AGENT_ITERATIONS if tools else 1
        total_input = 0
        total_output = 0
        iterations = 0

        while iterations < max_iter:
            iterations += 1

            llm_result = provider.chat(
                messages,
                model=route.model,
                tools=tools,
                max_tokens=route.max_tokens,
                temperature=route.temperature,
            )
            total_input += llm_result.input_tokens
            total_output += llm_result.output_tokens

            # Error handling
            if llm_result.finish_reason == "error":
                report_result(route.provider, False)
                if tools:
                    # Retry without tools
                    llm_result = provider.chat(messages, model=route.model, tools=None, max_tokens=route.max_tokens)
                    total_input += llm_result.input_tokens
                    total_output += llm_result.output_tokens
                if llm_result.finish_reason == "error":
                    result.text = self._fallback_response(feature, tier, locale)
                    result.guardrail_flags.append("llm_error")
                    return result
                break

            report_result(route.provider, True)

            # Tool calls
            if llm_result.tool_calls:
                # Add assistant message
                messages.append({"role": "assistant", "content": llm_result.content or ""})

                for tc in llm_result.tool_calls:
                    tool_output = execute_tool(tc["name"], tc["arguments"], user_id, thread_id=thread_id)
                    result.tools_used.append(tc["name"])

                    # Format tool result for the provider
                    if route.provider == "anthropic":
                        messages.append({
                            "role": "user",
                            "content": [{"type": "tool_result", "tool_use_id": tc["id"], "content": tool_output}],
                        })
                    else:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": tool_output,
                        })
            else:
                # Final response
                result.text = llm_result.content or ""
                break

        # If loop exhausted without response
        if not result.text:
            result.text = "I had trouble processing that. Could you rephrase?"

        # ============================
        # 5. POST-GUARDRAILS
        # ============================
        post_check = check_all_guardrails(
            tier=tier,
            user_message=message,
            response_text=result.text,
            tools_used=result.tools_used,
            user_id=user_id,
            plan=plan,
            model=route.model,
        )
        if post_check["blocked"]:
            result.text = post_check["replacement_text"] or result.text
            result.guardrail_flags.extend(post_check["all_warnings"])
        elif post_check["all_warnings"]:
            result.guardrail_flags.extend(post_check["all_warnings"])

        # ============================
        # 6. COST TRACKING + MEMORY
        # ============================
        result.tokens = {"input": total_input, "output": total_output}
        result.est_cost = llm_result.estimated_cost_usd if llm_result else 0.0

        # Log usage
        cost_logger.log_usage(UsageEntry(
            timestamp=datetime.now().isoformat(),
            user_id=user_id,
            feature=feature,
            provider=route.provider,
            model=route.model,
            input_tokens=total_input,
            output_tokens=total_output,
            latency_ms=llm_result.latency_ms if llm_result else 0,
            estimated_cost_usd=result.est_cost,
            tools_used=result.tools_used,
        ))

        # Store chat and extract insights
        if feature == "chat" and user_id:
            store_message(user_id, "user", message, thread_id=thread_id)
            store_message(user_id, "assistant", result.text, result.tools_used or None, thread_id=thread_id)
            extract_insights(user_id, message, role="user")
            extract_insights(user_id, result.text, role="assistant")
            personalization_store.update_from_message(user_id, message, role="user", thread_id=thread_id)

        # Cache if applicable
        if feature in ("daily_insight", "challenge", "pre_run") and result.text:
            set_cache(feature, message, tier, result.text, long_ttl=True)

        return result

    # ============================
    # HELPER METHODS
    # ============================

    def _rules_only(self, feature: str, context: dict) -> str:
        """Handle Level 0 (math/rules only) requests."""
        user_id = context.get("user_id", 0)

        if feature == "pace_zones":
            from agent.tools_full import execute_tool
            result = execute_tool("calculate_pace_zones", {"five_k_minutes": 0}, user_id)
            data = json.loads(result)
            fmt = data.get("formatted", {})
            return f"Your pace zones:\n- Easy: {fmt.get('easy', '?')}\n- Tempo: {fmt.get('tempo', '?')}\n- Interval: {fmt.get('interval', '?')}\n- Race: {fmt.get('race', '?')}"

        if feature == "vo2max":
            from agent.tools_full import execute_tool
            result = execute_tool("estimate_vo2max", {}, user_id)
            data = json.loads(result)
            return f"Estimated VO2max: {data.get('vo2max', '?')} ml/kg/min ({data.get('category', '?')})"

        if feature == "race_predict":
            msg = context.get("message", "")
            from agent.tools_full import execute_tool
            result = execute_tool("predict_race_time", {"known_distance_km": 5, "known_time_minutes": 0, "target_distance_km": 10}, user_id)
            return json.loads(result).get("predicted_time", "Cannot predict without race data")

        if feature == "readiness":
            from agent.tools_full import execute_tool
            result = execute_tool("calculate_readiness", {}, user_id)
            data = json.loads(result)
            return f"Readiness: {data.get('readiness_score', '?')}/5 - {data.get('recommendation', '')}"

        return "Feature handled by rules engine."

    def _fallback_response(self, feature: str, tier: str, locale: str) -> str:
        """Rule-based fallback when LLM is unavailable."""
        fallbacks = {
            "en": {
                "daily_insight": "Focus on consistency today. If you ran yesterday, take it easy or rest. If you rested, aim for an easy 20-30 minute run.",
                "pre_run": "Warmup: 5 minutes walking, then 5 minutes easy jog. Stay hydrated. Run by feel today.",
                "post_run": "Great job getting out there! Hydrate, stretch gently, and get good sleep tonight.",
                "challenge": "This week's challenge: Run one session purely by feel - no watch, no pace targets. Just enjoy the movement.",
                "chat": "I'm having trouble connecting right now. Please try again in a moment. In the meantime - if you haven't run today, a 20-minute easy jog is always a good default!",
                "weekly_summary": "Keep showing up consistently. That's the most important thing at every level.",
                "proactive": "Remember: easy days should feel easy. If you're tired, rest is training too.",
            },
            "hinglish": {
                "daily_insight": "Aaj consistency pe focus karo. Kal run kiya tha? Toh aaj easy ya rest. Rest liya? Toh 20-30 min easy run karo.",
                "pre_run": "Warmup: 5 min walk, phir 5 min easy jog. Hydrated raho. Aaj feel se run karo.",
                "post_run": "Bahut badhiya! Ab hydrate karo, halka stretch, aur raat ko achi neend lo.",
                "chat": "Abhi connection issue aa raha hai. Thodi der mein try karo. Tab tak - agar aaj run nahi kiya, toh 20 min easy jog best option hai!",
            },
        }
        lang_fallbacks = fallbacks.get(locale, fallbacks["en"])
        return lang_fallbacks.get(feature, lang_fallbacks.get("chat", "Please try again shortly."))

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

    def _rag_query_for_feature(self, feature: str, context: dict) -> str:
        tier = context.get("tier", "pace")
        message = context.get("message", "")
        queries = {
            "daily_insight": f"daily coaching tip for {tier} runner",
            "pre_run": f"pre-run warmup preparation {tier}",
            "post_run": f"post-run recovery analysis {tier}",
            "challenge": f"training challenge {tier} runner",
            "weekly_summary": f"weekly training review {tier}",
            "proactive": f"proactive coaching alerts {tier}",
            "race_predict": f"race prediction methodology",
            "injury_risk": f"injury risk ACWR prevention",
            "profiling": f"runner classification profiling",
            "plan": f"training plan periodization {tier} {message}",
        }
        return queries.get(feature, message or f"{feature} for {tier}")

    def _feature_instruction(self, feature: str, context: dict) -> str:
        instructions = {
            "daily_insight": "\n\nGENERATE A DAILY INSIGHT: One actionable tip for today (2-3 sentences). Personal to their current state.",
            "pre_run": "\n\nGENERATE A PRE-RUN BRIEF: Warmup, hydration, pacing guidance for today's run. Concise (3-4 sentences).",
            "post_run": "\n\nANALYZE THE RUN: Score it, identify patterns, suggest recovery. Be specific about what went well.",
            "challenge": "\n\nGENERATE A CHALLENGE: One specific, achievable challenge for this week. Make it personal.",
            "weekly_summary": "\n\nGENERATE WEEKLY SUMMARY: Volume, consistency, achievements, one focus for next week. Data-driven.",
            "proactive": "\n\nPROACTIVE CHECK: Warning signs (overtraining, injury risk)? If nothing to flag, give an encouraging nudge.",
            "plan": "\n\nGENERATE TRAINING PLAN: Periodized, with specific sessions. Use calculate_pace_zones for all paces. Never invent numbers.",
            "profiling": "\n\nPROFILE THE RUNNER: Classify tier, estimate VO2max, assign zones, suggest coach personality. Explain reasoning.",
            "injury_risk": "\n\nASSESS INJURY RISK: Check ACWR, recent load, history. Be specific about concerns. If safe, say so clearly.",
            "race_predict": "\n\nPREDICT RACE TIME: Use predict_race_time tool. Explain the prediction and what training could improve it.",
        }
        return instructions.get(feature, "")


# Singleton
coach = CoachEngine()
