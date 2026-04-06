# =============================================================================
# backend/tests/test_pattern_analyzer.py
# Tests the full Behavior → Pattern → Prediction → Action pipeline
# Run: pytest backend/tests/ -v
# =============================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pattern_analyzer import (
    detect_patterns, explain_patterns, predict_issue,
    decide_action, run_full_pipeline
)


class FakeEvent:
    def __init__(self, event_type, count=1):
        self.event_type = event_type
        self.count = count


# ── detect_patterns ────────────────────────────────────────────────────────────

def test_detect_rage_clicks():
    events = [FakeEvent("rage_click", 5)]
    p = detect_patterns(events, "test-001")
    assert p.rage_click_count == 5

def test_detect_scroll_oscillation():
    events = [FakeEvent("scroll_oscillation", 3)]
    p = detect_patterns(events, "test-002")
    assert p.scroll_oscillation_detected is True
    assert p.scroll_oscillation_count == 3

def test_detect_idle_converts_to_seconds():
    events = [FakeEvent("idle", 2)]
    p = detect_patterns(events, "test-003")
    assert p.idle_seconds == 10.0   # 2 * 5s = 10s

def test_detect_repeated_action():
    events = [FakeEvent("repeated_action", 4)]
    p = detect_patterns(events, "test-004")
    assert p.repeated_action_count == 4

def test_detect_multiple_signals():
    events = [
        FakeEvent("rage_click", 4),
        FakeEvent("scroll_oscillation", 2),
        FakeEvent("idle", 1),
    ]
    p = detect_patterns(events, "test-005")
    assert p.rage_click_count == 4
    assert p.scroll_oscillation_detected is True
    assert p.idle_seconds == 5.0


# ── explain_patterns ───────────────────────────────────────────────────────────

def test_explain_rage_click():
    events = [FakeEvent("rage_click", 5)]
    p = detect_patterns(events, "s")
    explanations = explain_patterns(p)
    assert any("rage" in e.lower() for e in explanations)

def test_explain_no_signals_returns_ok_message():
    p = detect_patterns([], "s")
    explanations = explain_patterns(p)
    assert len(explanations) == 1
    assert "no significant" in explanations[0].lower()

def test_explain_idle_over_10s():
    events = [FakeEvent("idle", 3)]  # 15 seconds
    p = detect_patterns(events, "s")
    explanations = explain_patterns(p)
    assert any("idle" in e.lower() or "extended" in e.lower() for e in explanations)


# ── predict_issue ──────────────────────────────────────────────────────────────

def test_predict_high_rage_plus_scroll():
    events = [FakeEvent("rage_click", 4), FakeEvent("scroll_oscillation", 2)]
    p = detect_patterns(events, "s")
    p.cognitive_load_index = 60.0
    issue, reason = predict_issue(p)
    assert issue == "HIGH"
    assert "rage" in reason.lower()

def test_predict_high_from_cli_score():
    events = []
    p = detect_patterns(events, "s")
    p.cognitive_load_index = 75.0
    issue, reason = predict_issue(p)
    assert issue == "HIGH"

def test_predict_medium_repeated_actions():
    events = [FakeEvent("repeated_action", 3)]
    p = detect_patterns(events, "s")
    p.cognitive_load_index = 30.0
    issue, reason = predict_issue(p)
    assert issue == "MEDIUM"

def test_predict_none_no_signals():
    p = detect_patterns([], "s")
    p.cognitive_load_index = 0.0
    issue, reason = predict_issue(p)
    assert issue == "NONE"

def test_predict_low_single_small_signal():
    events = [FakeEvent("idle", 1)]
    p = detect_patterns(events, "s")
    p.cognitive_load_index = 5.0
    issue, _ = predict_issue(p)
    assert issue in ["LOW", "NONE"]


# ── decide_action ──────────────────────────────────────────────────────────────

def test_decide_high_triggers_auto_rollback():
    action, reason = decide_action("HIGH", "severe confusion")
    assert action == "AUTO_ROLLBACK"
    assert "rollback" in reason.lower()

def test_decide_medium_triggers_monitor():
    action, _ = decide_action("MEDIUM", "moderate signals")
    assert action == "MONITOR"

def test_decide_none_no_action():
    action, _ = decide_action("NONE", "normal")
    assert action == "NONE"


# ── run_full_pipeline ─────────────────────────────────────────────────────────

def test_full_pipeline_high_scenario():
    events = [
        FakeEvent("rage_click", 5),
        FakeEvent("scroll_oscillation", 3),
        FakeEvent("repeated_action", 3),
    ]
    result = run_full_pipeline(events, "pipeline-test", cognitive_load_index=83.0)

    assert result.predicted_issue == "HIGH"
    assert result.action_taken == "AUTO_ROLLBACK"
    assert len(result.explanation) > 0
    assert result.rage_click_count == 5
    assert result.scroll_oscillation_detected is True

def test_full_pipeline_normal_scenario():
    events = []
    result = run_full_pipeline(events, "pipeline-normal", cognitive_load_index=0.0)

    assert result.predicted_issue == "NONE"
    assert result.action_taken == "NONE"

def test_full_pipeline_populates_all_fields():
    events = [FakeEvent("rage_click", 2)]
    result = run_full_pipeline(events, "pipeline-check", cognitive_load_index=20.0)

    assert result.session_id == "pipeline-check"
    assert result.cognitive_load_index == 20.0
    assert result.explanation is not None
    assert result.prediction_reason is not None
    assert result.action_reason is not None
