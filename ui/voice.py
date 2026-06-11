"""Browser-based voice input/output for the chat UI.

Input  : the browser captures microphone audio (via streamlit-mic-recorder)
         and it is transcribed to text. Degrades gracefully to text-only if
         the component or its backend is unavailable.
Output : the coach's reply is spoken aloud using the browser's built-in
         SpeechSynthesis API (pure client-side JavaScript, no extra deps).
         Multiple strong voice styles are available and each coach has a
         distinct default voice.
"""

import json
import streamlit as st
import streamlit.components.v1 as components

try:  # optional dependency — app must still run without it
    from streamlit_mic_recorder import speech_to_text as _speech_to_text
    _VOICE_INPUT_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    _speech_to_text = None
    _VOICE_INPUT_AVAILABLE = False


LANGUAGES = {
    "English (US)": "en-US",
    "English (UK)": "en-GB",
    "English (India)": "en-IN",
    "Hindi": "hi-IN",
    "Spanish": "es-ES",
    "French": "fr-FR",
    "German": "de-DE",
}

# Selectable voice styles. Each lists preferred browser-voice name fragments
# (tried in order) plus rate/pitch shaping for a strong, clear delivery.
VOICE_STYLES = {
    "Strong Male": {
        "prefer": ["Google US English", "Microsoft Guy", "Microsoft David", "Daniel", "Alex", "Mark", "Fred"],
        "rate": 1.0, "pitch": 0.95,
    },
    "Strong Female": {
        "prefer": ["Microsoft Aria", "Microsoft Jenny", "Google US English", "Samantha", "Microsoft Zira", "Victoria"],
        "rate": 1.0, "pitch": 1.05,
    },
    "Deep & Commanding": {
        "prefer": ["Microsoft David", "Microsoft Guy", "Daniel", "Alex", "Google UK English Male"],
        "rate": 0.92, "pitch": 0.8,
    },
    "Energetic": {
        "prefer": ["Google US English", "Microsoft Aria", "Microsoft Zira", "Samantha"],
        "rate": 1.12, "pitch": 1.15,
    },
    "Calm & Warm": {
        "prefer": ["Google UK English Female", "Microsoft Jenny", "Samantha", "Microsoft Aria"],
        "rate": 0.9, "pitch": 1.0,
    },
}

# Each coach's signature default voice style.
COACH_VOICE_DEFAULT = {
    "scientist": "Strong Male",
    "energizer": "Energetic",
    "warrior": "Deep & Commanding",
    "sage": "Calm & Warm",
}


def voice_input_available() -> bool:
    return _VOICE_INPUT_AVAILABLE


def default_voice_for(coach_style: str) -> str:
    return COACH_VOICE_DEFAULT.get(coach_style, "Strong Male")


def voice_input(key: str = "voice_input", language: str = "en-US"):
    """Render a mic button; return the transcribed text once, or None."""
    if not _VOICE_INPUT_AVAILABLE:
        return None
    try:
        return _speech_to_text(
            start_prompt="🎤 Speak",
            stop_prompt="⏹️ Stop",
            just_once=True,
            use_container_width=True,
            language=language,
            key=key,
        )
    except Exception:
        return None


def speak(text: str, nonce, style: str = "Strong Male", lang: str = "en-US") -> None:
    """Speak `text` aloud in the browser using the chosen voice style.

    `nonce` forces a re-render so a fresh reply is spoken exactly once. Voice
    selection happens client-side, robust to the async voice list and to
    voices unavailable on a given browser/OS.
    """
    if not text:
        return
    cfg = VOICE_STYLES.get(style, VOICE_STYLES["Strong Male"])
    payload = json.dumps(text)
    prefer = json.dumps(cfg["prefer"])
    components.html(
        f"""
        <script>
        (function() {{
            const NONCE = {json.dumps(str(nonce))};
            if (window.__lastSpokenNonce === NONCE) return;
            window.__lastSpokenNonce = NONCE;
            const synth = window.parent.speechSynthesis || window.speechSynthesis;
            if (!synth) return;
            const prefer = {prefer};
            const text = {payload};

            function pickVoice(voices) {{
                for (const frag of prefer) {{
                    const v = voices.find(x => x.name && x.name.toLowerCase().includes(frag.toLowerCase()));
                    if (v) return v;
                }}
                const en = voices.find(x => x.lang && x.lang.startsWith('en'));
                return en || voices[0] || null;
            }}

            function go() {{
                try {{
                    const voices = synth.getVoices() || [];
                    synth.cancel();
                    const u = new SpeechSynthesisUtterance(text);
                    u.rate = {cfg['rate']};
                    u.pitch = {cfg['pitch']};
                    u.lang = {json.dumps(lang)};
                    const v = pickVoice(voices);
                    if (v) u.voice = v;
                    synth.speak(u);
                }} catch (e) {{ /* TTS unsupported — ignore */ }}
            }}

            if ((synth.getVoices() || []).length === 0) {{
                synth.onvoiceschanged = go;
                setTimeout(go, 250);
            }} else {{
                go();
            }}
        }})();
        </script>
        """,
        height=0,
    )


def stop_speaking() -> None:
    components.html(
        """
        <script>
        try { (window.parent.speechSynthesis || window.speechSynthesis).cancel(); } catch (e) {}
        </script>
        """,
        height=0,
    )
