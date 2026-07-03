"""AssistantPromptAssembler — builds the layered prompt from context + question.

Produces a system/context/user triple. The system layer encodes the hard rules (never
compute, only explain the supplied facts, include the non-advice disclaimer). No model is
invoked here — this is the foundation the future assistant will call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

_SYSTEM_PROMPT = (
    "You are FinOS Copilot, a financial assistant. You ONLY explain and prioritize the "
    "pre-computed facts provided in the context. You must NEVER perform arithmetic or "
    "invent figures — every number you cite must appear verbatim in the context. Quote "
    "amounts in the user's currency. Keep answers concise and actionable. This is "
    "information, not regulated financial advice; add a brief disclaimer when discussing "
    "investments."
)


@dataclass(frozen=True, slots=True)
class AssistantPrompt:
    system: str
    context: dict[str, Any]
    user: str

    def to_messages(self) -> list[dict[str, str]]:
        """Provider-neutral message list a future LLM client can consume."""
        return [
            {"role": "system", "content": self.system},
            {
                "role": "system",
                "content": "CONTEXT (only source of facts):\n"
                + json.dumps(self.context, separators=(",", ":")),
            },
            {"role": "user", "content": self.user},
        ]


class AssistantPromptAssembler:
    def assemble(self, context: dict[str, Any], question: str) -> AssistantPrompt:
        return AssistantPrompt(system=_SYSTEM_PROMPT, context=context, user=question.strip())
