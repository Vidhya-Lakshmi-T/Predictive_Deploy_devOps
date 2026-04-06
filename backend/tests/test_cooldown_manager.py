# =============================================================================
# backend/tests/test_cooldown_manager.py
# Tests the post-rollback cooldown state logic
# Run: pytest backend/tests/ -v
# =============================================================================

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cooldown_manager import CooldownManager


def make_frozen_state(cli=85.0, issue="HIGH"):
    return {
        "session_id": "test-sess",
        "cognitive_load_index": cli,
        "predicted_issue": issue,
        "action_taken": "AUTO_ROLLBACK_EXECUTED",
        "action_reason": "Test rollback",
        "explanation": ["Rage clicks detected"],
        "system_state": "COOLDOWN",
        "cooldown_seconds_remaining": 15,
    }


def test_enter_cooldown_marks_session():
    cm = CooldownManager()
    cm.enter_cooldown("sess-001", make_frozen_state())
    assert cm.is_in_cooldown("sess-001") is True


def test_session_not_in_cooldown_by_default():
    cm = CooldownManager()
    assert cm.is_in_cooldown("unknown-session") is False


def test_frozen_state_preserves_cli():
    cm = CooldownManager()
    cm.enter_cooldown("sess-002", make_frozen_state(cli=92.5))
    frozen = cm.get_frozen_state("sess-002")
    assert frozen["cognitive_load_index"] == 92.5


def test_frozen_state_has_cooldown_fields():
    cm = CooldownManager()
    cm.enter_cooldown("sess-003", make_frozen_state())
    frozen = cm.get_frozen_state("sess-003")
    assert frozen["system_state"] == "COOLDOWN"
    assert "cooldown_seconds_remaining" in frozen
    assert frozen["cooldown_seconds_remaining"] > 0


def test_frozen_state_preserves_prediction():
    cm = CooldownManager()
    cm.enter_cooldown("sess-004", make_frozen_state(issue="HIGH"))
    frozen = cm.get_frozen_state("sess-004")
    assert frozen["predicted_issue"] == "HIGH"


def test_get_system_status_during_cooldown():
    cm = CooldownManager()
    cm.enter_cooldown("sess-005", make_frozen_state(cli=77.0))
    status = cm.get_system_status()
    assert status["any_in_cooldown"] is True
    assert status["system_state"] == "COOLDOWN"
    assert len(status["active_cooldowns"]) == 1
    assert status["active_cooldowns"][0]["frozen_cli"] == 77.0


def test_get_system_status_empty_is_normal():
    cm = CooldownManager()
    status = cm.get_system_status()
    assert status["any_in_cooldown"] is False
    assert status["system_state"] == "NORMAL"
    assert status["active_cooldowns"] == []


def test_multiple_sessions_in_cooldown():
    cm = CooldownManager()
    cm.enter_cooldown("sess-A", make_frozen_state(cli=80.0))
    cm.enter_cooldown("sess-B", make_frozen_state(cli=90.0))
    status = cm.get_system_status()
    assert len(status["active_cooldowns"]) == 2


def test_cooldown_expires_after_duration():
    """Use a very short cooldown to test expiry without waiting 15s."""
    import importlib
    import cooldown_manager as cm_module

    original = cm_module.COOLDOWN_SECONDS
    cm_module.COOLDOWN_SECONDS = 1   # 1 second for this test

    cm = CooldownManager()
    cm.enter_cooldown("sess-expire", make_frozen_state())
    assert cm.is_in_cooldown("sess-expire") is True

    time.sleep(1.1)  # wait for expiry

    assert cm.is_in_cooldown("sess-expire") is False

    cm_module.COOLDOWN_SECONDS = original  # restore


def test_frozen_state_returns_none_after_expiry():
    import cooldown_manager as cm_module
    original = cm_module.COOLDOWN_SECONDS
    cm_module.COOLDOWN_SECONDS = 1

    cm = CooldownManager()
    cm.enter_cooldown("sess-stale", make_frozen_state())
    time.sleep(1.1)
    assert cm.get_frozen_state("sess-stale") is None

    cm_module.COOLDOWN_SECONDS = original
