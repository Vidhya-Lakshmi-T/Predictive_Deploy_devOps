/**
 * tracker.js — User Confusion Signal Tracker (v4 — simple and clear)
 *
 * What changed from v3:
 *   - Removed ALL cooldown logic and timers
 *   - Removed frozen state / session reset
 *   - After rollback: UI locks on last result, shows what happened clearly
 *   - Banner stays visible permanently (user dismisses manually or sees dashboard)
 *   - No confusion about timers or resets
 *
 * Signals tracked:
 *   rage_click         — 3+ rapid clicks in same area
 *   scroll_oscillation — 3+ up-down scroll reversals
 *   repeated_action    — same button clicked 3+ times
 *   idle               — no interaction for 5+ seconds
 */

(function () {
  "use strict";

  const API_ENDPOINT        = "http://40.80.93.95:8000/track";
  const SEND_INTERVAL_MS    = 5000;
  const RAGE_CLICK_WINDOW   = 1000;
  const RAGE_CLICK_THRESH   = 3;
  const IDLE_MS             = 5000;
  const SCROLL_THRESH       = 3;

  // ── Session ──────────────────────────────────────────────────────────────
  let SESSION_ID = sessionStorage.getItem("confusion_session_id")
                   || (() => {
                        const id = "sess-" + Math.random().toString(36).substr(2, 9);
                        sessionStorage.setItem("confusion_session_id", id);
                        return id;
                      })();

  // ── After rollback: lock the display, stop sending new batches ───────────
  // This is the only state flag — no cooldown, no timer, no countdown.
  let rollbackFired = false;

  // ── Event counters ────────────────────────────────────────────────────────
  const counts = { rage_click: 0, scroll_oscillation: 0, repeated_action: 0, idle: 0 };

  // ── Rage Click Detection ──────────────────────────────────────────────────
  let clicks = [];
  document.addEventListener("click", function (e) {
    if (rollbackFired) return;
    const now = Date.now();
    clicks.push({ time: now, x: e.clientX, y: e.clientY });
    clicks = clicks.filter(c => now - c.time < RAGE_CLICK_WINDOW);
    if (clicks.length >= RAGE_CLICK_THRESH) {
      const f = clicks[0];
      if (clicks.every(c => Math.abs(c.x - f.x) < 50 && Math.abs(c.y - f.y) < 50)) {
        counts.rage_click++;
        log("Rage click detected (" + counts.rage_click + " total)");
        clicks = [];
      }
    }
  });

  // ── Scroll Oscillation Detection ──────────────────────────────────────────
  let lastY = window.scrollY, lastDir = null, dirChanges = 0;
  window.addEventListener("scroll", function () {
    if (rollbackFired) return;
    const cur = window.scrollY;
    const dir = cur > lastY ? "down" : "up";
    if (lastDir && dir !== lastDir) {
      dirChanges++;
      if (dirChanges >= SCROLL_THRESH) {
        counts.scroll_oscillation++;
        log("Scroll oscillation detected");
        dirChanges = 0;
      }
    }
    lastDir = dir;
    lastY = cur;
  });

  // ── Repeated Action Detection ─────────────────────────────────────────────
  const btnCounts = {};
  document.addEventListener("click", function (e) {
    if (rollbackFired) return;
    const t = e.target.closest("button, a, [data-action]");
    if (!t) return;
    const key = t.id || t.innerText.trim().substring(0, 30);
    if (!key) return;
    btnCounts[key] = (btnCounts[key] || 0) + 1;
    if (btnCounts[key] === 3) {
      counts.repeated_action++;
      log("Repeated action detected on: " + key);
    }
    setTimeout(() => delete btnCounts[key], 30000);
  });

  // ── Idle Detection ────────────────────────────────────────────────────────
  let idleTimer = null;
  function resetIdle() {
    if (rollbackFired) return;
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      counts.idle++;
      log("Idle hesitation detected");
    }, IDLE_MS);
  }
  ["mousemove","keydown","scroll","click","touchstart"]
    .forEach(ev => document.addEventListener(ev, resetIdle, { passive: true }));
  resetIdle();

  // ── Batch Sender ──────────────────────────────────────────────────────────
  async function sendBatch() {
    if (rollbackFired) return;

    const events = Object.entries(counts)
      .filter(([, v]) => v > 0)
      .map(([event_type, count]) => ({
        session_id: SESSION_ID, event_type, count,
        metadata: { url: window.location.pathname },
      }));

    if (events.length === 0) return;

    try {
      const res  = await fetch(API_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: SESSION_ID, events }),
      });
      const data = await res.json();

      // Always reset counts after a successful send
      Object.keys(counts).forEach(k => counts[k] = 0);

      // Update live pipeline display
      updatePipelineDisplay(data);

      if (data.rollback_triggered) {
        rollbackFired = true;                     // stop further sends
        showRollbackState(data);                  // lock UI on rollback state
        log("🚨 ROLLBACK EXECUTED — display locked on final state");
      }

    } catch (err) {
      log("Send error: " + err.message);
    }
  }

  setInterval(sendBatch, SEND_INTERVAL_MS);
  window.addEventListener("beforeunload", sendBatch);

  // ── UI: Live Pipeline Panel ───────────────────────────────────────────────
  function updatePipelineDisplay(data) {
    const panel = document.getElementById("pipeline-display");
    if (!panel) return;

    const cli    = data.cognitive_load_index || 0;
    const issue  = data.predicted_issue  || "NONE";
    const action = data.action_taken     || "NONE";
    const dp     = data.detected_patterns || {};

    const cliColor    = cli >= 70 ? "#fc8181" : cli >= 40 ? "#f6ad55" : "#9ae6b4";
    const issueColor  = { HIGH:"#fc8181", MEDIUM:"#f6ad55", LOW:"#faf089", NONE:"#9ae6b4" }[issue] || "#e2e8f0";
    const actionColor = action.includes("ROLLBACK") ? "#fc8181" : action === "MONITOR" ? "#f6ad55" : "#9ae6b4";

    panel.innerHTML = `
      <div style="margin-bottom:12px">
        <div style="color:#90cdf4;font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">Step 1 — Detected signals</div>
        <div style="font-size:12px;line-height:1.8">
          Rage clicks: <b style="color:${(dp.rage_click_count||0)>3?'#fc8181':'#e2e8f0'}">${dp.rage_click_count||0}</b>
          &nbsp;|&nbsp;
          Scroll osc: <b style="color:${dp.scroll_oscillation_detected?'#fc8181':'#9ae6b4'}">${dp.scroll_oscillation_detected?"YES":"NO"}</b>
          &nbsp;|&nbsp;
          Repeated: <b style="color:${(dp.repeated_action_count||0)>2?'#f6ad55':'#e2e8f0'}">${dp.repeated_action_count||0}</b>
          &nbsp;|&nbsp;
          Idle: <b>${dp.idle_seconds||0}s</b>
        </div>
      </div>

      <div style="margin-bottom:12px">
        <div style="color:#90cdf4;font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">Step 2 — Cognitive Load Index</div>
        <span style="font-size:28px;font-weight:700;color:${cliColor}">${cli.toFixed(1)}</span>
        <span style="font-size:12px;color:#718096"> / 100 &nbsp;(threshold: 70)</span>
      </div>

      <div style="margin-bottom:12px">
        <div style="color:#90cdf4;font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">Step 3 — Explanation</div>
        ${(data.explanation||["No significant patterns yet."]).map(e =>
          `<div style="font-size:11px;color:#e2e8f0;line-height:1.6;margin-bottom:2px">• ${e}</div>`
        ).join("")}
      </div>

      <div style="margin-bottom:12px">
        <div style="color:#90cdf4;font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">Step 4 — Prediction</div>
        <span style="background:${issueColor};color:#1a1a1a;padding:3px 14px;border-radius:99px;font-size:13px;font-weight:700">${issue}</span>
        <div style="font-size:11px;color:#a0aec0;margin-top:5px;line-height:1.5">${data.prediction_reason||""}</div>
      </div>

      <div style="margin-bottom:12px">
        <div style="color:#90cdf4;font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">Step 5 — System action</div>
        <span style="background:${actionColor};color:#1a1a1a;padding:3px 14px;border-radius:99px;font-size:13px;font-weight:700">${action}</span>
        <div style="font-size:11px;color:#a0aec0;margin-top:5px;line-height:1.5">${data.action_reason||""}</div>
      </div>

      ${data.status_message ? `
        <div style="background:#2d3748;border-radius:6px;padding:8px 12px;font-size:11px;color:#e2e8f0;line-height:1.6">
          ${data.status_message}
        </div>` : ""}
    `;
  }

  // ── UI: Post-Rollback Locked State ────────────────────────────────────────
  // Called once when rollback fires. Updates the panel AND shows the
  // "what happened after rollback" explanation block clearly.
  function showRollbackState(data) {
    // 1. Update main pipeline panel with final values
    updatePipelineDisplay(data);

    // 2. Show the rollback banner (persistent — no auto-dismiss)
    showRollbackBanner(data.status_message || "AUTO ROLLBACK EXECUTED");

    // 3. Show the "what happened after rollback" explanation
    const wh = data.what_happened_after_rollback;
    if (wh) showPostRollbackExplanation(wh);

    // 4. Update the page header state badge if it exists
    const badge = document.getElementById("state-badge");
    if (badge) {
      badge.textContent = "🚨 ROLLED BACK";
      badge.style.background = "#742a2a";
      badge.style.color = "#fc8181";
    }
  }

  // ── UI: Rollback Banner (persistent until user sees it) ───────────────────
  function showRollbackBanner(message) {
    let b = document.getElementById("rollback-banner");
    if (!b) {
      b = document.createElement("div");
      b.id = "rollback-banner";
      b.style.cssText = `
        position:fixed;top:0;left:0;width:100%;z-index:99999;
        background:#c53030;color:#fff;font-family:system-ui,sans-serif;
        padding:14px 24px;display:flex;align-items:center;
        justify-content:space-between;box-shadow:0 2px 12px rgba(0,0,0,.4);
      `;
      document.body.prepend(b);
    }
    b.innerHTML = `
      <div>
        <div style="font-size:15px;font-weight:700">🚨 AUTO ROLLBACK EXECUTED</div>
        <div style="font-size:12px;margin-top:3px;opacity:.9">${message}</div>
      </div>
      <div style="font-size:12px;background:rgba(255,255,255,.15);padding:6px 14px;border-radius:6px;cursor:pointer"
           onclick="this.parentElement.style.display='none'">Dismiss ✕</div>
    `;
  }

  // ── UI: Post-Rollback Explanation Block ───────────────────────────────────
  // Shows a clear plain-English 5-step card explaining exactly what happened.
  function showPostRollbackExplanation(wh) {
    let card = document.getElementById("post-rollback-card");
    if (!card) {
      card = document.createElement("div");
      card.id = "post-rollback-card";
      card.style.cssText = `
        position:fixed;bottom:16px;right:16px;width:420px;
        background:#1a202c;border:2px solid #fc8181;border-radius:12px;
        padding:18px 20px;z-index:99998;
        font-family:system-ui,sans-serif;box-shadow:0 4px 24px rgba(0,0,0,.5);
      `;
      document.body.appendChild(card);
    }

    const steps = [
      { icon: "🖱️", label: "What user did",         text: wh.step_1_what_user_did },
      { icon: "📊", label: "What system detected",   text: wh.step_2_what_system_saw },
      { icon: "🎯", label: "What was predicted",     text: wh.step_3_what_was_predicted },
      { icon: "⚡", label: "What action was taken",  text: wh.step_4_what_action_was_taken },
      { icon: "✅", label: "What is stable now",     text: wh.step_5_what_is_stable_now },
    ];

    card.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
        <div style="color:#fc8181;font-size:13px;font-weight:700">What Happened After Rollback</div>
        <div style="color:#718096;font-size:11px;cursor:pointer"
             onclick="this.parentElement.parentElement.style.display='none'">✕ close</div>
      </div>

      ${steps.map((s, i) => `
        <div style="display:flex;gap:10px;margin-bottom:10px;padding-bottom:10px;
                    ${i < steps.length - 1 ? 'border-bottom:1px solid #2d3748' : ''}">
          <div style="font-size:16px;min-width:22px;padding-top:1px">${s.icon}</div>
          <div>
            <div style="color:#90cdf4;font-size:10px;text-transform:uppercase;
                        letter-spacing:.07em;margin-bottom:2px">${s.label}</div>
            <div style="color:#e2e8f0;font-size:12px;line-height:1.6">${s.text}</div>
          </div>
        </div>
      `).join("")}

      <div style="background:#742a2a;border-radius:6px;padding:8px 12px;margin-top:4px">
        <div style="color:#feb2b2;font-size:10px;text-transform:uppercase;
                    letter-spacing:.07em;margin-bottom:3px">Plain summary</div>
        <div style="color:#fed7d7;font-size:11px;line-height:1.7">${wh.plain_summary}</div>
      </div>
    `;
  }

  // ── Debug log helper ──────────────────────────────────────────────────────
  function log(msg) {
    console.debug("[Tracker] " + msg);
    const el = document.getElementById("debug-log");
    if (el) {
      el.textContent += "[" + new Date().toLocaleTimeString() + "] " + msg + "\n";
      el.scrollTop = el.scrollHeight;
    }
  }

  // ── Expose for force-demo button in index.html ────────────────────────────
  window._trackerGetSession  = () => SESSION_ID;
  window._trackerForceUpdate = updatePipelineDisplay;
  window._trackerShowRollback = showRollbackState;

  log("v4 loaded. Session: " + SESSION_ID);

})();
