"""Simulation orchestration — assembles inputs and runs the pure decision engine.

Deterministic end to end. The future AI assistant calls this to answer "can I afford
X?" without ever doing the arithmetic itself (SIMULATION_ENGINE.md).
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domain.clock import Clock
from app.domain.enums import GoalStatus, GoalType
from app.domain.money import Money
from app.domain.reporting import total_income, total_spending
from app.domain.simulation import (
    EmiPlan,
    GoalSimInput,
    PurchaseSimulation,
    compute_emi,
    simulate_purchase,
)
from app.modules.accounts import repository as accounts_repo
from app.modules.accounts import service as accounts_service
from app.modules.goals import repository as goals_repo
from app.modules.goals import service as goals_service
from app.modules.ledger.records import reporting_records

_SURPLUS_LOOKBACK_DAYS = 90
_SURPLUS_MONTHS = 3


class SimulationInputError(AppError):
    status_code = 422
    code = "simulation_invalid"


async def _cash_balance(session: AsyncSession, user_id: uuid.UUID, currency: str) -> int:
    total = 0
    for account in await accounts_repo.list_(session, user_id, limit=1000):
        if account.currency != currency:
            continue
        balance = await accounts_service.get_balance(session, user_id=user_id, account=account)
        total += balance.amount_minor
    return total


async def _monthly_surplus(
    session: AsyncSession, user_id: uuid.UUID, currency: str, now: dt.datetime
) -> int:
    since = now - dt.timedelta(days=_SURPLUS_LOOKBACK_DAYS)
    records = await reporting_records(
        session, user_id, currency=currency, date_from=since, date_to=now
    )
    net = (
        total_income(records, currency).amount_minor
        - total_spending(records, currency).amount_minor
    )
    return net // _SURPLUS_MONTHS


async def _goal_inputs(
    session: AsyncSession, user_id: uuid.UUID, currency: str, clock: Clock
) -> tuple[list[GoalSimInput], Money]:
    goals: list[GoalSimInput] = []
    emergency_floor = Money(0, currency)
    for goal in await goals_repo.list_(session, user_id, status=GoalStatus.ACTIVE, limit=1000):
        if goal.currency != currency:
            continue
        projection, current = await goals_service.get_projection(
            session, user_id=user_id, goal=goal, clock=clock
        )
        goals.append(
            GoalSimInput(
                goal_id=goal.id,
                name=goal.name,
                target=projection.target,
                current=current,
                deadline=goal.deadline,
                observed_monthly=projection.observed_monthly,
            )
        )
        if goal.goal_type is GoalType.EMERGENCY_FUND:
            emergency_floor = Money(goal.target_amount_minor, currency)
    return goals, emergency_floor


async def simulate_purchase_scenario(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    amount: Money,
    funding: str,
    emi_annual_rate_bps: int | None,
    emi_months: int | None,
    clock: Clock,
) -> tuple[PurchaseSimulation, str]:
    currency = amount.currency
    now = clock.now()
    cash_before = Money(await _cash_balance(session, user_id, currency), currency)
    surplus = Money(await _monthly_surplus(session, user_id, currency, now), currency)
    goals, emergency_floor = await _goal_inputs(session, user_id, currency, clock)

    emi: EmiPlan | None = None
    if funding == "emi":
        if emi_annual_rate_bps is None or emi_months is None:
            raise SimulationInputError("emi funding requires emi_annual_rate_bps and emi_months")
        emi = compute_emi(principal=amount, annual_rate_bps=emi_annual_rate_bps, months=emi_months)

    sim = simulate_purchase(
        amount=amount,
        cash_before=cash_before,
        emergency_floor=emergency_floor,
        monthly_surplus=surplus,
        goals=goals,
        as_of=now.date(),
        emi=emi,
    )
    return sim, funding
