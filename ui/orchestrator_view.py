"""
ui/orchestrator_view.py
───────────────────────
Premium UI for V Orchestrator.

Architecture:
─────────────
- The view has three exclusive states: INPUT (no run), RUNNING (active run),
  COMPLETED (finished run still on screen).
- The RUNNING state lives inside an `st.fragment(run_every="400ms")` which
  drains the run queue and re-renders every 400ms. This is the only thing
  on the page that auto-refreshes — everything else is static.
- Custom HTML+CSS provides a Miami-Beach dark aesthetic (deep navy → cyan →
  coral). Streamlit widgets (buttons, textareas) are themed via global CSS in
  streamlit_app.py.

Public surface (used by streamlit_app.py):
- render_orchestrator_section()        Main entrypoint
- get_global_status_for_sidebar()      Tuple used by the sidebar status pill
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import streamlit as st

from crews.orchestrator.departments import DEPARTMENT_LABELS
from ui.run_manager import OrchRun, drain_updates, request_stop, start_run


# ── Phase metadata ──────────────────────────────────────────────────────────
# Single source of truth for icons, labels, and brand colors per phase.
# Used by the timeline, the phase chip, and the global sidebar status.

PHASE_META: dict[str, dict] = {
    "idle":         {"label": "Idle",          "icon": "💤", "color": "#64748b"},
    "queued":       {"label": "Queued",        "icon": "⏳", "color": "#64748b"},
    "analyzing":    {"label": "Analyzing",     "icon": "🧠", "color": "#38bdf8"},
    "decomposing":  {"label": "Planning",      "icon": "🧩", "color": "#a855f7"},
    "executing":    {"label": "Executing",     "icon": "⚡", "color": "#06b6d4"},
    "aggregating":  {"label": "Aggregating",   "icon": "📦", "color": "#0ea5e9"},
    "evaluating":   {"label": "Evaluating",    "icon": "🧪", "color": "#f59e0b"},
    "refining":     {"label": "Refining",      "icon": "♻️", "color": "#ec4899"},
    "synthesizing": {"label": "Synthesizing",  "icon": "✨", "color": "#22d3ee"},
    "completed":    {"label": "Completed",     "icon": "✅", "color": "#10b981"},
    "failed":       {"label": "Failed",        "icon": "❌", "color": "#ef4444"},
}

# Order shown in the horizontal timeline. (refining is hidden by default — it
# appears as a subtle re-trigger of executing/aggregating/evaluating.)
PHASE_TIMELINE = [
    "analyzing", "decomposing", "executing", "aggregating",
    "evaluating", "synthesizing", "completed",
]


# ── CSS ─────────────────────────────────────────────────────────────────────
# All component-scoped styles for this view. Class prefix `v-` to avoid
# collisions with Streamlit's internal classes.

_CSS = """
<style>
/* ── Hero ─────────────────────────────────────────────────────────────── */
.v-hero {
    position: relative;
    padding: 2.4rem 2.2rem 2.1rem 2.2rem;
    border-radius: 24px;
    background:
        radial-gradient(ellipse at 90% 0%, rgba(236, 72, 153, 0.18) 0%, transparent 55%),
        radial-gradient(ellipse at 10% 100%, rgba(6, 182, 212, 0.22) 0%, transparent 55%),
        linear-gradient(135deg, #08101e 0%, #0f1a2e 50%, #0a1426 100%);
    border: 1px solid rgba(56, 189, 248, 0.14);
    overflow: hidden;
    margin-bottom: 1.4rem;
    box-shadow: 0 24px 60px -28px rgba(6, 182, 212, 0.35);
}
.v-hero::before {
    content: "";
    position: absolute; inset: 0;
    background: repeating-linear-gradient(
        45deg,
        rgba(56, 189, 248, 0.025) 0px,
        rgba(56, 189, 248, 0.025) 1px,
        transparent 1px,
        transparent 14px
    );
    pointer-events: none;
}
.v-hero-eyebrow {
    font-size: 0.7rem;
    letter-spacing: 0.32em;
    text-transform: uppercase;
    color: #38bdf8;
    font-weight: 600;
    opacity: 0.9;
    position: relative;
}
.v-hero-title {
    font-size: 2.6rem;
    font-weight: 800;
    margin: 0.45rem 0 0.5rem 0;
    letter-spacing: -0.025em;
    line-height: 1.05;
    background: linear-gradient(120deg, #f1f5f9 0%, #38bdf8 45%, #ec4899 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    position: relative;
}
.v-hero-subtitle {
    color: #94a3b8;
    font-size: 1rem;
    max-width: 62ch;
    line-height: 1.6;
    position: relative;
}

/* ── Phase chip ───────────────────────────────────────────────────────── */
.v-chip-row {
    display: flex; align-items: center; gap: 0.75rem;
    margin-bottom: 1rem;
}
.v-phase-chip {
    display: inline-flex; align-items: center; gap: 0.55rem;
    padding: 0.55rem 1rem;
    border-radius: 14px;
    font-weight: 600; font-size: 0.9rem;
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid rgba(56, 189, 248, 0.22);
    color: #e2e8f0;
    backdrop-filter: blur(10px);
}
.v-phase-chip-dot {
    width: 8px; height: 8px; border-radius: 50%;
    box-shadow: 0 0 0 0 currentColor;
    animation: v-pulse-ring 1.6s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
.v-phase-chip-elapsed {
    color: #64748b;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
    margin-left: 0.4rem;
}
@keyframes v-pulse-ring {
    0%   { box-shadow: 0 0 0 0 currentColor; opacity: 1; }
    70%  { box-shadow: 0 0 0 10px transparent; opacity: 0.6; }
    100% { box-shadow: 0 0 0 0 transparent;  opacity: 1; }
}

/* ── Timeline ─────────────────────────────────────────────────────────── */
.v-timeline {
    display: flex; align-items: center; gap: 0;
    padding: 1.2rem 0.4rem 0.4rem 0.4rem;
    margin-bottom: 0.6rem;
}
.v-tl-step {
    display: flex; flex-direction: column; align-items: center;
    gap: 0.4rem; flex: 0 0 auto; min-width: 72px;
}
.v-tl-dot {
    width: 34px; height: 34px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    background: rgba(15, 23, 42, 0.85);
    border: 2px solid rgba(100, 116, 139, 0.28);
    font-size: 0.92rem;
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.v-tl-dot--done {
    background: rgba(16, 185, 129, 0.18);
    border-color: #10b981;
}
.v-tl-dot--active {
    background: rgba(56, 189, 248, 0.22);
    border-color: #38bdf8;
    transform: scale(1.12);
    box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.5);
    animation: v-pulse-ring-big 1.6s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
@keyframes v-pulse-ring-big {
    0%   { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.55); }
    70%  { box-shadow: 0 0 0 14px rgba(56, 189, 248, 0); }
    100% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0); }
}
.v-tl-label {
    font-size: 0.68rem; color: #94a3b8; font-weight: 500;
    text-align: center; white-space: nowrap;
}
.v-tl-step--active .v-tl-label { color: #38bdf8; font-weight: 600; }
.v-tl-step--done   .v-tl-label { color: #6ee7b7; }
.v-tl-line {
    flex: 1 1 auto; height: 2px; min-width: 18px;
    background: rgba(100, 116, 139, 0.22);
    align-self: flex-start; margin-top: 17px;
    transition: background 0.4s ease;
}
.v-tl-line--done {
    background: linear-gradient(90deg, #10b981 0%, #38bdf8 100%);
}

/* ── Section title ────────────────────────────────────────────────────── */
.v-section-title {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.2em;
    color: #94a3b8;
    font-weight: 700;
    margin: 1.4rem 0 0.7rem 0;
    display: flex; align-items: center; gap: 0.45rem;
}

/* ── Subtask cards ────────────────────────────────────────────────────── */
.v-card {
    position: relative;
    padding: 0.95rem 1.1rem;
    border-radius: 14px;
    background: rgba(15, 23, 42, 0.55);
    border: 1px solid rgba(56, 189, 248, 0.1);
    margin-bottom: 0.65rem;
    transition: all 0.2s ease;
    border-left-width: 3px;
}
.v-card:hover {
    border-color: rgba(56, 189, 248, 0.32);
    background: rgba(15, 23, 42, 0.78);
    transform: translateX(2px);
}
.v-card--in_progress {
    border-left-color: #06b6d4;
    background: linear-gradient(90deg,
        rgba(6, 182, 212, 0.10) 0%,
        rgba(15, 23, 42, 0.6) 60%);
    animation: v-card-glow 2.2s ease-in-out infinite;
}
.v-card--completed { border-left-color: #10b981; }
.v-card--failed    { border-left-color: #ef4444; }
.v-card--pending   {
    border-left-color: rgba(100, 116, 139, 0.5);
    opacity: 0.78;
}
@keyframes v-card-glow {
    0%, 100% { box-shadow: 0 0 0 0 rgba(6, 182, 212, 0.0); }
    50%      { box-shadow: 0 0 22px -6px rgba(6, 182, 212, 0.35); }
}

.v-card-head {
    display: flex; align-items: center; gap: 0.55rem;
    margin-bottom: 0.45rem;
}
.v-card-emoji { font-size: 1.15rem; }
.v-card-name {
    font-weight: 700; color: #f1f5f9; font-size: 0.9rem;
    letter-spacing: -0.005em;
}
.v-card-id {
    color: #475569; font-size: 0.72rem;
    font-family: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace;
}
.v-card-status {
    margin-left: auto;
    padding: 0.18rem 0.6rem;
    border-radius: 8px;
    font-size: 0.66rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    white-space: nowrap;
}
.v-card-status--in_progress {
    background: rgba(6, 182, 212, 0.18);
    color: #67e8f9;
    border: 1px solid rgba(6, 182, 212, 0.4);
}
.v-card-status--completed {
    background: rgba(16, 185, 129, 0.16);
    color: #6ee7b7;
}
.v-card-status--failed {
    background: rgba(239, 68, 68, 0.16);
    color: #fca5a5;
}
.v-card-status--pending {
    background: rgba(100, 116, 139, 0.18);
    color: #cbd5e1;
}
.v-card-desc {
    color: #cbd5e1; font-size: 0.88rem; line-height: 1.55;
}

/* ── Live log ─────────────────────────────────────────────────────────── */
.v-log {
    background: rgba(2, 6, 23, 0.7);
    border: 1px solid rgba(56, 189, 248, 0.12);
    border-radius: 14px;
    padding: 1rem 1.15rem;
    height: 360px;
    overflow-y: auto;
    font-family: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace;
    font-size: 0.82rem;
    line-height: 1.75;
}
.v-log-line { color: #cbd5e1; word-break: break-word; }
.v-log-line--recent {
    animation: v-fade-in 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes v-fade-in {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0); }
}
/* Color-coded log levels (classified by leading emoji in run_manager) */
.v-log--success { color: #6ee7b7; }
.v-log--info    { color: #93c5fd; }
.v-log--action  { color: #67e8f9; }
.v-log--eval    { color: #fcd34d; }
.v-log--refine  { color: #f9a8d4; }
.v-log--warn    { color: #fcd34d; }
.v-log--error   { color: #fca5a5; }
.v-log--stop    { color: #fcd34d; }

/* ── Score panel ──────────────────────────────────────────────────────── */
.v-score {
    padding: 1.2rem 1.4rem;
    border-radius: 16px;
    background:
        radial-gradient(ellipse at top right, rgba(236, 72, 153, 0.06) 0%, transparent 50%),
        linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 59, 0.5) 100%);
    border: 1px solid rgba(56, 189, 248, 0.16);
    display: flex; flex-direction: column; gap: 0.5rem;
}
.v-score-row { display: flex; align-items: baseline; gap: 1rem; }
.v-score-label {
    color: #94a3b8;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.2em;
    font-weight: 700;
}
.v-score-value {
    font-size: 2.4rem;
    font-weight: 800;
    line-height: 1;
    background: linear-gradient(90deg, #38bdf8 0%, #ec4899 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    font-variant-numeric: tabular-nums;
}
.v-score-bar {
    height: 8px;
    background: rgba(56, 189, 248, 0.08);
    border-radius: 999px;
    overflow: hidden;
}
.v-score-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #06b6d4 0%, #ec4899 100%);
    border-radius: 999px;
    transition: width 0.7s cubic-bezier(0.34, 1.4, 0.64, 1);
    box-shadow: 0 0 16px -2px rgba(6, 182, 212, 0.5);
}
.v-score-feedback {
    color: #cbd5e1;
    font-size: 0.86rem;
    line-height: 1.55;
    margin-top: 0.4rem;
}

/* ── Final answer ─────────────────────────────────────────────────────── */
.v-final {
    padding: 1.7rem 1.9rem;
    border-radius: 18px;
    background:
        radial-gradient(ellipse at top right, rgba(16, 185, 129, 0.06) 0%, transparent 50%),
        linear-gradient(135deg, rgba(15, 23, 42, 0.7) 0%, rgba(6, 78, 59, 0.15) 100%);
    border: 1px solid rgba(16, 185, 129, 0.22);
    margin-top: 1rem;
}
.v-final-head {
    display: flex; align-items: center; gap: 0.6rem;
    padding-bottom: 0.85rem;
    margin-bottom: 1rem;
    border-bottom: 1px solid rgba(16, 185, 129, 0.16);
}
.v-final-title {
    font-weight: 700; color: #6ee7b7;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.2em;
}

/* ── History card ─────────────────────────────────────────────────────── */
.v-hist-row {
    display: flex; align-items: center; gap: 0.75rem;
    padding: 0.4rem 0;
    font-size: 0.85rem;
}
.v-hist-meta {
    color: #64748b; font-size: 0.78rem;
    font-variant-numeric: tabular-nums;
}
.v-hist-task {
    color: #e2e8f0; font-weight: 500;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* ── Empty state ──────────────────────────────────────────────────────── */
.v-empty {
    color: #64748b;
    font-size: 0.86rem;
    padding: 1.5rem 1rem;
    text-align: center;
    border: 1px dashed rgba(56, 189, 248, 0.15);
    border-radius: 12px;
}
</style>
"""


# ════════════════════════════════════════════════════════════════════════════
# Public entrypoints
# ════════════════════════════════════════════════════════════════════════════

def render_orchestrator_section() -> None:
    """Top-level renderer for the V Orchestrator view."""
    st.markdown(_CSS, unsafe_allow_html=True)

    st.session_state.setdefault("orch_run", None)
    st.session_state.setdefault("orch_history", [])

    current: Optional[OrchRun] = st.session_state.orch_run

    _render_hero()

    if current is None:
        _render_input_form()
    elif current.is_active:
        _render_running_view(current)
    else:
        _render_completed_view(current)

    _render_history(exclude_thread_id=current.thread_id if current else None)


def get_global_status_for_sidebar() -> tuple[str, str, str, str]:
    """
    Return (label, icon, color, detail) for the sidebar status pill.

    Used by streamlit_app.py — kept here so all phase metadata stays in one
    place.
    """
    run: Optional[OrchRun] = st.session_state.get("orch_run")

    if run is None:
        return ("Idle", "💤", "#64748b", "No active run")

    if run.is_active:
        meta = PHASE_META.get(run.phase, PHASE_META["queued"])
        return (meta["label"], meta["icon"], meta["color"], f"Running · {run.elapsed:.1f}s")

    if run.status == "completed":
        return ("Completed", "✅", "#10b981", f"Last run · {run.elapsed:.1f}s")
    if run.status == "stopped":
        return ("Stopped", "⏹", "#f59e0b", f"Stopped · {run.elapsed:.1f}s")
    return ("Failed", "❌", "#ef4444", run.error or "Unknown error")


# ════════════════════════════════════════════════════════════════════════════
# State views
# ════════════════════════════════════════════════════════════════════════════

def _render_hero() -> None:
    """Static hero block — same on every state."""
    st.markdown("""
    <div class="v-hero">
        <div class="v-hero-eyebrow">V Platform · Miami Beach · 2026</div>
        <div class="v-hero-title">🚀 V Orchestrator</div>
        <div class="v-hero-subtitle">
            The CEO agent of V Platform. Hand it any goal — it analyzes,
            plans, delegates across departments, evaluates the result, and
            iterates until it&rsquo;s good enough to ship.
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_input_form() -> None:
    """Idle state — task input + Launch button."""
    user_task = st.text_area(
        label="What should V Platform handle?",
        placeholder=(
            "Например: «Запусти промо новой круассановой линии V Bakery — "
            "нужны 5 постов для Instagram, email-анонс для базы клиентов и "
            "скрипт для команды у прилавка». Или: «Подготовь onboarding-неделю "
            "для нового MLO в команде»."
        ),
        height=170,
        key="orch_task_input",
        label_visibility="collapsed",
    )

    col_a, col_b, _spacer = st.columns([1.5, 1.1, 1.6])
    with col_a:
        run_clicked = st.button(
            "🚀  Launch V Orchestrator",
            type="primary",
            use_container_width=True,
            disabled=not user_task.strip(),
        )
    with col_b:
        clear_clicked = st.button(
            "🧹  Clear history",
            use_container_width=True,
            disabled=not st.session_state.orch_history,
        )

    if clear_clicked:
        st.session_state.orch_history = []
        st.toast("History cleared", icon="🧹")
        st.rerun()

    if run_clicked and user_task.strip():
        st.session_state.orch_run = start_run(user_task.strip())
        st.rerun()


def _render_running_view(run: OrchRun) -> None:
    """Active run — delegate everything dynamic to an auto-refreshing fragment."""
    _running_fragment(run.thread_id)


@st.fragment(run_every="400ms")
def _running_fragment(run_thread_id: str) -> None:
    """
    Auto-refreshing inner view for an active run.

    Drains the queue, renders live state, and triggers a full app rerun once
    the run finishes (so the parent can switch to _render_completed_view).
    """
    run: Optional[OrchRun] = st.session_state.get("orch_run")
    # If the user navigated away or cleared, stop the fragment cleanly.
    if run is None or run.thread_id != run_thread_id:
        st.rerun(scope="app")
        return

    # Pull whatever the runner thread has produced since last frame.
    drain_updates(run)

    # Detect lifecycle end → finalize + bubble up.
    if not run.is_alive:
        # One last drain to capture trailing __DONE__/__STOPPED__/__ERROR__
        drain_updates(run)
        if run.is_active:
            run.is_active = False
            run.finished_at = time.time()
            if run.status == "running":
                run.status = "completed"
        # Snapshot into history (avoid duplicates if user clicks away/back).
        if not any(h["thread_id"] == run.thread_id for h in st.session_state.orch_history):
            st.session_state.orch_history.append(run.to_history_entry())
        st.rerun(scope="app")
        return

    # ── Live header: phase chip + Stop button ───────────────────────────────
    meta = PHASE_META.get(run.phase, PHASE_META["queued"])
    head_a, head_b = st.columns([3, 1])
    with head_a:
        st.markdown(
            f'<div class="v-chip-row">'
            f'<div class="v-phase-chip">'
            f'<span class="v-phase-chip-dot" style="background:{meta["color"]}; color:{meta["color"]}"></span>'
            f'<span style="font-size:1.05rem">{meta["icon"]}</span>'
            f'<span>{meta["label"]}</span>'
            f'<span class="v-phase-chip-elapsed">· {run.elapsed:.1f}s</span>'
            f'{"<span class=\"v-phase-chip-elapsed\">· iter " + str(run.iteration + 1) + "</span>" if run.iteration > 0 else ""}'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    with head_b:
        if st.button("⏹  Stop run", key="v_stop_run", use_container_width=True):
            request_stop(run)
            st.toast("Stopping after the current step…", icon="⏹")

    # ── Timeline ────────────────────────────────────────────────────────────
    _render_timeline(run.phase)

    # ── Plan + Log side by side ─────────────────────────────────────────────
    col_plan, col_log = st.columns([1.1, 1])
    with col_plan:
        st.markdown('<div class="v-section-title">🧩 Subtask plan</div>', unsafe_allow_html=True)
        _render_plan_cards(run.plan)
    with col_log:
        st.markdown('<div class="v-section-title">📡 Live execution log</div>', unsafe_allow_html=True)
        _render_log(run.log)

    # ── Score (only after evaluate node has fired) ──────────────────────────
    if run.score is not None:
        st.markdown('<div class="v-section-title">🧪 Quality check</div>', unsafe_allow_html=True)
        _render_score(run.score, run.feedback)


def _render_completed_view(run: OrchRun) -> None:
    """Final state — full answer + actions + collapsible details."""
    # Status chip
    if run.status == "completed":
        chip_text, chip_color = f"✅  Completed in {run.elapsed:.1f}s", "#10b981"
    elif run.status == "stopped":
        chip_text, chip_color = f"⏹  Stopped after {run.elapsed:.1f}s", "#f59e0b"
    else:
        chip_text, chip_color = f"❌  Failed after {run.elapsed:.1f}s", "#ef4444"

    st.markdown(
        f'<div class="v-chip-row">'
        f'<div class="v-phase-chip" style="border-color:{chip_color}55; color:{chip_color}">'
        f'{chip_text}</div></div>',
        unsafe_allow_html=True,
    )

    # Action row
    col_a, col_b, _spacer = st.columns([1.2, 1.1, 1.7])
    with col_a:
        if st.button("🔄  New task", type="primary", use_container_width=True, key="v_new_task"):
            st.session_state.orch_run = None
            st.rerun()
    with col_b:
        if st.button("🔁  Re-run this", use_container_width=True, key="v_rerun"):
            st.session_state.orch_run = start_run(run.task)
            st.rerun()

    # Final answer
    if run.final_answer:
        st.markdown(
            '<div class="v-final">'
            '<div class="v-final-head">'
            '<span style="font-size:1.4rem">🎯</span>'
            '<span class="v-final-title">V Orchestrator · Final answer</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        # Streamlit renders Markdown well — let it own the body.
        st.markdown(run.final_answer)
        st.markdown('</div>', unsafe_allow_html=True)
    elif run.error:
        st.error(f"Run failed: {run.error}")
    else:
        st.warning("No final answer was produced.")

    # Collapsible details
    with st.expander("📋  Execution details", expanded=False):
        col_a, col_b = st.columns([1.1, 1])
        with col_a:
            st.markdown('<div class="v-section-title">🧩 Subtasks</div>', unsafe_allow_html=True)
            _render_plan_cards(run.plan)
        with col_b:
            st.markdown('<div class="v-section-title">📡 Log</div>', unsafe_allow_html=True)
            _render_log(run.log)
        if run.score is not None:
            st.markdown('<div class="v-section-title">🧪 Quality check</div>', unsafe_allow_html=True)
            _render_score(run.score, run.feedback)


# ════════════════════════════════════════════════════════════════════════════
# Component renderers
# ════════════════════════════════════════════════════════════════════════════

def _render_timeline(current_phase: str) -> None:
    """Horizontal phase timeline (analyze → … → completed)."""
    if current_phase in PHASE_TIMELINE:
        current_idx = PHASE_TIMELINE.index(current_phase)
    elif current_phase == "refining":
        # Refining loops back to executing — show executing as the active step.
        current_idx = PHASE_TIMELINE.index("executing")
    elif current_phase == "failed":
        current_idx = -2
    else:
        current_idx = -1  # queued / idle

    parts: list[str] = ['<div class="v-timeline">']
    for i, ph in enumerate(PHASE_TIMELINE):
        meta = PHASE_META[ph]
        if i < current_idx:
            step_state, dot_state = "v-tl-step--done", "v-tl-dot--done"
        elif i == current_idx:
            step_state, dot_state = "v-tl-step--active", "v-tl-dot--active"
        else:
            step_state, dot_state = "", ""
        parts.append(
            f'<div class="v-tl-step {step_state}">'
            f'<div class="v-tl-dot {dot_state}">{meta["icon"]}</div>'
            f'<div class="v-tl-label">{meta["label"]}</div>'
            f'</div>'
        )
        if i < len(PHASE_TIMELINE) - 1:
            line_cls = "v-tl-line v-tl-line--done" if i < current_idx else "v-tl-line"
            parts.append(f'<div class="{line_cls}"></div>')
    parts.append('</div>')

    st.markdown("".join(parts), unsafe_allow_html=True)


def _render_plan_cards(plan: list[dict]) -> None:
    """Subtask plan as styled cards."""
    if not plan:
        st.markdown(
            '<div class="v-empty">'
            'The plan will appear once the orchestrator finishes decomposing the task.'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    status_label_map = {
        "pending":     "Queued",
        "in_progress": "Running",
        "completed":   "Done",
        "failed":      "Failed",
    }

    parts: list[str] = []
    for st_ in plan:
        dept_meta = DEPARTMENT_LABELS.get(st_["department"], {})
        emoji = dept_meta.get("emoji", "•")
        name = dept_meta.get("name", st_["department"])
        status = st_["status"]
        status_label = status_label_map.get(status, status)
        desc = _escape(st_.get("description") or "")

        parts.append(
            f'<div class="v-card v-card--{status}">'
            f'<div class="v-card-head">'
            f'<span class="v-card-emoji">{emoji}</span>'
            f'<span class="v-card-name">{name}</span>'
            f'<span class="v-card-id">· {_escape(st_["id"])}</span>'
            f'<span class="v-card-status v-card-status--{status}">{status_label}</span>'
            f'</div>'
            f'<div class="v-card-desc">{desc}</div>'
            f'</div>'
        )

    st.markdown("".join(parts), unsafe_allow_html=True)


def _render_log(lines: list[str]) -> None:
    """Color-coded streaming log."""
    if not lines:
        st.markdown(
            '<div class="v-log"><div style="color:#475569; font-style:italic;">'
            'Awaiting first event…'
            '</div></div>',
            unsafe_allow_html=True,
        )
        return

    visible = lines[-30:]
    recent_threshold = max(0, len(visible) - 3)
    rendered_lines: list[str] = []
    for i, line in enumerate(visible):
        cls_extra = _classify_log_line(line)
        recent_cls = " v-log-line--recent" if i >= recent_threshold else ""
        rendered_lines.append(
            f'<div class="v-log-line{recent_cls} {cls_extra}">{_escape(line)}</div>'
        )

    st.markdown(f'<div class="v-log">{"".join(rendered_lines)}</div>', unsafe_allow_html=True)


def _render_score(score: float, feedback: str) -> None:
    """Quality score gauge + feedback."""
    score_clamped = max(0.0, min(1.0, score))
    pct = int(round(score_clamped * 100))
    feedback_html = _escape(feedback) if feedback else "No feedback notes."
    st.markdown(
        f'<div class="v-score">'
        f'<div class="v-score-row">'
        f'<div class="v-score-value">{score_clamped:.2f}</div>'
        f'<div class="v-score-label">Quality · {pct}%</div>'
        f'</div>'
        f'<div class="v-score-bar"><div class="v-score-bar-fill" style="width: {pct}%"></div></div>'
        f'<div class="v-score-feedback">{feedback_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_history(exclude_thread_id: Optional[str] = None) -> None:
    """Recent runs panel with re-run actions."""
    raw = st.session_state.get("orch_history", [])
    history = [h for h in raw if h["thread_id"] != exclude_thread_id]
    if not history:
        return

    st.markdown('<div class="v-section-title">📜 Recent runs</div>', unsafe_allow_html=True)

    for entry in reversed(history[-10:]):
        ts = datetime.fromtimestamp(entry["started_at"]).strftime("%H:%M:%S")
        status_emoji = {"completed": "✅", "stopped": "⏹", "failed": "❌"}.get(entry["status"], "•")
        score_str = f" · score {entry['score']:.2f}" if entry.get("score") is not None else ""
        elapsed = entry.get("elapsed", 0.0)
        task_preview = entry["task"][:90] + ("…" if len(entry["task"]) > 90 else "")

        with st.expander(
            f"{status_emoji}  {ts}  ·  {task_preview}  ·  {elapsed:.1f}s{score_str}",
            expanded=False,
        ):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                if entry.get("final_answer"):
                    st.markdown(entry["final_answer"])
                elif entry.get("error"):
                    st.error(entry["error"])
                else:
                    st.info("No final answer for this run.")
            with col_b:
                if st.button(
                    "🔁  Re-run",
                    key=f"v_rerun_hist_{entry['thread_id']}",
                    use_container_width=True,
                ):
                    st.session_state.orch_run = start_run(entry["task"])
                    st.rerun()

            if entry.get("plan") or entry.get("log"):
                with st.expander("Show details", expanded=False):
                    if entry.get("plan"):
                        _render_plan_cards(entry["plan"])
                    if entry.get("log"):
                        _render_log(entry["log"])


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════

def _classify_log_line(line: str) -> str:
    """Map a log line to a CSS class based on its leading emoji / keywords."""
    if not line:
        return ""
    if "❌" in line or "Error" in line or "failed" in line.lower():
        return "v-log--error"
    if "⏹" in line or "Stopped" in line:
        return "v-log--stop"
    if "⚠️" in line:
        return "v-log--warn"
    if "✅" in line or "🎯" in line:
        return "v-log--success"
    if "🧠" in line or "📊" in line or "🧩" in line or "📦" in line:
        return "v-log--info"
    if "▶️" in line or "⚡" in line:
        return "v-log--action"
    if "🧪" in line:
        return "v-log--eval"
    if "♻️" in line:
        return "v-log--refine"
    return ""


def _escape(text: str) -> str:
    """Minimal HTML escape — we control most of the content but log lines are open-ended."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
