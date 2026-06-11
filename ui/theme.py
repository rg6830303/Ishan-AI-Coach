"""Shared visual theme: coach/tier metadata and global CSS injection."""

import streamlit as st

# Per-persona visual identity.
COACH_META = {
    "scientist": {
        "name": "The Scientist",
        "icon": "🔬",
        "color": "#00A8E8",
        "tagline": "Data-driven precision",
        "blurb": "Logical, evidence-led, optimizes everything with numbers.",
    },
    "energizer": {
        "name": "The Energizer",
        "icon": "⚡",
        "color": "#FF7A00",
        "tagline": "High-energy fun",
        "blurb": "Warm, playful, makes every run feel like an adventure.",
    },
    "warrior": {
        "name": "The Warrior",
        "icon": "🔥",
        "color": "#E63946",
        "tagline": "No-excuses discipline",
        "blurb": "Direct, commanding, forges mental toughness through work.",
    },
    "sage": {
        "name": "The Sage",
        "icon": "🧘",
        "color": "#7B2CBF",
        "tagline": "Patient wisdom",
        "blurb": "Calm, reflective, trusts the process and the long game.",
    },
}

# Per-tier visual identity.
TIER_META = {
    "spark": {"icon": "🌱", "color": "#FF8C00", "label": "Beginner"},
    "pace": {"icon": "🏃", "color": "#2E86FF", "label": "Intermediate"},
    "tempo": {"icon": "🚀", "color": "#8B5CF6", "label": "Advanced"},
    "apex": {"icon": "🏆", "color": "#FF2D55", "label": "Elite"},
}


def coach_meta(style: str) -> dict:
    return COACH_META.get(style, COACH_META["energizer"])


def tier_meta(tier: str) -> dict:
    return TIER_META.get(tier, TIER_META["pace"])


def inject_global_css() -> None:
    st.markdown(
        """
        <style>
        /* ---- Layout polish ---- */
        .block-container { padding-top: 2.2rem; max-width: 1100px; }
        h1, h2, h3 { letter-spacing: -0.01em; }

        /* ---- Brand header ---- */
        .ss-brand {
            display:flex; align-items:center; gap:.6rem;
            font-weight:800; font-size:1.6rem;
            background:linear-gradient(90deg,#FF7A00,#FF2D55,#8B5CF6);
            -webkit-background-clip:text; background-clip:text; color:transparent;
        }

        /* ---- Cards ---- */
        .ss-card {
            border-radius:16px; padding:1.1rem 1.3rem; margin:.5rem 0;
            border:1px solid rgba(255,255,255,.08);
            background:rgba(255,255,255,.03);
        }
        .ss-pill {
            display:inline-block; padding:4px 12px; border-radius:999px;
            font-weight:700; font-size:.8rem; color:#fff;
        }
        .ss-chip {
            display:inline-block; padding:3px 10px; margin:2px;
            border-radius:999px; font-size:.78rem;
            background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.12);
        }
        .ss-muted { color:#9aa0a6; font-size:.85rem; }

        /* ---- Coach hero ---- */
        .ss-hero {
            border-radius:20px; padding:1.4rem 1.6rem; margin-bottom:1rem;
            color:#fff;
        }
        .ss-hero h2 { margin:0; color:#fff; }
        .ss-hero p { margin:.2rem 0 0 0; opacity:.92; }

        /* ---- Chat bubbles ---- */
        [data-testid="stChatMessage"] { border-radius:16px; }

        /* ---- Buttons ---- */
        .stButton > button { border-radius:10px; font-weight:600; }

        /* ---- Metric cards ---- */
        [data-testid="stMetric"] {
            background:rgba(255,255,255,.03);
            border:1px solid rgba(255,255,255,.08);
            border-radius:14px; padding:.6rem .8rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def coach_hero(style: str, tier: str, tier_name: str) -> None:
    """A gradient hero banner introducing the active coach."""
    cm = coach_meta(style)
    tm = tier_meta(tier)
    st.markdown(
        f"""
        <div class="ss-hero" style="background:linear-gradient(135deg,{cm['color']},{tm['color']});">
            <h2>{cm['icon']} {cm['name']}</h2>
            <p>{cm['tagline']} · {tm['icon']} {tier_name} ({tm['label']}) tier</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
