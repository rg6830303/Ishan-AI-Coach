"""Sprint Society AI Coach — Multi-Tab Testbed (v2).

Run: streamlit run app_v2.py

This version uses the headless engine (coach.handle) and provides one
tab per AI feature + a debug panel showing model/tokens/cost.
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.models import init_db
from ui.theme import inject_global_css
from ui.feature_tabs import FEATURE_TABS, render_runner_selector
from ui.debug_panel import render_debug_panel
from config import groq_key_is_configured

st.set_page_config(
    page_title="Sprint Society AI Coach — Testbed",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_css()
init_db()
os.makedirs("data/usage_logs", exist_ok=True)
os.makedirs("data/personalization", exist_ok=True)

# Sidebar: runner selector + debug panel
render_runner_selector()

runner = st.session_state.get("test_runner")
if runner:
    render_debug_panel(runner["id"], runner["plan"])

# Check API keys
has_groq = groq_key_is_configured()
has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

if not has_groq and not has_anthropic:
    st.warning("No API key configured. Set GROQ_API_KEY or ANTHROPIC_API_KEY in .env to enable LLM calls.")

# Status bar
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.markdown("# AI Coach Testbed")
with col2:
    st.markdown(f"**Groq:** {'🟢' if has_groq else '🔴'}")
with col3:
    st.markdown(f"**Claude:** {'🟢' if has_anthropic else '🔴'}")

# Feature tabs
tab_names = list(FEATURE_TABS.keys())
tabs = st.tabs(tab_names)

for tab, (name, render_fn) in zip(tabs, FEATURE_TABS.items()):
    with tab:
        render_fn()
