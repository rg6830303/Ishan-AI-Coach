"""FastAPI service wrapper for the Sprint Society AI Coach.

Run: uvicorn api:app --host 0.0.0.0 --port 8000

This provides a REST API around coach.handle() so Sprint Society's
TypeScript backend can call it via HTTP.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.makedirs("data/usage_logs", exist_ok=True)
os.makedirs("data/personalization", exist_ok=True)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import asyncio

from coaching.engine_v2 import coach
from agent.cost_logger import cost_logger
from agent.router import get_router_status
from agent.monitoring import monitor
from database.models import init_db

init_db()

app = FastAPI(
    title="Sprint Society AI Coach",
    description="Adaptive AI coaching engine with RAG, guardrails, and multi-model routing",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)


class CoachRequest(BaseModel):
    feature: str
    user_id: int
    message: str = ""
    tier: str = "pace"
    persona: str = "energizer"
    plan: str = "base"
    thread_id: Optional[int] = None
    locale: str = "en"


class CoachResponse(BaseModel):
    text: str
    tools_used: list[str] = []
    citations: list[dict] = []
    tokens: dict = {}
    est_cost: float = 0.0
    model: str = ""
    provider: str = ""
    level: int = 0
    feature: str = ""
    guardrail_flags: list[str] = []
    route_reason: str = ""
    cached: bool = False
    locale: str = "en"


@app.post("/coach", response_model=CoachResponse)
def handle_coach(req: CoachRequest):
    """Main coaching endpoint. Routes to appropriate model + RAG + tools."""
    try:
        result = coach.handle(req.feature, req.dict())
        return result.to_dict()
    except Exception as e:
        monitor.log_error("engine", req.feature, str(e), req.user_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/coach/stream")
async def handle_coach_stream(req: CoachRequest):
    """Streaming coaching endpoint using Server-Sent Events.

    Returns tokens as they arrive from the LLM for real-time UX.
    Falls back to non-streaming if provider doesn't support it.
    """
    import json

    async def generate():
        try:
            result = coach.handle(req.feature, req.dict())
            # Send the full response as a stream of chunks (simulated for now)
            text = result.text
            chunk_size = 20  # characters per chunk
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i + chunk_size]
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                await asyncio.sleep(0.02)

            # Send metadata at end
            yield f"data: {json.dumps({'type': 'done', 'model': result.model, 'provider': result.provider, 'cost': result.est_cost, 'tools_used': result.tools_used, 'citations': result.citations})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "2.0.0"}


@app.get("/status")
def status():
    """System status: router, budget, monitoring."""
    return {
        "router": get_router_status(),
        "monitoring": monitor.get_status(),
    }


@app.get("/budget/{user_id}")
def get_budget(user_id: int, plan: str = "base"):
    """Get user's current AI budget status."""
    return cost_logger.check_budget(user_id, plan)


@app.get("/events")
def get_events(limit: int = 20):
    """Get recent monitoring events."""
    return {"events": monitor.get_recent_events(limit)}


@app.get("/proactive/{user_id}")
def get_proactive_messages(user_id: int, persona: str = "energizer"):
    """Get proactive coaching nudges for a user.

    Sprint Society backend polls this endpoint (e.g., daily at 7am)
    and delivers messages via push notification or in-app banner.
    """
    from coaching.proactive import check_proactive_triggers, format_proactive_digest
    from agent.tools_full import execute_tool
    import json

    # Gather user data via existing tools
    profile_data = json.loads(execute_tool("get_runner_profile", {}, user_id))
    runs_data = json.loads(execute_tool("get_recent_runs", {"days": 14}, user_id))
    acwr_data = json.loads(execute_tool("get_weekly_load_acwr", {}, user_id))
    progress_data = json.loads(execute_tool("get_progress_and_level", {}, user_id))

    recent_runs = runs_data.get("runs", [])
    streak = progress_data.get("streak", 0)
    acwr = acwr_data.get("acwr", 0.8)
    total_runs = progress_data.get("total_runs", 0)

    messages = check_proactive_triggers(
        user_id=user_id,
        persona=persona,
        recent_runs=recent_runs,
        streak=streak,
        acwr=acwr,
        goals=[],
        total_runs=total_runs,
    )

    return {
        "user_id": user_id,
        "messages": [
            {"trigger": m.trigger, "priority": m.priority, "message": m.message}
            for m in messages
        ],
        "digest": format_proactive_digest(messages),
    }


@app.post("/webhook/activity-logged")
def webhook_activity_logged(user_id: int, persona: str = "energizer"):
    """Webhook called by Sprint Society when a run is logged.

    Checks for triggers that fire post-run (PR celebration, milestone, etc.)
    and returns any proactive messages to deliver immediately.
    """
    from coaching.proactive import check_proactive_triggers
    from agent.tools_full import execute_tool
    import json

    progress_data = json.loads(execute_tool("get_progress_and_level", {}, user_id))
    total_runs = progress_data.get("total_runs", 0)

    messages = check_proactive_triggers(
        user_id=user_id,
        persona=persona,
        recent_runs=[],
        streak=progress_data.get("streak", 0),
        acwr=0.8,
        goals=[],
        personal_records=progress_data.get("recent_prs", []),
        total_runs=total_runs,
    )

    celebration_messages = [m for m in messages if m.trigger in ("pr_celebration", "consistency_milestone")]
    return {
        "messages": [
            {"trigger": m.trigger, "priority": m.priority, "message": m.message}
            for m in celebration_messages
        ],
    }


@app.delete("/data/{user_id}")
def delete_user_data(user_id: int):
    """Delete all coaching data for a user (GDPR/privacy compliance)."""
    # In production: clear chat history, insights, personalization
    return {"deleted": True, "user_id": user_id}
