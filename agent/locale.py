"""Locale system for multilingual coaching responses.

Supports: English (en), Hindi (hi), Hinglish (hinglish)

The locale affects:
1. System prompt instruction (what language to reply in)
2. Fallback responses (pre-written in each language)
3. Disclaimer text
4. Persona voice adaptation (Hinglish has its own flavor)

Note: The corpus remains in English (knowledge is language-agnostic).
The LLM handles translation in its response generation.
"""

# Language detection (simple heuristic)
HINDI_CHARS = set("अआइईउऊएऐओऔकखगघचछजझटठडढणतथदधनपफबभमयरलवशषसह")
HINGLISH_MARKERS = [
    "karo", "karna", "hai", "nahi", "mein", "kya", "aaj", "kal",
    "bhai", "didi", "yaar", "bata", "chal", "tera", "mera",
    "kaisa", "kaise", "kyun", "abhi", "phir", "lekin",
    "achha", "theek", "sahi", "galat", "zyada", "kam",
    "shuru", "khatam", "dard", "thakaan", "bhago", "daudo",
]


def detect_locale(message: str) -> str:
    """Detect language from user message.

    Returns 'hi' for Hindi (Devanagari), 'hinglish' for Roman Hindi,
    'en' for English.
    """
    if not message:
        return "en"

    # Check for Devanagari characters
    if any(c in HINDI_CHARS for c in message):
        return "hi"

    # Check for Hinglish markers
    words = message.lower().split()
    hinglish_count = sum(1 for w in words if w in HINGLISH_MARKERS)
    if hinglish_count >= 2 or (hinglish_count >= 1 and len(words) <= 5):
        return "hinglish"

    return "en"


# Pre-written responses per locale (used in fallback mode)
FALLBACK_RESPONSES = {
    "en": {
        "daily_insight": "Focus on consistency today. If you ran yesterday, take it easy or rest. If you rested, aim for an easy 20-30 minute run.",
        "pre_run": "Warmup: 5 minutes walking, then 5 minutes easy jog. Stay hydrated. Run by feel today.",
        "post_run": "Great job getting out there! Hydrate, stretch gently, and get good sleep tonight.",
        "challenge": "This week's challenge: Run one session purely by feel - no watch, no pace targets. Just enjoy the movement.",
        "chat": "I'm having trouble connecting right now. Please try again in a moment. In the meantime, a 20-minute easy jog is always a good default!",
        "weekly_summary": "Keep showing up consistently. That's the most important thing at every level.",
        "proactive": "Remember: easy days should feel easy. If you're tired, rest is training too.",
        "injury_risk": "Listen to your body. Persistent pain (>3 days) that worsens with running = see a professional.",
        "plan": "A good plan has: 80% easy runs, 1-2 quality sessions/week, a weekly long run, and a rest day. Start there.",
        "budget_exhausted": "You've reached today's coaching limit. See you tomorrow! Keep running.",
    },
    "hinglish": {
        "daily_insight": "Aaj consistency pe focus karo. Kal run kiya tha? Toh aaj easy ya rest. Rest liya? Toh 20-30 min easy run karo.",
        "pre_run": "Warmup: 5 min walk, phir 5 min easy jog. Hydrated raho. Aaj feel se run karo.",
        "post_run": "Bahut badhiya! Ab hydrate karo, halka stretch, aur raat ko achi neend lo.",
        "challenge": "Is hafte ka challenge: Ek run bina watch ke karo. Na pace dekho, na distance. Bas enjoy karo.",
        "chat": "Abhi connection issue aa raha hai. Thodi der mein try karo. Tab tak agar aaj run nahi kiya, toh 20 min easy jog best option hai!",
        "weekly_summary": "Consistent raho. Wahi sabse important hai har level pe.",
        "proactive": "Yaad rakh: easy days SACH mein easy hone chahiye. Thaka hua hai? Rest bhi training hai.",
        "injury_risk": "Apne body ko suno. 3 din se zyada dard jo running se badhe = doctor ke paas jao.",
        "plan": "Acha plan: 80% easy runs, 1-2 quality sessions/week, weekly long run, aur ek rest day. Yahi se shuru karo.",
        "budget_exhausted": "Aaj ka AI budget khatam ho gaya hai boss. Kal phir baat karte hain!",
    },
    "hi": {
        "daily_insight": "आज निरंतरता पर ध्यान दें। कल दौड़े थे? तो आज आसान या आराम करें। आराम किया? तो 20-30 मिनट आसान दौड़ लगाएं।",
        "pre_run": "वार्मअप: 5 मिनट चलना, फिर 5 मिनट आसान जॉगिंग। हाइड्रेटेड रहें। आज अनुभव से दौड़ें।",
        "post_run": "बहुत बढ़िया! अब हाइड्रेट करें, हल्का स्ट्रेच, और रात को अच्छी नींद लें।",
        "challenge": "इस हफ्ते की चुनौती: एक रन बिना घड़ी के करें। बस दौड़ने का आनंद लें।",
        "chat": "अभी कनेक्शन में समस्या आ रही है। कुछ देर बाद कोशिश करें।",
        "weekly_summary": "निरंतर रहें। हर स्तर पर यही सबसे महत्वपूर्ण है।",
        "proactive": "याद रखें: आसान दिन सच में आसान होने चाहिए। थके हैं? आराम भी प्रशिक्षण है।",
        "budget_exhausted": "आज की AI कोचिंग सीमा पूरी हो गई है। कल मिलते हैं!",
    },
}

