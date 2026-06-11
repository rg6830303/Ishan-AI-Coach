# 🏃 Sprint Society — AI Running Coach

An **agentic RAG** running coach built with Streamlit and the **Groq API**. It ships
**4 distinct coach personalities** and adapts to **4 runner tiers**, learns about you
continuously from every message, and remembers it all in local JSON/JSONL files.

> Four personalities × four levels × continuous personalization.

---

## ✨ Features

### Four AI coaches (personalities)
| Coach | Style | Voice |
|-------|-------|-------|
| 🔬 **The Scientist** | Data-driven precision | Leads with numbers, physiology, evidence |
| ⚡ **The Energizer** | High-energy fun | Celebrates everything, playful, warm |
| 🔥 **The Warrior** | No-excuses discipline | Direct, accountable, mental toughness |
| 🧘 **The Sage** | Patient wisdom | Calm, reflective, trusts the process |

### Four runner tiers (auto-classified from your profile)
🌱 **Spark** (Beginner) · 🏃 **Pace** (Intermediate) · 🚀 **Tempo** (Advanced) · 🏆 **Apex** (Elite)

Each tier has its own safety guardrails, volume/intensity limits, coaching depth, and
chooses a Groq model sized to the complexity (8B for Spark/Pace, 70B for Tempo/Apex).

### Per-coach knowledge brains + 10-level training cycles
Every coach has its **own complete knowledge brain** (`knowledge/corpus/coach_*.md`)
covering its full methodology, motivation style, and how it handles every performance
level — and its **own unique 10-level training cycle**:

| Coach | Cycle | Levels 1 → 10 |
|-------|-------|---------------|
| 🔬 Scientist | **The Lab Protocol** | Baseline Diagnostics → Performance Mastery |
| ⚡ Energizer | **The Adventure Ladder** | First Steps → Unstoppable |
| 🔥 Warrior | **The Forge** | Recruit → Champion |
| 🧘 Sage | **The Path** | Seed → Mountain |

The coach places you at a level, names it, frames every session as a step toward the next
one, and **levels you up** (via the `set_training_level` tool) when you meet the criteria.
Your level, history, and progress are shown in the **🎯 Training Cycle** tab.

### Chat threads (saved & loaded)
Keep multiple named conversations. Create, switch, rename, and delete threads from the
sidebar — each is stored in SQLite and reloads exactly where you left off.

### Agentic RAG on Groq
The coach runs a tool-calling loop with four tools:
- `calculate_pace_zones` — VO2max & pace zones from your 5K time or profile
- `retrieve_knowledge` — hybrid (FAISS dense + BM25 sparse) search over the coaching corpus
- `check_guardrails` — validates recommendations against tier-specific safety rules
- `log_training_run` — records runs you mention straight into your training log

### Continuous personalization (the coaches update themselves)
Every message is analyzed for goals, injuries, preferences, mood, topics, and mileage.
These signals are merged into an evolving model that is injected into the coach's prompt
**on the same turn**, so it reacts immediately and remembers next time. Everything is
stored locally and visible in the UI:

```
data/personalization/<user_id>/
├── profile.json          # snapshot of your structured profile
├── personalization.json  # evolving model the coach reads every turn
├── events.jsonl          # append-only log of every interaction
└── training_log.jsonl    # every run you (or the coach) logs
```

### Voice (browser-based, optional)
- 🎤 **Speak** your message — captured in the browser and transcribed to text.
- 🔊 **Read replies aloud** — the coach's answer is spoken with the browser's
  built-in speech synthesis. **Multiple strong voice styles** (Strong Male, Strong
  Female, Deep & Commanding, Energetic, Calm & Warm), and each coach has a signature
  default voice. A 🔈 Test / ⏹️ Stop control lets you preview.
Both degrade gracefully to text-only if unavailable.

### Knowledge base
Markdown corpus under `knowledge/corpus/`, covering general running science plus dedicated
files for **psychology**, coaching **mentality**, **tactics/tips**, **planning**, and
**tier-specific** mentality/psychology/tactics/planning for all four runner types.

