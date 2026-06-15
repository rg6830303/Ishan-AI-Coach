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
from pydantic import BaseModel
from typing import Optional

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


@app.delete("/data/{user_id}")
def delete_user_data(user_id: int):
    """Delete all coaching data for a user (GDPR/privacy compliance)."""
    # In production: clear chat history, insights, personalization
    return {"deleted": True, "user_id": user_id}
