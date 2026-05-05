"""
crews/orchestrator/departments.py
─────────────────────────────────
Registry that maps a department name to its callable runner.

This is the single source of truth used by the orchestrator's `execute` node
to dispatch subtasks. Adding a new department to V Platform = adding one line
here plus creating a new crew module.

Each runner has the signature:
    runner(subtask: str, context: str = "") -> str
"""

from __future__ import annotations

from typing import Callable

from crews.bakery import crew as bakery_crew
from crews.comms import crew as comms_crew
from crews.marketing import crew as marketing_crew
from crews.mlo_coach import crew as mlo_coach_crew


DepartmentRunner = Callable[[str, str], str]


DEPARTMENTS: dict[str, DepartmentRunner] = {
    "marketing": marketing_crew.run,
    "bakery":    bakery_crew.run,
    "comms":     comms_crew.run,
    "mlo_coach": mlo_coach_crew.run,
}


# Human-readable metadata for the UI sidebar / status display.
DEPARTMENT_LABELS: dict[str, dict[str, str]] = {
    "marketing": {"name": "V Marketing", "emoji": "📣", "summary": "Brand, content, social, ads"},
    "bakery":    {"name": "V Bakery",    "emoji": "🥐", "summary": "Recipes, menus, operations"},
    "comms":     {"name": "V Comms",     "emoji": "✉️", "summary": "Emails, announcements, PR"},
    "mlo_coach": {"name": "V MLO Coach", "emoji": "🏠", "summary": "MLO coaching, real estate finance"},
}


def get_runner(department: str) -> DepartmentRunner:
    """Return the runner for a department, raising a clear error if unknown."""
    try:
        return DEPARTMENTS[department]
    except KeyError as e:
        raise ValueError(
            f"Unknown department {department!r}. "
            f"Known: {sorted(DEPARTMENTS.keys())}."
        ) from e


def list_departments() -> list[str]:
    """For UI listings."""
    return list(DEPARTMENTS.keys())
