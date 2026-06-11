"""Browser-based voice input/output for the chat UI.

Input  : the browser captures microphone audio (via streamlit-mic-recorder)
         and it is transcribed to text. Degrades gracefully to text-only if
         the component or its backend is unavailable.
Output : the coach's reply is spoken aloud using the browser's built-in
         SpeechSynthesis API (pure client-side JavaScript, no extra deps).
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


def voice_input_available() -> bool:
    return _VOICE_INPUT_AVAILABLE


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
        # Network/transcription failure — fall back silently to text input.
        return None


def speak(text: str, nonce, rate: float = 1.0, pitch: float = 1.0) -> None:
    """Speak `text` aloud in the browser. `nonce` forces a re-render so a
    fresh reply is spoken exactly once."""
    if not text:
        return
    payload = json.dumps(text)
    components.html(
        f"""
        <script>
        (function() {{
            const NONCE = {json.dumps(str(nonce))};
            if (window.__lastSpokenNonce === NONCE) return;
            window.__lastSpokenNonce = NONCE;
            try {{
                const synth = window.parent.speechSynthesis || window.speechSynthesis;
                synth.cancel();
                const u = new SpeechSynthesisUtterance({payload});
                u.rate = {rate};
                u.pitch = {pitch};
                u.lang = 'en-US';
                synth.speak(u);
            }} catch (e) {{ /* TTS unsupported — ignore */ }}
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
