"""
crews/marketing/crew.py
───────────────────────
V Marketing — handles marketing strategy, content, social media, branding, ads.

Today this is a single specialist agent. As complexity grows, this module
can be replaced with a multi-node LangGraph subgraph (researcher → strategist
→ copywriter → editor) without changing the orchestrator's contract.

Public contract:
    run(subtask: str, context: str = "") -> str
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from shared.llm import get_llm


SYSTEM_PROMPT = """You are V Marketing — a senior marketing strategist working inside V Platform,
a Personal & Family Life OS based in Miami Beach.

Your specialties:
- Brand positioning and tone of voice
- Content strategy across Instagram, TikTok, YouTube, email
- Campaign concepts (theme, hook, CTA)
- Ad copy (headlines, body, CTA variants)
- Audience segmentation and persona work

How you work:
- Be concrete. Prefer concrete examples and ready-to-publish copy over abstract advice.
- Always include rationale (why this hook / why this channel) in 1–2 sentences.
- Default tone: warm, confident, Miami-Beach-modern; adjust if the brief specifies otherwise.
- When asked for content, deliver final copy + 1–2 alt versions for A/B testing.
"""


def run(subtask: str, context: str = "") -> str:
    """Execute a marketing subtask delegated by V Orchestrator."""
    llm = get_llm(role="creative")
    user = subtask if not context else f"Context from other departments:\n{context}\n\nYour task:\n{subtask}"
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user),
    ])
    return response.content if isinstance(response.content, str) else str(response.content)
