"""
ui/department_views.py
──────────────────────
Direct-access views for each department.

Useful when the user already knows which specialist they want — skips the
orchestrator overhead. Styled to match the same Miami-Beach dark aesthetic
as the orchestrator view.
"""

from __future__ import annotations

import time

import streamlit as st

from crews.orchestrator.departments import DEPARTMENTS, DEPARTMENT_LABELS


# Per-department gradient accent. Keeps every tab visually distinct without
# losing the unified palette.
_DEPT_ACCENTS: dict[str, tuple[str, str]] = {
    "marketing": ("#ec4899", "#f472b6"),   # coral pink
    "bakery":    ("#f59e0b", "#fcd34d"),   # warm amber
    "comms":     ("#06b6d4", "#67e8f9"),   # cyan
    "mlo_coach": ("#a855f7", "#c084fc"),   # violet
}
_DEFAULT_ACCENT = ("#38bdf8", "#7dd3fc")

_CSS = """
<style>
/* ── Header ───────────────────────────────────────────────────────────── */
.v-dept-header {
    position: relative;
    padding: 2rem 2rem 1.7rem 2rem;
    border-radius: 22px;
    background:
        radial-gradient(ellipse at 100% 0%, rgba(236, 72, 153, 0.14) 0%, transparent 55%),
        radial-gradient(ellipse at 0% 100%, rgba(6, 182, 212, 0.18) 0%, transparent 55%),
        linear-gradient(135deg, #08101e 0%, #0f1a2e 50%, #0a1426 100%);
    border: 1px solid rgba(56, 189, 248, 0.12);
    margin-bottom: 1.5rem;
    overflow: hidden;
    box-shadow: 0 18px 50px -28px rgba(6, 182, 212, 0.3);
}
.v-dept-header::before {
    content: "";
    position: absolute; inset: 0;
    background: repeating-linear-gradient(
        45deg,
        rgba(56, 189, 248, 0.025) 0px, rgba(56, 189, 248, 0.025) 1px,
        transparent 1px, transparent 14px
    );
    pointer-events: none;
}
.v-dept-header-eyebrow {
    font-size: 0.68rem; letter-spacing: 0.32em;
    text-transform: uppercase; color: #38bdf8;
    font-weight: 600; opacity: 0.9; position: relative;
}
.v-dept-header-title {
    font-size: 2.1rem; font-weight: 800;
    margin: 0.4rem 0 0.4rem 0; letter-spacing: -0.025em;
    line-height: 1.05; position: relative;
    background: linear-gradient(120deg, #f1f5f9 0%, #38bdf8 45%, #ec4899 100%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
}
.v-dept-header-sub {
    color: #94a3b8; font-size: 0.96rem;
    line-height: 1.6; max-width: 64ch; position: relative;
}

/* ── Department panel (per tab) ──────────────────────────────────────── */
.v-dept-panel {
    padding: 1.5rem 1.7rem;
    border-radius: 18px;
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.65) 0%, rgba(15, 23, 42, 0.35) 100%);
    border: 1px solid rgba(56, 189, 248, 0.12);
    margin-top: 0.6rem;
    margin-bottom: 1.1rem;
}
.v-dept-panel-head {
    display: flex; align-items: flex-start; gap: 0.95rem;
    padding-bottom: 1rem;
    margin-bottom: 1rem;
    border-bottom: 1px solid rgba(56, 189, 248, 0.08);
}
.v-dept-panel-emoji {
    font-size: 2.1rem; line-height: 1;
    flex-shrink: 0;
}
.v-dept-panel-name {
    font-weight: 800; color: #f1f5f9;
    font-size: 1.25rem; letter-spacing: -0.015em;
    line-height: 1.2;
}
.v-dept-panel-summary {
    color: #94a3b8; font-size: 0.88rem;
    margin-top: 0.3rem; line-height: 1.55;
    max-width: 60ch;
}

/* ── Output card ──────────────────────────────────────────────────────── */
.v-dept-output {
    padding: 1.5rem 1.7rem;
    border-radius: 16px;
    background:
        radial-gradient(ellipse at top right, rgba(16, 185, 129, 0.05) 0%, transparent 50%),
        linear-gradient(135deg, rgba(15, 23, 42, 0.6) 0%, rgba(6, 78, 59, 0.10) 100%);
    border: 1px solid rgba(16, 185, 129, 0.18);
    margin-top: 1rem;
}
.v-dept-output-head {
    display: flex; align-items: center; gap: 0.55rem;
    padding-bottom: 0.7rem;
    margin-bottom: 0.85rem;
    border-bottom: 1px solid rgba(16, 185, 129, 0.14);
}
.v-dept-output-title {
    font-weight: 700; color: #6ee7b7;
    font-size: 0.72rem;
    text-transform: uppercase; letter-spacing: 0.2em;
}
.v-dept-output-meta {
    margin-left: auto;
    color: #64748b; font-size: 0.72rem;
    font-variant-numeric: tabular-nums;
}

/* ── Empty hint ───────────────────────────────────────────────────────── */
.v-dept-empty {
    color: #64748b; font-size: 0.86rem;
    padding: 1.2rem 1rem; text-align: center; font-style: italic;
    border: 1px dashed rgba(56, 189, 248, 0.13);
    border-radius: 12px;
    margin-top: 0.4rem;
}
</style>
"""


