"""The Financial Calculation Engine.

PURE, deterministic business logic. Rules for this package:

* No I/O of any kind — no database, no HTTP, no filesystem, no LLM.
* No hidden clocks or randomness — inject `now`/`seed` as arguments.
* Money is always integer minor units via the `Money` value type — never floats.

Everything here is unit-tested to death. It is the single source of truth for every
number the user sees. See ARCHITECTURE.md (ADR-004, ADR-005) and docs/AI.md.
"""
