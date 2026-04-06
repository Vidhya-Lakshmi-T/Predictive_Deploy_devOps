from datetime import datetime, timedelta
from typing import Optional

COOLDOWN_SECONDS = 15


class CooldownManager:

    def __init__(self):
        self._sessions: dict = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def enter_cooldown(self, session_id: str, frozen_state: dict):
        now = datetime.utcnow()
        self._sessions[session_id] = {
            "rollback_at": now.isoformat(),
            "cooldown_until": (now + timedelta(seconds=COOLDOWN_SECONDS)).isoformat(),
            "frozen_state": frozen_state,
            "seconds_remaining": COOLDOWN_SECONDS,
        }

    def is_in_cooldown(self, session_id: str) -> bool:
        entry = self._sessions.get(session_id)
        if not entry:
            return False

        cooldown_until = datetime.fromisoformat(entry["cooldown_until"])

        if datetime.utcnow() < cooldown_until:
            return True

        # 🔥 EXPIRED → CLEANUP
        del self._sessions[session_id]
        return False

    def get_frozen_state(self, session_id: str) -> Optional[dict]:
        entry = self._sessions.get(session_id)
        if not entry:
            return None

        cooldown_until = datetime.fromisoformat(entry["cooldown_until"])

        # 🔥🔥 CRITICAL FIX — HANDLE EXPIRY
        if datetime.utcnow() >= cooldown_until:
            del self._sessions[session_id]
            return None

        seconds_left = max(0, (cooldown_until - datetime.utcnow()).total_seconds())

        result = dict(entry["frozen_state"])
        result["system_state"] = "COOLDOWN"
        result["cooldown_seconds_remaining"] = round(seconds_left, 1)
        result["rollback_at"] = entry["rollback_at"]
        result["cooldown_until"] = entry["cooldown_until"]

        return result

    def get_system_status(self) -> dict:
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
                # 🔥 CLEANUP EXPIRED
                del self._sessions[session_id]

        any_in_cooldown = len(active_cooldowns) > 0

        return {
            "any_in_cooldown": any_in_cooldown,
            "system_state": "COOLDOWN" if any_in_cooldown else "NORMAL",
            "active_cooldowns": active_cooldowns,
        }


cooldown_manager = CooldownManager()
