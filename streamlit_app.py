"""
streamlit_app.py
────────────────
V Platform — Personal & Family Life OS (Miami Beach, 2026)

Phase 1 dashboard. Thin shell that:
- applies global Miami-Beach dark theme (CSS injection)
- renders a branded sidebar with a live global status pill
- routes between V Orchestrator / Departments / About

Run:
    cp .env.example .env       # then add ANTHROPIC_API_KEY (or OPENAI_API_KEY)
    pip install -r requirements.txt
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

# Load .env BEFORE importing modules that consume env at import time.
load_dotenv()

from crews.orchestrator.departments import DEPARTMENT_LABELS                       # noqa: E402
from ui.department_views import render_department_section                          # noqa: E402
from ui.orchestrator_view import (                                                 # noqa: E402
    get_global_status_for_sidebar,
    render_orchestrator_section,
)


# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="V Platform · Phase 1",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Global theme ────────────────────────────────────────────────────────────
# Component-scoped styles live in the views; this block handles platform-wide
# elements: background, sidebar shell, default Streamlit widgets, scrollbar.

_GLOBAL_CSS = """
<style>
/* === Base background === */
.stApp {
    background:
        radial-gradient(ellipse 80% 50% at 50% -10%, rgba(6, 182, 212, 0.08) 0%, transparent 60%),
        radial-gradient(ellipse 60% 40% at 100% 100%, rgba(236, 72, 153, 0.05) 0%, transparent 60%),
        linear-gradient(180deg, #06080f 0%, #0a0e1a 50%, #0c1426 100%);
    color: #e2e8f0;
}
.stApp > header { background: transparent; }

/* Hide top "Made with Streamlit" / hamburger */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stHeader"] { background: transparent; height: 0; }

/* Main content padding */
.main .block-container {
    padding-top: 2rem;
    padding-bottom: 4rem;
    max-width: 1320px;
}

/* === Sidebar shell === */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #050811 0%, #08101e 100%);
    border-right: 1px solid rgba(56, 189, 248, 0.08);
}
[data-testid="stSidebar"] > div:first-child { padding-top: 1.4rem; }
[data-testid="stSidebar"] hr {
    border-color: rgba(56, 189, 248, 0.08);
    margin: 1rem 0;
}

