# =============================================================================
# confusion_engine.py — Core novelty of this project
#
# Computes a "Confusion Score" (0–100) from raw user behavior events.
# This is the patent-worthy signal: multi-dimensional frontend behavioral
# telemetry used as a deterministic CI/CD gate — not server metrics.
#
# Score weights (tunable):
#   rage_click        → +30  (user clicking frantically = very confused)
#   scroll_oscillation → +20  (user scrolling up-down = can't find content)
#   repeated_action   → +25  (user repeating same action = nothing working)
#   idle              → +15  (user frozen = overwhelmed or lost)
# =============================================================================

from typing import List

# ── Weight table (edit these to tune sensitivity) ─────────────────────────────
CONFUSION_WEIGHTS = {
    "rage_click":         30,
    "scroll_oscillation": 20,
    "repeated_action":    25,
    "idle":               15,
}

# Maximum possible raw score (all signals firing at count=1)
MAX_RAW_SCORE = sum(CONFUSION_WEIGHTS.values())  # 90

# Rollback threshold — scores above this trigger automated rollback
ROLLBACK_THRESHOLD = 70


def compute_confusion_score(events: list) -> float:
    """
    Given a list of BehaviorEvent objects, compute a normalized confusion score.

    Returns:
        float: score between 0 and 100
    """
    raw_score = 0

    for event in events:
        event_type = event.event_type
        count = event.count

        if event_type not in CONFUSION_WEIGHTS:
            continue  # ignore unknown events

        weight = CONFUSION_WEIGHTS[event_type]

        # Apply diminishing returns for very high counts to avoid
        # a single spammy event from dominating the score.
        # Formula: weight × log-scaled count contribution
        effective_count = min(count, 5)  # cap at 5 to normalize
        contribution = weight * (effective_count / 5)

        raw_score += contribution

    # Normalize to 0–100
    normalized = min((raw_score / MAX_RAW_SCORE) * 100, 100)
    return round(normalized, 2)


def score_to_severity(score: float) -> str:
    """Map a confusion score to a human-readable severity label."""
    if score < 30:
        return "low"
    elif score < 60:
        return "medium"
    elif score < ROLLBACK_THRESHOLD:
        return "high"
    else:
        return "critical"


def explain_score(events: list) -> dict:
    """
    Return a breakdown of what contributed to the score.
    Useful for dashboard display and debugging.
    """
    breakdown = {}
    for event in events:
        event_type = event.event_type
        if event_type in CONFUSION_WEIGHTS:
            weight = CONFUSION_WEIGHTS[event_type]
            effective_count = min(event.count, 5)
            contribution = round(weight * (effective_count / 5), 2)
            breakdown[event_type] = {
                "count": event.count,
                "weight": weight,
                "contribution": contribution,
            }
    return breakdown
