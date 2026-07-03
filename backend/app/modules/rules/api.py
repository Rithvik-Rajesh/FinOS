"""Rules REST API — CRUD plus simulation and testing."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import ClockDep, CorrelationId, CurrentUserId, DbSession
from app.api.schemas import Page
from app.domain.rules import TransactionFacts
from app.modules.rules import repository as repo
from app.modules.rules import service
from app.modules.rules.schemas import (
    RuleCreate,
    RuleOut,
    RuleSimulateRequest,
    RuleSimulateResponse,
    RuleTestRequest,
    RuleTestResponse,
    RuleUpdate,
    SimulatedChange,
)

router = APIRouter(prefix="/rules", tags=["rules"])


@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: RuleCreate,
    session: DbSession,
    user_id: CurrentUserId,
    correlation_id: CorrelationId,
) -> RuleOut:
    rule = await service.create_rule(
        session, user_id=user_id, data=body, correlation_id=correlation_id
    )
    return RuleOut.model_validate(rule)


@router.get("", response_model=Page[RuleOut])
async def list_rules(
    session: DbSession,
    user_id: CurrentUserId,
    active_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[RuleOut]:
    rows = await repo.list_(session, user_id, active_only=active_only, limit=limit, offset=offset)
    return Page(items=[RuleOut.model_validate(r) for r in rows], has_more=len(rows) == limit)


@router.patch("/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: uuid.UUID,
    body: RuleUpdate,
    session: DbSession,
    user_id: CurrentUserId,
    correlation_id: CorrelationId,
) -> RuleOut:
    rule = await service.update_rule(
        session, user_id=user_id, rule_id=rule_id, data=body, correlation_id=correlation_id
    )
    return RuleOut.model_validate(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: uuid.UUID,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> None:
    await service.delete_rule(
        session, user_id=user_id, rule_id=rule_id, clock=clock, correlation_id=correlation_id
    )


@router.post("/test", response_model=RuleTestResponse)
async def test_rule(body: RuleTestRequest) -> RuleTestResponse:
    """Validate a draft rule and check whether it matches a sample transaction."""
    facts = TransactionFacts(
        type=body.facts.type,
        amount_minor=body.facts.amount_minor,
        currency=body.facts.currency,
        hour_of_day=body.facts.hour_of_day,
        day_of_week=body.facts.day_of_week,
        merchant_name=body.facts.merchant_name,
        counterparty=body.facts.counterparty,
        account_name=body.facts.account_name,
        note=body.facts.note,
    )
    return RuleTestResponse(matches=service.test_draft(body.rule, facts))


@router.post("/simulate", response_model=RuleSimulateResponse)
async def simulate_rules(
    body: RuleSimulateRequest,
    session: DbSession,
    user_id: CurrentUserId,
) -> RuleSimulateResponse:
    """Dry-run rules over recent transactions without mutating anything."""
    evaluated, changes = await service.simulate(
        session, user_id=user_id, draft=body.draft_rule, limit=body.limit
    )
    return RuleSimulateResponse(
        evaluated=evaluated,
        changed=sum(1 for c in changes if c.changed),
        changes=[
            SimulatedChange(
                transaction_id=c.transaction_id,
                current_category_id=c.current_category_id,
                proposed_category_id=c.proposed_category_id,
                changed=c.changed,
            )
            for c in changes
        ],
    )
