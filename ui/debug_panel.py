"""Debug panel for Streamlit — shows model, tools, tokens, cost per call."""

import streamlit as st
from agent.cost_logger import cost_logger


def render_debug_panel(user_id: int, plan: str = "base"):
    """Render the debug/cost panel in the sidebar."""
    with st.sidebar:
        st.markdown("---")
        st.markdown("### Debug Panel")

        budget = cost_logger.check_budget(user_id, plan)

        # Budget meter
        percent = budget["percent_used"]
        color = "green" if percent < 50 else ("orange" if percent < 80 else "red")
        st.markdown(f"**Budget:** :{'green' if percent < 50 else 'orange' if percent < 80 else 'red'}[{percent}% used]")
        st.progress(min(percent / 100, 1.0))

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Spent", f"${budget['spent_usd']:.4f}")
            st.metric("Calls today", f"{budget['daily_calls_today']}/{budget['daily_cap']}")
        with col2:
            st.metric("Remaining", f"${budget['remaining_usd']:.4f}")
            st.metric("Plan", budget["plan"].upper())

        if not budget["can_call"]:
            st.error("Budget exhausted or daily cap reached")


def render_call_debug(result: dict):
    """Show debug info for the last LLM call."""
    if not result:
        return

    with st.expander("Last call debug", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**Provider:** {result.get('provider', '?')}")
            st.markdown(f"**Model:** {result.get('model', '?')}")
        with col2:
            tokens = result.get('tokens', {})
            st.markdown(f"**In:** {tokens.get('input', 0)} tok")
            st.markdown(f"**Out:** {tokens.get('output', 0)} tok")
        with col3:
            st.markdown(f"**Cost:** ${result.get('est_cost', 0):.5f}")
            st.markdown(f"**Level:** {result.get('level', '?')}")

        if result.get("tools_used"):
            st.markdown(f"**Tools:** {', '.join(result['tools_used'])}")

        if result.get("citations"):
            st.markdown("**Citations:**")
            for c in result["citations"]:
                st.markdown(f"- {c['title']} ({c['source']})")

        if result.get("guardrail_flags"):
            st.warning(f"Guardrail flags: {result['guardrail_flags']}")
