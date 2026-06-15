"""Monitoring and alerting for the AI coach system.

Tracks:
- Errors per provider (with timestamps)
- Cost per user per feature
- Refusals/guardrail blocks
- Latency per feature
- Token usage patterns

Alerts on:
- Cost spike (single user using >50% of monthly budget in one day)
- Error spike (>5 errors in 10 minutes from same provider)
- Guardrail block spike (>10 blocks in 1 hour — possible abuse or bug)
"""

import json
import os
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from collections import defaultdict

from config import DATA_DIR

MONITOR_DIR = os.path.join(DATA_DIR, "monitoring")
os.makedirs(MONITOR_DIR, exist_ok=True)


@dataclass
class MonitorEvent:
    timestamp: str
    event_type: str  # "error", "guardrail_block", "cost_spike", "latency_high"
    provider: str = ""
    user_id: int = 0
    feature: str = ""
    details: str = ""
    severity: str = "info"  # "info", "warning", "critical"


class Monitor:
    """System monitor with alerting."""

    def __init__(self):
        self._events: list[MonitorEvent] = []
        self._error_counts: dict[str, list[float]] = defaultdict(list)  # provider -> [timestamps]
        self._block_timestamps: list[float] = []
        self._daily_user_costs: dict[int, float] = defaultdict(float)

    def log_error(self, provider: str, feature: str, error: str, user_id: int = 0):
        """Log an LLM provider error."""
        now = time.time()
        self._error_counts[provider].append(now)

        # Clean old entries (keep last 10 min)
        self._error_counts[provider] = [t for t in self._error_counts[provider] if now - t < 600]

        event = MonitorEvent(
            timestamp=datetime.now().isoformat(),
            event_type="error",
            provider=provider,
            user_id=user_id,
            feature=feature,
            details=error[:200],
            severity="warning" if len(self._error_counts[provider]) < 5 else "critical",
        )
        self._events.append(event)
        self._persist_event(event)

        # Alert if spike
        if len(self._error_counts[provider]) >= 5:
            self._alert(f"ERROR SPIKE: {provider} has {len(self._error_counts[provider])} errors in 10min")

    def log_guardrail_block(self, category: str, user_id: int, feature: str, message_preview: str):
        """Log a guardrail block."""
        now = time.time()
        self._block_timestamps.append(now)
        self._block_timestamps = [t for t in self._block_timestamps if now - t < 3600]

        event = MonitorEvent(
            timestamp=datetime.now().isoformat(),
            event_type="guardrail_block",
            user_id=user_id,
            feature=feature,
            details=f"[{category}] {message_preview[:100]}",
            severity="info" if len(self._block_timestamps) < 10 else "warning",
        )
        self._events.append(event)
        self._persist_event(event)

        if len(self._block_timestamps) >= 10:
            self._alert(f"BLOCK SPIKE: {len(self._block_timestamps)} guardrail blocks in 1 hour")

    def log_cost(self, user_id: int, cost_usd: float, feature: str, plan: str):
        """Log a cost event and check for spikes."""
        from agent.cost_logger import BUDGET_CEILINGS_USD

        self._daily_user_costs[user_id] += cost_usd
        ceiling = BUDGET_CEILINGS_USD.get(plan, 0.036)

        # Alert if user burns >50% of monthly budget in one day
        if self._daily_user_costs[user_id] > ceiling * 0.5:
            event = MonitorEvent(
                timestamp=datetime.now().isoformat(),
                event_type="cost_spike",
                user_id=user_id,
                feature=feature,
                details=f"User {user_id} spent ${self._daily_user_costs[user_id]:.4f} today (>{ceiling*0.5:.4f} threshold)",
                severity="warning",
            )
            self._events.append(event)
            self._persist_event(event)
            self._alert(f"COST SPIKE: User {user_id} at {self._daily_user_costs[user_id]/ceiling*100:.0f}% of monthly budget in one day")

    def log_latency(self, feature: str, latency_ms: int, provider: str):
        """Log high latency."""
        if latency_ms > 5000:  # >5s is concerning
            event = MonitorEvent(
                timestamp=datetime.now().isoformat(),
                event_type="latency_high",
                provider=provider,
                feature=feature,
                details=f"{latency_ms}ms",
                severity="warning" if latency_ms > 10000 else "info",
            )
            self._events.append(event)
            self._persist_event(event)

    def log_refusal(self, feature: str, user_id: int, reason: str):
        """Log when the system refuses to answer (scope violation)."""
        event = MonitorEvent(
            timestamp=datetime.now().isoformat(),
            event_type="refusal",
            user_id=user_id,
            feature=feature,
            details=reason[:200],
            severity="info",
        )
        self._events.append(event)
        self._persist_event(event)

    def get_status(self) -> dict:
        """Get current monitoring status."""
        now = time.time()
        recent_errors = {
            provider: len([t for t in timestamps if now - t < 600])
            for provider, timestamps in self._error_counts.items()
        }
        return {
            "total_events": len(self._events),
            "recent_errors_10min": recent_errors,
            "blocks_last_hour": len([t for t in self._block_timestamps if now - t < 3600]),
            "daily_top_spenders": dict(sorted(self._daily_user_costs.items(), key=lambda x: -x[1])[:5]),
            "alerts_active": self._check_active_alerts(),
        }

    def get_recent_events(self, limit: int = 20) -> list[dict]:
        """Get most recent events."""
        return [asdict(e) for e in self._events[-limit:]]

    def _check_active_alerts(self) -> list[str]:
        """Check for any active alert conditions."""
        alerts = []
        now = time.time()
        for provider, timestamps in self._error_counts.items():
            recent = len([t for t in timestamps if now - t < 600])
            if recent >= 5:
                alerts.append(f"{provider}: {recent} errors in 10min")
        if len([t for t in self._block_timestamps if now - t < 3600]) >= 10:
            alerts.append(f"High guardrail block rate")
        return alerts

    def _alert(self, message: str):
        """Trigger an alert (in production: webhook/email/push)."""
        print(f"[ALERT] {datetime.now().isoformat()} — {message}")
        # In production: send to Slack/email/push notification
        alert_path = os.path.join(MONITOR_DIR, "alerts.jsonl")
        with open(alert_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"time": datetime.now().isoformat(), "message": message}) + "\n")

    def _persist_event(self, event: MonitorEvent):
        """Write event to disk for persistence."""
        log_path = os.path.join(MONITOR_DIR, f"events_{datetime.now().strftime('%Y-%m-%d')}.jsonl")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event)) + "\n")

    def reset_daily(self):
        """Reset daily counters (call at midnight)."""
        self._daily_user_costs.clear()


# Singleton
monitor = Monitor()
