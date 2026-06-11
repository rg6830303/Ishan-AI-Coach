import streamlit as st
from database.auth import signup, login
from ui.theme import COACH_META, TIER_META


def render_auth_page():
    """Login / signup with a branded hero and coach showcase."""
    _, center, _ = st.columns([1, 2, 1])

    with center:
        st.markdown(
            """
            <div style="text-align:center; padding:1.5rem 0 0.5rem 0;">
                <div class="ss-brand" style="justify-content:center; font-size:2.4rem;">
                    🏃 Sprint Society
                </div>
                <p style="font-size:1.15rem; color:#9aa0a6; margin-top:.2rem;">
                    Your AI running coach — four personalities, four levels, infinitely personal.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab_login, tab_signup = st.tabs(["🔑 Login", "✨ Sign Up"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Login", use_container_width=True, type="primary")

                if submitted:
                    if not email or not password:
                        st.error("Please fill in all fields.")
                    else:
                        user = login(email, password)
                        if user:
                            st.session_state["user"] = user
                            st.session_state["page"] = "main"
                            st.rerun()
                        else:
                            st.error("Invalid email or password.")

        with tab_signup:
            with st.form("signup_form"):
                name = st.text_input("Full Name", key="signup_name")
                email = st.text_input("Email", key="signup_email")
                password = st.text_input("Password", type="password", key="signup_password")
                confirm = st.text_input("Confirm Password", type="password", key="signup_confirm")
                submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")

                if submitted:
                    if not name or not email or not password:
                        st.error("Please fill in all fields.")
                    elif password != confirm:
                        st.error("Passwords don't match.")
                    elif len(password) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        user = signup(name, email, password)
                        if user:
                            st.session_state["user"] = user
                            st.session_state["page"] = "profiling"
                            st.success("Account created! Let's set up your profile.")
                            st.rerun()
                        else:
                            st.error("Email already registered. Try logging in.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("##### Meet your coaches")
    cols = st.columns(4)
    for col, (style, cm) in zip(cols, COACH_META.items()):
        with col:
            st.markdown(
                f"""
                <div class="ss-card" style="text-align:center; border-top:3px solid {cm['color']};">
                    <div style="font-size:2rem;">{cm['icon']}</div>
                    <div style="font-weight:700;">{cm['name']}</div>
                    <div class="ss-muted">{cm['tagline']}</div>
                    <div style="font-size:.82rem; margin-top:.4rem;">{cm['blurb']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("##### Four levels, one journey")
    tcols = st.columns(4)
    for col, (tier, tm) in zip(tcols, TIER_META.items()):
        with col:
            st.markdown(
                f"<div class='ss-card' style='text-align:center;'>"
                f"<span style='font-size:1.4rem;'>{tm['icon']}</span> "
                f"<b>{tier.capitalize()}</b><br><span class='ss-muted'>{tm['label']}</span></div>",
                unsafe_allow_html=True,
            )