/* === Logo === */
.v-logo {
    display: flex; align-items: center; gap: 0.85rem;
    padding: 0 1rem 0.4rem 1rem;
    margin-bottom: 0.4rem;
}
.v-logo-mark {
    width: 42px; height: 42px;
    border-radius: 12px;
    background:
        radial-gradient(circle at 30% 30%, rgba(255,255,255,0.18) 0%, transparent 50%),
        linear-gradient(135deg, #06b6d4 0%, #0ea5e9 50%, #ec4899 100%);
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 1.3rem; color: white;
    box-shadow:
        0 8px 24px -8px rgba(6, 182, 212, 0.55),
        inset 0 1px 0 rgba(255,255,255,0.18);
    letter-spacing: -0.04em;
}
.v-logo-text { line-height: 1.2; }
.v-logo-name {
    font-weight: 800; color: #f1f5f9; font-size: 1rem;
    letter-spacing: -0.015em;
}
.v-logo-tag {
    font-size: 0.68rem; color: #64748b;
    letter-spacing: 0.16em; text-transform: uppercase;
    margin-top: 0.1rem;
}

/* === Sidebar section title === */
.v-side-title {
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.22em;
    color: #475569;
    font-weight: 700;
    margin: 1.3rem 1rem 0.5rem 1rem;
}

/* === Status pill === */
.v-side-status {
    margin: 0 0.9rem;
    padding: 0.75rem 0.9rem;
    border-radius: 13px;
    background:
        linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(15, 23, 42, 0.5) 100%);
    border: 1px solid rgba(56, 189, 248, 0.14);
    transition: all 0.3s ease;
}
.v-side-status-row {
    display: flex; align-items: center; gap: 0.55rem;
    font-size: 0.86rem; font-weight: 600; color: #f1f5f9;
}
.v-side-status-icon {
    font-size: 1.1rem;
    line-height: 1;
}
.v-side-status-dot {
    width: 8px; height: 8px; border-radius: 50%;
    flex-shrink: 0;
}
.v-side-status-dot--active {
    box-shadow: 0 0 0 0 currentColor;
    animation: v-side-pulse 1.6s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
@keyframes v-side-pulse {
    0%   { box-shadow: 0 0 0 0 currentColor; opacity: 1; }
    70%  { box-shadow: 0 0 0 8px transparent; opacity: 0.55; }
    100% { box-shadow: 0 0 0 0 transparent;  opacity: 1; }
}
.v-side-status-detail {
    margin-top: 0.35rem;
    font-size: 0.72rem;
    color: #64748b;
    letter-spacing: 0.02em;
    font-variant-numeric: tabular-nums;
}

/* === Department row === */
.v-side-dept {
    display: flex; align-items: flex-start; gap: 0.65rem;
    padding: 0.4rem 1rem;
    transition: background 0.15s;
    border-radius: 8px;
    margin: 0 0.5rem;
}
.v-side-dept:hover { background: rgba(56, 189, 248, 0.05); }
.v-side-dept-emoji { font-size: 1rem; line-height: 1.4; }
.v-side-dept-body { line-height: 1.3; }
.v-side-dept-name {
    font-size: 0.84rem; color: #e2e8f0; font-weight: 600;
}
.v-side-dept-tag {
    font-size: 0.7rem; color: #64748b; margin-top: 0.1rem;
}

/* === Config values === */
.v-side-config {
    margin: 0 1rem;
    color: #94a3b8;
    font-size: 0.78rem;
    line-height: 1.85;
}
.v-side-config code {
    background: rgba(56, 189, 248, 0.08);
    color: #67e8f9;
    padding: 0.06rem 0.4rem;
    border-radius: 5px;
    font-size: 0.74rem;
    font-family: 'SF Mono', 'Menlo', monospace;
}

/* === Version footer === */
.v-side-footer {
    margin: 2rem 1rem 1rem 1rem;
    padding-top: 1rem;
    border-top: 1px solid rgba(56, 189, 248, 0.06);
    color: #334155;
    font-size: 0.65rem;
    letter-spacing: 0.22em;
    text-transform: uppercase;
}

/* === Sidebar nav (radio styled as tabs) === */
[data-testid="stSidebar"] [data-baseweb="radio"] {
    background: rgba(15, 23, 42, 0.4);
    border: 1px solid rgba(56, 189, 248, 0.1);
    border-radius: 12px;
    padding: 0.4rem;
    margin: 0 0.9rem;
    display: flex;
    gap: 0.3rem;
}
[data-testid="stSidebar"] [data-baseweb="radio"] > label {
    flex: 1;
    border-radius: 8px;
    padding: 0.55rem 0.6rem;
    margin: 0 !important;
    cursor: pointer;
    transition: all 0.2s;
    color: #94a3b8;
    font-size: 0.84rem;
    font-weight: 500;
    border: 1px solid transparent;
}
[data-testid="stSidebar"] [data-baseweb="radio"] > label:hover {
    background: rgba(56, 189, 248, 0.06);
    color: #e2e8f0;
}
[data-testid="stSidebar"] [data-baseweb="radio"] > label > div:first-child {
    display: none !important;  /* hide the radio circle */
}
[data-testid="stSidebar"] [data-baseweb="radio"] > label[aria-checked="true"],
[data-testid="stSidebar"] [data-baseweb="radio"] > label > div > div[data-checked="true"] ~ * {
    /* fallback for various Streamlit versions */
}
[data-testid="stSidebar"] [data-baseweb="radio"] > label:has(input:checked) {
    background: linear-gradient(135deg, rgba(6, 182, 212, 0.16) 0%, rgba(236, 72, 153, 0.10) 100%);
    color: #f1f5f9;
    border-color: rgba(56, 189, 248, 0.32);
    box-shadow: 0 4px 16px -6px rgba(6, 182, 212, 0.4);
}

/* === Form widgets === */
.stTextArea textarea,
.stTextInput input {
    background: rgba(15, 23, 42, 0.7) !important;
    border: 1px solid rgba(56, 189, 248, 0.16) !important;
    color: #f1f5f9 !important;
    border-radius: 14px !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
    font-size: 0.95rem !important;
}
.stTextArea textarea:focus,
.stTextInput input:focus {
    border-color: rgba(56, 189, 248, 0.55) !important;
    box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.10) !important;
    outline: none !important;
}
.stTextArea textarea::placeholder,
.stTextInput input::placeholder {
    color: #475569 !important;
}

