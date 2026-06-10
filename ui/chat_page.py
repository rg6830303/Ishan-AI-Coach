import streamlit as st
import json
from agent.agent_loop import run_agent
from agent.personas import get_persona_name
from database.auth import get_profile
from database.memory import get_chat_history, clear_chat_history
from config import TIERS


def render_chat_page():
    user = st.session_state.get("user")
    if not user:
        st.session_state["page"] = "auth"
        st.rerun()
        return

    profile = get_profile(user["id"])
    if not profile or not profile.get("profiling_complete"):
        st.session_state["page"] = "profiling"
        st.rerun()
        return

    tier = profile.get("tier", "pace")
    coach_style = profile.get("coach_style", "energizer")
    coach_name = get_persona_name(coach_style)
    tier_info = TIERS.get(tier, TIERS["pace"])

    with st.sidebar:
        _render_sidebar(profile, tier_info, coach_name)

    st.markdown(f"### Chat with {coach_name}")
    st.caption(f"{tier_info['name']} tier | Model: `{tier_info['model']}`")

    if "messages" not in st.session_state:
        history = get_chat_history(user["id"])
        if history:
            st.session_state["messages"] = history
        else:
            st.session_state["messages"] = []

    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("tool_calls"):
                with st.expander("Tool calls made"):
                    for tc in msg["tool_calls"]:
                        st.code(f"{tc['tool']}({json.dumps(tc.get('args', {}))})")
                        st.text(tc.get("result", "")[:300])

    if prompt := st.chat_input("Ask your coach anything..."):
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner(f"{coach_name} is thinking..."):
                result = run_agent(user["id"], prompt)

            st.markdown(result["response"])

            if result.get("tool_calls"):
                with st.expander("Tool calls made"):
                    for tc in result["tool_calls"]:
                        st.code(f"{tc['tool']}({json.dumps(tc.get('args', {}))})")
                        st.text(tc.get("result", "")[:300])

        st.session_state["messages"].append({
            "role": "assistant",
            "content": result["response"],
            "tool_calls": result.get("tool_calls"),
        })


def _render_sidebar(profile, tier_info, coach_name):
    st.markdown(f"## {coach_name}")

    tier_colors = {"spark": "orange", "pace": "blue", "tempo": "purple", "apex": "red"}
    tier = profile.get("tier", "pace")
    color = tier_colors.get(tier, "gray")
    st.markdown(
        f'<span style="background-color:{color};color:white;padding:4px 12px;'
        f'border-radius:12px;font-weight:bold;">{tier_info["name"]} - {tier_info["label"]}</span>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("**Your Profile**")
    st.markdown(f"- Age: {profile.get('age')}")
    st.markdown(f"- Experience: {profile.get('running_experience')}")
    st.markdown(f"- Fitness: {profile.get('fitness_level')}")
    st.markdown(f"- Dream race: {profile.get('dream_race')}")
    days = profile.get("training_days", 3)
    st.markdown(f"- Training days: {days} per week")

    five_k = profile.get("recent_5k_time")
    if five_k:
        mins = int(five_k)
        secs = int((five_k - mins) * 60)
        st.markdown(f"- 5K time: {mins}:{secs:02d}")

    st.markdown("---")

    if st.button("Clear Chat History"):
        user = st.session_state.get("user")
        if user:
            clear_chat_history(user["id"])
            st.session_state["messages"] = []
            st.rerun()

    if st.button("Re-do Profiling"):
        st.session_state["page"] = "profiling"
        st.session_state["profile_step"] = 0
        st.session_state["profile_data"] = {}
        st.rerun()

    if st.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
