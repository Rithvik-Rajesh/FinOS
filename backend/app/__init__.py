"""FinOS backend — a FastAPI modular monolith.

Layering (see ARCHITECTURE.md):
    api/        HTTP concern only.
    modules/    Feature modules (service/repository/models per module).
    domain/     PURE, deterministic money engine. No I/O. Never imports an LLM.
    llm/        Provider-abstracted AI client. ONLY modules/ai may import this.
    core/       Config, logging, errors, security, the Money value type.
    db/         SQLAlchemy session, base model, mixins.
"""

__version__ = "0.1.0"
