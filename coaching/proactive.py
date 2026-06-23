"""Proactive coaching triggers — the coach initiates, not the runner.

Detects situations that warrant a coach reaching out:
- Missed planned runs (inactivity)
- Streak at risk
- Volume spike (ACWR > 1.3)
- Recent PR (celebration)
- Goal deadline approaching
- Consistency milestone
- Overtraining signals

Each trigger produces a persona-appropriate message.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass
class ProactiveMessage:
    trigger: str
    priority: str  # "high", "medium", "low"
    message: str
    persona: str
    data: dict


# Persona-specific nudge templates
INACTIVITY_MESSAGES = {
    "scientist": "Your training consistency has dropped. {days} days since your last run. "
                 "Research shows breaks >5 days begin aerobic detraining. "
                 "A 20-minute easy run today preserves your adaptations.",
    "energizer": "Hey! It's been {days} days — your running shoes miss you! "
                 "Even 10 minutes counts. Get out there and remember why you started!",
    "warrior": "You committed to a plan. It's been {days} days. "
               "No excuses. Lace up. Even 15 minutes. Show up.",
    "sage": "It's been {days} days. That's okay — life has seasons. "
            "When you're ready, start with a walk. The miles will come back.",
}

STREAK_RISK_MESSAGES = {
    "scientist": "Your {streak}-day streak ends today if you don't log a run. "
                 "Even a 1km shakeout maintains the consistency metric.",
    "energizer": "Your {streak}-day streak is on the line! "
                 "A quick 10-minute jog keeps the magic alive. You've got this!",
    "warrior": "Streak: {streak} days. Don't break the chain. "
               "Get it done. Even 1km. Discipline is showing up on hard days.",
    "sage": "You have a {streak}-day streak. Beautiful consistency. "
            "If your body says rest today, that's wisdom too. The streak serves you, not the other way around.",
}

VOLUME_SPIKE_MESSAGES = {
    "scientist": "Alert: your ACWR is {acwr:.2f} (above 1.3 threshold). "
                 "Injury risk increases 2-4x at this ratio. "
                 "Recommendation: reduce this week's volume by 20% and prioritize easy running.",
    "energizer": "Whoa! You've been on fire lately — but your body needs a breather. "
                 "This week, let's dial it back a bit so you can come back even stronger!",
    "warrior": "Your load ratio is {acwr:.2f}. That's a red zone. "
               "Smart warriors know when to pull back. Reduce volume 20% this week. "
               "Recover now, attack harder next week.",
    "sage": "Your body has been working hard — load ratio is {acwr:.2f}. "
            "Listen to what it's telling you. An easy week now prevents a forced month off later.",
}

PR_CELEBRATION_MESSAGES = {
    "scientist": "New personal record: {distance} in {time}. "
                 "That's a {improvement}% improvement. Your VDOT has moved to approximately {vdot}. "
                 "Updated training zones recommended.",
    "energizer": "YOU DID IT! New PR: {distance} in {time}! "
                 "That's {improvement}% faster! AMAZING work — you should be SO proud!",
    "warrior": "{distance} PR: {time}. Earned through discipline. "
               "Good. Now — what's the next target?",
    "sage": "A new personal best: {distance} in {time}. "
            "Beautiful. Enjoy this moment. "
            "This is what patient, consistent practice produces over time.",
}

GOAL_APPROACHING_MESSAGES = {
    "scientist": "Your {goal} is {weeks_left} weeks away. "
                 "Based on current fitness, projected finish: {prediction}. "
                 "Focus this block: {focus}.",
    "energizer": "Your {goal} is just {weeks_left} weeks away! Getting exciting! "
                 "You're in great shape for this — let's make these final weeks count!",
    "warrior": "{goal}: {weeks_left} weeks out. Time to sharpen. "
               "Every session from now counts. Execute perfectly.",
    "sage": "Your {goal} is approaching — {weeks_left} weeks. "
            "Trust the training you've done. This final stretch is about arriving healthy, not fit-at-all-costs.",
}

CONSISTENCY_MILESTONE_MESSAGES = {
    "scientist": "Milestone: {milestone}. "
                 "Consistency is the #1 predictor of improvement. "
                 "Your aerobic base has measurably developed over this period.",
    "energizer": "MILESTONE! {milestone}! "
                 "Look how far you've come! This is incredible! Keep this energy going!",
    "warrior": "{milestone}. That's what showing up looks like. "
               "Most people quit before this point. You didn't.",
    "sage": "{milestone}. "
            "One run at a time, one day at a time. This is how lifelong runners are made.",
}


def check_proactive_triggers(
    user_id: int,
    persona: str,
    recent_runs: list[dict],
    streak: int,
    acwr: float,
    goals: list[dict],
    personal_records: list[dict] | None = None,
    total_runs: int = 0,
) -> list[ProactiveMessage]:
    """Check all proactive triggers and return messages for any that fire.

    Args:
        recent_runs: Last 14 days of runs [{date, distance_km, duration_min, type}]
        streak: Current consecutive-day running streak
        acwr: Acute:Chronic Workload Ratio (7d / 28d rolling avg)
        goals: Active goals [{type, target, deadline_date}]
        personal_records: Recent PRs [{distance, time, date, previous_time}]
        total_runs: Total lifetime runs logged
    """
    messages: list[ProactiveMessage] = []
    today = datetime.now()

    # 1. INACTIVITY CHECK
    if recent_runs:
        last_run_date = max(
            datetime.fromisoformat(r["date"]) if isinstance(r["date"], str) else r["date"]
            for r in recent_runs
        )
        days_since = (today - last_run_date).days
    else:
        days_since = 7  # Assume inactive if no data

    if days_since >= 3:
        priority = "high" if days_since >= 5 else "medium"
        template = INACTIVITY_MESSAGES.get(persona, INACTIVITY_MESSAGES["energizer"])
        messages.append(ProactiveMessage(
            trigger="inactivity",
            priority=priority,
            message=template.format(days=days_since),
            persona=persona,
            data={"days_since_last_run": days_since},
        ))

    # 2. STREAK AT RISK
    if streak >= 3:
        last_run_today = any(
            isinstance(r.get("date"), str) and r["date"][:10] == today.strftime("%Y-%m-%d")
            for r in recent_runs
        )
        if not last_run_today:
            template = STREAK_RISK_MESSAGES.get(persona, STREAK_RISK_MESSAGES["energizer"])
            messages.append(ProactiveMessage(
                trigger="streak_risk",
                priority="medium",
                message=template.format(streak=streak),
                persona=persona,
                data={"current_streak": streak},
            ))

    # 3. VOLUME SPIKE (ACWR > 1.3)
    if acwr > 1.3:
        priority = "high" if acwr > 1.5 else "medium"
        template = VOLUME_SPIKE_MESSAGES.get(persona, VOLUME_SPIKE_MESSAGES["scientist"])
        messages.append(ProactiveMessage(
            trigger="volume_spike",
            priority=priority,
            message=template.format(acwr=acwr),
            persona=persona,
            data={"acwr": acwr},
        ))

    # 4. RECENT PR CELEBRATION
    if personal_records:
        for pr in personal_records:
            pr_date = pr.get("date", "")
            if isinstance(pr_date, str):
                try:
                    pr_dt = datetime.fromisoformat(pr_date)
                    if (today - pr_dt).days <= 2:
                        prev = pr.get("previous_time", 0)
                        curr_time = pr.get("time", 0)
                        improvement = round((prev - curr_time) / prev * 100, 1) if prev > 0 else 0
                        template = PR_CELEBRATION_MESSAGES.get(persona, PR_CELEBRATION_MESSAGES["energizer"])
                        messages.append(ProactiveMessage(
                            trigger="pr_celebration",
                            priority="medium",
                            message=template.format(
                                distance=pr.get("distance", "?"),
                                time=pr.get("time_formatted", f"{curr_time:.1f} min"),
                                improvement=improvement,
                                vdot=pr.get("new_vdot", "?"),
                            ),
                            persona=persona,
                            data=pr,
                        ))
                except (ValueError, TypeError):
                    pass

    # 5. GOAL APPROACHING
    for goal in goals:
        deadline = goal.get("deadline_date")
        if deadline:
            try:
                deadline_dt = datetime.fromisoformat(deadline) if isinstance(deadline, str) else deadline
                weeks_left = (deadline_dt - today).days // 7
                if 1 <= weeks_left <= 4:
                    template = GOAL_APPROACHING_MESSAGES.get(persona, GOAL_APPROACHING_MESSAGES["energizer"])
                    focus = "race-specific work and taper" if weeks_left <= 2 else "maintaining volume with sharpening"
                    messages.append(ProactiveMessage(
                        trigger="goal_approaching",
                        priority="high" if weeks_left <= 2 else "medium",
                        message=template.format(
                            goal=goal.get("target", "your race"),
                            weeks_left=weeks_left,
                            prediction=goal.get("prediction", "on track"),
                            focus=focus,
                        ),
                        persona=persona,
                        data={"goal": goal, "weeks_left": weeks_left},
                    ))
            except (ValueError, TypeError):
                pass

    # 6. CONSISTENCY MILESTONES
    milestones = [10, 25, 50, 100, 200, 365, 500, 1000]
    for m in milestones:
        if total_runs == m:
            template = CONSISTENCY_MILESTONE_MESSAGES.get(persona, CONSISTENCY_MILESTONE_MESSAGES["energizer"])
            milestone_text = f"{m} total runs logged"
            if m == 365:
                milestone_text = "365 runs — a year of consistent running"
            elif m == 100:
                milestone_text = "100 runs — triple digits!"
            messages.append(ProactiveMessage(
                trigger="consistency_milestone",
                priority="low",
                message=template.format(milestone=milestone_text),
                persona=persona,
                data={"total_runs": total_runs, "milestone": m},
            ))
            break

    # Sort by priority (high > medium > low)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    messages.sort(key=lambda m: priority_order.get(m.priority, 1))

    return messages


def format_proactive_digest(messages: list[ProactiveMessage], max_messages: int = 3) -> str:
    """Format proactive messages into a single digest for delivery."""
    if not messages:
        return ""

    top = messages[:max_messages]
    lines = []
    for msg in top:
        lines.append(msg.message)

    return "\n\n".join(lines)
