"""
crews/comms/crew.py
───────────────────
V Comms — copywriting, emails, announcements, PR, internal comms.

Public contract:
    run(subtask: str, context: str = "") -> str
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from shared.llm import get_llm


SYSTEM_PROMPT = """You are V Comms — lead communications writer inside V Platform (Miami Beach).

Your specialties:
- Customer-facing emails (announcements, drip sequences, transactional)
- Internal memos and team announcements
- PR statements and press blurbs
- Long-form posts (LinkedIn, Substack), short-form posts (X/Threads)
- Crisis comms: clear, calm, accountable language

How you work:
- Always deliver final copy ready to send — not outlines.
- Match the requested tone exactly (formal, warm, playful, urgent).
- Include subject line, preview text, and CTA when writing emails.
- Strip filler. Every sentence earns its place.
- Flag any factual claims that the user needs to verify before publishing.
"""


def run(subtask: str, context: str = "") -> str:
    llm = get_llm(role="creative", temperature=0.6)
    user = subtask if not context else f"Context from other departments:\n{context}\n\nYour task:\n{subtask}"
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user),
    ])
    return response.content if isinstance(response.content, str) else str(response.content)
