# =============================================================================
# rollback.py — Rollback Engine (v4 — switches active version file)
#
# What "rollback" actually means in this project:
#
#   BEFORE rollback:  users are served  app_v2_broken.html   (bad deployment)
#   AFTER  rollback:  users are served  app_v1_stable.html   (stable version)
#
# How it works:
#   The FastAPI /app endpoint reads a tiny file called "active_version.txt"
#   to know which HTML file to serve. Rollback just writes "v1" into that file.
#
#   This is a simple but REAL version switch — not just a log message.
#
# In production this would be:
#   - kubectl rollout undo deployment/app
#   - git revert + re-deploy
#   - AWS CodeDeploy switch target group
# =============================================================================

import logging
import os
from datetime import datetime
from confusion_engine import ROLLBACK_THRESHOLD
from database import insert_rollback_log

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("rollback.log"),
    ],
)
logger = logging.getLogger("rollback_engine")

# Path to the version control file (lives next to main.py in backend/)
VERSION_FILE = os.path.join(os.path.dirname(__file__), "..", "frontend", "active_version.txt")

# Version filenames
VERSIONS = {
    "v2": "app_v2_broken.html",    # the bad deployment
    "v1": "app_v1_stable.html",    # the stable version
}


# ── Version management ────────────────────────────────────────────────────────

def get_active_version() -> str:
    """Read which version is currently active. Default: v2 (the broken one)."""
    try:
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        # First run — default to v2 (simulate a bad deploy being live)
        set_active_version("v2")
        return "v2"


def set_active_version(version: str):
    """Write the active version to the control file."""
    os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
    with open(VERSION_FILE, "w") as f:
        f.write(version)
    logger.info(f"Active version set to: {version} ({VERSIONS.get(version, '?')})")


# ── Rollback trigger ──────────────────────────────────────────────────────────

def trigger_rollback(
    session_id: str,
    score: float,
    timestamp: str,
    reason: str = "",
    trigger_mode: str = "AUTO",
    trigger_source: str = "behavior-pipeline",
):
    """
    Execute rollback:
      1. Log the event
      2. Store in MongoDB
      3. Switch active version from v2 → v1
    """
    logger.warning("=" * 60)
    logger.warning("🚨 PREDICTIVE ROLLBACK TRIGGERED")
    logger.warning(f"   Session   : {session_id}")
    logger.warning(f"   Score     : {score}")
    logger.warning(f"   Threshold : {ROLLBACK_THRESHOLD}")
    logger.warning(f"   Reason    : {reason}")
    logger.warning(f"   Time      : {timestamp}")
    logger.warning("=" * 60)

    # Store rollback event
    insert_rollback_log({
        "session_id": session_id,
        "confusion_score": score,
        "threshold": ROLLBACK_THRESHOLD,
        "reason": reason,
        "timestamp": timestamp,
        "status": "executed",
        "trigger_mode": trigger_mode,
        "trigger_source": trigger_source,
        "manual_triggered": trigger_mode.upper() == "MANUAL",
        "rolled_back_from": "v2 (app_v2_broken.html)",
        "rolled_back_to":   "v1 (app_v1_stable.html)",
    })

    # ── THE ACTUAL VERSION SWITCH ─────────────────────────────────────────
    previous = get_active_version()
    set_active_version("v1")
    logger.info(f"Version switched: {previous} → v1 (stable)")
    logger.info("Users will now be served: app_v1_stable.html")
