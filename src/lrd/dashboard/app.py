"""Main dashboard — dark Model-Guard-style UI.

Sections (top to bottom):
  1. Sidebar nav   (option_menu)
  2. Summary cards (Active Models · Latest Alert · Drift Indicators)
  3. Recent Activity + Recent Slack Alerts (two-column)
  4. Performance & Drift over time (Plotly)
  5. Latest Regression Analysis + side-by-side diff
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# make src/ importable when run via `streamlit run`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402
from streamlit_option_menu import option_menu  # noqa: E402

from lrd.dashboard.data import (  # noqa: E402
    DEFAULT_DB,
    latest_regression,
    list_alerts,
    list_runs,
    perf_history,
    summary_stats,
)
from lrd.dashboard.theme import COLORS, inject_css  # noqa: E402

# ─── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Model Guard — LLM Regression Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()


# ─── Sidebar nav ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<h2 style='color:#06B6D4; padding: 4px 0 16px 0; margin: 0;'>"
        "🛡️ Model Guard</h2>",
        unsafe_allow_html=True,
    )
    selected = option_menu(
        menu_title=None,
        options=["Dashboard", "Runs", "Alerts", "Settings"],
        icons=["speedometer2", "list-task", "bell-fill", "gear"],
        default_index=0,
        styles={
            "container": {"padding": "0", "background": COLORS["sidebar_bg"]},
            "icon": {"color": COLORS["accent"], "font-size": "16px"},
            "nav-link": {
                "color": COLORS["text"],
                "font-size": "14px",
                "padding": "10px 12px",
                "border-radius": "6px",
                "--hover-color": COLORS["card_hover"],
            },
            "nav-link-selected": {
                "background-color": COLORS["accent_dim"],
                "color": "white",
                "font-weight": "500",
            },
        },
    )

    st.markdown(
        f"<p style='color:{COLORS['muted']}; font-size: 0.7rem; "
        f"margin-top: 24px;'>v0.1.0 · Phase 3 · {DEFAULT_DB.name}</p>",
        unsafe_allow_html=True,
    )


# ─── Reusable HTML helpers ──────────────────────────────────────────────────
def html(s: str) -> None:
    st.markdown(s, unsafe_allow_html=True)


def stat_card(label: str, value: str, sub: str = "", color: str = "") -> str:
    color_cls = f" {color}" if color else ""
    sub_html = f"<div class='lrd-stat-sub'>{sub}</div>" if sub else ""
    return (
        f"<div class='lrd-card'>"
        f"<div class='lrd-stat-label'>{label}</div>"
        f"<div class='lrd-stat-value{color_cls}'>{value}</div>"
        f"{sub_html}"
        f"</div>"
    )


def pill(text: str, kind: str = "info") -> str:
    return f"<span class='lrd-pill {kind}'>{text}</span>"


# ─── Page: Dashboard ────────────────────────────────────────────────────────
def page_dashboard():
    st.markdown("## Dashboard: Model Guard")
    st.caption("CI/CD for LLM behavior — golden-set regression detection")

    stats = summary_stats(DEFAULT_DB)

    # ── Row 1: 3 summary cards + recent alerts side panel ──
    main_col, side_col = st.columns([3, 1.3], gap="medium")

    with main_col:
        st.markdown("#### Summary")
        c1, c2, c3 = st.columns(3)
        with c1:
            html(stat_card(
                "ACTIVE MODELS MONITORED",
                str(stats["active_models"]),
                color="cyan",
            ))
        with c2:
            sev = stats["latest_severity"]
            color = "red" if sev == "Critical" else ("warn" if sev == "Degraded" else "")
            html(stat_card(
                "LATEST REGRESSION ALERT",
                sev if sev else "—",
                color=color,
            ))
        with c3:
            drift = stats["drift_30d"]
            color = "warn" if drift > 0 else ""
            html(stat_card(
                "DRIFT INDICATORS (30 days)",
                f"{drift} flagged" if drift else "0 flagged",
                color=color,
            ))

        # ── Recent Activity ──
        st.markdown("#### Recent Activity")
        runs = list_runs(DEFAULT_DB, limit=8)
        rows_html = ""
        for r in runs:
            rate = (r["n_passed"] or 0) / max(r["n_cases"] or 1, 1)
            ok = rate >= 0.99
            dot = "ok" if ok else "err"
            verdict_pill = pill("PASS Tests Passed", "ok") if ok else \
                pill(f"REGRESSION: {r['n_cases'] - r['n_passed']} fail", "err")
            ts = str(r["started_at"])[:19] if r["started_at"] else ""
            label = f"{r['sut_name']} — run <code style='color:{COLORS['muted']}'>{r['run_id'][:8]}</code>"
            rows_html += (
                f"<div class='lrd-act-row'>"
                f"  <div class='lrd-act-dot {dot}'></div>"
                f"  <div class='lrd-act-text'>{label}<br>"
                f"    <span class='lrd-act-meta'>{ts}</span></div>"
                f"  <div>{verdict_pill}</div>"
                f"</div>"
            )
        if not rows_html:
            rows_html = (
                f"<div class='lrd-act-row'><div class='lrd-act-text' "
                f"style='color:{COLORS['muted']}'>No runs yet — try `make run`</div></div>"
            )
        html(f"<div class='lrd-card' style='padding: 0; padding: 8px 4px;'>{rows_html}</div>")

    # ── Right: Recent Slack Alerts panel ──
    with side_col:
        st.markdown("#### Recent Slack Alerts")
        alerts = list_alerts(limit=4)
        if not alerts:
            html(
                f"<div class='lrd-card'>"
                f"<div style='color:{COLORS['muted']}; font-size:0.86rem;'>"
                f"No alerts yet. They appear here when a run regresses vs baseline.</div>"
                f"</div>"
            )
        else:
            inner = ""
            for a in alerts:
                ts = a["mtime"].strftime("%Y-%m-%d %H:%M UTC")
                inner += (
                    f"<div class='lrd-alert-row'>"
                    f"  <div>{pill('CRITICAL', 'err')} "
                    f"     <span class='lrd-alert-title' style='margin-left:6px'>"
                    f"        Model Guard: {a['sut_name'] or 'unknown'}</span></div>"
                    f"  <div class='lrd-alert-body'>{a['text'][:120]}</div>"
                    f"  <div class='lrd-alert-time'>{ts}</div>"
                    f"</div>"
                )
            html(f"<div class='lrd-card'>{inner}</div>")

    # ── Performance & Drift Over Time ──
    st.markdown("#### Performance & Drift Over Time")
    series = perf_history(DEFAULT_DB, limit=50)
    if not series:
        html(
            f"<div class='lrd-card'><div style='color:{COLORS['muted']}'>"
            f"No history yet — run a few golden sets to populate the chart.</div></div>"
        )
    else:
        fig = go.Figure()
        # group by SUT
        by_sut: dict[str, list[dict]] = {}
        for s in series:
            by_sut.setdefault(s["sut_name"] or "?", []).append(s)
        palette = [COLORS["accent"], "#A78BFA", COLORS["ok"], COLORS["warn"]]
        for i, (sut, points) in enumerate(by_sut.items()):
            fig.add_trace(go.Scatter(
                x=[p["started_at"] for p in points],
                y=[p["avg_score"] * 100 for p in points],
                mode="lines+markers",
                name=sut,
                line=dict(color=palette[i % len(palette)], width=2.5),
                marker=dict(size=6),
                hovertemplate="<b>%{x}</b><br>avg score: %{y:.1f}%<extra></extra>",
            ))
        # threshold dashed line at 80% (default)
        if series:
            fig.add_hline(
                y=80, line_dash="dash", line_color=COLORS["warn"],
                annotation_text="threshold 80%", annotation_position="bottom right",
                annotation_font_color=COLORS["warn"],
            )
        fig.update_layout(
            plot_bgcolor=COLORS["card"],
            paper_bgcolor=COLORS["card"],
            font=dict(color=COLORS["text"]),
            margin=dict(l=20, r=20, t=10, b=30),
            height=320,
            hovermode="x unified",
            yaxis=dict(
                title="Avg score (%)",
                gridcolor=COLORS["border"],
                range=[0, 105],
            ),
            xaxis=dict(gridcolor=COLORS["border"]),
            legend=dict(bgcolor=COLORS["card"], bordercolor=COLORS["border"]),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Latest Regression Analysis + Diff ──
    st.markdown("#### Latest Regression Analysis")
    reg = latest_regression(DEFAULT_DB)
    if not reg:
        html(
            f"<div class='lrd-card'><div style='color:{COLORS['muted']}'>"
            f"No regressions detected in any run pair. Break a prompt to see this card "
            f"come alive.</div></div>"
        )
    else:
        delta = (reg.avg_score_current - reg.avg_score_baseline) * 100
        delta_str = f"{delta:+.0f}%"
        meta = (
            f"<b>Model:</b> {reg.sut_name} · "
            f"<b>Run:</b> <code>{reg.current_run_id}</code> · "
            f"<b>Status:</b> {pill('REGRESSION', 'err')} · "
            f"<b>Quality:</b> {reg.pass_rate_current * 100:.0f}% "
            f"<span style='color:{COLORS['err']}'>({delta_str})</span>"
        )
        html(f"<div class='lrd-card'>{meta}</div>")

        col_prev, col_curr = st.columns(2)
        with col_prev:
            html(
                f"<div class='lrd-diff-label'>PREVIOUS OUTPUT (baseline {reg.baseline_run_id[:8]} · case {reg.case_id})</div>"
                f"<div class='lrd-diff-prev'>{(reg.previous_output or '(empty)')[:1200]}</div>"
            )
        with col_curr:
            html(
                f"<div class='lrd-diff-label'>CURRENT OUTPUT (run {reg.current_run_id[:8]} · same case)</div>"
                f"<div class='lrd-diff-curr'>{(reg.current_output or '(empty)')[:1200]}</div>"
            )


# ─── Page: Runs (table) ─────────────────────────────────────────────────────
def page_runs():
    st.markdown("## Runs")
    runs = list_runs(DEFAULT_DB, limit=200)
    if not runs:
        st.info("No runs yet. Try `make run`.")
        return
    import pandas as pd
    df = pd.DataFrame(runs)
    df["pass_rate"] = (df["n_passed"] / df["n_cases"]).round(3)
    df = df[["run_id", "started_at", "sut_name", "n_cases", "n_passed",
             "pass_rate", "avg_score", "golden_path"]]
    st.dataframe(df, use_container_width=True, hide_index=True)


# ─── Page: Alerts ───────────────────────────────────────────────────────────
def page_alerts():
    st.markdown("## Alerts")
    alerts = list_alerts(limit=50)
    if not alerts:
        st.info("No alerts yet.")
        return
    for a in alerts:
        with st.expander(f"🚨  {a['filename']}  ·  {a['mtime'].isoformat(timespec='seconds')}"):
            st.markdown(f"**Run:** `{a['run_id']}` · **SUT:** {a['sut_name']}")
            st.markdown(f"**Plain text:** {a['text']}")
            st.code(json.dumps(a["payload"], indent=2), language="json")


# ─── Page: Settings ─────────────────────────────────────────────────────────
def page_settings():
    st.markdown("## Settings")
    from lrd.config import settings
    info = {
        "DuckDB path": str(DEFAULT_DB),
        "Groq model (SUT)": settings.groq_model,
        "Gemini judge model": settings.gemini_model,
        "Gemini embed model": settings.gemini_embed_model,
        "ml-research-agent path": settings.mlra_path,
        "Slack webhook": "set" if settings.slack_webhook_url else "(not set — simulated)",
    }
    for k, v in info.items():
        st.markdown(f"**{k}:** `{v}`")


# ─── Router ─────────────────────────────────────────────────────────────────
if selected == "Dashboard":
    page_dashboard()
elif selected == "Runs":
    page_runs()
elif selected == "Alerts":
    page_alerts()
elif selected == "Settings":
    page_settings()