/* === Buttons === */
div[data-testid="stButton"] > button {
    border-radius: 12px;
    border: 1px solid rgba(56, 189, 248, 0.22);
    background: rgba(15, 23, 42, 0.5);
    color: #cbd5e1;
    font-weight: 600;
    padding: 0.55rem 1rem;
    transition: all 0.2s;
}
div[data-testid="stButton"] > button:hover:not(:disabled) {
    border-color: rgba(56, 189, 248, 0.5);
    background: rgba(15, 23, 42, 0.85);
    color: #f1f5f9;
    transform: translateY(-1px);
}
div[data-testid="stButton"] > button:disabled {
    opacity: 0.45;
    cursor: not-allowed;
}
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #06b6d4 0%, #0ea5e9 50%, #ec4899 200%);
    border: none;
    color: white;
    font-weight: 700;
    letter-spacing: 0.01em;
    padding: 0.65rem 1.3rem;
    box-shadow: 0 8px 24px -8px rgba(6, 182, 212, 0.55);
}
div[data-testid="stButton"] > button[kind="primary"]:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 12px 32px -8px rgba(6, 182, 212, 0.75);
    filter: brightness(1.07);
}

/* === Expanders === */
[data-testid="stExpander"] {
    background: rgba(15, 23, 42, 0.4);
    border: 1px solid rgba(56, 189, 248, 0.08);
    border-radius: 12px;
    transition: border-color 0.2s;
}
[data-testid="stExpander"]:hover {
    border-color: rgba(56, 189, 248, 0.18);
}
[data-testid="stExpander"] summary {
    color: #cbd5e1;
    font-weight: 500;
    font-size: 0.88rem;
}
[data-testid="stExpander"] summary:hover { color: #f1f5f9; }

/* === Tabs (department view) === */
[data-baseweb="tab-list"] {
    background: transparent;
    gap: 0.4rem;
    border-bottom: 1px solid rgba(56, 189, 248, 0.08);
}
[data-baseweb="tab"] {
    background: transparent;
    color: #64748b;
    font-weight: 600;
    font-size: 0.92rem;
    padding: 0.6rem 1.1rem;
    border-radius: 10px 10px 0 0;
    transition: all 0.2s;
}
[data-baseweb="tab"]:hover {
    color: #94a3b8;
    background: rgba(56, 189, 248, 0.04);
}
button[aria-selected="true"][data-baseweb="tab"] {
    color: #38bdf8;
    background: rgba(56, 189, 248, 0.06);
}
[data-baseweb="tab-highlight"] {
    background: linear-gradient(90deg, #06b6d4 0%, #ec4899 100%) !important;
    height: 2px !important;
}

/* === Toast === */
[data-testid="stToast"] {
    background: rgba(15, 23, 42, 0.95) !important;
    border: 1px solid rgba(56, 189, 248, 0.3) !important;
    color: #e2e8f0 !important;
    border-radius: 12px !important;
    backdrop-filter: blur(12px);
}

/* === Alerts === */
.stAlert {
    background: rgba(15, 23, 42, 0.6) !important;
    border-radius: 12px !important;
    border-width: 1px !important;
}

/* === Scrollbar === */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: rgba(15, 23, 42, 0.3); }
::-webkit-scrollbar-thumb {
    background: rgba(56, 189, 248, 0.2);
    border-radius: 6px;
    border: 2px solid transparent;
    background-clip: content-box;
}
::-webkit-scrollbar-thumb:hover { background: rgba(56, 189, 248, 0.4); background-clip: content-box; }

/* === Markdown body in main area === */
.main h1, .main h2, .main h3, .main h4 {
    color: #f1f5f9;
    letter-spacing: -0.015em;
}
.main h2 { font-size: 1.5rem; margin-top: 1.4rem; }
.main h3 { font-size: 1.2rem; margin-top: 1.2rem; color: #e2e8f0; }
.main p, .main li { color: #cbd5e1; line-height: 1.7; }
.main code {
    background: rgba(56, 189, 248, 0.1);
    color: #67e8f9;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    font-size: 0.88em;
}
.main hr {
    border-color: rgba(56, 189, 248, 0.1);
    margin: 1.5rem 0;
}
</style>
"""


# ════════════════════════════════════════════════════════════════════════════
# Sidebar
# ════════════════════════════════════════════════════════════════════════════

_NAV_OPTIONS  = ["🚀 Orchestrator", "🏢 Departments", "ℹ️ About"]
_NAV_KEYS     = ["orchestrator", "departments", "about"]


def render_sidebar() -> str:
    """Render the branded sidebar and return the active section key."""
    with st.sidebar:
        # ── Logo ─────────────────────────────────────────────────────────────
        st.markdown("""
        <div class="v-logo">
            <div class="v-logo-mark">V</div>
            <div class="v-logo-text">
                <div class="v-logo-name">V Platform</div>
                <div class="v-logo-tag">Miami Beach · 2026</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Global status (live-updating per app rerun) ──────────────────────
        label, icon, color, detail = get_global_status_for_sidebar()
        is_active = label not in ("Idle", "Completed", "Stopped", "Failed")
        dot_class = "v-side-status-dot v-side-status-dot--active" if is_active else "v-side-status-dot"

        st.markdown(f"""
        <div class="v-side-title">Status</div>
        <div class="v-side-status">
            <div class="v-side-status-row">
                <span class="{dot_class}" style="background:{color}; color:{color};"></span>
                <span class="v-side-status-icon">{icon}</span>
                <span style="color:{color}">{label}</span>
            </div>
            <div class="v-side-status-detail">{detail}</div>
        </div>
        """, unsafe_allow_html=True)

        # ── Navigation ───────────────────────────────────────────────────────
        st.markdown('<div class="v-side-title">Navigation</div>', unsafe_allow_html=True)

        st.session_state.setdefault("nav", "orchestrator")
        current_idx = _NAV_KEYS.index(st.session_state.nav)

        selected_label = st.radio(
            "Navigation",
            options=_NAV_OPTIONS,
            index=current_idx,
            label_visibility="collapsed",
            key="v_nav_radio",
        )
        new_nav = _NAV_KEYS[_NAV_OPTIONS.index(selected_label)]
        if new_nav != st.session_state.nav:
            st.session_state.nav = new_nav
            st.rerun()

        # ── Departments overview ─────────────────────────────────────────────
        st.markdown('<div class="v-side-title">Departments</div>', unsafe_allow_html=True)
        for meta in DEPARTMENT_LABELS.values():
            st.markdown(f"""
            <div class="v-side-dept">
                <div class="v-side-dept-emoji">{meta["emoji"]}</div>
                <div class="v-side-dept-body">
                    <div class="v-side-dept-name">{meta["name"]}</div>
                    <div class="v-side-dept-tag">{meta["summary"]}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # ── Configuration ────────────────────────────────────────────────────
        st.markdown('<div class="v-side-title">Configuration</div>', unsafe_allow_html=True)
        provider = os.getenv("LLM_PROVIDER", "anthropic")

        # Surface a clear warning if the API key is missing.
        if provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
            st.error("ANTHROPIC_API_KEY is not set", icon="⚠️")
        elif provider == "openai" and not os.getenv("OPENAI_API_KEY"):
            st.error("OPENAI_API_KEY is not set", icon="⚠️")
        else:
            st.markdown(f"""
            <div class="v-side-config">
                Provider · <code>{provider}</code><br>
                Max iterations · <code>{os.getenv("V_ORCHESTRATOR_MAX_ITERATIONS", "2")}</code><br>
                Quality threshold · <code>{os.getenv("V_ORCHESTRATOR_QUALITY_THRESHOLD", "0.8")}</code>
            </div>
            """, unsafe_allow_html=True)

        # ── Footer ───────────────────────────────────────────────────────────
        st.markdown(
            '<div class="v-side-footer">Phase 1 · LangGraph</div>',
            unsafe_allow_html=True,
        )

    return st.session_state.nav


# ════════════════════════════════════════════════════════════════════════════
# About view
# ════════════════════════════════════════════════════════════════════════════

def render_about() -> None:
    """About page — vision, architecture, roadmap."""
    st.markdown("""
    <div style="padding: 0.5rem 0 1rem 0;">
        <div style="font-size: 0.7rem; letter-spacing: 0.32em;
                    color: #38bdf8; font-weight: 600; text-transform: uppercase;">
            About
        </div>
        <h1 style="
            background: linear-gradient(120deg, #f1f5f9 0%, #38bdf8 50%, #ec4899 100%);
            -webkit-background-clip: text; background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.6rem; margin: 0.4rem 0 0.8rem 0; font-weight: 800;
            letter-spacing: -0.025em; line-height: 1.05;
        ">
            V Platform
        </h1>
        <div style="color: #94a3b8; font-size: 1.05rem; line-height: 1.65; max-width: 70ch;">
            A Personal &amp; Family Life Operating System headquartered in Miami Beach.
            Organized as a small company of AI agents with a CEO orchestrator that
            delegates to specialist departments.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Two-up explainer cards
    card_a, card_b = st.columns(2, gap="medium")
    with card_a:
        st.markdown("""
        <div style="
            padding: 1.6rem; border-radius: 18px; height: 100%;
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.6) 0%, rgba(6, 182, 212, 0.04) 100%);
            border: 1px solid rgba(56, 189, 248, 0.14);
        ">
            <div style="font-size: 1.9rem; margin-bottom: 0.55rem;">🚀</div>
            <h3 style="color: #f1f5f9; margin: 0 0 0.5rem 0; font-size: 1.15rem; letter-spacing: -0.01em;">
                V Orchestrator
            </h3>
            <div style="color: #94a3b8; font-size: 0.92rem; line-height: 1.6;">
                The CEO agent. Hand it any goal &mdash; it figures out how to achieve
                it by analyzing, planning, delegating to departments, evaluating
                output, and iterating when needed.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with card_b:
        st.markdown("""
        <div style="
            padding: 1.6rem; border-radius: 18px; height: 100%;
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.6) 0%, rgba(236, 72, 153, 0.04) 100%);
            border: 1px solid rgba(236, 72, 153, 0.14);
        ">
            <div style="font-size: 1.9rem; margin-bottom: 0.55rem;">🏢</div>
            <h3 style="color: #f1f5f9; margin: 0 0 0.5rem 0; font-size: 1.15rem; letter-spacing: -0.01em;">
                Departments
            </h3>
            <div style="color: #94a3b8; font-size: 0.92rem; line-height: 1.6;">
                Specialist agents &mdash; each one owns its domain. Marketing, Bakery,
                Comms, MLO Coach. The orchestrator delegates to them; they can also
                be queried directly.
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Architecture summary
    st.markdown("""
    <div style="margin-top: 1.6rem;">
        <div style="font-size:0.7rem; text-transform:uppercase; letter-spacing:0.22em;
                    color:#94a3b8; font-weight:700; margin-bottom: 0.65rem;">
            Phase 1 architecture
        </div>
        <div style="
            padding: 1.4rem 1.6rem; border-radius: 16px;
            background: rgba(15, 23, 42, 0.55);
            border: 1px solid rgba(56, 189, 248, 0.12);
            color: #cbd5e1; line-height: 1.75;
        ">
            <strong style="color:#f1f5f9">Framework</strong> &middot; LangGraph &mdash; stateful
            multi-agent workflows with conditional routing and iterative refinement.<br><br>
            <strong style="color:#f1f5f9">Flow</strong> &middot;
            <code style="background:rgba(56,189,248,0.1); color:#67e8f9; padding:0.1rem 0.4rem; border-radius:4px;">analyze</code> →
            <code style="background:rgba(56,189,248,0.1); color:#67e8f9; padding:0.1rem 0.4rem; border-radius:4px;">decompose</code> →
            <code style="background:rgba(56,189,248,0.1); color:#67e8f9; padding:0.1rem 0.4rem; border-radius:4px;">execute</code> →
            <code style="background:rgba(56,189,248,0.1); color:#67e8f9; padding:0.1rem 0.4rem; border-radius:4px;">aggregate</code> →
            <code style="background:rgba(56,189,248,0.1); color:#67e8f9; padding:0.1rem 0.4rem; border-radius:4px;">evaluate</code> →
            (<code style="background:rgba(236,72,153,0.12); color:#f9a8d4; padding:0.1rem 0.4rem; border-radius:4px;">refine</code> ↻) →
            <code style="background:rgba(56,189,248,0.1); color:#67e8f9; padding:0.1rem 0.4rem; border-radius:4px;">synthesize</code>.<br><br>
            <strong style="color:#f1f5f9">Coming next</strong> &middot; long-term memory,
            tool use (calendar, email, CRM), parallel subtask execution,
            human-in-the-loop approvals, per-department subgraphs.
        </div>
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

def main() -> None:
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)

    section = render_sidebar()

    if section == "orchestrator":
        render_orchestrator_section()
    elif section == "departments":
        render_department_section()
    else:
        render_about()


if __name__ == "__main__":
    main()