# Disclaimers per locale
DISCLAIMERS = {
    "en": "Note: This is AI coaching guidance, not medical advice. Consult a healthcare professional for medical concerns.",
    "hinglish": "Note: Yeh AI coaching guidance hai, medical advice nahi. Medical concerns ke liye doctor se milein.",
    "hi": "नोट: यह AI कोचिंग मार्गदर्शन है, चिकित्सा सलाह नहीं। चिकित्सा संबंधी चिंताओं के लिए डॉक्टर से मिलें।",
}


def get_fallback(feature: str, locale: str) -> str:
    """Get fallback response for a feature in the given locale."""
    lang_responses = FALLBACK_RESPONSES.get(locale, FALLBACK_RESPONSES["en"])
    return lang_responses.get(feature, lang_responses.get("chat", "Please try again."))


def get_disclaimer(locale: str) -> str:
    """Get the medical disclaimer in the given locale."""
    return DISCLAIMERS.get(locale, DISCLAIMERS["en"])


def get_locale_instruction(locale: str) -> str:
    """Get the system prompt instruction for language."""
    if locale == "hi":
        return "\n\nREPLY IN HINDI (Devanagari script). Keep technical running terms in English (pace, tempo, interval, VO2max)."
    elif locale == "hinglish":
        return "\n\nREPLY IN HINGLISH (Roman Hindi mixed with English). Be natural and conversational like texting a friend. Example: 'Bhai, aaj ka run kaisa tha? Teri pace thodi fast thi easy day ke liye.'"
    return ""


# Persona voice modifiers per locale
PERSONA_LOCALE_HINTS = {
    "energizer": {
        "en": "",
        "hinglish": " Use 'bhai/didi', 'mast', 'zabardast', 'chal let's go!', 'tu champion hai!'",
        "hi": "",
    },
    "warrior": {
        "en": "",
        "hinglish": " Use 'kaam kar', 'koi excuse nahi', 'tera time aayega', 'mehnat kar'",
        "hi": "",
    },
    "sage": {
        "en": "",
        "hinglish": " Use 'dheeraj rakh', 'waqt lagega', 'safar lambi hai', 'sabr ka phal meetha hota hai'",
        "hi": "",
    },
    "scientist": {
        "en": "",
        "hinglish": " Use technical terms in English but explain in Hinglish: 'Tera ACWR 1.2 hai — matlab safe zone mein hai tu'",
        "hi": "",
    },
}


def get_persona_locale_hint(persona: str, locale: str) -> str:
    """Get persona-specific language hints for the locale."""
    return PERSONA_LOCALE_HINTS.get(persona, {}).get(locale, "")
