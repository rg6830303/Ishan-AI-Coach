import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.models import init_db
from database.auth import is_profiling_complete
from ui.auth_page import render_auth_page
from ui.profiling_page import render_profiling_page
from ui.chat_page import render_chat_page
from ui.sidebar import render_classification_result
from ui.theme import inject_global_css
from config import groq_key_is_configured

st.set_page_config(
    page_title="Sprint Society AI Coach",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="auto",
)

inject_global_css()
init_db()

if not groq_key_is_configured():
    st.warning("⚠️ No Groq API key detected — the coaches can't respond until one is set.", icon="⚠️")
    with st.expander("🔑 How to fix this (30 seconds)", expanded=True):
        st.markdown(
            "**On Streamlit Cloud (this deployment):**\n"
            "1. Open your app → **⋮ menu → Settings → Secrets**.\n"
            "2. Paste exactly this (with your real key) and **Save**:\n"
        )
        st.code('GROQ_API_KEY = "gsk_your_real_key_here"', language="toml")
        st.markdown(
            "3. The app reboots automatically and this warning disappears.\n\n"
            "**Running locally:** create a `.env` file with `GROQ_API_KEY=gsk_...` "
            "(see the README). Get a free key at https://console.groq.com/keys."
        )

if "page" not in st.session_state:
    st.session_state["page"] = "auth"

if st.session_state.get("user") and st.session_state["page"] == "auth":
    user = st.session_state["user"]
    if is_profiling_complete(user["id"]):
        st.session_state["page"] = "chat"
    else:
        st.session_state["page"] = "profiling"

page = st.session_state.get("page", "auth")

if page == "auth":
    render_auth_page()
elif page == "profiling":
    render_profiling_page()
elif page == "result":
    render_classification_result()
elif page == "chat":
    render_chat_page()
else:
    st.session_state["page"] = "auth"
    st.rerun()