---

## 🚀 Run it locally

### 1. Prerequisites
- Python 3.10+
- A free **Groq API key** → https://console.groq.com/keys

### 2. Install
```bash
pip install -r requirements.txt
```

### 3. Add your Groq key
Create a `.env` file in the project root:
```
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL_SMALL=llama-3.1-8b-instant
GROQ_MODEL_LARGE=llama-3.3-70b-versatile
```
> The app also tolerates a loosely-formatted `.env.txt` for convenience, but a proper
> `.env` (or Streamlit secrets) is recommended.

### 4. (Optional) Build the dense vector index
The app works out-of-the-box using BM25. For higher-quality semantic retrieval, build the
FAISS index once (requires `sentence-transformers`, included in requirements):
```bash
python scripts/build_index.py
```
If the index isn't present, retrieval automatically falls back to BM25.

### 5. Launch
```bash
streamlit run app.py
```
Open http://localhost:8501, sign up, complete the 8-step profiling wizard, and start chatting.

---

## ☁️ Deploy to Streamlit Community Cloud

1. Push this repo to GitHub (public or private).
2. Go to https://share.streamlit.io → **New app** → pick this repo, branch `main`, file `app.py`.
3. In **Advanced settings → Secrets**, add:
   ```toml
   GROQ_API_KEY = "gsk_your_key_here"
   GROQ_MODEL_SMALL = "llama-3.1-8b-instant"
   GROQ_MODEL_LARGE = "llama-3.3-70b-versatile"
   ```
4. Deploy. 🎉

**Notes for cloud:**
- Never commit your real key — `.env` and `.env.txt` are git-ignored; use Streamlit secrets.
  `config.py` reads the key from environment **or** Streamlit secrets automatically.
- Accounts, profiles, **chats and chat threads** (SQLite) and the personalization JSON/JSONL
  all save and reload correctly while the app is running — log out, come back, switch threads,
  and everything is there. Note the disk is **ephemeral on redeploy/reboot**: for permanent
  durability across redeploys, point `DB_PATH`/`DATA_DIR` at a mounted volume or external DB.
- Browser mic access requires HTTPS — Streamlit Cloud serves over HTTPS, so voice input works.

### Keeping the app awake (no sleeping from inactivity)
Community Cloud sleeps apps with no traffic. This repo ships a GitHub Actions
workflow (`.github/workflows/keep-alive.yml`) that pings the app every 10 minutes
to keep it awake. To use it:
1. Set a repo **variable** `APP_URL` to your deployed URL: **Repo → Settings →
   Secrets and variables → Actions → Variables → New variable** →
   `APP_URL = https://your-app.streamlit.app` (or just edit the default in the workflow).
2. Enable Actions if prompted, then it runs automatically (or trigger it once from the
   **Actions** tab → *Keep Streamlit app awake* → *Run workflow*).

> GitHub's scheduled workflows can be delayed a few minutes and are auto-disabled after
> ~60 days with no repo commits. For rock-solid uptime, also point a free uptime monitor
> (e.g. **UptimeRobot** or **cron-job.org**) at the same URL on a 5-minute interval.

---

## 🗂️ Project structure
```
app.py                  # entry point + routing
config.py               # env/key loading, tiers, models, paths
agent/                  # agentic loop, tools, personas, system prompts
coaching/               # per-coach 10-level training cycles + progression logic
engine/                 # classifier, guardrails, pace calculator, VO2max
knowledge/              # corpus (markdown incl. per-coach brains), chunking, retriever
personalization/        # JSON/JSONL store + signal extractor (continuous learning)
database/               # SQLite models, auth, threads, conversation/insight memory
ui/                     # theme, auth, profiling wizard, chat + dashboards, voice
scripts/build_index.py  # one-off FAISS index builder
```

---

## ⚠️ Disclaimer
This is an educational coaching assistant, not medical advice. Always stop for sharp or
worsening pain and consult a professional for injuries or health concerns.
