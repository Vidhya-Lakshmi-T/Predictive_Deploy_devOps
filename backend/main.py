# =============================================================================
# main.py — FastAPI entry point (v4 — simplified, instant, demo-clear)
#
# What changed from v3:
#   - Removed cooldown manager entirely
#   - Removed frozen state logic
#   - Rollback is instant — no delays, no timers
#   - /track always returns fresh state
#   - Added "what_happened_after_rollback" field explaining post-rollback state
#   - Added GET /last-rollback for dashboard to always show last event clearly
# =============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import uvicorn

from fastapi.responses import FileResponse, HTMLResponse
from confusion_engine import compute_confusion_score
from pattern_analyzer import run_full_pipeline
from rollback import trigger_rollback, get_active_version, set_active_version, VERSIONS
from database import (
    insert_event,
    insert_score,
    insert_pattern,
    get_recent_events,
    get_recent_scores,
    get_rollback_logs,
    get_recent_patterns,
    insert_rollback_log,
)

import os

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = FastAPI(
    title="Predictive Deployment Control API",
    description="Behavior → Pattern → Prediction → Instant Action",
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Models ────────────────────────────────────────────────────────────────────

class BehaviorEvent(BaseModel):
    session_id: str
    event_type: str
    count: int = 1
    metadata: Optional[dict] = {}

class EventBatch(BaseModel):
    session_id: str
    events: List[BehaviorEvent]

# ── In-memory: track which sessions already rolled back (prevent re-trigger) ──
_rolled_back_sessions: set = set()

# ── What-happened explanation generator ───────────────────────────────────────

def build_post_rollback_explanation(patterns, cli: float) -> dict:
    """
    Builds a plain-English, step-by-step explanation of WHAT HAPPENED
    after rollback was triggered. This is shown permanently on the UI.
    """
    # Collect which signals fired
    signals = []
    if patterns.rage_click_count > 3:
        signals.append(f"rage clicks ({patterns.rage_click_count}x rapid clicks)")
    if patterns.scroll_oscillation_detected:
        signals.append(f"scroll confusion ({patterns.scroll_oscillation_count} reversals)")
    if patterns.repeated_action_count > 2:
        signals.append(f"repeated failed actions ({patterns.repeated_action_count}x)")
    if patterns.idle_seconds >= 5:
        signals.append(f"idle hesitation ({patterns.idle_seconds:.0f}s of no interaction)")

    signal_text = " + ".join(signals) if signals else "multiple confusion signals"

    return {
        "step_1_what_user_did":    f"User showed confusion: {signal_text}.",
        "step_2_what_system_saw":  f"Cognitive Load Index reached {cli:.1f}/100 — above the 70-point threshold.",
        "step_3_what_was_predicted": "System predicted a HIGH-severity UI failure. User was unable to complete their intended action.",
        "step_4_what_action_was_taken": "AUTO ROLLBACK executed instantly. The bad deployment was replaced with the last known stable version.",
        "step_5_what_is_stable_now": (
            "The previous stable version is now live. "
            "Users are being served the version that worked correctly. "
            "No manual intervention was required. "
            "System continues monitoring for further confusion signals."
        ),
        "plain_summary": (
            f"User struggled ({signal_text}) → "
            f"System detected high confusion (score {cli:.1f}) → "
            f"Predicted issue: HIGH → "
            f"Rollback triggered → "
            f"Stable version restored → "
            f"Monitoring continues."
        ),
    }


def utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "running", "version": "4.0.0", "service": "Predictive Deployment Control"}


@app.get("/app", response_class=HTMLResponse)
async def serve_app():
    """
    Serves the CURRENTLY ACTIVE version of the app.
    - Before rollback: serves app_v2_broken.html  (bad deployment)
    - After  rollback: serves app_v1_stable.html  (stable version)

    This is the REAL version switch — not just a log message.
    Open http://localhost:8000/app in your browser to see the active version.
    """
    active = get_active_version()
    filename = VERSIONS.get(active, "app_v1_stable.html")
    filepath = os.path.join(FRONTEND_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)


@app.get("/version")
async def current_version():
    """Returns which version is currently active — used by dashboard."""
    active = get_active_version()
    filename = VERSIONS.get(active, "app_v1_stable.html")
    is_stable = active == "v1"
    return {
        "active_version": active,
        "filename": filename,
        "is_stable": is_stable,
        "label": "✅ Stable (v1)" if is_stable else "⚠️ Broken deployment (v2)",
        "description": (
            "app_v1_stable.html — checkout works, users can complete purchases"
            if is_stable else
            "app_v2_broken.html — checkout stuck, users confused and frustrated"
        ),
    }


@app.post("/reset-version")
async def reset_to_broken():
    """
    Reset active version back to v2 (broken) for demo restart.
    Use this at the start of each demo to simulate a bad deploy going live.
    """
    set_active_version("v2")
    return {
        "status": "reset",
        "active_version": "v2",
        "message": "Demo reset. app_v2_broken.html is now live. Run demo again."
    }


