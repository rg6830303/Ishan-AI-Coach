import streamlit as st
from config import TIERS
from agent.personas import get_persona_name


def render_classification_result():
    """Show classification result after profiling is complete."""
    classification = st.session_state.get("classification")
    if not classification:
        st.session_state["page"] = "chat"
        st.rerun()
        return

    tier = classification["tier"]
    tier_info = TIERS.get(tier, TIERS["pace"])
    score = classification["score"]
    breakdown = classification["breakdown"]

    profile_data = st.session_state.get("profile_data", {})
    coach_style = profile_data.get("coach_style", "energizer")
    coach_name = get_persona_name(coach_style)

    st.markdown("---")
    st.markdown("## Your Coach Assignment")
    st.markdown("")

    tier_colors = {"spark": "#FF6B00", "pace": "#0066FF", "tempo": "#8B00FF", "apex": "#FF0040"}
    color = tier_colors.get(tier, "#666")

    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, {color}22, {color}11);
                    border: 2px solid {color}; border-radius: 16px;
                    padding: 2rem; text-align: center; margin: 1rem 0;">
            <h1 style="color: {color}; margin: 0;">{tier_info['name']}</h1>
            <p style="font-size: 1.2rem; color: #666;">{tier_info['label']} Coach</p>
            <p style="font-size: 2rem; margin: 0.5rem 0;">{coach_name}</p>
            <p style="color: #888;">Score: {score}/100</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Score Breakdown")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Experience", f"{breakdown['experience']:.0f}")
    with col2:
        st.metric("Fitness", f"{breakdown['fitness']:.0f}")
    with col3:
        st.metric("5K Time", f"{breakdown['five_k']:.0f}")
    with col4:
        st.metric("Training Days", f"{breakdown['training_days']:.0f}")

    st.markdown("---")
    st.markdown(f"**What this means:** {tier_info['description']}")
    st.markdown(f"**Your coach persona:** {coach_name} will guide you with their unique style.")
    st.markdown(f"**AI Model:** `{tier_info['model']}`")

    st.markdown("")
    if st.button("Start Chatting with Your Coach", type="primary", use_container_width=True):
        st.session_state["page"] = "chat"
        st.rerun()
