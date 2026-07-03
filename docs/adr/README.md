# Architecture Decision Records

One file per significant, hard-to-reverse decision. The accepted decisions for the initial
design are recorded inline in [../../ARCHITECTURE.md](../../ARCHITECTURE.md#10-architecture-decision-records)
(ADR-001 … ADR-007). As the project evolves, new decisions get their own file here:

```
NNNN-short-title.md
```

Each ADR states: **Context · Decision · Consequences · Alternatives considered · Status**
(proposed / accepted / superseded). Link new ADRs from ARCHITECTURE.md.

Current decisions of record:

| ADR | Decision |
|---|---|
| 001 | Modular monolith over microservices |
| 002 | Local database: Drift over Isar |
| 003 | Auth: Supabase (managed) as IdP; data in our Postgres |
| 004 | Money as integer minor units |
| 005 | Deterministic engine vs LLM (the AI wall) |
| 006 | Sync: client UUIDs, outbox, delta, LWW |
| 007 | Subscriptions are a specialization of recurring items |
