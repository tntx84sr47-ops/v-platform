"""
crews/orchestrator/state.py
───────────────────────────
The shared state that flows through the V Orchestrator LangGraph.

LangGraph state is just a TypedDict where each key is a "channel". Channels can
be:
  - replaced on every update (default), or
  - reduced via Annotated[T, reducer]   (e.g. append to a log)

We keep state explicit and small — every field has a clear purpose.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Literal, Optional, TypedDict


# Departments the orchestrator can route work to.
# Add a new value here AND register a runner in crews/orchestrator/departments.py
# to expand the platform.
DepartmentName = Literal["marketing", "bakery", "comms", "mlo_coach"]

SubtaskStatus = Literal["pending", "in_progress", "completed", "failed"]
OrchestratorPhase = Literal[
    "idle",
    "analyzing",
    "decomposing",
    "executing",
    "aggregating",
    "evaluating",
    "refining",
    "synthesizing",
    "completed",
    "failed",
]


class Subtask(TypedDict):
    """One unit of work owned by a single department."""
    id: str
    description: str
    department: DepartmentName
    priority: int          # 1 = highest, 5 = lowest
    status: SubtaskStatus
    result: Optional[str]
    error: Optional[str]


class OrchestratorState(TypedDict, total=False):
    """
    The full state object shared between every node in the orchestrator graph.

    `total=False` means every key is optional — the graph fills them in over time.
    """

    # ── Inputs ────────────────────────────────────────────────────────────────
    user_task: str

    # ── Planning artifacts ────────────────────────────────────────────────────
    analysis: str                 # Free-text analysis from analyze_task_node
    subtasks: list[Subtask]       # Plan produced by decompose_task_node

    # ── Execution ─────────────────────────────────────────────────────────────
    iteration: int                # 0 on first execution, increments on refine
    max_iterations: int

    # ── Evaluation ────────────────────────────────────────────────────────────
    quality_score: float          # 0.0–1.0
    quality_feedback: str
    quality_threshold: float

    # ── Outputs ───────────────────────────────────────────────────────────────
    aggregated_result: str        # Concatenated department outputs
    final_answer: str             # Polished synthesis returned to user

    # ── Telemetry ─────────────────────────────────────────────────────────────
    phase: OrchestratorPhase
    log: Annotated[list[str], add]  # Reducer: append-only event log for the UI


def initial_state(user_task: str, *, max_iterations: int = 2, quality_threshold: float = 0.8) -> OrchestratorState:
    """Construct a fresh state for a new orchestrator run."""
    return OrchestratorState(
        user_task=user_task.strip(),
        analysis="",
        subtasks=[],
        iteration=0,
        max_iterations=max_iterations,
        quality_score=0.0,
        quality_feedback="",
        quality_threshold=quality_threshold,
        aggregated_result="",
        final_answer="",
        phase="idle",
        log=[],
    )
