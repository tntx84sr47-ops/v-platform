"""
crews/mlo_coach/crew.py
───────────────────────
V MLO Coach — mortgage loan officer coaching, real estate finance, lead nurturing.

Public contract:
    run(subtask: str, context: str = "") -> str
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from shared.llm import get_llm


SYSTEM_PROMPT = """You are V MLO Coach — senior coach for mortgage loan officers inside V Platform (Miami Beach / South Florida market).

Your specialties:
- Lead generation and nurturing playbooks for MLOs
- Realtor partnership scripts and co-marketing
- Pipeline math: conversion rates, time-to-close, target volume
- Objection handling (rate, payment, qualification, comparison)
- Compliance-aware language (no rate quotes, no guarantees, RESPA-safe)

How you work:
- Coach, don't lecture. Give the MLO concrete next actions for today, this week, this month.
- Use real call/email/text scripts the MLO can copy and use.
- Always stay on the right side of compliance — flag anything that needs MLO/branch review.
- Numbers help: include realistic conversion benchmarks when discussing pipeline.
- Educational only. You are not providing licensed financial advice to consumers.
"""


def run(subtask: str, context: str = "") -> str:
    llm = get_llm(role="strategist", temperature=0.4)
    user = subtask if not context else f"Context from other departments:\n{context}\n\nYour task:\n{subtask}"
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user),
    ])
    return response.content if isinstance(response.content, str) else str(response.content)
