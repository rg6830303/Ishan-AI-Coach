"""Unified LLM provider interface.

Supports Groq (OpenAI-compatible) and Anthropic (Claude) behind a single
interface so the agent loop can route between them transparently.

Usage:
    from agent.providers import get_provider, Provider

    provider = get_provider("anthropic")  # or "groq"
    result = provider.chat(messages, tools=TOOL_DEFINITIONS, model="haiku")
"""

import json
import time
import os
from dataclasses import dataclass, field
from typing import Any

import config


@dataclass
class LLMResponse:
    """Normalized response from any provider."""
    content: str | None = None
    tool_calls: list[dict] | None = None
    finish_reason: str = "stop"
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    provider: str = ""
    estimated_cost_usd: float = 0.0


# Pricing per 1M tokens (input, output)
PRICING = {
    # Groq
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    # Anthropic
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-6": (15.0, 75.0),
}

# Model aliases for convenience
MODEL_ALIASES = {
    "8b": "llama-3.1-8b-instant",
    "70b": "llama-3.3-70b-versatile",
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
}


def resolve_model(model: str) -> str:
    """Resolve alias to full model name."""
    return MODEL_ALIASES.get(model, model)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a call."""
    model = resolve_model(model)
    pricing = PRICING.get(model, (0.5, 1.0))
    cost = (input_tokens * pricing[0] + output_tokens * pricing[1]) / 1_000_000
    return round(cost, 6)


class GroqProvider:
    """Groq provider using OpenAI-compatible API."""

    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(
            api_key=config.get_groq_api_key(),
            base_url=config.GROQ_BASE_URL,
        )

    def chat(
        self,
        messages: list[dict],
        model: str = "70b",
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        model = resolve_model(model)
        start = time.time()

        kwargs: dict[str, Any] = dict(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as e:
            return LLMResponse(
                content=f"[Groq error: {str(e)}]",
                finish_reason="error",
                model=model,
                provider="groq",
                latency_ms=int((time.time() - start) * 1000),
            )

        choice = response.choices[0]
        usage = response.usage

        # Normalize tool calls
        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = []
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args,
                })

        input_tok = usage.prompt_tokens if usage else 0
        output_tok = usage.completion_tokens if usage else 0

        return LLMResponse(
            content=choice.message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            model=model,
            input_tokens=input_tok,
            output_tokens=output_tok,
            latency_ms=int((time.time() - start) * 1000),
            provider="groq",
            estimated_cost_usd=estimate_cost(model, input_tok, output_tok),
        )


class AnthropicProvider:
    """Anthropic Claude provider."""

    def __init__(self):
        try:
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            self.client = anthropic.Anthropic(api_key=api_key)
            self.available = True
        except Exception as e:
            self.client = None
            self.available = False
            self._init_error = str(e)

    def _convert_tools_to_anthropic(self, tools: list[dict]) -> list[dict]:
        """Convert OpenAI tool format to Anthropic tool format."""
        anthropic_tools = []
        for tool in tools:
            fn = tool.get("function", {})
            anthropic_tools.append({
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        return anthropic_tools

    def _convert_messages_for_anthropic(self, messages: list[dict]) -> tuple[str, list[dict]]:
        """Extract system prompt and convert messages for Anthropic format.

        Returns (system_prompt, messages_without_system).
        """
        system_prompt = ""
        converted = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_prompt = content
                continue
            elif role == "tool":
                # Anthropic uses tool_result content blocks
                converted.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", "unknown"),
                        "content": content,
                    }],
                })
            elif role == "assistant":
                # Check if the original message had tool_calls (from OpenAI format)
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    blocks = []
                    if content:
                        blocks.append({"type": "text", "text": content})
                    for tc in msg.tool_calls:
                        try:
                            args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                        except (json.JSONDecodeError, TypeError, AttributeError):
                            args = {}
                        blocks.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.function.name,
                            "input": args,
                        })
                    converted.append({"role": "assistant", "content": blocks})
                else:
                    converted.append({"role": "assistant", "content": content or ""})
            else:
                converted.append({"role": "user", "content": content or ""})

        return system_prompt, converted

    def chat(
        self,
        messages: list[dict],
        model: str = "haiku",
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        if not self.available:
            return LLMResponse(
                content=f"[Anthropic unavailable: {self._init_error}]",
                finish_reason="error",
                model=resolve_model(model),
                provider="anthropic",
            )

        model = resolve_model(model)
        start = time.time()

        system_prompt, converted_messages = self._convert_messages_for_anthropic(messages)

        kwargs: dict[str, Any] = dict(
            model=model,
            messages=converted_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = self._convert_tools_to_anthropic(tools)

        try:
            response = self.client.messages.create(**kwargs)
        except Exception as e:
            return LLMResponse(
                content=f"[Anthropic error: {str(e)}]",
                finish_reason="error",
                model=model,
                provider="anthropic",
                latency_ms=int((time.time() - start) * 1000),
            )

        # Parse response
        content_text = ""
        tool_calls = None

        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })

        finish = "tool_calls" if response.stop_reason == "tool_use" else "stop"
        input_tok = response.usage.input_tokens
        output_tok = response.usage.output_tokens

        return LLMResponse(
            content=content_text or None,
            tool_calls=tool_calls,
            finish_reason=finish,
            model=model,
            input_tokens=input_tok,
            output_tokens=output_tok,
            latency_ms=int((time.time() - start) * 1000),
            provider="anthropic",
            estimated_cost_usd=estimate_cost(model, input_tok, output_tok),
        )


# Singleton instances (lazy-init)
_groq: GroqProvider | None = None
_anthropic: AnthropicProvider | None = None


def get_provider(name: str = "groq") -> GroqProvider | AnthropicProvider:
    """Get a provider instance by name."""
    global _groq, _anthropic

    if name == "groq":
        if _groq is None:
            _groq = GroqProvider()
        return _groq
    elif name in ("anthropic", "claude"):
        if _anthropic is None:
            _anthropic = AnthropicProvider()
        return _anthropic
    else:
        raise ValueError(f"Unknown provider: {name}. Use 'groq' or 'anthropic'.")


def get_best_available_provider(prefer: str = "groq") -> GroqProvider | AnthropicProvider:
    """Get the best available provider, with fallback."""
    if prefer == "groq" and config.groq_key_is_configured():
        return get_provider("groq")
    elif prefer == "anthropic":
        p = get_provider("anthropic")
        if p.available:
            return p
    # Fallback
    if config.groq_key_is_configured():
        return get_provider("groq")
    p = get_provider("anthropic")
    if p.available:
        return p
    raise RuntimeError("No LLM provider available. Set GROQ_API_KEY or ANTHROPIC_API_KEY.")
