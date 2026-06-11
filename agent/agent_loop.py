import json
from openai import OpenAI
from config import GROQ_API_KEY, GROQ_BASE_URL, TIERS, MAX_AGENT_ITERATIONS
from agent.tools import TOOL_DEFINITIONS, execute_tool
from agent.system_prompts import build_system_prompt
from database.auth import get_profile
from database.memory import get_chat_history, get_top_insights, store_message, extract_insights
from personalization.store import store as personalization_store


def get_client() -> OpenAI:
    return OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)


def format_profile_summary(profile: dict) -> str:
    """Create a concise profile summary for the system prompt."""
    if not profile:
        return "No profile data available."

    five_k = profile.get("recent_5k_time")
    five_k_str = f"{five_k:.1f} min" if five_k else "not recorded"

    return (
        f"Name: (user)\n"
        f"Tier: {profile.get('tier', 'unknown').upper()}\n"
        f"Age: {profile.get('age', '?')} | Gender: {profile.get('gender', '?')}\n"
        f"Height: {profile.get('height_cm', '?')}cm | Weight: {profile.get('weight_kg', '?')}kg\n"
        f"Fitness: {profile.get('fitness_level', '?')} | Experience: {profile.get('running_experience', '?')}\n"
        f"5K time: {five_k_str}\n"
        f"Dream race: {profile.get('dream_race', '?')}\n"
        f"Why they run: {profile.get('running_why', '?')}\n"
        f"Training days/week: {profile.get('training_days', '?')}\n"
        f"Preferred time: {profile.get('preferred_time', '?')}\n"
        f"Bad run response: {profile.get('bad_run_response', '?')}\n"
        f"Injuries: {profile.get('injury_history', [])}"
    )


def run_agent(user_id: int, user_message: str) -> dict:
    """
    Main agent loop. Sends user message to Groq with tools, handles tool calls,
    returns final response with metadata about tool usage.
    """
    client = get_client()
    profile = get_profile(user_id)

    tier = profile.get("tier", "pace") if profile else "pace"
    coach_style = profile.get("coach_style", "energizer") if profile else "energizer"
    model = TIERS.get(tier, TIERS["pace"])["model"]

    profile_summary = format_profile_summary(profile)
    insights = get_top_insights(user_id)

    # Keep the JSON profile snapshot fresh, then continuously learn from this
    # message before building the prompt so the coach reacts in the same turn.
    if profile:
        personalization_store.sync_profile(user_id, profile)
    personalization_store.update_from_message(user_id, user_message, role="user")
    personalization_block = personalization_store.build_prompt_block(user_id)

    system_prompt = build_system_prompt(
        tier, coach_style, profile_summary, insights, personalization_block
    )

    chat_history = get_chat_history(user_id)

    messages = [{"role": "system", "content": system_prompt}]
    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    store_message(user_id, "user", user_message)
    extract_insights(user_id, user_message, role="user")

    tool_calls_made = []
    iterations = 0

    while iterations < MAX_AGENT_ITERATIONS:
        iterations += 1

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=1024,
            )
        except Exception as e:
            error_msg = f"Error calling Groq API: {str(e)}"
            return {"response": error_msg, "tool_calls": [], "error": True}

        choice = response.choices[0]

        if choice.finish_reason == "tool_calls" or (choice.message.tool_calls):
            messages.append(choice.message)

            for tool_call in choice.message.tool_calls:
                func_name = tool_call.function.name
                try:
                    func_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    func_args = {}

                result = execute_tool(func_name, func_args, user_id)

                tool_calls_made.append({
                    "tool": func_name,
                    "args": func_args,
                    "result": result[:500],
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
        else:
            final_text = choice.message.content or ""
            store_message(user_id, "assistant", final_text, tool_calls_made if tool_calls_made else None)
            extract_insights(user_id, final_text, role="assistant")
            personalization_store.log_event(user_id, "assistant_message", {
                "preview": final_text[:160],
                "tools_used": [tc["tool"] for tc in tool_calls_made],
            })

            return {
                "response": final_text,
                "tool_calls": tool_calls_made,
                "model": model,
                "tier": tier,
                "persona": coach_style,
                "error": False,
            }

    final_text = "I apologize, but I'm having trouble processing your request. Could you rephrase it?"
    store_message(user_id, "assistant", final_text)
    return {"response": final_text, "tool_calls": tool_calls_made, "error": True}
