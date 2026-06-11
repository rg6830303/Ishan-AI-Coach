import streamlit as st
from config import TIERS
from ui.theme import coach_meta, tier_meta


def render_classification_result():
    """Show classification result after profiling is complete."""
    classification = st.session_state.get("classification")
    if not classification:
        st.session_state["page"] = "chat"
        st.rerun()
        return

    tier = classification["tier"]
    tier_info = TIERS.get(tier, TIERS["pace"])
    tm = tier_meta(tier)
    score = classification["score"]
    breakdown = classification["breakdown"]

    profile_data = st.session_state.get("profile_data", {})
    coach_style = profile_data.get("coach_style", "energizer")
    cm = coach_meta(coach_style)

    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown("## 🎯 Your Coach Assignment")

        st.markdown(
            f"""
            <div style="background:linear-gradient(135deg,{cm['color']}33,{tm['color']}22);
                        border:2px solid {tm['color']}; border-radius:20px;
                        padding:2rem; text-align:center; margin:1rem 0;">
                <div style="font-size:3rem;">{cm['icon']} {tm['icon']}</div>
                <h1 style="color:{tm['color']}; margin:.2rem 0;">{tier_info['name']} Tier</h1>
                <p style="font-size:1.1rem; color:#9aa0a6;">{tier_info['label']} · {tm['label']} runner</p>
                <p style="font-size:1.6rem; margin:.4rem 0;">{cm['name']}</p>
                <p style="color:#9aa0a6;">Match score: {score}/100</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### Score breakdown")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Experience", f"{breakdown['experience']:.0f}")
        c2.metric("Fitness", f"{breakdown['fitness']:.0f}")
        c3.metric("5K Time", f"{breakdown['five_k']:.0f}")
        c4.metric("Training Days", f"{breakdown['training_days']:.0f}")

        st.markdown(f"**What this means:** {tier_info['description']}")
        st.markdown(f"**Your coach:** {cm['name']} — {cm['blurb']}")
        st.markdown(f"**AI model:** `{tier_info['model']}`")

        st.markdown("")
        if st.button(f"Start chatting with {cm['name']} →", type="primary", use_container_width=True):
            st.session_state["page"] = "chat"
            st.rerun()
