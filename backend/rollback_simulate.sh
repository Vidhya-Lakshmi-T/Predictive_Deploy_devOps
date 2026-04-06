#!/bin/bash
# =============================================================================
# rollback_simulate.sh
# Simulates a deployment rollback.
# In production replace this with: kubectl rollout undo / git revert / etc.
# =============================================================================

SESSION_ID=${1:-"unknown"}
SCORE=${2:-"0"}
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "=============================================="
echo "  ROLLBACK EXECUTED"
echo "  Session   : $SESSION_ID"
echo "  Score     : $SCORE"
echo "  Time      : $TIMESTAMP"
echo "  Action    : Reverting to last stable build"
echo "=============================================="

# Simulate revert delay
sleep 1

echo "Previous stable version restored successfully."
echo "Users will be served v(N-1) until next safe deploy."
exit 0
