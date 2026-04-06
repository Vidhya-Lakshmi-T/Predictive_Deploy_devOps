# =============================================================================
# database.py — MongoDB connection and CRUD operations
#
# Collections:
#   events    — raw behavior events from frontend tracker
#   scores    — computed confusion scores per session
#   rollbacks — rollback decision log
#
# Set MONGO_URI environment variable to override default localhost connection.
# =============================================================================

import os
from datetime import datetime
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure

# ── Connection setup ──────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "predictive_deploy"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")  # verify connection
    db = client[DB_NAME]
    print(f"[DB] Connected to MongoDB at {MONGO_URI}")
except ConnectionFailure:
    print("[DB] WARNING: MongoDB not reachable. Running in mock mode.")
    db = None


def _collection(name: str):
    """Return a MongoDB collection, or None if DB is unavailable."""
    return db[name] if db is not None else None


# ── Events ────────────────────────────────────────────────────────────────────

def insert_event(event_doc: dict):
    col = _collection("events")
    if col is not None:
        col.insert_one(event_doc)


def get_recent_events(limit: int = 100) -> list:
    col = _collection("events")
    if col is None:
        return _mock_events(limit)
    docs = col.find({}, {"_id": 0}).sort("timestamp", DESCENDING).limit(limit)
    return list(docs)


# ── Scores ────────────────────────────────────────────────────────────────────

def insert_score(score_doc: dict):
    col = _collection("scores")
    if col is not None:
        col.insert_one(score_doc)


def get_recent_scores(limit: int = 50) -> list:
    col = _collection("scores")
    if col is None:
        return _mock_scores(limit)
    docs = col.find({}, {"_id": 0}).sort("timestamp", DESCENDING).limit(limit)
    return list(docs)


# ── Patterns ──────────────────────────────────────────────────────────────────

def insert_pattern(pattern_doc: dict):
    col = _collection("patterns")
    if col is not None:
        col.insert_one(pattern_doc)


def get_recent_patterns(limit: int = 20) -> list:
    col = _collection("patterns")
    if col is None:
        return _mock_patterns(limit)
    docs = col.find({}, {"_id": 0}).sort("timestamp", DESCENDING).limit(limit)
    return list(docs)


# ── Rollbacks ─────────────────────────────────────────────────────────────────

def insert_rollback_log(rollback_doc: dict):
    col = _collection("rollbacks")
    if col is not None:
        col.insert_one(rollback_doc)


def get_rollback_logs(limit: int = 20) -> list:
    col = _collection("rollbacks")
    if col is None:
        return []
    docs = col.find({}, {"_id": 0}).sort("timestamp", DESCENDING).limit(limit)
    return list(docs)


# ── Mock data (used when MongoDB is unavailable) ──────────────────────────────

def _mock_patterns(limit: int) -> list:
    """Return sample pattern analysis results for dashboard demo without MongoDB."""
    return [
        {
            "session_id": "demo-001",
            "timestamp": "2024-01-01T10:00:10",
            "rage_click_count": 5,
            "scroll_oscillation_detected": True,
            "scroll_oscillation_count": 4,
            "repeated_action_count": 3,
            "idle_seconds": 10.0,
            "cognitive_load_index": 83.33,
            "explanation": [
                "Rage clicks detected: 5 — user clicked the same area 5x rapidly.",
                "Scroll oscillation detected: 4 reversals — user unable to find target content.",
                "Repeated actions: 3 — action not producing expected result.",
            ],
            "predicted_issue": "HIGH",
            "prediction_reason": "Rage clicks (5) combined with scroll oscillation indicate severe navigation failure.",
            "action_taken": "AUTO_ROLLBACK_EXECUTED",
            "action_reason": "Prediction was HIGH severity. Auto-triggered rollback without human intervention.",
        },
        {
            "session_id": "demo-002",
            "timestamp": "2024-01-01T10:01:00",
            "rage_click_count": 1,
            "scroll_oscillation_detected": True,
            "scroll_oscillation_count": 2,
            "repeated_action_count": 0,
            "idle_seconds": 5.0,
            "cognitive_load_index": 44.44,
            "explanation": [
                "Scroll oscillation detected: 2 reversals.",
                "Idle hesitation: 5 seconds.",
            ],
            "predicted_issue": "MEDIUM",
            "prediction_reason": "Scroll oscillation + 5s idle. User searched, couldn't find content.",
            "action_taken": "MONITOR",
            "action_reason": "Flagged for monitoring. Will escalate if signals worsen.",
        },
        {
            "session_id": "demo-003",
            "timestamp": "2024-01-01T10:02:00",
            "rage_click_count": 0,
            "scroll_oscillation_detected": False,
            "scroll_oscillation_count": 0,
            "repeated_action_count": 0,
            "idle_seconds": 0.0,
            "cognitive_load_index": 3.33,
            "explanation": ["No significant confusion patterns detected in this batch."],
            "predicted_issue": "NONE",
            "prediction_reason": "All behavioral signals within normal range.",
            "action_taken": "NONE",
            "action_reason": "No action required.",
        },
    ][:limit]


def _mock_events(limit: int) -> list:
    """Return sample events so the dashboard works without MongoDB."""
    events = [
        {"session_id": "demo-001", "event_type": "rage_click",         "count": 3, "timestamp": "2024-01-01T10:00:00"},
        {"session_id": "demo-001", "event_type": "scroll_oscillation",  "count": 2, "timestamp": "2024-01-01T10:00:05"},
        {"session_id": "demo-001", "event_type": "repeated_action",     "count": 4, "timestamp": "2024-01-01T10:00:10"},
        {"session_id": "demo-002", "event_type": "idle",                "count": 1, "timestamp": "2024-01-01T10:01:00"},
        {"session_id": "demo-002", "event_type": "rage_click",          "count": 5, "timestamp": "2024-01-01T10:01:15"},
    ]
    return events[:limit]


def _mock_scores(limit: int) -> list:
    """Return sample scores so the dashboard works without MongoDB."""
    return [
        {"session_id": "demo-001", "score": 75.0, "timestamp": "2024-01-01T10:00:10"},
        {"session_id": "demo-002", "score": 88.5, "timestamp": "2024-01-01T10:01:15"},
        {"session_id": "demo-003", "score": 22.0, "timestamp": "2024-01-01T10:02:00"},
        {"session_id": "demo-004", "score": 55.5, "timestamp": "2024-01-01T10:03:00"},
        {"session_id": "demo-005", "score": 91.0, "timestamp": "2024-01-01T10:04:00"},
    ][:limit]
