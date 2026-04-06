# =============================================================================
# pattern_analyzer.py — Behavior Pattern Detection + Explanation + Prediction
#
# This is the NEW brain of the system. It implements the full pipeline:
#
#   Raw Events → Detected Patterns → Explanation → Prediction → Action
#
# No ML — pure rule-based logic that is transparent and auditable.
# =============================================================================

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone


# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class DetectedPatterns:
    """Structured output of pattern detection from a batch of events."""
    session_id: str
    timestamp: str

    # Detected signal counts
    rage_click_count: int = 0
    scroll_oscillation_detected: bool = False
    scroll_oscillation_count: int = 0
    repeated_action_count: int = 0
    idle_seconds: float = 0.0

    # Computed fields
    cognitive_load_index: float = 0.0   # renamed from confusion_score
    explanation: List[str] = field(default_factory=list)
    predicted_issue: str = "NONE"       # NONE | LOW | MEDIUM | HIGH
    prediction_reason: str = ""
    action_taken: str = "NONE"          # NONE | MONITOR | AUTO_ROLLBACK
    action_reason: str = ""


# ── Pattern Detector ──────────────────────────────────────────────────────────

def detect_patterns(events: list, session_id: str) -> DetectedPatterns:
    """
    Step 1 of the pipeline: extract structured patterns from raw events.

    Args:
        events: list of BehaviorEvent objects from the tracker
        session_id: current user session

    Returns:
        DetectedPatterns with all signal counts filled in
    """
    patterns = DetectedPatterns(
        session_id=session_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    for event in events:
        etype = event.event_type
        count = event.count

        if etype == "rage_click":
            patterns.rage_click_count += count

        elif etype == "scroll_oscillation":
            patterns.scroll_oscillation_count += count
            if count >= 1:
                patterns.scroll_oscillation_detected = True

        elif etype == "repeated_action":
            patterns.repeated_action_count += count

        elif etype == "idle":
            # Each idle event represents one idle period of ~5 seconds
            patterns.idle_seconds += count * 5.0

    return patterns


# ── Pattern Explainer ─────────────────────────────────────────────────────────

def explain_patterns(patterns: DetectedPatterns) -> List[str]:
    """
    Step 2 of the pipeline: generate human-readable explanations of WHY
    the cognitive load index increased.

    Returns:
        List of explanation strings shown on the dashboard
    """
    explanations = []

    if patterns.rage_click_count >= 4:
        explanations.append(
            f"Rage clicks detected: {patterns.rage_click_count} — "
            f"user clicked the same area {patterns.rage_click_count}x rapidly, "
            f"indicating frustration with an unresponsive UI element."
        )
    elif patterns.rage_click_count > 0:
        explanations.append(
            f"Rapid clicks detected: {patterns.rage_click_count} — "
            f"user is clicking faster than expected, possible UI lag."
        )

    if patterns.scroll_oscillation_detected:
        explanations.append(
            f"Scroll oscillation detected: {patterns.scroll_oscillation_count} reversals — "
            f"user is scrolling up and down repeatedly, unable to find target content."
        )

    if patterns.repeated_action_count > 2:
        explanations.append(
            f"Repeated actions: {patterns.repeated_action_count} — "
            f"user triggered the same action more than twice, suggesting the action "
            f"is not producing the expected result."
        )
    elif patterns.repeated_action_count > 0:
        explanations.append(
            f"Repeated action: {patterns.repeated_action_count} — user retried an action."
        )

    if patterns.idle_seconds >= 10:
        explanations.append(
            f"Extended idle time: {patterns.idle_seconds:.0f} seconds — "
            f"user has stopped interacting completely, likely overwhelmed or lost."
        )
    elif patterns.idle_seconds >= 5:
        explanations.append(
            f"Idle hesitation: {patterns.idle_seconds:.0f} seconds — "
            f"user paused longer than expected before next action."
        )

    if not explanations:
        explanations.append("No significant confusion patterns detected in this batch.")

    return explanations


# ── Prediction Engine ─────────────────────────────────────────────────────────

def predict_issue(patterns: DetectedPatterns) -> tuple[str, str]:
    """
    Step 3 of the pipeline: apply rule-based prediction logic.

    Rules (in priority order):
        HIGH   — rage_clicks > 3 AND scroll_oscillation → user is clearly lost
        HIGH   — rage_clicks > 3 AND repeated_actions > 2 → multiple frustration signals
        HIGH   — cognitive_load_index >= 70 → composite score too high
        MEDIUM — repeated_actions > 2 → action not working
        MEDIUM — scroll_oscillation AND idle_seconds >= 5 → searching + stuck
        MEDIUM — cognitive_load_index >= 40 → elevated load
        LOW    — any single signal present
        NONE   — no signals

    Returns:
        (predicted_issue: str, reason: str)
    """

    cli = patterns.cognitive_load_index

    # ── HIGH severity rules ────────────────────────────────────────────────────
    if patterns.rage_click_count > 3 and patterns.scroll_oscillation_detected:
        return (
            "HIGH",
            f"Rage clicks ({patterns.rage_click_count}) combined with scroll oscillation "
            f"indicate severe navigation failure. User cannot find or activate target element."
        )

    if patterns.rage_click_count > 3 and patterns.repeated_action_count > 2:
        return (
            "HIGH",
            f"Multiple frustration signals: {patterns.rage_click_count} rage clicks + "
            f"{patterns.repeated_action_count} repeated actions. "
            f"UI is not responding as the user expects."
        )

    if cli >= 70:
        return (
            "HIGH",
            f"Cognitive Load Index reached {cli:.1f}/100 — composite behavioral signals "
            f"exceed rollback threshold of 70."
        )

    # ── MEDIUM severity rules ──────────────────────────────────────────────────
    if patterns.repeated_action_count > 2:
        return (
            "MEDIUM",
            f"Repeated actions ({patterns.repeated_action_count}) detected. "
            f"User is retrying the same operation — expected outcome not being reached."
        )

    if patterns.scroll_oscillation_detected and patterns.idle_seconds >= 5:
        return (
            "MEDIUM",
            f"Scroll oscillation + {patterns.idle_seconds:.0f}s idle time. "
            f"User searched for content, couldn't find it, and stopped."
        )

    if cli >= 40:
        return (
            "MEDIUM",
            f"Cognitive Load Index at {cli:.1f}/100 — elevated behavioral signals, monitoring."
        )

    # ── LOW severity ──────────────────────────────────────────────────────────
    if (patterns.rage_click_count > 0 or patterns.scroll_oscillation_detected
            or patterns.repeated_action_count > 0 or patterns.idle_seconds > 0):
        return (
            "LOW",
            "Minor confusion signals detected. No action required yet — continuing to monitor."
        )

    return ("NONE", "All behavioral signals within normal range.")


# ── Action Decider ────────────────────────────────────────────────────────────

def decide_action(predicted_issue: str, prediction_reason: str) -> tuple[str, str]:
    """
    Step 4 of the pipeline: decide what automated action to take.

    Rules:
        HIGH   → AUTO_ROLLBACK (no human needed)
        MEDIUM → MONITOR (flag for ops team)
        LOW    → MONITOR (log only)
        NONE   → NONE

    Returns:
        (action: str, action_reason: str)
    """

    if predicted_issue == "HIGH":
        return (
            "AUTO_ROLLBACK",
            f"Prediction was HIGH severity. Auto-triggered rollback without human intervention. "
            f"Reason: {prediction_reason}"
        )

    elif predicted_issue == "MEDIUM":
        return (
            "MONITOR",
            f"Prediction was MEDIUM severity. Flagged for monitoring. "
            f"Will escalate to AUTO_ROLLBACK if signals worsen. Reason: {prediction_reason}"
        )

    elif predicted_issue == "LOW":
        return (
            "MONITOR",
            f"Low-level signals logged. Passive monitoring active. Reason: {prediction_reason}"
        )

    return ("NONE", "No action required.")


# ── Full Pipeline Runner ──────────────────────────────────────────────────────

def run_full_pipeline(events: list, session_id: str, cognitive_load_index: float) -> DetectedPatterns:
    """
    Runs the complete pipeline in sequence:
        detect → explain → predict → decide

    Args:
        events: raw behavior events from tracker
        session_id: current session
        cognitive_load_index: pre-computed score from confusion_engine

    Returns:
        Fully populated DetectedPatterns object
    """

    # Step 1 — Detect
    patterns = detect_patterns(events, session_id)
    patterns.cognitive_load_index = cognitive_load_index

    # Step 2 — Explain
    patterns.explanation = explain_patterns(patterns)

    # Step 3 — Predict
    patterns.predicted_issue, patterns.prediction_reason = predict_issue(patterns)

    # Step 4 — Decide
    patterns.action_taken, patterns.action_reason = decide_action(
        patterns.predicted_issue, patterns.prediction_reason
    )

    return patterns
