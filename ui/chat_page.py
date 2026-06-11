import json
import streamlit as st

from agent.agent_loop import run_agent
from database.auth import get_profile
from database.memory import get_chat_history, clear_chat_history
from personalization.store import store as personalization_store
from config import TIERS
from ui.theme import coach_meta, tier_meta, coach_hero
from ui.voice import voice_input, voice_input_available, speak, LANGUAGES


def render_chat_page():
    user = st.session_state.get("user")
    if not user:
        st.session_state["page"] = "auth"
        st.rerun()
        return

    profile = get_profile(user["id"])
    if not profile or not profile.get("profiling_complete"):
        st.session_state["page"] = "profiling"
        st.rerun()
        return

    tier = profile.get("tier", "pace")
    coach_style = profile.get("coach_style", "energizer")
    cm = coach_meta(coach_style)
    tier_info = TIERS.get(tier, TIERS["pace"])

    # Keep the JSON profile snapshot in sync for the dashboard.
    personalization_store.sync_profile(user["id"], profile)

    with st.sidebar:
        _render_sidebar(user, profile, tier_info, coach_style)

    coach_hero(coach_style, tier, tier_info["name"])

    tab_chat, tab_memory, tab_log, tab_activity = st.tabs(
        ["💬 Chat", "🧠 Coach's Memory", "📊 Training Log", "📡 Activity"]
    )

    with tab_chat:
        _render_chat_tab(user, profile, cm, tier_info)
    with tab_memory:
        _render_memory_tab(user)
    with tab_log:
        _render_training_log_tab(user)
    with tab_activity:
        _render_activity_tab(user)


# ----------------------------------------------------------------- chat tab
def _render_chat_tab(user, profile, cm, tier_info):
    st.caption(f"Model: `{tier_info['model']}` · responses adapt to everything you share.")

    if "messages" not in st.session_state:
        st.session_state["messages"] = get_chat_history(user["id"]) or []

    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"], avatar=cm["icon"] if msg["role"] == "assistant" else "🏃"):
            st.markdown(msg["content"])
            if msg.get("tool_calls"):
                _render_tool_calls(msg["tool_calls"])

    # ---- Voice input row ----
    spoken = None
    if st.session_state.get("voice_enabled") and voice_input_available():
        lang = st.session_state.get("voice_lang", "en-US")
        c1, c2 = st.columns([1, 4])
        with c1:
            spoken = voice_input(key="chat_voice", language=lang)
        with c2:
            st.caption("🎤 Tap **Speak**, talk, then **Stop** — your words become the message.")

    typed = st.chat_input("Ask your coach anything...")
    prompt = (spoken or "").strip() or (typed or "").strip()

    if prompt:
        _handle_prompt(user, cm, prompt)


def _handle_prompt(user, cm, prompt):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🏃"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=cm["icon"]):
        with st.spinner(f"{cm['name']} is thinking..."):
            result = run_agent(user["id"], prompt)
        st.markdown(result["response"])
        if result.get("tool_calls"):
            _render_tool_calls(result["tool_calls"])

    st.session_state["messages"].append({
        "role": "assistant",
        "content": result["response"],
        "tool_calls": result.get("tool_calls"),
    })

    # Speak the reply if auto-read is on.
    if st.session_state.get("auto_read") and not result.get("error"):
        nonce = len(st.session_state["messages"])
        speak(result["response"], nonce=nonce)

    st.rerun()


def _render_tool_calls(tool_calls):
    if not tool_calls:
        return
    with st.expander(f"🔧 {len(tool_calls)} tool call(s) used"):
        for tc in tool_calls:
            st.code(f"{tc['tool']}({json.dumps(tc.get('args', {}))})", language="python")
            st.text((tc.get("result", "") or "")[:300])


