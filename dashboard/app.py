import time
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

API_BASE = f"http://{HOST}:8000"
ROLLBACK_THRESHOLD = 70
REFRESH_INTERVAL = 20
DISPLAY_TZ = ZoneInfo("Asia/Kolkata")

st.set_page_config(
    page_title="Predictive Deployment Control",
    page_icon="🧠",
    layout="wide",
)


def fetch(endpoint, fallback=None):
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=3)
        return r.json()
    except Exception:
        return fallback if fallback is not None else []


def format_ts(ts: str, with_seconds: bool = True) -> str:
    if not ts:
        return "-"
    try:
        parsed = pd.Timestamp(ts)
        if parsed.tzinfo is None:
            parsed = parsed.tz_localize("UTC")
        local = parsed.tz_convert(DISPLAY_TZ)
        pattern = "%Y-%m-%d %I:%M:%S %p IST" if with_seconds else "%Y-%m-%d %I:%M %p IST"
        return local.strftime(pattern)
    except Exception:
        return ts


def rollback_kind(rb: dict) -> str:
    return "MANUAL" if rb.get("manual_triggered") or rb.get("trigger_mode") == "MANUAL" else "AUTO"


def version_status_label(version_info: dict) -> str:
    return "v1 Stable" if version_info.get("is_stable", False) else "v2 Broken"


patterns_list = fetch("/patterns?limit=20", fallback=[])
rollbacks_list = fetch("/rollbacks?limit=10", fallback=[])
history = fetch("/score/history?limit=60", fallback=[])
latest_score = fetch("/score/latest", fallback={"score": 0})
version_info = fetch("/version", fallback={"active_version": "v2", "is_stable": False})
last_rollback = fetch("/last-rollback", fallback={"has_rollback": False})

latest_pattern = patterns_list[0] if patterns_list else {}
cli_score = latest_score.get("score", 0)
has_rollback = last_rollback.get("has_rollback", False)

st.title("Predictive Deployment Control")
st.caption("User Behavior -> Pattern Detection -> Prediction -> Autonomous Action")

st.markdown(
    """
<div style="background:#1e1e2e;padding:10px 18px;border-radius:8px;margin-bottom:1rem;font-family:monospace;font-size:12px;color:#cdd6f4">
  <span style="color:#89b4fa">BEHAVIOR</span>
  <span style="color:#6c7086"> -> </span>
  <span style="color:#a6e3a1">DETECTION</span>
  <span style="color:#6c7086"> -> </span>
  <span style="color:#fab387">PREDICTION</span>
  <span style="color:#6c7086"> -> </span>
  <span style="color:#f38ba8">ROLLBACK</span>
  <span style="color:#6c7086"> -> </span>
  <span style="color:#a6e3a1">STABLE VERSION LIVE</span>
</div>
""",
    unsafe_allow_html=True,
)

c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    icon = "RED" if cli_score >= 70 else "AMBER" if cli_score >= 40 else "GREEN"
    st.metric("Cognitive Load Index", f"{icon} {cli_score:.1f} / 100", delta=f"Threshold: {ROLLBACK_THRESHOLD}", delta_color="inverse")

with c2:
    pred = latest_pattern.get("predicted_issue", "NONE")
    st.metric("Prediction", pred)

with c3:
    action = latest_pattern.get("action_taken", "NONE")
    st.metric("System Decision", "AUTO ROLLBACK" if "ROLLBACK" in action else action)

with c4:
    st.metric("Total Rollbacks", len(rollbacks_list))

with c5:
    is_stable = version_info.get("is_stable", False)
    st.metric(
        "Active Version",
        version_status_label(version_info),
        delta="Stable live" if is_stable else "Broken live",
        delta_color="normal" if is_stable else "inverse",
    )

st.divider()

