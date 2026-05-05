"""
crews/orchestrator/graph.py
───────────────────────────
The actual LangGraph wiring for V Orchestrator.

Topology:

    START
      │
      ▼
   analyze ──► decompose ──► execute ──► aggregate ──► evaluate
                                                         │
                                            ┌────────────┴────────────┐
                                            │                         │
                                       (low score &                (good
                                        iter < max)              enough)
                                            │                         │
                                            ▼                         ▼
                                          refine ──► execute     synthesize
                                                                      │
                                                                      ▼
                                                                     END

Public API:
    build_orchestrator_graph()     → returns a compiled CompiledGraph
    run_orchestrator(user_task)    → one-shot synchronous runner
    stream_orchestrator(user_task) → generator yielding state snapshots for the UI
"""

from __future__ import annotations

import os
from typing import Iterator

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import (
    aggregate_results_node,
    analyze_task_node,
    decompose_task_node,
    evaluate_quality_node,
    execute_subtasks_node,
    refine_node,
    should_refine,
    synthesize_final_node,
)
from .state import OrchestratorState, initial_state


def build_orchestrator_graph(*, with_checkpointer: bool = True):
    """
    Assemble and compile the orchestrator graph.

    Args:
        with_checkpointer: attach an in-memory checkpointer so a run can be
                           resumed/inspected. Set False for stateless tests.
    """
    g = StateGraph(OrchestratorState)

    # Register nodes ---------------------------------------------------------
    g.add_node("analyze",    analyze_task_node)
    g.add_node("decompose",  decompose_task_node)
    g.add_node("execute",    execute_subtasks_node)
    g.add_node("aggregate",  aggregate_results_node)
    g.add_node("evaluate",   evaluate_quality_node)
    g.add_node("refine",     refine_node)
    g.add_node("synthesize", synthesize_final_node)

    # Wire edges -------------------------------------------------------------
    g.add_edge(START, "analyze")
    g.add_edge("analyze", "decompose")
    g.add_edge("decompose", "execute")
    g.add_edge("execute", "aggregate")
    g.add_edge("aggregate", "evaluate")

    # Conditional: either refine (loop back) or finalize.
    g.add_conditional_edges(
        "evaluate",
        should_refine,
        {
            "refine":     "refine",
            "synthesize": "synthesize",
        },
    )

    # Refining produces new subtasks → execute them.
    g.add_edge("refine", "execute")

    # Done.
    g.add_edge("synthesize", END)

    checkpointer = MemorySaver() if with_checkpointer else None
    return g.compile(checkpointer=checkpointer)


# Module-level singleton — building the graph is cheap, but we want to share
# it across Streamlit reruns.
_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_orchestrator_graph()
    return _GRAPH


# ── Convenience runners ────────────────────────────────────────────────────

def _build_initial(user_task: str) -> OrchestratorState:
    return initial_state(
        user_task,
        max_iterations=int(os.getenv("V_ORCHESTRATOR_MAX_ITERATIONS", "2")),
        quality_threshold=float(os.getenv("V_ORCHESTRATOR_QUALITY_THRESHOLD", "0.8")),
    )


def run_orchestrator(user_task: str, *, thread_id: str = "default") -> OrchestratorState:
    """Synchronous one-shot run. Returns the final state."""
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(_build_initial(user_task), config=config)
    return result  # type: ignore[return-value]


def stream_orchestrator(user_task: str, *, thread_id: str = "default") -> Iterator[tuple[str, dict]]:
    """
    Stream state updates for the UI.

    Yields tuples of (node_name, partial_state_update) as each node completes.
    The UI uses this to render a live progress feed.
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    # stream_mode="updates" → each yield is {node_name: partial_update}
    for chunk in graph.stream(_build_initial(user_task), config=config, stream_mode="updates"):
        for node_name, update in chunk.items():
            yield node_name, update or {}
