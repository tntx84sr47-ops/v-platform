"""
shared/llm.py
─────────────
Centralized LLM factory for V Platform.

Why a factory?
- Single place to configure provider, model, temperature
- Easy to swap providers (Anthropic ⇆ OpenAI) without touching agent code
- Consistent retry/timeout settings across all agents
- Future-proof: add Gemini, local models, etc. here only

Usage:
    from shared.llm import get_llm
    llm = get_llm(temperature=0.3)         # default provider
    llm = get_llm(role="creative")         # preset for creative work
    llm = get_llm(role="strategist")       # preset for analysis/planning
"""

from __future__ import annotations

import os
from typing import Literal, Optional

from langchain_core.language_models.chat_models import BaseChatModel

# Lazy imports inside the factory to keep import cost low if a provider is unused.

ProviderName = Literal["anthropic", "openai"]
RolePreset = Literal["default", "strategist", "creative", "fast"]


# Role presets — temperature/model tuned for different cognitive jobs.
# Strategist: deterministic, sharp reasoning (decomposition, evaluation).
# Creative:   higher temperature for marketing/copy work.
# Fast:       cheaper/quicker model for simple routing decisions.
_ROLE_PRESETS: dict[RolePreset, dict] = {
    "default":    {"temperature": 0.5},
    "strategist": {"temperature": 0.2},
    "creative":   {"temperature": 0.85},
    "fast":       {"temperature": 0.3, "fast": True},
}


def get_llm(
    role: RolePreset = "default",
    *,
    provider: Optional[ProviderName] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> BaseChatModel:
    """
    Build a chat LLM instance.

    Args:
        role:        Preset that tunes temperature/model for the agent's job.
        provider:    Override LLM_PROVIDER env var.
        model:       Override the default model for the chosen provider.
        temperature: Override the role preset temperature.

    Returns:
        A LangChain BaseChatModel ready to be used in LangGraph nodes.
    """
    preset = _ROLE_PRESETS[role]
    chosen_provider: ProviderName = provider or os.getenv("LLM_PROVIDER", "anthropic")  # type: ignore[assignment]
    final_temp = temperature if temperature is not None else preset["temperature"]

    if chosen_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        chosen_model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        if preset.get("fast"):
            chosen_model = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")

        return ChatAnthropic(
            model=chosen_model,
            temperature=final_temp,
            timeout=60,
            max_retries=2,
        )

    if chosen_provider == "openai":
        from langchain_openai import ChatOpenAI

        chosen_model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        if preset.get("fast"):
            chosen_model = os.getenv("OPENAI_FAST_MODEL", "gpt-4o-mini")

        return ChatOpenAI(
            model=chosen_model,
            temperature=final_temp,
            timeout=60,
            max_retries=2,
        )

    raise ValueError(f"Unknown LLM provider: {chosen_provider!r}")
