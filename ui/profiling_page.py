import streamlit as st
from database.auth import save_profile
from engine.classifier import classify_runner
from ui.theme import COACH_META


def render_profiling_page():
    """8-step profiling wizard to collect runner metrics."""
    user = st.session_state.get("user")
    if not user:
        st.session_state["page"] = "auth"
        st.rerun()
        return

    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown("## 🧭 Runner Profile Setup")
        st.caption("Help us understand you so we can assign the perfect coach.")

        if "profile_step" not in st.session_state:
            st.session_state["profile_step"] = 0
        if "profile_data" not in st.session_state:
            st.session_state["profile_data"] = {}

        step = st.session_state["profile_step"]
        total_steps = 8

        st.progress((step + 1) / total_steps, text=f"Step {step + 1} of {total_steps}")

        if step == 0:
            _step_basics()
        elif step == 1:
            _step_fitness()
        elif step == 2:
            _step_dream_race()
        elif step == 3:
            _step_motivation()
        elif step == 4:
            _step_schedule()
        elif step == 5:
            _step_mindset()
        elif step == 6:
            _step_performance()
        elif step == 7:
            _step_coach_style()


def _nav_buttons(can_back=True):
    col1, col2 = st.columns(2)
    with col1:
        if can_back and st.session_state["profile_step"] > 0:
            if st.button("Back", use_container_width=True):
                st.session_state["profile_step"] -= 1
                st.rerun()
    with col2:
        if st.button("Next", type="primary", use_container_width=True):
            st.session_state["profile_step"] += 1
            st.rerun()


def _step_basics():
    st.markdown("### Basic Information")
    data = st.session_state["profile_data"]

    data["gender"] = st.radio(
        "Gender", ["male", "female", "non-binary"],
        index=["male", "female", "non-binary"].index(data.get("gender", "male")),
        horizontal=True,
    )
    data["age"] = st.slider("Age", 16, 70, data.get("age", 28))
    data["height_cm"] = st.slider("Height (cm)", 140, 210, data.get("height_cm", 170))
    data["weight_kg"] = st.slider("Weight (kg)", 40, 150, data.get("weight_kg", 70))

    _nav_buttons(can_back=False)


def _step_fitness():
    st.markdown("### Fitness Level")
    data = st.session_state["profile_data"]

    options = ["sedentary", "lightly_active", "active", "very_active"]
    labels = [
        "Sedentary (desk job, minimal exercise)",
        "Lightly Active (walk/light exercise 1-2x/week)",
        "Active (exercise 3-5x/week)",
        "Very Active (intense exercise 6-7x/week)",
    ]
    idx = options.index(data.get("fitness_level", "active"))
    choice = st.radio("Current fitness level", labels, index=idx)
    data["fitness_level"] = options[labels.index(choice)]

    exp_options = ["none", "beginner", "intermediate", "advanced"]
    exp_labels = [
        "None (never ran consistently)",
        "Beginner (0-6 months of running)",
        "Intermediate (6 months - 2 years)",
        "Advanced (2+ years consistent running)",
    ]
    exp_idx = exp_options.index(data.get("running_experience", "beginner"))
    exp_choice = st.radio("Running experience", exp_labels, index=exp_idx)
    data["running_experience"] = exp_options[exp_labels.index(exp_choice)]

    _nav_buttons()


def _step_dream_race():
    st.markdown("### Dream Race")
    data = st.session_state["profile_data"]

    races = ["5K", "10K", "Half Marathon", "Marathon", "Ultra", "No race goal"]
    idx = races.index(data.get("dream_race", "5K")) if data.get("dream_race") in races else 0
    data["dream_race"] = st.radio("What's your dream race?", races, index=idx)

    _nav_buttons()


def _step_motivation():
    st.markdown("### Why Do You Run?")
    data = st.session_state["profile_data"]

    motivations = ["compete", "health", "mental clarity", "social", "weight loss", "fun"]
    labels = [
        "Competition & Racing",
        "Health & Longevity",
        "Mental Clarity & Stress Relief",
        "Social Connection",
        "Weight Management",
        "Pure Fun & Freedom",
    ]
    idx = motivations.index(data.get("running_why", "health")) if data.get("running_why") in motivations else 1
    choice = st.radio("Primary motivation", labels, index=idx)
    data["running_why"] = motivations[labels.index(choice)]

    _nav_buttons()


