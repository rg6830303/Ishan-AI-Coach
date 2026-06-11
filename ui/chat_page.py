import json
import streamlit as st

from agent.agent_loop import run_agent
from database.auth import get_profile
from database.memory import (
    get_full_thread, clear_chat_history,
    list_threads, create_thread, rename_thread, delete_thread,
    get_or_create_active_thread,
)
from personalization.store import store as personalization_store
from coaching.cycles import get_cycle, get_level, estimate_starting_level
from coaching.plans import generate_periodized_plan
from config import TIERS
from ui.theme import coach_meta, tier_meta, coach_hero
from ui.voice import (
    voice_input, voice_input_available, speak, stop_speaking,
    LANGUAGES, VOICE_STYLES, default_voice_for,
)


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

    personalization_store.sync_profile(user["id"], profile)

    # Ensure an active thread exists.
    if "thread_id" not in st.session_state or st.session_state.get("thread_id") is None:
        st.session_state["thread_id"] = get_or_create_active_thread(user["id"])
        st.session_state["messages"] = get_full_thread(user["id"], st.session_state["thread_id"])

    with st.sidebar:
        _render_sidebar(user, profile, tier_info, coach_style)

    coach_hero(coach_style, tier, tier_info["name"])

    tab_dash, tab_cal, tab_builder, tab_chat, tab_memory, tab_cycle, tab_log, tab_activity = st.tabs(
        ["📊 Dashboard", "📅 Calendar & Workouts", "🗺️ Plan Builder", "💬 AI Coach Chat", "🧠 Coach's Memory", "🎯 Training Cycle", "📊 Training Log", "📡 Activity"]
    )

    with tab_dash:
        _render_dashboard_tab(user, profile)
    with tab_cal:
        _render_calendar_tab(user)
    with tab_builder:
        _render_plan_builder_tab(user, profile)
    with tab_chat:
        _render_chat_tab(user, profile, cm, coach_style, tier_info)
    with tab_memory:
        _render_memory_tab(user)
    with tab_cycle:
        _render_cycle_tab(user, profile, coach_style)
    with tab_log:
        _render_training_log_tab(user)
    with tab_activity:
        _render_activity_tab(user)


# ----------------------------------------------------------------- chat tab
def _render_chat_tab(user, profile, cm, coach_style, tier_info):
    level = personalization_store.get_training_level(
        user["id"], coach_style, default=estimate_starting_level(coach_style, profile)
    )
    lvl_info = get_level(coach_style, level)
    cycle = get_cycle(coach_style)
    st.caption(
        f"Model: `{tier_info['model']}` · Level {level}/10 · "
        f"**{lvl_info['name']}** ({cycle['cycle_name']})"
    )

    if "messages" not in st.session_state:
        st.session_state["messages"] = get_full_thread(user["id"], st.session_state["thread_id"])

    for msg in st.session_state["messages"]:
        avatar = cm["icon"] if msg["role"] == "assistant" else "🏃"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])
            if msg.get("tool_calls"):
                _render_citations_and_sources(msg["tool_calls"])
                _render_tool_calls(msg["tool_calls"])

    spoken = None
    if st.session_state.get("voice_enabled") and voice_input_available():
        lang = st.session_state.get("voice_lang", "en-US")
        c1, c2 = st.columns([1, 4])
        with c1:
            spoken = voice_input(key=f"voice_{st.session_state['thread_id']}", language=lang)
        with c2:
            st.caption("🎤 Tap **Speak**, talk, then **Stop** — your words become the message.")

    typed = st.chat_input("Ask your coach anything...")
    prompt = (spoken or "").strip() or (typed or "").strip()

    if prompt:
        _handle_prompt(user, cm, coach_style, prompt)


