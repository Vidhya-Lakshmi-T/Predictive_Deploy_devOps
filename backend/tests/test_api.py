# =============================================================================
# backend/tests/test_api.py
# Integration tests for FastAPI endpoints using httpx async client
# Run: pytest backend/tests/ -v
# =============================================================================

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root_returns_running():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "running"


def test_health_endpoint():
    r = client.get("/health")
    assert r.status_code == 200
    assert "timestamp" in r.json()


def test_track_low_confusion():
    payload = {
        "session_id": "test-low",
        "events": [
            {"session_id": "test-low", "event_type": "idle", "count": 1}
        ],
    }
    r = client.post("/track", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "cognitive_load_index" in data
    assert data["cognitive_load_index"] < 70
    assert data["rollback_triggered"] == False


def test_track_high_confusion_triggers_rollback():
    payload = {
        "session_id": "test-high-unique-" + os.urandom(4).hex(),
        "events": [
            {"session_id": "x", "event_type": "rage_click",         "count": 5},
            {"session_id": "x", "event_type": "scroll_oscillation",  "count": 5},
            {"session_id": "x", "event_type": "repeated_action",     "count": 5},
        ],
    }
    r = client.post("/track", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["cognitive_load_index"] >= 70
    assert data["rollback_triggered"] == True


def test_score_latest_returns_score():
    r = client.get("/score/latest")
    assert r.status_code == 200
    assert "score" in r.json()


def test_manual_rollback_endpoint():
    r = client.post("/rollback?session_id=test-manual")
    assert r.status_code == 200
    assert r.json()["status"] == "rollback triggered"
    assert r.json()["trigger_mode"] == "MANUAL"