def _step_schedule():
    st.markdown("### Training Schedule")
    data = st.session_state["profile_data"]

    times = ["morning", "afternoon", "evening", "flexible"]
    time_labels = ["Early Morning (5-8am)", "Afternoon (12-4pm)", "Evening (5-9pm)", "Flexible"]
    time_idx = times.index(data.get("preferred_time", "morning")) if data.get("preferred_time") in times else 0
    choice = st.radio("Preferred running time", time_labels, index=time_idx)
    data["preferred_time"] = times[time_labels.index(choice)]

    data["training_days"] = st.slider(
        "Training days per week", 1, 7, data.get("training_days", 3)
    )

    _nav_buttons()


def _step_mindset():
    st.markdown("### Running Mindset")
    data = st.session_state["profile_data"]

    responses = ["push_harder", "analyze", "rest", "forget"]
    response_labels = [
        "Push harder next time (competitive drive)",
        "Analyze what went wrong (data-driven)",
        "Rest and reset (recovery-first)",
        "Shake it off, move on (resilient)",
    ]
    idx = responses.index(data.get("bad_run_response", "analyze")) if data.get("bad_run_response") in responses else 1
    choice = st.radio("After a bad run, you typically...", response_labels, index=idx)
    data["bad_run_response"] = responses[response_labels.index(choice)]

    injuries = ["knee", "ankle", "hip", "back", "shin splints", "hamstring", "none"]
    current = data.get("injury_history", [])
    data["injury_history"] = st.multiselect(
        "Any injury history? (select all that apply)", injuries, default=current
    )

    _nav_buttons()


def _step_performance():
    st.markdown("### Performance Data")
    data = st.session_state["profile_data"]

    st.markdown("*Optional: If you've run a 5K recently, this helps us calibrate your paces.*")
    has_5k = st.checkbox("I have a recent 5K time", value=data.get("recent_5k_time") is not None)

    if has_5k:
        existing = data.get("recent_5k_time")
        try:
            existing = float(existing) if existing is not None else 28.0
        except (TypeError, ValueError):
            existing = 28.0
        default_min = min(60, max(12, int(existing)))
        default_sec = min(59, max(0, int(round((existing - int(existing)) * 60))))
        col1, col2 = st.columns(2)
        with col1:
            mins = st.number_input("Minutes", 12, 60, default_min)
        with col2:
            secs = st.number_input("Seconds", 0, 59, default_sec)
        data["recent_5k_time"] = mins + secs / 60
    else:
        data["recent_5k_time"] = None

    _nav_buttons()


def _step_coach_style():
    st.markdown("### Choose Your Coach")
    data = st.session_state["profile_data"]

    styles = ["scientist", "energizer", "warrior", "sage"]

    current_style = data.get("coach_style", "energizer")
    idx = styles.index(current_style) if current_style in styles else 1

    cols = st.columns(2)
    for i, style in enumerate(styles):
        meta = COACH_META[style]
        with cols[i % 2]:
            st.markdown(
                f"<div class='ss-card' style='border-top:3px solid {meta['color']};'>"
                f"<div style='font-size:1.6rem;'>{meta['icon']} <b>{meta['name']}</b></div>"
                f"<div class='ss-muted'>{meta['tagline']}</div>"
                f"<div style='font-size:.85rem; margin-top:.3rem;'>{meta['blurb']}</div></div>",
                unsafe_allow_html=True,
            )

    choice_labels = [f"{COACH_META[s]['icon']} {COACH_META[s]['name']}" for s in styles]
    selected = st.radio("Pick your coach personality", choice_labels, index=idx)
    data["coach_style"] = styles[choice_labels.index(selected)]

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back", use_container_width=True):
            st.session_state["profile_step"] -= 1
            st.rerun()
    with col2:
        if st.button("Complete Profile", type="primary", use_container_width=True):
            _finalize_profile()


def _finalize_profile():
    """Classify runner and save profile."""
    user = st.session_state["user"]
    data = st.session_state["profile_data"]

    classification = classify_runner(data)
    data["tier"] = classification["tier"]
    data["tier_score"] = classification["score"]

    success = save_profile(user["id"], data)
    if success:
        st.session_state["classification"] = classification
        st.session_state["page"] = "result"
        st.rerun()
    else:
        st.error("Failed to save profile. Please try again.")
