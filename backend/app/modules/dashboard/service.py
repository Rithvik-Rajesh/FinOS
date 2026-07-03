"""Dashboard aggregation — one optimized read for the home screen.

A backend-for-frontend façade that assembles every section by calling each engine once
(O(engines), never O(items)); spending slices are returned as ids for the client to map.
Read-only; returns the response schema directly (documented in DASHBOARD_ARCHITECTURE.md).
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import MoneySchema
from app.domain.clock import Clock
from app.domain.enums import ForecastHorizon, GoalStatus
from app.domain.money import Money
from app.domain.reporting import (
    spending_by_category,
    spending_by_merchant,
    total_income,
    total_spending,
)
from app.domain.reviews import savings_rate
from app.modules.accounts import repository as accounts_repo
from app.modules.accounts import service as accounts_service
from app.modules.calendar import service as calendar_service
from app.modules.dashboard.schemas import (
    DashboardGoal,
    DashboardResponse,
    ForecastPoint,
    ForecastSection,
    OverviewSection,
    SpendingSlice,
    UpcomingItem,
)
from app.modules.forecasting import service as forecasting_service
from app.modules.goals import repository as goals_repo
from app.modules.goals import service as goals_service
from app.modules.insights import service as insights_service
from app.modules.insights.schemas import InsightOut
from app.modules.ledger.facts import DEFAULT_TZ
from app.modules.ledger.records import reporting_records

_TOP_N = 5
_UPCOMING_DAYS = 14


async def _current_balance(session: AsyncSession, user_id: uuid.UUID, currency: str) -> int:
    total = 0
    for account in await accounts_repo.list_(session, user_id, limit=1000):
        if account.currency != currency:
            continue
        balance = await accounts_service.get_balance(session, user_id=user_id, account=account)
        total += balance.amount_minor
    return total


async def build_dashboard(
    session: AsyncSession, *, user_id: uuid.UUID, currency: str, clock: Clock
) -> DashboardResponse:
    currency = currency.upper()
    now = clock.now()
    month_start_d = now.astimezone(DEFAULT_TZ).date().replace(day=1)
    month_start = dt.datetime.combine(month_start_d, dt.time.min, tzinfo=DEFAULT_TZ)
    records = await reporting_records(
        session, user_id, currency=currency, date_from=month_start, date_to=now
    )

    spent = total_spending(records, currency)
    income = total_income(records, currency)
    net = income - spent
    balance = Money(await _current_balance(session, user_id, currency), currency)

    # Goals (top by priority).
    goals_out: list[DashboardGoal] = []
    progresses: list[float] = []
    for goal in await goals_repo.list_(session, user_id, status=GoalStatus.ACTIVE, limit=_TOP_N):
        if goal.currency != currency:
            continue
        projection, current = await goals_service.get_projection(
            session, user_id=user_id, goal=goal, clock=clock
        )
        progresses.append(projection.progress_ratio)
        goals_out.append(
            DashboardGoal(
                goal_id=goal.id,
                name=goal.name,
                progress_ratio=projection.progress_ratio,
                health=projection.health,
                target=MoneySchema.from_money(projection.target),
                current=MoneySchema.from_money(current),
                projected_completion=projection.projected_completion,
            )
        )

    insights = await insights_service.generate(
        session, user_id=user_id, currency=currency, clock=clock
    )
    events = await calendar_service.build_events(
        session,
        user_id=user_id,
        start=now,
        end=now + dt.timedelta(days=_UPCOMING_DAYS),
        clock=clock,
    )
    bundle = await forecasting_service.build_forecast(
        session, user_id=user_id, currency=currency, horizon=ForecastHorizon.D30, clock=clock
    )

    overview = OverviewSection(
        current_balance=MoneySchema.from_money(balance),
        net_cashflow=MoneySchema.from_money(net),
        savings_rate_pct=savings_rate(income=income, spending=spent),
        active_goals=len(goals_out),
        avg_goal_progress=round(sum(progresses) / len(progresses), 4) if progresses else 0.0,
    )

    return DashboardResponse(
        currency=currency,
        generated_at=now,
        overview=overview,
        insights=[InsightOut.from_domain(i) for i in insights[:_TOP_N]],
        upcoming=[
            UpcomingItem(
                type=ev.type.value,
                title=ev.title,
                occurs_at=ev.occurs_at,
                amount=MoneySchema.from_money(ev.amount) if ev.amount is not None else None,
                direction=ev.direction,
            )
            for ev in events[: _TOP_N * 2]
        ],
        goals=goals_out,
        spending_by_category=[
            SpendingSlice(key=g.key, total=MoneySchema.from_money(g.total), count=g.count)
            for g in spending_by_category(records, currency)[:_TOP_N]
        ],
        spending_by_merchant=[
            SpendingSlice(key=g.key, total=MoneySchema.from_money(g.total), count=g.count)
            for g in spending_by_merchant(records, currency)[:_TOP_N]
        ],
        forecast=ForecastSection(
            horizon=ForecastHorizon.D30,
            ending_balance=MoneySchema.from_money(bundle.cash.ending_balance),
            min_balance=MoneySchema.from_money(bundle.cash.min_balance),
            min_balance_date=bundle.cash.min_balance_date,
            projected_negative=bundle.cash.projected_negative,
            timeline=[
                ForecastPoint(date=p.date, balance=MoneySchema.from_money(p.balance))
                for p in bundle.cash.timeline
            ],
        ),
    )
