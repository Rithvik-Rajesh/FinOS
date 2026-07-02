"""Feature modules — the unit of ownership and the future service-split boundary.

Each module has a consistent internal layering:
    api/         routers + request/response schemas
    service/     use-case orchestration, transactions
    repository/  data access (the ONLY place that touches the DB), tenant-scoped
    models/      SQLAlchemy models + Pydantic schemas
    events/      domain-event handlers

Cross-module access goes through another module's `service`, never its tables.
Only `modules/ai` may import `app.llm` (enforced by tests/test_architecture.py).
"""
