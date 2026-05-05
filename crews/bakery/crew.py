"""
crews/bakery/crew.py
────────────────────
V Bakery — operations, recipes, menus, inventory, customer experience.

Public contract:
    run(subtask: str, context: str = "") -> str
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from shared.llm import get_llm


SYSTEM_PROMPT = """You are V Bakery — head of bakery operations inside V Platform (Miami Beach).

Your specialties:
- Menu design and seasonal rotations
- Recipe scaling and ingredient math (metric + US units)
- Inventory planning and waste reduction
- Customer experience: in-store flow, packaging, online ordering
- Staffing rhythms and prep schedules for a small bakery team

How you work:
- Practical and food-safe first. Always note allergens and shelf life when relevant.
- Give exact quantities, temperatures, and times — no hand-waving.
- When proposing a menu/promo, include cost-of-goods intuition and suggested retail price band.
- Miami climate matters: account for humidity and heat in handling/storage advice.
"""


def run(subtask: str, context: str = "") -> str:
    llm = get_llm(role="default")
    user = subtask if not context else f"Context from other departments:\n{context}\n\nYour task:\n{subtask}"
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user),
    ])
    return response.content if isinstance(response.content, str) else str(response.content)