if has_rollback:
    rb = last_rollback
    rb_kind = rollback_kind(rb)
    is_manual_rb = rb_kind == "MANUAL"
    header_title = "MANUAL ROLLBACK EXECUTED" if is_manual_rb else "AUTO ROLLBACK EXECUTED"
    header_subtitle = (
        "Manual override restored the stable version"
        if is_manual_rb
        else "System detected high user confusion and automatically restored the stable version"
    )

    st.markdown(
        f"""
<div style="background:#1a1a1a;border:2px solid #fc8181;border-radius:12px;padding:0;margin-bottom:1.2rem;overflow:hidden">
  <div style="background:#742a2a;padding:12px 20px;display:flex;align-items:center;gap:10px">
    <span style="font-size:18px">ALERT</span>
    <div>
      <div style="color:#fc8181;font-size:15px;font-weight:700">{header_title}</div>
      <div style="color:#feb2b2;font-size:12px">{header_subtitle}</div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    left_info, right_info = st.columns(2)

    with left_info:
        st.markdown("#### What Happened")
        steps = [
            (
                "What the user did",
                (
                    f"User showed confusion signals. Cognitive Load Index reached **{rb.get('confusion_score', cli_score):.1f}/100** and crossed the rollback threshold."
                    if not is_manual_rb
                    else "A manual override was requested after the deployment was judged unsafe or unsuitable for users."
                ),
            ),
            (
                "What the system detected",
                (
                    "Behavior patterns such as rage clicks, scroll oscillation, repeated failed actions, or idle hesitation indicated a broken experience."
                    if not is_manual_rb
                    else "The rollback log records this as a manual intervention instead of an autonomous confusion-triggered rollback."
                ),
            ),
            (
                "What was decided",
                (
                    "The system classified the issue as HIGH severity and prepared an automatic rollback."
                    if not is_manual_rb
                    else "Operators bypassed automatic prediction and restored the previous stable build directly."
                ),
            ),
            (
                "What action was taken",
                (
                    "AUTO rollback replaced the bad deployment with the last known stable version."
                    if not is_manual_rb
                    else "MANUAL rollback replaced the bad deployment with the last known stable version."
                ),
            ),
            (
                "What is stable now",
                "The stable frontend is now live again and monitoring continues for new sessions.",
            ),
        ]

        for label, text in steps:
            st.markdown(f"**{label}**")
            st.markdown(
                f"<div style='font-size:13px;color:#4a5568;padding-left:12px;margin-bottom:10px;line-height:1.6'>{text}</div>",
                unsafe_allow_html=True,
            )

    with right_info:
        st.markdown("#### Rollback Summary")
        st.info(
            (
                f"User struggled with the UI -> score reached {rb.get('confusion_score', cli_score):.1f} -> automatic rollback executed -> stable version restored -> monitoring continues."
                if not is_manual_rb
                else "Manual rollback requested -> stable version restored -> monitoring continues."
            )
        )

        st.markdown("#### Rollback Details")
        st.markdown(
            f"""
| Field | Value |
|---|---|
| Session | `{rb.get('session_id', '?')[:22]}` |
| Trigger mode | {rb_kind} |
| Trigger source | {rb.get('trigger_source', '-')} |
| Score at trigger | {rb.get('confusion_score', 0):.1f} / 100 |
| Threshold | {rb.get('threshold', ROLLBACK_THRESHOLD)} |
| Time | {format_ts(rb.get('timestamp', ''))} |
| Status | {rb.get('status', 'triggered')} |
"""
        )

        st.markdown("#### What This Means")
        st.success(
            "Stable version is live and monitoring continues.\n\n"
            + (
                "This event was behavior-triggered, so it demonstrates the autonomous rollback path."
                if not is_manual_rb
                else "This event was manual, so it should not be interpreted as an autonomous model decision."
            )
        )

        st.markdown("#### The Actual Version Switch")
        before_col, after_col = st.columns(2)
        with before_col:
            st.error("Before rollback\n\nFile: `app_v2_broken.html`\n\nBroken checkout flow\n\nMultiple confusing actions")
        with after_col:
            st.success("After rollback\n\nFile: `app_v1_stable.html`\n\nSingle successful checkout\n\nStable purchase flow")

        st.info("Open `http://localhost:8000/app` to view the active switched frontend, not just the operator console.")

        if st.button("Reset Demo To Broken v2", use_container_width=True):
            try:
                r = requests.post(f"{API_BASE}/reset-version", timeout=3)
                if r.status_code == 200:
                    st.success("Demo reset. Broken v2 is live again.")
                else:
                    st.error("Reset failed.")
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()

left, right = st.columns([1.4, 1])

with left:
    st.subheader("Detected Behavior Patterns")
    if latest_pattern:
        rage = latest_pattern.get("rage_click_count", 0)
        scroll = latest_pattern.get("scroll_oscillation_detected", False)
        scroll_count = latest_pattern.get("scroll_oscillation_count", 0)
        repeated = latest_pattern.get("repeated_action_count", 0)
        idle_s = latest_pattern.get("idle_seconds", 0.0)

        pc1, pc2, pc3, pc4 = st.columns(4)
        pc1.metric("Rage Clicks", rage)
        pc2.metric("Scroll Osc.", "YES" if scroll else "NO", delta=f"{scroll_count} reversals" if scroll else None)
        pc3.metric("Repeated Actions", repeated)
        pc4.metric("Idle Time", f"{idle_s:.0f}s")
    else:
        st.info("No behavior data yet. Open the demo page and interact.")

    st.subheader("Why The Score Changed")
    if latest_pattern:
        for exp in latest_pattern.get("explanation", []):
            st.write(f"- {exp}")
    else:
        st.info("No explanations yet.")

    st.subheader("Cognitive Load Index History")
    if history:
        df = pd.DataFrame(history)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").dt.tz_convert(DISPLAY_TZ)
        df = df.sort_values("timestamp")
        df["Rollback Threshold"] = ROLLBACK_THRESHOLD
        df = df.rename(columns={"score": "Cognitive Load Index"})
        st.line_chart(df.set_index("timestamp")[["Cognitive Load Index", "Rollback Threshold"]], color=["#3b82f6", "#ef4444"], height=220)
        if rollbacks_list:
            rb_times = [format_ts(r.get("timestamp", ""), with_seconds=False) for r in rollbacks_list[:3]]
            st.caption(f"Rollback events at: {', '.join(rb_times)}")
    else:
        st.info("No history yet.")

with right:
    st.subheader("Prediction Status")
    if latest_pattern:
        pi = latest_pattern.get("predicted_issue", "NONE")
        reason = latest_pattern.get("prediction_reason", "")
        if pi == "HIGH":
            st.error("HIGH")
        elif pi == "MEDIUM":
            st.warning("MEDIUM")
        elif pi == "LOW":
            st.info("LOW")
        else:
            st.success("NONE")
        if reason:
            st.caption(reason)
    else:
        st.success("No predictions yet.")

    st.subheader("System Decision")
    if latest_pattern:
        act = latest_pattern.get("action_taken", "NONE")
        act_reason = latest_pattern.get("action_reason", "")
        if "ROLLBACK" in act:
            st.error("AUTO ROLLBACK EXECUTED")
        elif act == "MONITOR":
            st.warning("MONITORING")
        else:
            st.success("NO ACTION REQUIRED")
        if act_reason:
            with st.expander("Full decision reason"):
                st.write(act_reason)
    else:
        st.success("No action taken yet.")

    st.divider()

    st.subheader("Rollback Actions Log")
    if rollbacks_list:
        for rb in rollbacks_list[:6]:
            score_val = rb.get("confusion_score", 0)
            ts = format_ts(rb.get("timestamp", ""))
            sid = rb.get("session_id", "?")[:20]
            kind = rollback_kind(rb)
            with st.expander(f"{kind} | score {score_val:.1f} | {ts}"):
                st.write(f"**Session:** `{sid}`")
                st.write(f"**Trigger mode:** {kind}")
                st.write(f"**Trigger source:** {rb.get('trigger_source', '-')}")
                st.write(f"**Score at trigger:** {score_val:.1f} / 100")
                st.write(f"**Threshold:** {rb.get('threshold', ROLLBACK_THRESHOLD)}")
                st.write(f"**Reason:** {rb.get('reason', 'N/A')}")
                st.write(f"**Rolled back from:** {rb.get('rolled_back_from', '-')}")
                st.write(f"**Rolled back to:** {rb.get('rolled_back_to', '-')}")
    else:
        st.success("No rollbacks yet.")

    st.divider()
    st.caption("Manual override")
    if st.button("Force Rollback Now", type="primary", use_container_width=True):
        try:
            r = requests.post(f"{API_BASE}/rollback?session_id=manual-dashboard", timeout=3)
            if r.status_code == 200:
                st.success("Manual rollback logged and stable version restored.")
            else:
                st.error("Failed.")
        except Exception as e:
            st.error(f"API unreachable: {e}")

st.divider()
st.subheader("Full Pattern Analysis Log")
if patterns_list:
    rows = [
        {
            "Time (IST)": format_ts(p.get("timestamp", "")),
            "Session": p.get("session_id", "")[:18],
            "CLI Score": p.get("cognitive_load_index", 0),
            "Rage": p.get("rage_click_count", 0),
            "Scroll Osc": "Yes" if p.get("scroll_oscillation_detected") else "No",
            "Repeated": p.get("repeated_action_count", 0),
            "Idle(s)": p.get("idle_seconds", 0),
            "Prediction": p.get("predicted_issue", "NONE"),
            "Action": p.get("action_taken", "NONE"),
        }
        for p in patterns_list
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("No pattern records yet.")

with st.expander("Raw Event Feed"):
    evs = fetch("/events?limit=30", fallback=[])
    if evs:
        df_ev = pd.DataFrame(evs)
        if "timestamp" in df_ev.columns:
            df_ev["timestamp"] = df_ev["timestamp"].apply(format_ts)
            df_ev = df_ev.rename(columns={"timestamp": "timestamp_ist"})
        cols = [c for c in ["timestamp_ist", "session_id", "event_type", "count"] if c in df_ev.columns]
        st.dataframe(df_ev[cols], use_container_width=True, hide_index=True)
    else:
        st.info("No events yet.")

st.caption(f"Auto-refreshing every {REFRESH_INTERVAL}s | API: {API_BASE} | Display timezone: Asia/Kolkata")
time.sleep(REFRESH_INTERVAL)
st.rerun()
