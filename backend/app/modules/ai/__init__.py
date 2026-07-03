"""AI copilot foundation.

This module (and only this module) is permitted to import `app.llm`. The foundation here
gathers *already-computed* deterministic outputs and assembles context/prompts — it never
computes a financial value and does not call a model. The final assistant is out of scope
(see AI_COPILOT_ARCHITECTURE.md).
"""