@app.post("/track")
async def track_events(batch: EventBatch):
    """
    Main pipeline endpoint. Always runs fresh — no freezing, no cooldown.
    If rollback fires, returns full explanation of what happened next.
    """
    timestamp = utc_now_iso()

    # ── Store raw events ───────────────────────────────────────────────────
    for event in batch.events:
        insert_event({
            "session_id": batch.session_id,
            "event_type": event.event_type,
            "count": event.count,
            "metadata": event.metadata,
            "timestamp": timestamp,
        })

    # ── Compute Cognitive Load Index ───────────────────────────────────────
    cli = compute_confusion_score(batch.events)
    insert_score({"session_id": batch.session_id, "score": cli, "timestamp": timestamp})

    # ── Run full pattern pipeline ──────────────────────────────────────────
    patterns = run_full_pipeline(batch.events, batch.session_id, cli)

    # ── Store pattern record ───────────────────────────────────────────────
    insert_pattern({
        "session_id": patterns.session_id,
        "timestamp": patterns.timestamp,
        "rage_click_count": patterns.rage_click_count,
        "scroll_oscillation_detected": patterns.scroll_oscillation_detected,
        "scroll_oscillation_count": patterns.scroll_oscillation_count,
        "repeated_action_count": patterns.repeated_action_count,
        "idle_seconds": patterns.idle_seconds,
        "cognitive_load_index": cli,
        "explanation": patterns.explanation,
        "predicted_issue": patterns.predicted_issue,
        "prediction_reason": patterns.prediction_reason,
        "action_taken": patterns.action_taken,
        "action_reason": patterns.action_reason,
    })

    # ── Build response ─────────────────────────────────────────────────────
    response = {
        "session_id": batch.session_id,
        "timestamp": timestamp,
        "system_state": "STABLE",         # always STABLE or ROLLED_BACK
        "cognitive_load_index": cli,
        "detected_patterns": {
            "rage_click_count": patterns.rage_click_count,
            "scroll_oscillation_detected": patterns.scroll_oscillation_detected,
            "repeated_action_count": patterns.repeated_action_count,
            "idle_seconds": patterns.idle_seconds,
        },
        "explanation": patterns.explanation,
        "predicted_issue": patterns.predicted_issue,
        "prediction_reason": patterns.prediction_reason,
        "action_taken": patterns.action_taken,
        "action_reason": patterns.action_reason,
        "rollback_triggered": False,
        "what_happened_after_rollback": None,  # only populated when rollback fires
        "status_message": "System monitoring. No action required.",
    }

    # ── Instant rollback — no delay, no timer ──────────────────────────────
    if patterns.action_taken == "AUTO_ROLLBACK":
        already_done = batch.session_id in _rolled_back_sessions

        if not already_done:
            # Execute rollback immediately
            trigger_rollback(
                session_id=batch.session_id,
                score=cli,
                timestamp=timestamp,
                reason=patterns.action_reason,
                trigger_mode="AUTO",
                trigger_source="behavior-pipeline",
            )
            _rolled_back_sessions.add(batch.session_id)

            # Build the plain-English post-rollback explanation
            explanation_block = build_post_rollback_explanation(patterns, cli)

            response["rollback_triggered"]          = True
            response["system_state"]               = "ROLLED_BACK"
            response["action_taken"]               = "AUTO_ROLLBACK_EXECUTED"
            response["what_happened_after_rollback"] = explanation_block
            response["status_message"]             = (
                "⚠️ High confusion detected — AUTO ROLLBACK EXECUTED. "
                "Stable version is now live. System stabilized after rollback. "
                "Monitoring continues."
            )
        else:
            # Already rolled back this session — keep showing stable state
            response["system_state"]  = "ROLLED_BACK"
            response["action_taken"]  = "AUTO_ROLLBACK_EXECUTED"
            response["status_message"] = (
                "✅ System stabilized after rollback. "
                "Stable version is live. Monitoring continues."
            )

    return response


@app.post("/rollback")
async def manual_rollback(session_id: str = "manual"):
    """Manually trigger rollback — also called by GitHub Actions."""
    timestamp = utc_now_iso()
    trigger_rollback(
        session_id=session_id,
        score=999,
        timestamp=timestamp,
        reason="Manual override / CI pipeline trigger",
        trigger_mode="MANUAL",
        trigger_source="dashboard-or-ci",
    )
    return {
        "status": "rollback triggered",
        "session_id": session_id,
        "timestamp": timestamp,
        "trigger_mode": "MANUAL",
        "status_message": (
            "⚠️ Manual rollback executed. "
            "Stable version restored. Monitoring continues."
        ),
    }


@app.get("/score/latest")
async def latest_score():
    scores = get_recent_scores(limit=1)
    if not scores:
        return {"score": 0, "message": "No scores recorded yet"}
    s = scores[0]
    return {"score": s["score"], "session_id": s["session_id"], "timestamp": s["timestamp"]}


@app.get("/score/history")
async def score_history(limit: int = 50):
    return get_recent_scores(limit=limit)


@app.get("/patterns")
async def recent_patterns(limit: int = 20):
    return get_recent_patterns(limit=limit)


@app.get("/last-rollback")
async def last_rollback():
    """
    Returns the most recent rollback event with full context.
    Dashboard uses this to always show what happened last, even after restart.
    """
    logs = get_rollback_logs(limit=1)
    if not logs:
        return {"has_rollback": False}
    rb = logs[0]
    return {"has_rollback": True, **rb}


@app.get("/events")
async def recent_events(limit: int = 100):
    return get_recent_events(limit=limit)


@app.get("/rollbacks")
async def rollback_history(limit: int = 20):
    return get_rollback_logs(limit=limit)


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "4.0.0",
            "timestamp": utc_now_iso()}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
