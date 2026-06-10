import streamlit as st
from database.auth import signup, login


def render_auth_page():
    """Render login/signup page."""
    st.markdown(
        """
        <div style="text-align: center; padding: 2rem 0;">
            <h1 style="font-size: 2.5rem; margin-bottom: 0;">Sprint Society</h1>
            <p style="font-size: 1.2rem; color: #666;">AI Running Coach</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login", use_container_width=True)

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
            submitted = st.form_submit_button("Create Account", use_container_width=True)

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
