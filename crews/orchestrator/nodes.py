"""
crews/orchestrator/nodes.py
───────────────────────────
The actual functions that LangGraph runs as nodes.

Each node:
- Receives the full OrchestratorState
- Does one focused thing
- Returns a partial state dict that LangGraph merges into the global state

Design principles:
- Nodes are pure functions of state where possible (deterministic given inputs).
- All LLM calls are isolated here so the graph wiring (graph.py) stays trivial.
- Errors are caught and turned into log entries + status flags rather than crashing
  the whole run — Phase 1 must be observable, not fragile.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from shared.llm import get_llm

from .departments import DEPARTMENT_LABELS, get_runner
from .prompts import (
    ANALYSIS_PROMPT,
    DECOMPOSITION_PROMPT,
    EVALUATION_PROMPT,
    ORCHESTRATOR_IDENTITY,
    REFINEMENT_PROMPT,
    SYNTHESIS_PROMPT,
)
from .state import OrchestratorState, Subtask


# ── helpers ─────────────────────────────────────────────────────────────────

_VALID_DEPARTMENTS = set(DEPARTMENT_LABELS.keys())


def _extract_json(text: str) -> Any:
    """
    Extract a JSON value from an LLM response, tolerating accidental
    ```json fences or surrounding prose.
    """
    # Strip code fences if present
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)

    # Find first JSON-looking span (object or array) and try to parse it.
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    raise ValueError(f"Could not parse JSON from LLM response: {text[:300]}")


def _llm_call(prompt: str, *, role: str = "default") -> str:
    """Single-shot LLM call with the orchestrator identity baked in."""
    llm = get_llm(role=role)  # type: ignore[arg-type]
    response = llm.invoke([
        SystemMessage(content=ORCHESTRATOR_IDENTITY),
        HumanMessage(content=prompt),
    ])
    return response.content if isinstance(response.content, str) else str(response.content)


# ── 1. analyze ──────────────────────────────────────────────────────────────

def analyze_task_node(state: OrchestratorState) -> dict:
    """Read the user task and produce a strategic analysis."""
    user_task = state["user_task"]
    prompt = ANALYSIS_PROMPT.format(user_task=user_task)
    analysis = _llm_call(prompt, role="strategist")

    return {
        "phase": "analyzing",
        "analysis": analysis,
        "log": [f"📊 Analyzed task ({len(analysis)} chars)."],
    }


# ── 2. decompose ────────────────────────────────────────────────────────────

def decompose_task_node(state: OrchestratorState) -> dict:
    """Turn the analysis into a concrete subtask plan."""
    prompt = DECOMPOSITION_PROMPT.format(
        analysis=state["analysis"],
        user_task=state["user_task"],
    )
    raw = _llm_call(prompt, role="strategist")

    try:
        plan_raw = _extract_json(raw)
        if not isinstance(plan_raw, list):
            raise ValueError("Plan must be a JSON array.")
        subtasks: list[Subtask] = []
        for i, item in enumerate(plan_raw, start=1):
            dept = item.get("department")
            if dept not in _VALID_DEPARTMENTS:
                # Self-heal: drop unknown departments rather than failing the whole run
                continue
            subtasks.append(Subtask(
                id=str(item.get("id") or f"task_{i}"),
                description=str(item["description"]).strip(),
                department=dept,
                priority=int(item.get("priority", 3)),
                status="pending",
                result=None,
                error=None,
            ))

        if not subtasks:
            raise ValueError("Decomposition produced zero valid subtasks.")
    except Exception as e:
        return {
            "phase": "failed",
            "log": [f"❌ Decomposition failed: {e}"],
            "subtasks": [],
        }

    # Order by priority so important work runs first.
    subtasks.sort(key=lambda s: s["priority"])

    plan_summary = ", ".join(
        f"{DEPARTMENT_LABELS[s['department']]['emoji']} {DEPARTMENT_LABELS[s['department']]['name']}"
        for s in subtasks
    )

    return {
        "phase": "decomposing",
        "subtasks": subtasks,
        "log": [f"🧩 Decomposed into {len(subtasks)} subtask(s): {plan_summary}"],
    }


# ── 3. execute ──────────────────────────────────────────────────────────────

def execute_subtasks_node(state: OrchestratorState) -> dict:
    """
    Run every pending subtask sequentially, passing already-completed results
    as context to later subtasks (lightweight 'memory' between specialists).

    Sequential is the right default for v1: it keeps results coherent and
    makes the live UI log readable. Parallel fan-out can replace this loop
    later (LangGraph supports it via Send / branching).
    """
    subtasks = list(state.get("subtasks") or [])
    if not subtasks:
        return {"phase": "failed", "log": ["❌ No subtasks to execute."]}

    log_entries: list[str] = []
    completed_context = state.get("aggregated_result", "") or ""

    for st in subtasks:
        if st["status"] == "completed":
            continue  # Already done in a previous iteration.

        st["status"] = "in_progress"
        label = DEPARTMENT_LABELS[st["department"]]
        log_entries.append(f"▶️ {label['emoji']} {label['name']} → {st['description'][:80]}")

        try:
            runner = get_runner(st["department"])
            result = runner(st["description"], completed_context)
            st["result"] = result
            st["status"] = "completed"
            log_entries.append(f"✅ {label['name']} done ({len(result)} chars).")
            # Make this result visible to subsequent specialists.
            completed_context += f"\n\n### {label['name']} — {st['id']}\n{result}"
        except Exception as e:  # noqa: BLE001
            st["status"] = "failed"
            st["error"] = str(e)
            log_entries.append(f"❌ {label['name']} failed: {e}")

    return {
        "phase": "executing",
        "subtasks": subtasks,
        "log": log_entries,
    }


# ── 4. aggregate ────────────────────────────────────────────────────────────

def aggregate_results_node(state: OrchestratorState) -> dict:
    """Concatenate the raw outputs from every completed subtask."""
    parts: list[str] = []
    for st in state.get("subtasks", []):
        if st["status"] != "completed" or not st["result"]:
            continue
        label = DEPARTMENT_LABELS[st["department"]]
        parts.append(f"## {label['emoji']} {label['name']} — {st['id']}\n\n{st['result']}")

    aggregated = "\n\n---\n\n".join(parts) if parts else ""

    return {
        "phase": "aggregating",
        "aggregated_result": aggregated,
        "log": [f"📦 Aggregated {len(parts)} department result(s)."],
    }


# ── 5. evaluate ─────────────────────────────────────────────────────────────

def evaluate_quality_node(state: OrchestratorState) -> dict:
    """Score the aggregated result against the original task."""
    aggregated = state.get("aggregated_result", "")
    if not aggregated:
        return {
            "phase": "evaluating",
            "quality_score": 0.0,
            "quality_feedback": "No aggregated content produced.",
            "log": ["⚠️ Nothing to evaluate."],
        }

    prompt = EVALUATION_PROMPT.format(
        user_task=state["user_task"],
        aggregated_result=aggregated,
    )
    raw = _llm_call(prompt, role="strategist")

    try:
        verdict = _extract_json(raw)
        score = float(verdict.get("score", 0.0))
        feedback = str(verdict.get("feedback", "")).strip()
    except Exception as e:  # noqa: BLE001
        # If the evaluator misbehaves, treat the result as good enough rather
        # than spinning forever. We still log the failure.
        return {
            "phase": "evaluating",
            "quality_score": state.get("quality_threshold", 0.8),
            "quality_feedback": "Evaluator unavailable; accepting result as-is.",
            "log": [f"⚠️ Evaluator parse error ({e}); skipping refine."],
        }

    return {
        "phase": "evaluating",
        "quality_score": score,
        "quality_feedback": feedback,
        "log": [f"🧪 Quality score: {score:.2f}"],
    }


# ── 6. refine (re-plan) ─────────────────────────────────────────────────────

def refine_node(state: OrchestratorState) -> dict:
    """
    Build a *new*, smaller subtask plan that targets the evaluator's feedback.
    The graph then loops back through `execute` to run only these new subtasks.
    """
    prompt = REFINEMENT_PROMPT.format(
        score=state.get("quality_score", 0.0),
        feedback=state.get("quality_feedback", ""),
        aggregated_result=state.get("aggregated_result", ""),
        user_task=state["user_task"],
    )
    raw = _llm_call(prompt, role="strategist")

    try:
        plan_raw = _extract_json(raw)
        new_subtasks: list[Subtask] = []
        for i, item in enumerate(plan_raw, start=1):
            dept = item.get("department")
            if dept not in _VALID_DEPARTMENTS:
                continue
            new_subtasks.append(Subtask(
                id=str(item.get("id") or f"refine_{state.get('iteration', 0) + 1}_{i}"),
                description=str(item["description"]).strip(),
                department=dept,
                priority=int(item.get("priority", 2)),
                status="pending",
                result=None,
                error=None,
            ))
    except Exception as e:  # noqa: BLE001
        return {
            "phase": "failed",
            "log": [f"❌ Refinement plan parse failed: {e}"],
        }

    # Keep already-completed work, append the new targeted subtasks.
    merged = list(state.get("subtasks", [])) + new_subtasks

    return {
        "phase": "refining",
        "subtasks": merged,
        "iteration": state.get("iteration", 0) + 1,
        "log": [f"♻️ Refining: added {len(new_subtasks)} targeted subtask(s)."],
    }


# ── 7. synthesize final ─────────────────────────────────────────────────────

def synthesize_final_node(state: OrchestratorState) -> dict:
    """Produce the polished, user-facing final answer."""
    prompt = SYNTHESIS_PROMPT.format(
        user_task=state["user_task"],
        aggregated_result=state.get("aggregated_result", ""),
    )
    final = _llm_call(prompt, role="default")
    return {
        "phase": "completed",
        "final_answer": final,
        "log": ["🎯 Final answer synthesized."],
    }


# ── conditional router ─────────────────────────────────────────────────────

def should_refine(state: OrchestratorState) -> str:
    """
    Decide whether to loop back for another pass or move on to synthesis.

    Returns the literal node name to route to.
    """
    score = state.get("quality_score", 0.0)
    threshold = state.get("quality_threshold", 0.8)
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 2)

    if score >= threshold:
        return "synthesize"
    if iteration >= max_iter:
        return "synthesize"
    return "refine"
