"""
ui/run_manager.py
─────────────────
Threaded run manager for V Orchestrator.

Why a thread? Streamlit's main script blocks on synchronous code. If we run the
orchestrator inline, we can't update the UI mid-run, can't react to a Stop
click, and can't show a real elapsed timer.

The pattern:
    Streamlit script ──► start_run() ──► spawns daemon thread
                                          │
                                          ▼
                                    runs stream_orchestrator()
                                          │
                                          ▼
                                    pushes (node_name, update) into a Queue
                                          │
    Streamlit fragment ◄── drain_updates() ───┘   (every ~400ms)

Graceful stop is implemented as a `threading.Event`. The thread checks it
between graph nodes — so a stop takes effect at the next node boundary, not
mid-LLM-call. Honest semantics, predictable behavior.
"""

from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

# Streamlit's threading helper — silences "missing ScriptRunContext" warnings
# when our background thread is started. The thread doesn't actually call
# Streamlit APIs, but adding the context keeps the logs clean.
try:
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
except ImportError:  # very old Streamlit — skip silently
    add_script_run_ctx = None  # type: ignore[assignment]
    get_script_run_ctx = None  # type: ignore[assignment]

from crews.orchestrator.graph import stream_orchestrator


# Sentinel keys placed into the queue by the runner thread to signal lifecycle.
_DONE     = "__DONE__"
_STOPPED  = "__STOPPED__"
_ERROR    = "__ERROR__"


@dataclass
class OrchRun:
    """
    One orchestrator run — live, completed, stopped, or failed.

    The dataclass is the single source of truth for the UI: the fragment reads
    fields off it, the thread writes updates into the queue, and `drain_updates`
    moves data from queue → fields.
    """

    # Identity ────────────────────────────────────────────────────────────────
    thread_id: str
    task: str

    # Threading primitives ────────────────────────────────────────────────────
    _queue: queue.Queue = field(default_factory=queue.Queue, repr=False)
    stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    thread: Optional[threading.Thread] = field(default=None, repr=False)

    # Lifecycle ───────────────────────────────────────────────────────────────
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    is_active: bool = True
    status: str = "running"   # running | completed | stopped | failed
    error: Optional[str] = None

    # Aggregated graph state (populated by drain_updates) ─────────────────────
    phase: str = "queued"
    log: list[str] = field(default_factory=list)
    plan: list[dict] = field(default_factory=list)
    score: Optional[float] = None
    feedback: str = ""
    aggregated_result: str = ""
    final_answer: str = ""
    iteration: int = 0

    # ── Derived properties ──────────────────────────────────────────────────

    @property
    def elapsed(self) -> float:
        """Wall-clock seconds since the run started."""
        end = self.finished_at if self.finished_at is not None else time.time()
        return max(0.0, end - self.started_at)

    @property
    def is_alive(self) -> bool:
        """Whether the underlying thread is still running."""
        return self.thread is not None and self.thread.is_alive()

    def to_history_entry(self) -> dict:
        """Snapshot the run as a plain dict for storage in session history."""
        return {
            "thread_id":         self.thread_id,
            "task":              self.task,
            "status":            self.status,
            "phase":             self.phase,
            "log":               list(self.log),
            "plan":              list(self.plan),
            "score":             self.score,
            "feedback":          self.feedback,
            "final_answer":      self.final_answer,
            "started_at":        self.started_at,
            "finished_at":       self.finished_at,
            "elapsed":           self.elapsed,
            "iteration":         self.iteration,
            "error":             self.error,
        }


# ── Thread target ───────────────────────────────────────────────────────────

def _runner(task: str, thread_id: str, q: queue.Queue, stop_event: threading.Event) -> None:
    """
    Background thread: stream orchestrator updates into the queue.

    Why we wrap stream_orchestrator instead of letting the UI consume it
    directly: this thread is the *only* place we check the stop event, so the
    UI never has to know about graph internals.
    """
    try:
        for node_name, update in stream_orchestrator(task, thread_id=thread_id):
            if stop_event.is_set():
                q.put((_STOPPED, {}))
                return
            q.put((node_name, update or {}))
        q.put((_DONE, {}))
    except Exception as e:  # noqa: BLE001
        q.put((_ERROR, {"error": f"{type(e).__name__}: {e}"}))


# ── Public API ──────────────────────────────────────────────────────────────

def start_run(task: str) -> OrchRun:
    """Create an OrchRun and start its background thread."""
    run = OrchRun(thread_id=uuid.uuid4().hex, task=task.strip())
    t = threading.Thread(
        target=_runner,
        args=(run.task, run.thread_id, run._queue, run.stop_event),
        name=f"v-orch-{run.thread_id[:8]}",
        daemon=True,
    )

    # Attach Streamlit's script run context so the logs stay clean.
    if add_script_run_ctx and get_script_run_ctx:
        ctx = get_script_run_ctx()
        if ctx is not None:
            add_script_run_ctx(t, ctx)

    run.thread = t
    t.start()
    return run


def drain_updates(run: OrchRun) -> int:
    """
    Move every available message from the queue into the run's fields.

    Safe to call frequently; returns the number of updates applied so the
    caller (the fragment) can decide whether anything changed.
    """
    if run.status != "running":
        return 0

    applied = 0
    try:
        while True:
            node_name, update = run._queue.get_nowait()
            applied += 1

            if node_name == _STOPPED:
                run.status = "stopped"
                run.is_active = False
                run.finished_at = time.time()
                run.log.append("⏹ Stopped by user.")
                return applied

            if node_name == _DONE:
                run.status = "completed"
                run.is_active = False
                run.finished_at = time.time()
                return applied

            if node_name == _ERROR:
                run.status = "failed"
                run.is_active = False
                run.finished_at = time.time()
                run.error = update.get("error", "Unknown error")
                run.log.append(f"❌ Error: {run.error}")
                return applied

            _apply_node_update(run, update)

    except queue.Empty:
        pass

    return applied


def request_stop(run: OrchRun) -> None:
    """Signal graceful stop. Takes effect at the next graph node boundary."""
    if run.is_alive:
        run.stop_event.set()


# ── internal ────────────────────────────────────────────────────────────────

def _apply_node_update(run: OrchRun, update: dict) -> None:
    """Merge a partial OrchestratorState update into our aggregated run state."""
    if "phase" in update:
        run.phase = update["phase"]
    if "log" in update and isinstance(update["log"], list):
        run.log.extend(update["log"])
    if "subtasks" in update and update["subtasks"]:
        run.plan = list(update["subtasks"])
    if "quality_score" in update:
        run.score = float(update["quality_score"])
    if "quality_feedback" in update:
        run.feedback = str(update["quality_feedback"])
    if "aggregated_result" in update:
        run.aggregated_result = update["aggregated_result"]
    if "iteration" in update:
        run.iteration = int(update["iteration"])
    if "final_answer" in update:
        run.final_answer = update["final_answer"]