def render_department_section() -> None:
    """Tabbed view: one tab per department for direct conversations."""
    st.markdown(_CSS, unsafe_allow_html=True)

    # ── Header ─────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="v-dept-header">
        <div class="v-dept-header-eyebrow">V Platform · Direct Access</div>
        <div class="v-dept-header-title">🏢 Departments</div>
        <div class="v-dept-header-sub">
            Skip the orchestrator and talk to a specialist directly. Use this
            when you already know which department owns the problem and don&rsquo;t
            need cross-team coordination.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Tabs ───────────────────────────────────────────────────────────────
    dept_keys = list(DEPARTMENTS.keys())
    tabs = st.tabs(
        [f"{DEPARTMENT_LABELS[k]['emoji']}  {DEPARTMENT_LABELS[k]['name']}" for k in dept_keys]
    )

    for tab, key in zip(tabs, dept_keys):
        with tab:
            _render_department_tab(key)


def _render_department_tab(key: str) -> None:
    """Render one department tab — header + input + output."""
    label = DEPARTMENT_LABELS[key]
    accent_a, accent_b = _DEPT_ACCENTS.get(key, _DEFAULT_ACCENT)

    # ── Department panel header (with custom accent border) ───────────────
    st.markdown(f"""
    <div class="v-dept-panel" style="border-color:{accent_a}33;">
        <div class="v-dept-panel-head" style="border-bottom-color:{accent_a}22;">
            <div class="v-dept-panel-emoji" style="filter: drop-shadow(0 0 12px {accent_a}55);">
                {label['emoji']}
            </div>
            <div>
                <div class="v-dept-panel-name">{label['name']}</div>
                <div class="v-dept-panel-summary">{label['summary']}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Input + actions ───────────────────────────────────────────────────
    prompt_key  = f"dept_{key}_input"
    output_key  = f"dept_{key}_output"
    running_key = f"dept_{key}_running"
    elapsed_key = f"dept_{key}_elapsed"

    user_input = st.text_area(
        "Your request",
        key=prompt_key,
        height=140,
        placeholder=f"Ask {label['name']} for something specific…",
        label_visibility="collapsed",
    )

    col_a, col_b, _spacer = st.columns([1.5, 1.1, 1.6])
    with col_a:
        send_clicked = st.button(
            f"📨  Send to {label['name']}",
            key=f"dept_{key}_btn",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.get(running_key, False) or not user_input.strip(),
        )
    with col_b:
        clear_clicked = st.button(
            "🧹  Clear",
            key=f"dept_{key}_clear",
            use_container_width=True,
            disabled=not st.session_state.get(output_key),
        )

    if clear_clicked:
        st.session_state.pop(output_key, None)
        st.session_state.pop(elapsed_key, None)
        st.rerun()

    if send_clicked and user_input.strip():
        st.session_state[running_key] = True
        try:
            t0 = time.time()
            with st.spinner(f"{label['name']} is working…"):
                result = DEPARTMENTS[key](user_input.strip(), "")
            st.session_state[output_key]  = result
            st.session_state[elapsed_key] = time.time() - t0
        finally:
            st.session_state[running_key] = False

    # ── Output ────────────────────────────────────────────────────────────
    output = st.session_state.get(output_key)
    elapsed = st.session_state.get(elapsed_key)

    if output:
        meta = f"{elapsed:.1f}s" if elapsed else ""
        st.markdown(f"""
        <div class="v-dept-output">
            <div class="v-dept-output-head">
                <span style="font-size:1.2rem">🎯</span>
                <span class="v-dept-output-title">{label['name']} · Response</span>
                <span class="v-dept-output-meta">{meta}</span>
            </div>
        """, unsafe_allow_html=True)
        st.markdown(output)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="v-dept-empty">'
            'Send a request above to see the response here.'
            '</div>',
            unsafe_allow_html=True,
        )
