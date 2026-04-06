# =============================================================================
# backend/tests/test_confusion_engine.py
# Run: pytest backend/tests/ -v
# =============================================================================

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from confusion_engine import (
    compute_confusion_score,
    score_to_severity,
    explain_score,
    ROLLBACK_THRESHOLD,
)


# ── Fake event class (mirrors BehaviorEvent shape) ────────────────────────────
class FakeEvent:
    def __init__(self, event_type, count=1):
        self.event_type = event_type
        self.count = count
        self.metadata = {}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_empty_events_returns_zero():
    score = compute_confusion_score([])
    assert score == 0.0


def test_single_rage_click():
    events = [FakeEvent("rage_click", count=5)]
    score = compute_confusion_score(events)
    assert score > 0
    assert score <= 100


def test_all_signals_at_max_gives_high_score():
    events = [
        FakeEvent("rage_click",         count=5),
        FakeEvent("scroll_oscillation",  count=5),
        FakeEvent("repeated_action",     count=5),
        FakeEvent("idle",               count=5),
    ]
    score = compute_confusion_score(events)
    assert score == 100.0


def test_score_above_threshold_triggers_rollback_zone():
    events = [
        FakeEvent("rage_click",        count=5),
        FakeEvent("repeated_action",   count=5),
        FakeEvent("scroll_oscillation", count=5),
    ]
    score = compute_confusion_score(events)
    assert score >= ROLLBACK_THRESHOLD


def test_low_activity_stays_below_threshold():
    events = [FakeEvent("idle", count=1)]
    score = compute_confusion_score(events)
    assert score < ROLLBACK_THRESHOLD


def test_unknown_event_type_ignored():
    events = [FakeEvent("unknown_event", count=10)]
    score = compute_confusion_score(events)
    assert score == 0.0


def test_score_normalized_to_100():
    # Extreme counts should never exceed 100
    events = [
        FakeEvent("rage_click",         count=999),
        FakeEvent("scroll_oscillation",  count=999),
        FakeEvent("repeated_action",     count=999),
        FakeEvent("idle",               count=999),
    ]
    score = compute_confusion_score(events)
    assert score == 100.0


def test_severity_labels():
    assert score_to_severity(10) == "low"
    assert score_to_severity(45) == "medium"
    assert score_to_severity(65) == "high"
    assert score_to_severity(80) == "critical"


def test_explain_score_has_all_signal_keys():
    events = [
        FakeEvent("rage_click", count=3),
        FakeEvent("idle", count=1),
    ]
    breakdown = explain_score(events)
    assert "rage_click" in breakdown
    assert "idle" in breakdown
    assert breakdown["rage_click"]["count"] == 3


def test_diminishing_returns_on_high_counts():
    # count=5 and count=100 should give same contribution (capped at 5)
    score_5   = compute_confusion_score([FakeEvent("rage_click", count=5)])
    score_100 = compute_confusion_score([FakeEvent("rage_click", count=100)])
    assert score_5 == score_100
