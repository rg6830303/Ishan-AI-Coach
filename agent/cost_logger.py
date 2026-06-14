"""Usage and cost tracking for AI coach.

Tracks per-user, per-feature token usage and estimated cost against
the 1/3-of-plan-price budget ceiling.

Budget ceilings (INR):
  Base plan (Rs 9/mo): AI budget = Rs 3/mo ~ $0.036/mo
  Pro plan (Rs 99/mo): AI budget = Rs 33/mo ~ $0.40/mo
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path

from config import DATA_DIR


LOGS_DIR = os.path.join(DATA_DIR, "usage_logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Budget ceilings in USD per month
BUDGET_CEILINGS_USD = {
    "free": 0.0,
    "base": 0.036,
    "pro": 0.40,
}

# Daily interaction caps (hard limits)
DAILY_CAPS = {
    "free": 2,
    "base": 5,
    "pro": 30,
}


@dataclass
class UsageEntry:
    timestamp: str
    user_id: int
    feature: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    estimated_cost_usd: float
    tools_used: list[str] = field(default_factory=list)
    cached: bool = False


@dataclass
class UserBudget:
    user_id: int
    plan: str
    month: str
    total_cost_usd: float = 0.0
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    daily_calls: int = 0
    last_call_date: str = ""

    @property
    def ceiling_usd(self) -> float:
        return BUDGET_CEILINGS_USD.get(self.plan, 0.0)

    @property
    def remaining_usd(self) -> float:
        return max(0, self.ceiling_usd - self.total_cost_usd)

    @property
    def budget_percent_used(self) -> float:
        if self.ceiling_usd <= 0:
            return 100.0
        return round((self.total_cost_usd / self.ceiling_usd) * 100, 1)

    @property
    def daily_cap(self) -> int:
        return DAILY_CAPS.get(self.plan, 2)

    @property
    def daily_calls_remaining(self) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        if self.last_call_date != today:
            return self.daily_cap
        return max(0, self.daily_cap - self.daily_calls)

    def can_make_call(self) -> bool:
        """Check if user can make another AI call."""
        if self.remaining_usd <= 0:
            return False
        if self.daily_calls_remaining <= 0:
            return False
        return True

    def budget_allows_model(self, model: str, estimated_tokens: int = 500) -> bool:
        """Check if budget allows a call to this model."""
        from agent.providers import estimate_cost
        est = estimate_cost(model, estimated_tokens, estimated_tokens)
        return est <= self.remaining_usd


class CostLogger:
    """Tracks usage per user and enforces budget ceilings."""

    def __init__(self):
        self._budgets: dict[int, UserBudget] = {}

    def _budget_path(self, user_id: int) -> str:
        return os.path.join(LOGS_DIR, f"user_{user_id}_budget.json")

    def _log_path(self, user_id: int) -> str:
        month = datetime.now().strftime("%Y-%m")
        return os.path.join(LOGS_DIR, f"user_{user_id}_{month}.jsonl")

    def get_budget(self, user_id: int, plan: str = "base") -> UserBudget:
        """Get or create user budget for current month."""
        current_month = datetime.now().strftime("%Y-%m")

        if user_id in self._budgets:
            budget = self._budgets[user_id]
            if budget.month == current_month:
                return budget

        # Try load from disk
        path = self._budget_path(user_id)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                budget = UserBudget(**data)
                if budget.month == current_month:
                    self._budgets[user_id] = budget
                    return budget
            except Exception:
                pass

        # New month or new user
        budget = UserBudget(user_id=user_id, plan=plan, month=current_month)
        self._budgets[user_id] = budget
        return budget

    def log_usage(self, entry: UsageEntry) -> None:
        """Log a usage entry and update budget."""
        # Write to JSONL log
        path = self._log_path(entry.user_id)
        with open(path, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

        # Update budget
        budget = self.get_budget(entry.user_id)
        budget.total_cost_usd += entry.estimated_cost_usd
        budget.total_calls += 1
        budget.total_input_tokens += entry.input_tokens
        budget.total_output_tokens += entry.output_tokens

        today = datetime.now().strftime("%Y-%m-%d")
        if budget.last_call_date != today:
            budget.daily_calls = 1
            budget.last_call_date = today
        else:
            budget.daily_calls += 1

        # Persist
        with open(self._budget_path(entry.user_id), "w") as f:
            json.dump(asdict(budget), f, indent=2)

    def check_budget(self, user_id: int, plan: str = "base") -> dict:
        """Return budget status for debug panel."""
        budget = self.get_budget(user_id, plan)
        return {
            "plan": budget.plan,
            "month": budget.month,
            "spent_usd": round(budget.total_cost_usd, 6),
            "ceiling_usd": budget.ceiling_usd,
            "remaining_usd": round(budget.remaining_usd, 6),
            "percent_used": budget.budget_percent_used,
            "total_calls": budget.total_calls,
            "daily_calls_today": budget.daily_calls,
            "daily_cap": budget.daily_cap,
            "daily_remaining": budget.daily_calls_remaining,
            "can_call": budget.can_make_call(),
        }


# Singleton
cost_logger = CostLogger()
