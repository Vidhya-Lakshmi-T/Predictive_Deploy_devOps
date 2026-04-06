# =============================================================================
# cooldown_manager.py — Post-Rollback Cooldown State Manager
#
# Problem it solves:
#   After rollback triggers, the tracker keeps sending new (empty) batches,
#   which immediately reset the score to 0 — making the demo confusing.
#
# Solution:
#   A server-side cooldown registry. When a session enters COOLDOWN state:
#     - /track calls return frozen last-known state instead of recomputing
#     - No new rollback can fire for this session during cooldown
#     - After COOLDOWN_SECONDS, the session is released and resets normally
#
# This is intentionally simple: a plain dict with timestamps. No Redis needed.
# =============================================================================

from datetime import datetime, timedelta
from typing import Optional

# How long to hold the frozen rollback state before allowing reset
COOLDOWN_SECONDS = 15


class CooldownManager:
    """
    Tracks sessions that are in post-rollback cooldown.

    State per session:
        - rollback_at      : when rollback was triggered
        - frozen_state     : the last pipeline result to display during cooldown
        - cooldown_until   : timestamp when cooldown expires
    """

    def __init__(self):
        # session_id → { rollback_at, frozen_state, cooldown_until }
        self._sessions: dict = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def enter_cooldown(self, session_id: str, frozen_state: dict):
        """
        Put a session into cooldown with a frozen pipeline result.
        Called immediately when AUTO_ROLLBACK fires.
        """
        now = datetime.utcnow()
        self._sessions[session_id] = {
            "rollback_at": now.isoformat(),
            "cooldown_until": (now + timedelta(seconds=COOLDOWN_SECONDS)).isoformat(),
            "frozen_state": frozen_state,
            "seconds_remaining": COOLDOWN_SECONDS,
        }

    def is_in_cooldown(self, session_id: str) -> bool:
        """Return True if session is still within cooldown window."""
        entry = self._sessions.get(session_id)
        if not entry:
            return False
        cooldown_until = datetime.fromisoformat(entry["cooldown_until"])
        if datetime.utcnow() < cooldown_until:
            return True
        # Expired — remove entry
        del self._sessions[session_id]
        return False

    def get_frozen_state(self, session_id: str) -> Optional[dict]:
        """
        Return the frozen pipeline result for a session in cooldown.
        Includes live countdown for the UI.
        """
        entry = self._sessions.get(session_id)
        if not entry:
            return None

        cooldown_until = datetime.fromisoformat(entry["cooldown_until"])
        seconds_left = max(0, (cooldown_until - datetime.utcnow()).total_seconds())

        # Return a copy with updated countdown
        result = dict(entry["frozen_state"])
        result["system_state"] = "COOLDOWN"
        result["cooldown_seconds_remaining"] = round(seconds_left, 1)
        result["rollback_at"] = entry["rollback_at"]
        result["cooldown_until"] = entry["cooldown_until"]
        return result

    def get_system_status(self) -> dict:
        """
        Return system-wide status: which sessions are in cooldown.
        Used by the /status endpoint the dashboard polls.
        """
        active_cooldowns = []
        now = datetime.utcnow()

        for session_id, entry in list(self._sessions.items()):
            cooldown_until = datetime.fromisoformat(entry["cooldown_until"])
            if now < cooldown_until:
                seconds_left = round((cooldown_until - now).total_seconds(), 1)
                active_cooldowns.append({
                    "session_id": session_id,
                    "rollback_at": entry["rollback_at"],
                    "seconds_remaining": seconds_left,
                    "frozen_cli": entry["frozen_state"].get("cognitive_load_index", 0),
                    "predicted_issue": entry["frozen_state"].get("predicted_issue", "HIGH"),
                })
            else:
                del self._sessions[session_id]

        any_in_cooldown = len(active_cooldowns) > 0
        return {
            "any_in_cooldown": any_in_cooldown,
            "system_state": "COOLDOWN" if any_in_cooldown else "NORMAL",
            "active_cooldowns": active_cooldowns,
        }


# ── Module-level singleton ─────────────────────────────────────────────────────
# Shared across the FastAPI app lifetime. Simple and sufficient for demo scale.
cooldown_manager = CooldownManager()
