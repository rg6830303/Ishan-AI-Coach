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

st.set_page_config(
    page_title="Sprint Society AI Coach",
    page_icon="🏃",
    layout="centered",
    initial_sidebar_state="auto",
)

init_db()

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
