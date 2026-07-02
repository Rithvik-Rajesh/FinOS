"""Provider-abstracted LLM client.

⚠️  IMPORT RULE: only `app.modules.ai` may import this package. This wall guarantees
AI-optionality and keeps the deterministic money path free of any model dependency
(ADR-005, docs/AI.md). The rule is enforced by tests/test_architecture.py.

The concrete provider clients (Anthropic/OpenAI), router, budget, and cache land in
Phase 7; this package exists now only to establish the boundary.
"""
