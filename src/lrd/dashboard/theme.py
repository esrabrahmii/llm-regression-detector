"""Dark theme — CSS injection for Streamlit. Approximates the dark MLOps
dashboard look (deep navy bg, raised cards, cyan accents, status pills)."""
from __future__ import annotations

import streamlit as st

COLORS = {
    "bg":         "#0A0E1A",   # deepest background
    "card":       "#141925",   # raised cards
    "card_hover": "#1B2230",
    "border":     "#262E3F",
    "text":       "#E6E9F0",
    "muted":      "#8B93A7",
    "accent":     "#06B6D4",   # cyan
    "accent_dim": "#0E7490",
    "ok":         "#10B981",   # green
    "warn":       "#F59E0B",
    "err":        "#EF4444",   # red
    "sidebar_bg": "#0A0E1A",
}

CSS = f"""
<style>
/* root surfaces */
.stApp {{ background: {COLORS["bg"]}; color: {COLORS["text"]}; }}
section[data-testid="stSidebar"] > div {{ background: {COLORS["sidebar_bg"]}; }}
section[data-testid="stSidebar"] {{ border-right: 1px solid {COLORS["border"]}; }}

/* headers */
h1, h2, h3, h4 {{ color: {COLORS["text"]} !important; }}
h1 {{ font-size: 1.5rem !important; font-weight: 600 !important; }}
.stCaption, [data-testid="stCaptionContainer"] p {{ color: {COLORS["muted"]} !important; }}

/* hide streamlit chrome */
#MainMenu, footer, header {{ visibility: hidden; }}
.stDeployButton {{ display: none; }}

/* cards */
.lrd-card {{
    background: {COLORS["card"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 14px;
    transition: border-color 0.15s;
}}
.lrd-card:hover {{ border-color: {COLORS["accent_dim"]}; }}

.lrd-stat-label {{
    color: {COLORS["muted"]};
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
}}
.lrd-stat-value {{
    color: {COLORS["text"]};
    font-size: 2.0rem;
    font-weight: 600;
    line-height: 1.0;
}}
.lrd-stat-value.cyan {{ color: {COLORS["accent"]}; }}
.lrd-stat-value.red  {{ color: {COLORS["err"]}; }}
.lrd-stat-value.warn {{ color: {COLORS["warn"]}; }}
.lrd-stat-sub {{
    color: {COLORS["muted"]};
    font-size: 0.78rem;
    margin-top: 6px;
}}

/* status pills */
.lrd-pill {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
}}
.lrd-pill.ok   {{ background: rgba(16,185,129,0.15); color: {COLORS["ok"]};   border: 1px solid rgba(16,185,129,0.4); }}
.lrd-pill.err  {{ background: rgba(239,68,68,0.15);  color: {COLORS["err"]};  border: 1px solid rgba(239,68,68,0.4);  }}
.lrd-pill.warn {{ background: rgba(245,158,11,0.15); color: {COLORS["warn"]}; border: 1px solid rgba(245,158,11,0.4); }}
.lrd-pill.info {{ background: rgba(6,182,212,0.15);  color: {COLORS["accent"]}; border: 1px solid rgba(6,182,212,0.4); }}

/* activity row */
.lrd-act-row {{
    display: flex;
    align-items: center;
    padding: 10px 12px;
    border-bottom: 1px solid {COLORS["border"]};
    gap: 12px;
}}
.lrd-act-row:last-child {{ border-bottom: none; }}
.lrd-act-dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}
.lrd-act-dot.ok  {{ background: {COLORS["ok"]}; }}
.lrd-act-dot.err {{ background: {COLORS["err"]}; }}
.lrd-act-text {{ flex-grow: 1; color: {COLORS["text"]}; font-size: 0.86rem; }}
.lrd-act-meta {{ color: {COLORS["muted"]}; font-size: 0.72rem; }}

/* alert row (sidebar-right alerts panel) */
.lrd-alert-row {{
    padding: 12px 0;
    border-bottom: 1px solid {COLORS["border"]};
}}
.lrd-alert-row:last-child {{ border-bottom: none; }}
.lrd-alert-title {{ color: {COLORS["text"]}; font-weight: 500; font-size: 0.86rem; }}
.lrd-alert-body  {{ color: {COLORS["muted"]}; font-size: 0.78rem; margin-top: 4px; }}
.lrd-alert-time  {{ color: {COLORS["muted"]}; font-size: 0.7rem; margin-top: 6px; }}

/* diff side-by-side */
.lrd-diff-prev, .lrd-diff-curr {{
    border-radius: 8px;
    padding: 14px;
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    font-size: 0.82rem;
    color: {COLORS["text"]};
    white-space: pre-wrap;
    line-height: 1.5;
    max-height: 320px;
    overflow-y: auto;
}}
.lrd-diff-prev {{ background: rgba(16,185,129,0.08); border: 1px solid rgba(16,185,129,0.3); }}
.lrd-diff-curr {{ background: rgba(239,68,68,0.08);  border: 1px solid rgba(239,68,68,0.3);  }}
.lrd-diff-label {{
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.7rem;
    color: {COLORS["muted"]};
    margin-bottom: 6px;
}}

/* "Run Full Test" cyan button */
.stButton > button[kind="primary"] {{
    background: {COLORS["accent"]} !important;
    color: #0A0E1A !important;
    border: none !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
}}
.stButton > button[kind="primary"]:hover {{
    background: {COLORS["accent_dim"]} !important;
    color: white !important;
}}
.stButton > button {{
    background: {COLORS["card"]} !important;
    color: {COLORS["text"]} !important;
    border: 1px solid {COLORS["border"]} !important;
    border-radius: 8px !important;
}}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