# --------------------------------------------------------------- memory tab
def _render_memory_tab(user):
    st.markdown("#### 🧠 What your coach has learned about you")
    st.caption("Updated automatically on every message. Stored locally as JSON.")

    data = personalization_store.get_personalization(user["id"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Interactions", data.get("interaction_count", 0))
    m2.metric("Goals tracked", len(data.get("goals", [])))
    active_inj = [i for i in data.get("injuries", []) if i.get("status") == "active"]
    m3.metric("Active niggles", len(active_inj))
    m4.metric("Achievements", len(data.get("achievements", [])))

    if data.get("summary"):
        st.markdown(f"<div class='ss-card'>📝 <b>Summary:</b> {data['summary']}</div>", unsafe_allow_html=True)

    cues = data.get("coaching_adjustments", {})
    active_cues = []
    if cues.get("has_active_injury"):
        active_cues.append("🩹 Prioritising injury safety")
    if cues.get("needs_encouragement"):
        active_cues.append("💛 Extra encouragement")
    if cues.get("wants_data"):
        active_cues.append("📐 Numbers & structure")
    if cues.get("prefers_brevity"):
        active_cues.append("✂️ Keeping it brief")
    if active_cues:
        st.markdown("**Active coaching adjustments:** " + "  ".join(f"<span class='ss-chip'>{c}</span>" for c in active_cues), unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**🎯 Goals**")
        if data.get("goals"):
            for g in data["goals"]:
                st.markdown(f"- {g['text']}  <span class='ss-muted'>(×{g.get('mentions',1)})</span>", unsafe_allow_html=True)
        else:
            st.caption("No goals detected yet — tell your coach what you're chasing.")

        st.markdown("**🏅 Achievements**")
        if data.get("achievements"):
            for a in data["achievements"][-6:]:
                st.markdown(f"- {a['text']}")
        else:
            st.caption("Share a recent win and it'll show up here.")

    with col_b:
        st.markdown("**🩹 Injuries / niggles**")
        if data.get("injuries"):
            for i in data["injuries"]:
                badge = "🔴" if i.get("status") == "active" else "🟢"
                st.markdown(f"- {badge} {i['area']} — {i.get('status','?')} (×{i.get('mentions',1)})")
        else:
            st.caption("None reported. 🙌")

        prefs = data.get("preferences", {})
        st.markdown("**❤️ Likes / 🚫 Dislikes**")
        if prefs.get("likes") or prefs.get("dislikes"):
            for v in prefs.get("likes", []):
                st.markdown(f"<span class='ss-chip'>❤️ {v}</span>", unsafe_allow_html=True)
            for v in prefs.get("dislikes", []):
                st.markdown(f"<span class='ss-chip'>🚫 {v}</span>", unsafe_allow_html=True)
        else:
            st.caption("No clear preferences yet.")

    topics = data.get("topics", {})
    if topics:
        st.markdown("**💬 What you talk about most**")
        st.bar_chart(dict(sorted(topics.items(), key=lambda kv: kv[1], reverse=True)))

    trend = data.get("sentiment_trend", [])
    if trend:
        mapping = {"positive": 1, "neutral": 0, "negative": -1}
        series = [mapping.get(s["sentiment"], 0) for s in trend][-20:]
        st.markdown("**🙂 Mood trend (recent messages)**")
        st.line_chart(series)

    with st.expander("🗂️ Raw personalization JSON"):
        st.json(data)


# ----------------------------------------------------------- training log tab
def _render_training_log_tab(user):
    st.markdown("#### 📊 Your training log")
    st.caption("Runs you log here (or that your coach records from chat) are saved as JSONL.")

    with st.expander("➕ Log a run manually"):
        with st.form("log_run_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                dist = st.number_input("Distance (km)", 0.0, 200.0, 5.0, step=0.5)
            with c2:
                dur = st.number_input("Duration (min)", 0, 600, 30, step=5)
            with c3:
                rtype = st.selectbox("Type", ["easy", "long", "tempo", "intervals", "recovery", "race", "other"])
            feel = st.text_input("How did it feel?", placeholder="e.g. strong, sore knee, tough but good")
            notes = st.text_area("Notes", placeholder="Anything worth remembering", height=70)
            if st.form_submit_button("Save run", type="primary"):
                entry = {"distance_km": dist, "duration_minutes": dur, "type": rtype}
                if feel:
                    entry["feel"] = feel
                if notes:
                    entry["notes"] = notes
                personalization_store.add_training_log(user["id"], entry)
                st.success("Run logged! 🎉")
                st.rerun()

    log = personalization_store.get_training_log(user["id"])
    if not log:
        st.info("No runs logged yet. Tell your coach about a run, or use the form above.")
        return

    total_km = sum(float(e.get("distance_km") or 0) for e in log)
    c1, c2, c3 = st.columns(3)
    c1.metric("Runs logged", len(log))
    c2.metric("Total distance", f"{total_km:.1f} km")
    c3.metric("Avg distance", f"{(total_km/len(log)):.1f} km")

    rows = [
        {
            "date": e.get("date", ""),
            "km": e.get("distance_km", ""),
            "min": e.get("duration_minutes", ""),
            "type": e.get("type", ""),
            "feel": e.get("feel", ""),
        }
        for e in reversed(log)
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


# -------------------------------------------------------------- activity tab
def _render_activity_tab(user):
    st.markdown("#### 📡 Recent activity")
    st.caption("Append-only event log (events.jsonl) — every interaction is captured.")
    events = personalization_store.get_events(user["id"], limit=60)
    if not events:
        st.info("No activity yet.")
        return
    icons = {
        "user_message": "🗣️", "assistant_message": "🤖", "training_log": "🏃",
        "profile_update": "⚙️", "voice_input": "🎤",
    }
    for ev in reversed(events):
        icon = icons.get(ev.get("type"), "•")
        ts = ev.get("ts", "")[:19].replace("T", " ")
        payload = ev.get("payload", {})
        preview = payload.get("preview", "")
        extra = ""
        if payload.get("topics"):
            extra = "  ".join(f"<span class='ss-chip'>{t}</span>" for t in payload["topics"])
        st.markdown(
            f"<div class='ss-card' style='padding:.5rem .8rem;'>{icon} "
            f"<span class='ss-muted'>{ts}</span> · <b>{ev.get('type','')}</b><br>"
            f"<span style='font-size:.85rem;'>{preview}</span> {extra}</div>",
            unsafe_allow_html=True,
        )


# ----------------------------------------------------------------- sidebar
def _render_sidebar(user, profile, tier_info, coach_style):
    cm = coach_meta(coach_style)
    tier = profile.get("tier", "pace")
    tm = tier_meta(tier)

    st.markdown(
        f"<div class='ss-card' style='text-align:center; border-top:3px solid {cm['color']};'>"
        f"<div style='font-size:2.2rem;'>{cm['icon']}</div>"
        f"<div style='font-weight:800; font-size:1.1rem;'>{cm['name']}</div>"
        f"<div class='ss-muted'>{cm['tagline']}</div></div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<div style='text-align:center; margin:.4rem 0;'>"
        f"<span class='ss-pill' style='background:{tm['color']};'>{tm['icon']} {tier_info['name']} · {tier_info['label']}</span></div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Your profile**")
    st.markdown(f"- 🎂 Age: {profile.get('age')}")
    st.markdown(f"- 🏋️ Fitness: {profile.get('fitness_level')}")
    st.markdown(f"- 🏃 Experience: {profile.get('running_experience')}")
    st.markdown(f"- 🏁 Dream race: {profile.get('dream_race')}")
    st.markdown(f"- 📅 Training days: {profile.get('training_days', 3)}/week")
    five_k = profile.get("recent_5k_time")
    if five_k:
        mins = int(five_k)
        secs = int(round((five_k - mins) * 60))
        st.markdown(f"- ⏱️ 5K: {mins}:{secs:02d}")

    st.divider()
    st.markdown("**🔊 Voice**")
    if voice_input_available():
        st.session_state["voice_enabled"] = st.toggle(
            "Voice input (mic)", value=st.session_state.get("voice_enabled", False)
        )
        label = st.selectbox("Language", list(LANGUAGES.keys()), index=0)
        st.session_state["voice_lang"] = LANGUAGES[label]
    else:
        st.caption("🎤 Mic input unavailable (install `streamlit-mic-recorder`).")
    st.session_state["auto_read"] = st.toggle(
        "Read replies aloud", value=st.session_state.get("auto_read", False)
    )

    st.divider()
    if st.button("🧹 Clear chat history", use_container_width=True):
        clear_chat_history(user["id"])
        st.session_state["messages"] = []
        st.rerun()
    if st.button("🔄 Re-do profiling", use_container_width=True):
        st.session_state["page"] = "profiling"
        st.session_state["profile_step"] = 0
        st.session_state["profile_data"] = {}
        st.rerun()
    if st.button("🚪 Logout", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
