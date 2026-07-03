"""AI copilot foundation API.

Exposes the assembled context/prompt so the foundation is verifiable end-to-end without a
model. When the assistant lands, it will call the same builders and hand the prompt to the
`app.llm` client.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.deps import ClockDep, CurrentUserId, DbSession
from app.modules.ai.context_builder import AssistantContextBuilder
from app.modules.ai.data_provider import AssistantDataProvider
from app.modules.ai.prompt_assembler import AssistantPromptAssembler

router = APIRouter(prefix="/ai", tags=["ai"])


class ContextRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class ContextResponse(BaseModel):
    system: str
    context: dict[str, Any]
    messages: list[dict[str, str]]


@router.post("/context", response_model=ContextResponse)
async def build_context(
    body: ContextRequest,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    currency: Annotated[str, Query(min_length=3, max_length=3)] = "INR",
) -> ContextResponse:
    """Assemble the deterministic context + prompt for a question (no model call)."""
    data = await AssistantDataProvider().gather(
        session, user_id=user_id, currency=currency, clock=clock
    )
    context = AssistantContextBuilder().build(data)
    prompt = AssistantPromptAssembler().assemble(context, body.question)
    return ContextResponse(
        system=prompt.system, context=prompt.context, messages=prompt.to_messages()
    )