def _handle_prompt(user, cm, coach_style, prompt):
    thread_id = st.session_state["thread_id"]

    # Auto-title a fresh thread from the first user message.
    if not st.session_state.get("messages"):
        title = " ".join(prompt.split()[:6])[:60] or "New chat"
        rename_thread(user["id"], thread_id, title)

    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🏃"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=cm["icon"]):
        with st.spinner(f"{cm['name']} is thinking..."):
            result = run_agent(user["id"], prompt, thread_id=thread_id)
        st.markdown(result["response"])
        if result.get("tool_calls"):
            _render_citations_and_sources(result["tool_calls"])
            _render_tool_calls(result["tool_calls"])

    st.session_state["messages"].append({
        "role": "assistant",
        "content": result["response"],
        "tool_calls": result.get("tool_calls"),
    })

    if st.session_state.get("auto_read") and not result.get("error"):
        style = st.session_state.get("voice_style") or default_voice_for(coach_style)
        speak(result["response"], nonce=len(st.session_state["messages"]), style=style)

    st.rerun()


def _render_citations_and_sources(tool_calls):
    if not tool_calls:
        return
        
    knowledge_sources = []
    web_sources = []
    
    for tc in tool_calls:
        tool_name = tc.get("tool")
        result_val = tc.get("result")
        
        if not result_val:
            continue
            
        parsed_result = None
        if isinstance(result_val, str):
            try:
                parsed_result = json.loads(result_val)
            except Exception:
                continue
        elif isinstance(result_val, list):
            parsed_result = result_val
            
        if not parsed_result:
            continue
            
        if tool_name == "retrieve_knowledge" and isinstance(parsed_result, list):
            knowledge_sources.extend(parsed_result)
        elif tool_name == "search_web" and isinstance(parsed_result, list):
            web_sources.extend(parsed_result)
            
    if not knowledge_sources and not web_sources:
        return
        
    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
    with st.expander("📚 Sources & Citations Used (RAG + Web Scraper)", expanded=True):
        if knowledge_sources:
            st.markdown("##### 📖 Knowledge Corpus Chunks (Metadata & Principles)")
            for src in knowledge_sources:
                st.markdown(
                    f"<div class='ss-card' style='border-left: 3px solid #0ea5e9; margin-bottom: 8px; padding: 10px; font-size: 0.85rem;'>"
                    f"<b>{src.get('title')}</b> <span class='ss-muted'>(Source: {src.get('source')}, Score: {src.get('relevance_score', 0.0)})</span><br>"
                    f"<div style='margin-top: 5px; color: #e2e8f0;'>{src.get('content')}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                
        if web_sources:
            st.markdown("##### 🌐 Live Web Search Results")
            for src in web_sources:
                st.markdown(
                    f"<div class='ss-card' style='border-left: 3px solid #a855f7; margin-bottom: 8px; padding: 10px; font-size: 0.85rem;'>"
                    f"🔗 <a href='{src.get('url')}' target='_blank' style='color: #38bdf8; font-weight: bold; text-decoration: underline;'>{src.get('title')}</a><br>"
                    f"<div style='margin-top: 5px; color: #e2e8f0;'>{src.get('snippet')}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )


def _render_tool_calls(tool_calls):
    if not tool_calls:
        return
    with st.expander(f"🔧 {len(tool_calls)} tool call(s) used"):
        for tc in tool_calls:
            st.code(f"{tc['tool']}({json.dumps(tc.get('args', {}))})", language="python")
            st.text((tc.get("result", "") or "")[:300])


# ------------------------------------------------------------- cycle tab
def _render_cycle_tab(user, profile, coach_style):
    cm = coach_meta(coach_style)
    cycle = get_cycle(coach_style)
    level = personalization_store.get_training_level(
        user["id"], coach_style, default=estimate_starting_level(coach_style, profile)
    )
    st.markdown(f"#### {cm['icon']} {cycle['cycle_name']}")
    st.caption(cycle["philosophy"])
    st.progress(level / 10.0, text=f"Level {level} of 10")

    for lv in cycle["levels"]:
        n = lv["n"]
        if n == level:
            border = cm["color"]
            badge = "📍 YOU ARE HERE"
        elif n < level:
            border = "#3ddc84"
            badge = "✅ cleared"
        else:
            border = "rgba(255,255,255,.12)"
            badge = "🔒 locked"
        st.markdown(
            f"<div class='ss-card' style='border-left:4px solid {border};'>"
            f"<b>Level {n} — {lv['name']}</b> "
            f"<span class='ss-muted'>{badge}</span><br>"
            f"<span style='font-size:.9rem;'>{lv['focus']}</span><br>"
            f"<span class='ss-muted'>⬆️ Level up: {lv['graduate']}</span></div>",
            unsafe_allow_html=True,
        )


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

    ml_dl = data.get("ml_dl_performance_analysis")
    if ml_dl:
        zone = ml_dl.get("readiness_zone", "Unknown")
        zone_color = "🟢" if zone == "Green" else "🟡" if zone == "Yellow" else "🔴"
        st.markdown(
            f"<div class='ss-card' style='border-top: 3px solid #3ddc84; margin-bottom: 15px;'>"
            f"🧬 <b>Physiological Readiness &amp; Performance Predictions (ML/DL Models)</b><br>"
            f"<div style='display:flex; justify-content:space-around; align-items:center; margin-top:10px;'>"
            f"<div><b>Injury Risk:</b> {ml_dl.get('injury_risk_percent', 0.0):.1f}%</div>"
            f"<div><b>Readiness Status:</b> {zone_color} {zone}</div>"
            f"<div><b>Est. Next Wk VDOT:</b> {ml_dl.get('predicted_future_vdot', 0.0):.1f}</div>"
            f"</div>"
            f"<div style='margin-top:10px; font-size:0.8rem;' class='ss-muted'>"
            f"Predictions generated by Random Forest Classifier and MLP Neural Network. Last updated: {ml_dl.get('analyzed_at','?')}"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    cues = data.get("coaching_adjustments", {})
    active_cues = []
    if cues.get("has_active_injury"):
        active_cues.append("🩹 Prioritising injury safety")
    if cues.get("needs_encouragement"):
        active_cues.append("💛 Extra encouragement")
    if cues.get("wants_data"):
        active_cues.append("📐 Numbers & structure")
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
                personalization_store.add_training_log(user["id"], entry, thread_id=st.session_state.get("thread_id"))
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
        "profile_update": "⚙️", "level_change": "🎯",
    }
    for ev in reversed(events):
        icon = icons.get(ev.get("type"), "•")
        ts = ev.get("ts", "")[:19].replace("T", " ")
        payload = ev.get("payload", {})
        preview = payload.get("preview", "")
        if ev.get("type") == "level_change":
            preview = f"Level {payload.get('from')} → {payload.get('to')}: {payload.get('reason','')}"
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

    # Fetch personalization data to get ML/DL predictions
    data = personalization_store.get_personalization(user["id"])
    ml_dl = data.get("ml_dl_performance_analysis")
    if ml_dl:
        zone = ml_dl.get("readiness_zone", "Unknown")
        zone_color = "🟢" if zone == "Green" else "🟡" if zone == "Yellow" else "🔴"
        st.markdown(
            f"<div class='ss-card' style='font-size: 0.85rem; padding: 0.8rem; margin: 0.4rem 0; border-left: 3px solid #3ddc84;'>"
            f"🧬 <b>ML/DL Physiological State:</b><br>"
            f"• Injury Risk: {ml_dl.get('injury_risk_percent', 0.0):.1f}%<br>"
            f"• Status: {zone_color} {zone}<br>"
            f"• Next Wk VDOT: {ml_dl.get('predicted_future_vdot', 0.0):.1f}"
            f"</div>",
            unsafe_allow_html=True
        )

    _render_threads_panel(user)

    st.divider()
    st.markdown("**🔊 Voice**")
    if voice_input_available():
        st.session_state["voice_enabled"] = st.toggle(
            "Voice input (mic)", value=st.session_state.get("voice_enabled", False)
        )
        label = st.selectbox("Input language", list(LANGUAGES.keys()), index=0)
        st.session_state["voice_lang"] = LANGUAGES[label]
    else:
        st.caption("🎤 Mic input unavailable (install `streamlit-mic-recorder`).")

    st.session_state["auto_read"] = st.toggle(
        "Read replies aloud", value=st.session_state.get("auto_read", False)
    )
    default_style = default_voice_for(coach_style)
    styles = list(VOICE_STYLES.keys())
    idx = styles.index(default_style) if default_style in styles else 0
    st.session_state["voice_style"] = st.selectbox("Coach voice", styles, index=idx)
    cc1, cc2 = st.columns(2)
    with cc1:
        if st.button("🔈 Test", use_container_width=True):
            speak(f"Hi, I'm {cm['name']}. Let's get to work.", nonce=f"test_{st.session_state['voice_style']}", style=st.session_state["voice_style"])
    with cc2:
        if st.button("⏹️ Stop", use_container_width=True):
            stop_speaking()

    st.divider()
    if st.button("🔄 Re-do profiling", use_container_width=True):
        st.session_state["page"] = "profiling"
        st.session_state["profile_step"] = 0
        st.session_state["profile_data"] = {}
        st.rerun()
    if st.button("🚪 Logout", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


def _render_threads_panel(user):
    st.markdown("**💬 Chat threads**")
    threads = list_threads(user["id"])
    active = st.session_state.get("thread_id")

    if st.button("➕ New chat", use_container_width=True):
        tid = create_thread(user["id"], "New chat")
        st.session_state["thread_id"] = tid
        st.session_state["messages"] = []
        st.rerun()

    if threads:
        labels = {}
        for t in threads:
            mark = "🟢 " if t["id"] == active else ""
            labels[t["id"]] = f"{mark}{t['title']}  ·  {t['message_count']} msg"
        chosen = st.radio(
            "Threads",
            options=[t["id"] for t in threads],
            format_func=lambda tid: labels.get(tid, "thread"),
            index=next((i for i, t in enumerate(threads) if t["id"] == active), 0),
            label_visibility="collapsed",
        )
        if chosen != active:
            st.session_state["thread_id"] = chosen
            st.session_state["messages"] = get_full_thread(user["id"], chosen)
            st.rerun()

        with st.expander("✏️ Manage this thread"):
            new_title = st.text_input("Rename", value=next((t["title"] for t in threads if t["id"] == active), ""))
            mc1, mc2 = st.columns(2)
            with mc1:
                if st.button("Save name", use_container_width=True):
                    rename_thread(user["id"], active, new_title)
                    st.rerun()
            with mc2:
                if st.button("🗑️ Delete", use_container_width=True):
                    delete_thread(user["id"], active)
                    st.session_state["thread_id"] = None
                    st.session_state.pop("messages", None)
                    st.rerun()


# ----------------------------------------------------------- dashboard tab
def _render_dashboard_tab(user, profile):
    st.markdown("### 📊 Runner Dashboard")
    
    # 1. Load data
    data = personalization_store.get_personalization(user["id"])
    log = personalization_store.get_training_log(user["id"])
    plan = personalization_store.get_active_plan(user["id"])
    ml_dl = data.get("ml_dl_performance_analysis")
    
    # 2. Key Metrics Row
    total_runs = len(log)
    total_km = sum(float(e.get("distance_km") or 0) for e in log)
    
    avg_pace_str = "N/A"
    if total_runs > 0:
        total_min = sum(float(e.get("duration_minutes") or 0) for e in log)
        if total_km > 0:
            avg_pace_sec = int((total_min * 60) / total_km)
            avg_pace_str = f"{avg_pace_sec // 60}:{avg_pace_sec % 60:02d}/km"
            
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Weekly Mileage (Total)", f"{total_km:.1f} km")
    m2.metric("Total Runs", total_runs)
    m3.metric("Average Pace", avg_pace_str)
    m4.metric("Active Level", f"Level {data.get('training_level', {}).get('level', 1)}")
    
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("#### 🏃 Active Training Program")
        if plan:
            st.markdown(
                f"<div class='ss-card' style='border-left: 4px solid #8b5cf6; margin-bottom: 15px;'>"
                f"🎯 <b>Goal:</b> {plan.get('goal')} Plan ({plan.get('total_weeks')} Weeks)<br>"
                f"🗓️ <b>Generated At:</b> {plan.get('generated_at', '?')[:10]} | <b>VDOT:</b> {plan.get('vdot', '?')}"
                f"</div>",
                unsafe_allow_html=True
            )
            
            # Find next scheduled workout
            next_workout = None
            completed_count = 0
            total_count = 0
            next_workout_week = 1
            for week in plan.get("weeks", []):
                for workout in week.get("schedule", []):
                    if workout["type"] != "rest":
                        total_count += 1
                        if workout["status"] == "completed":
                            completed_count += 1
                        elif workout["status"] == "scheduled" and next_workout is None:
                            next_workout = workout
                            next_workout_week = week["week_number"]
                            
            progress_pct = completed_count / total_count if total_count > 0 else 0.0
            st.progress(progress_pct, text=f"Program Progress: {completed_count}/{total_count} runs completed ({progress_pct*100:.1f}%)")
            
            if next_workout:
                st.markdown(f"##### 📅 Next Scheduled Workout (Week {next_workout_week})")
                color_map = {"easy": "#2e86ff", "tempo": "#8b5cf6", "interval": "#ff2d55", "recovery": "#ff8c00", "long": "#3ddc84"}
                type_color = color_map.get(next_workout["type"], "#9aa0a6")
                
                st.markdown(
                    f"<div class='ss-card' style='border-left: 4px solid {type_color};'>"
                    f"<span class='ss-pill' style='background:{type_color};'>{next_workout['type'].upper()}</span> "
                    f"<b>{next_workout['day']}</b> — {next_workout['distance_km']}km @ {next_workout['target_pace']}<br>"
                    f"<p style='margin-top: 5px; font-size: 0.9rem;'>{next_workout['description']}</p>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                
                with st.expander("⚡ Quick Log: Mark Next Workout as Completed"):
                    with st.form(f"quick_log_form_{next_workout['id']}"):
                        actual_dist = st.number_input("Actual Distance (km)", 0.0, 100.0, next_workout["distance_km"])
                        actual_dur = st.number_input("Actual Duration (minutes)", 1, 600, next_workout["duration_minutes"])
                        feel = st.text_input("How did it feel?", placeholder="strong, tired, sore knee...")
                        notes = st.text_area("Notes", placeholder="Any details...", height=70)
                        if st.form_submit_button("Complete Run", type="primary"):
                            logged_run = {
                                "distance_km": actual_dist,
                                "duration_minutes": actual_dur,
                                "type": next_workout["type"],
                                "feel": feel,
                                "notes": notes,
                            }
                            personalization_store.complete_workout(
                                user["id"], 
                                next_workout["id"], 
                                logged_run, 
                                thread_id=st.session_state.get("thread_id")
                            )
                            st.success(f"Log saved! Workout {next_workout['id']} marked completed. 🎉")
                            st.rerun()
            else:
                st.info("🎉 All workouts in your training plan are completed!")
        else:
            st.warning("⚠️ You do not have an active training plan yet. Use the **🗺️ Plan Builder** tab to create one!")
            
    with col2:
        st.markdown("#### 🧬 Physiological Predictions (ML/DL)")
        if ml_dl:
            zone = ml_dl.get("readiness_zone", "Unknown")
            zone_color = "🟢" if zone == "Green" else "🟡" if zone == "Yellow" else "🔴"
            st.markdown(
                f"<div class='ss-card' style='border-top: 3px solid #3ddc84;'>"
                f"<b>Readiness Level:</b> {zone_color} <b>{zone}</b><br><br>"
                f"• <b>Injury Risk:</b> {ml_dl.get('injury_risk_percent', 0.0):.1f}%<br>"
                f"• <b>Future VDOT:</b> {ml_dl.get('predicted_future_vdot', 0.0):.1f}<br>"
                f"• <b>Last Analysed:</b> {ml_dl.get('analyzed_at','?')[:19].replace('T',' ')}<br><br>"
                f"<span style='font-size:0.8rem;' class='ss-muted'>Random Forest Classifier evaluates injury patterns, and Multi-Layer Perceptron estimates performance capacity.</span>"
                f"</div>",
                unsafe_allow_html=True
            )
        else:
            st.info("Log your first training run to trigger the ML/DL physiological readiness pipeline!")

        st.markdown("#### 🩹 Active Injuries & Cues")
        active_inj = [i for i in data.get("injuries", []) if i.get("status") == "active"]
        if active_inj:
            for i in active_inj:
                st.markdown(
                    f"<div class='ss-card' style='border-left: 4px solid #ff2d55; background: rgba(255,45,85,0.05); padding: 0.8rem;'>"
                    f"🔴 <b>Active Niggle:</b> {i['area'].upper()}<br>"
                    f"<span style='font-size:0.8rem;'>First reported: {i.get('first_seen','?')[:10]} ({i.get('mentions', 1)} mentions)</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )
        else:
            st.markdown(
                f"<div class='ss-card' style='border-left: 4px solid #3ddc84; background: rgba(61,220,132,0.05); padding: 0.8rem;'>"
                f"🟢 <b>No Active Injuries:</b> You are cleared to train! Keep monitoring volume transitions."
                f"</div>",
                unsafe_allow_html=True
            )


# ----------------------------------------------------------- calendar tab
def _render_calendar_tab(user):
    st.markdown("### 📅 Training Calendar")
    plan = personalization_store.get_active_plan(user["id"])
    
    if not plan:
        st.warning("⚠️ No active training plan found. Build one in the **🗺️ Plan Builder** tab first.")
        return
        
    weeks_count = plan.get("total_weeks", 12)
    selected_week = st.slider("Select Plan Week", 1, weeks_count, 1)
    
    week_data = plan["weeks"][selected_week - 1]
    st.markdown(f"#### Week {selected_week} Schedule (Target: {week_data['target_volume_km']} km)")
    if week_data.get("is_deload"):
        st.info("🧘 **Deload Week:** Training volume is reduced by 25% for muscular/physiological adaptation and recovery.")
    elif week_data.get("is_taper"):
        st.success("⚡ **Taper Week:** Tapering volume to peak for race day while maintaining intensity.")
        
    for workout in week_data["schedule"]:
        w_id = workout["id"]
        w_day = workout["day"]
        w_type = workout["type"]
        w_dist = workout["distance_km"]
        w_dur = workout["duration_minutes"]
        w_pace = workout["target_pace"]
        w_desc = workout["description"]
        w_status = workout["status"]
        
        color_map = {
            "easy": "#2e86ff", 
            "tempo": "#8b5cf6", 
            "interval": "#ff2d55", 
            "recovery": "#ff8c00", 
            "long": "#3ddc84",
            "rest": "rgba(255,255,255,0.1)",
        }
        color = color_map.get(w_type, "#9aa0a6")
        
        status_text = "🟢 Completed" if w_status == "completed" else "🟡 Scheduled" if w_status == "scheduled" else "⚪ Rest Day"
        border_style = f"border-left: 4px solid {color};"
        
        st.markdown(
            f"<div class='ss-card' style='{border_style}'>"
            f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
            f"<span><b>{w_day}</b> — <span class='ss-pill' style='background:{color}; font-size:0.75rem;'>{w_type.upper()}</span></span>"
            f"<span style='font-size:0.85rem; font-weight:600;'>{status_text}</span>"
            f"</div>"
            f"<div style='margin-top: 5px; font-size: 0.95rem;'>"
            f"Pace Target: <b>{w_pace}</b> | Target Distance: <b>{w_dist} km</b> | Target Time: <b>{w_dur} mins</b>"
            f"<p style='margin-top: 4px; font-size: 0.85rem;' class='ss-muted'>{w_desc}</p>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True
        )
        
        if w_status == "scheduled" and w_type != "rest":
            with st.expander(f"📝 Log Completed Run for {w_day} (Week {selected_week})", expanded=False):
                with st.form(f"log_run_cal_{w_id}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        act_dist = st.number_input("Logged Distance (km)", 0.0, 100.0, w_dist)
                    with c2:
                        act_dur = st.number_input("Logged Duration (minutes)", 1, 600, w_dur)
                    feel = st.text_input("Run feel (e.g. strong, heavy legs, soreness)", key=f"feel_{w_id}")
                    notes = st.text_area("Notes", key=f"notes_{w_id}", height=60)
                    
                    if st.form_submit_button("Complete Workout"):
                        logged_run = {
                            "distance_km": act_dist,
                            "duration_minutes": act_dur,
                            "type": w_type,
                            "feel": feel,
                            "notes": notes,
                        }
                        personalization_store.complete_workout(
                            user_id=user["id"],
                            workout_id=w_id,
                            logged_run=logged_run,
                            thread_id=st.session_state.get("thread_id")
                        )
                        st.success(f"Logged! Week {selected_week} {w_day} marked completed.")
                        st.rerun()
                        
        elif w_status == "completed":
            logged = workout.get("logged_run", {})
            st.markdown(
                f"<div style='margin-left: 20px; font-size:0.85rem; background: rgba(61,220,132,0.05); padding: 5px 10px; border-radius: 8px; border: 1px dashed #3ddc84;'>"
                f"✅ <b>Logged Run:</b> {logged.get('distance_km')} km in {logged.get('duration_minutes')} mins | <b>Feel:</b> {logged.get('feel','?')} | <b>Notes:</b> {logged.get('notes','')}"
                f"</div>",
                unsafe_allow_html=True
            )
            st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)


# ----------------------------------------------------------- plan builder tab
def _render_plan_builder_tab(user, profile):
    st.markdown("### 🗺️ Running Plan Builder")
    st.caption("Generate a structured periodized training plan with custom goals, VDOT-based target paces, and build/recovery phases.")
    
    # Check current plan if exists
    plan = personalization_store.get_active_plan(user["id"])
    if plan:
        st.info(f"💡 You already have an active plan for **{plan.get('goal')}** ({plan.get('total_weeks')} weeks). Generating a new plan will replace it.")
        
    with st.form("plan_generator_form"):
        goal = st.selectbox("Select Goal", ["5K Prep", "10K Prep", "Half Marathon Prep", "Marathon Prep", "Base Building"])
        weeks = st.selectbox("Plan Duration (Weeks)", [8, 12, 16], index=1)
        days = st.slider("Run Frequency (Days/Week)", 3, 5, 3)
        
        # Pull 5k time from profile or set fallback
        default_5k = profile.get("recent_5k_time", 25.0) or 25.0
        five_k_input = st.number_input("Recent 5K Race Time (minutes)", 10.0, 60.0, float(default_5k), step=0.5, help="Used to calculate Jack Daniels VDOT score and pacing zones.")
        
        if st.form_submit_button("Generate & Activate Program", type="primary"):
            # Update temporary profile with form 5K time for calculation
            calc_profile = {**profile, "recent_5k_time": five_k_input}
            goal_key = goal.split()[0].lower() # E.g. 5k, 10k, half, marathon, base
            if "base" in goal_key:
                goal_key = "base"
                
            new_plan = generate_periodized_plan(calc_profile, goal_key, weeks=weeks, days_per_week=days)
            personalization_store.save_active_plan(user["id"], new_plan)
            st.success(f"🎉 New {weeks}-week {goal} plan activated! Paces computed successfully. Go to Calendar to view your schedule.")
            st.rerun()
