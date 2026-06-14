"""Multi-tab feature UI — one tab per AI coaching feature.

Each tab exercises the engine through coach.handle(feature, context)
so every feature can be tested independently against synthetic runners.
"""

import streamlit as st
from coaching.engine_v2 import coach
from tests.synthetic_runners import get_all_runners, runner_as_profile
from ui.debug_panel import render_call_debug


def _get_active_runner() -> dict | None:
    """Get the currently selected synthetic runner from session state."""
    return st.session_state.get("test_runner")


def _call_coach(feature: str, message: str, **extra) -> dict:
    """Call the coach engine and return result dict."""
    runner = _get_active_runner()
    if not runner:
        return {"text": "No runner selected. Pick one from the sidebar.", "est_cost": 0}

    context = {
        "user_id": runner["id"],
        "message": message,
        "tier": runner["tier"],
        "persona": runner["coach_style"],
        "plan": runner["plan"],
        "thread_id": st.session_state.get("thread_id"),
        "locale": st.session_state.get("locale", "en"),
        **extra,
    }

    result = coach.handle(feature, context)
    return result.to_dict()


def render_runner_selector():
    """Sidebar runner + persona + locale selector."""
    with st.sidebar:
        st.markdown("### Test Runner")
        runners = get_all_runners()
        names = [f"{r['name']} ({r['tier']})" for r in runners]
        selected = st.selectbox("Runner", names, index=0)
        idx = names.index(selected)
        st.session_state["test_runner"] = runners[idx]

        runner = runners[idx]
        st.markdown(f"**Tier:** {runner['tier'].upper()}")
        st.markdown(f"**Persona:** {runner['coach_style']}")
        st.markdown(f"**Plan:** {runner['plan']}")
        st.markdown(f"**Weekly km:** {runner['weekly_km']}")
        st.markdown(f"**Streak:** {runner['streak_days']} days")

        st.markdown("---")
        locale = st.radio("Language", ["en", "hinglish", "hi"], index=0, horizontal=True)
        st.session_state["locale"] = locale


def render_chat_tab():
    """Full chat interface with the AI coach."""
    st.markdown("### Chat with Coach")

    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []

    # Display history
    for msg in st.session_state["chat_messages"]:
        role = msg["role"]
        with st.chat_message(role):
            st.markdown(msg["content"])
            if msg.get("debug"):
                render_call_debug(msg["debug"])

    # Input
    if prompt := st.chat_input("Ask your coach..."):
        st.session_state["chat_messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Coach is thinking..."):
                result = _call_coach("chat", prompt)
            st.markdown(result["text"])
            render_call_debug(result)

        st.session_state["chat_messages"].append({
            "role": "assistant",
            "content": result["text"],
            "debug": result,
        })


def render_daily_insight_tab():
    """Daily coaching insight."""
    st.markdown("### Daily Insight")
    st.caption("One actionable tip personalized to your current training state.")

    if st.button("Generate Today's Insight", key="daily_btn"):
        with st.spinner("Generating..."):
            result = _call_coach("daily_insight", "Generate my daily coaching insight for today.")
        st.success(result["text"])
        render_call_debug(result)


def render_pre_run_tab():
    """Pre-run briefing."""
    st.markdown("### Pre-Run Brief")
    st.caption("What to do before your run today.")

    run_type = st.selectbox("Today's planned run", ["Easy", "Tempo", "Intervals", "Long Run", "Recovery"])
    if st.button("Get Pre-Run Brief", key="prerun_btn"):
        with st.spinner("Preparing brief..."):
            result = _call_coach("pre_run", f"I'm about to do a {run_type} run. Give me my pre-run brief.")
        st.info(result["text"])
        render_call_debug(result)


def render_post_run_tab():
    """Post-run analysis."""
    st.markdown("### Post-Run Analysis")
    st.caption("Analyze a completed run.")

    col1, col2, col3 = st.columns(3)
    with col1:
        distance = st.number_input("Distance (km)", 0.5, 50.0, 5.0, 0.5)
    with col2:
        duration = st.number_input("Duration (min)", 5, 300, 30, 1)
    with col3:
        feel = st.selectbox("How it felt", ["Great", "Good", "Okay", "Tough", "Terrible"])

    if st.button("Analyze Run", key="postrun_btn"):
        msg = f"I just finished a {distance}km run in {duration} minutes. It felt {feel.lower()}."
        with st.spinner("Analyzing..."):
            result = _call_coach("post_run", msg)
        st.markdown(result["text"])
        render_call_debug(result)


def render_plan_tab():
    """Training plan generation."""
    st.markdown("### Training Plan")
    st.caption("Generate or adjust your training plan.")

    goal = st.selectbox("Goal", ["5K", "10K", "Half Marathon", "Marathon", "General Fitness"])
    weeks = st.slider("Weeks available", 4, 24, 12)
    target = st.text_input("Target time (optional)", placeholder="e.g., 25:00 for 5K")

    if st.button("Generate Plan", key="plan_btn"):
        msg = f"Create a {weeks}-week training plan for {goal}."
        if target:
            msg += f" Target time: {target}."
        with st.spinner("Building plan..."):
            result = _call_coach("plan", msg)
        st.markdown(result["text"])
        render_call_debug(result)


def render_challenge_tab():
    """Weekly challenge generation."""
    st.markdown("### Weekly Challenge")
    st.caption("Get a personalized challenge for this week.")

    category = st.selectbox("Category", ["Any", "Bodyweight", "Nutrition", "Hydration", "Technique", "Breathing", "Mental"])
    if st.button("Generate Challenge", key="challenge_btn"):
        msg = f"Give me a {category.lower()} challenge for this week."
        with st.spinner("Creating challenge..."):
            result = _call_coach("challenge", msg)
        st.markdown(result["text"])
        render_call_debug(result)


def render_weekly_summary_tab():
    """Weekly training summary."""
    st.markdown("### Weekly Summary")
    st.caption("Review your past 7 days of training.")

    if st.button("Generate Weekly Summary", key="weekly_btn"):
        with st.spinner("Reviewing your week..."):
            result = _call_coach("weekly_summary", "Summarize my training for the past week.")
        st.markdown(result["text"])
        render_call_debug(result)


def render_injury_risk_tab():
    """Injury risk assessment."""
    st.markdown("### Injury Risk Check")
    st.caption("Assess your current injury risk based on training load.")

    if st.button("Check Injury Risk", key="injury_btn"):
        with st.spinner("Assessing..."):
            result = _call_coach("injury_risk", "Assess my current injury risk. Check my ACWR and recent load.")
        st.markdown(result["text"])
        render_call_debug(result)


def render_race_predict_tab():
    """Race time predictions."""
    st.markdown("### Race Predictions")
    st.caption("Predict your race times based on current fitness.")

    distance = st.selectbox("Predict for", ["5K", "10K", "Half Marathon", "Marathon"])
    if st.button("Predict", key="race_btn"):
        with st.spinner("Calculating..."):
            result = _call_coach("race_predict", f"Predict my {distance} time based on my current fitness.")
        st.markdown(result["text"])
        render_call_debug(result)


# Tab registry
FEATURE_TABS = {
    "Chat": render_chat_tab,
    "Daily Insight": render_daily_insight_tab,
    "Pre-Run": render_pre_run_tab,
    "Post-Run": render_post_run_tab,
    "Plan": render_plan_tab,
    "Challenge": render_challenge_tab,
    "Weekly": render_weekly_summary_tab,
    "Injury Risk": render_injury_risk_tab,
    "Race Predict": render_race_predict_tab,
}
