"""Integration tests for the financial planning layer (real services on SQLite)."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import MoneySchema
from app.domain.enums import (
    AccountType,
    BudgetHealth,
    BudgetPeriodType,
    ForecastHorizon,
    GoalStatus,
    GoalType,
    RecurrenceInterval,
    RecurringDirection,
    RecurringKind,
    RecurringStatus,
    TransactionType,
)
from app.domain.money import Money
from app.events.dispatcher import Dispatcher
from app.events.handlers import register_all
from app.modules.accounts import service as accounts_service
from app.modules.accounts.schemas import AccountCreate
from app.modules.budgets import repository as budgets_repo
from app.modules.budgets import service as budgets_service
from app.modules.budgets.schemas import AllocationInput, BudgetCreate
from app.modules.categories import service as categories_service
from app.modules.categories.schemas import CategoryCreate
from app.modules.forecasting import service as forecasting_service
from app.modules.goals import repository as goals_repo
from app.modules.goals import service as goals_service
from app.modules.goals.schemas import ContributionCreate, GoalCreate, MilestoneCreate
from app.modules.ledger import service as ledger_service
from app.modules.ledger.schemas import TransactionCreate
from app.modules.merchants import service as merchants_service
from app.modules.merchants.schemas import MerchantCreate
from app.modules.recurring import service as recurring_service
from app.modules.recurring.schemas import SeriesCreate
from app.modules.simulation import service as simulation_service
from app.modules.subscriptions import service as subscriptions_service
from tests.conftest import CLOCK, TEST_USER


def _money(minor: int) -> MoneySchema:
    return MoneySchema(amount_minor=minor, currency="INR")


async def _account(session: AsyncSession, opening: int = 0) -> uuid.UUID:
    acc = await accounts_service.create_account(
        session,
        user_id=TEST_USER,
        data=AccountCreate(
            name="Cash", type=AccountType.CASH, currency="INR", opening_balance_minor=opening
        ),
        clock=CLOCK,
    )
    await session.commit()
    return acc.id


async def _category(session: AsyncSession, name: str) -> uuid.UUID:
    cat = await categories_service.create_category(
        session, user_id=TEST_USER, data=CategoryCreate(name=name)
    )
    await session.commit()
    return cat.id


async def _expense(
    session: AsyncSession,
    account_id: uuid.UUID,
    minor: int,
    *,
    category_id: uuid.UUID | None = None,
    merchant_id: uuid.UUID | None = None,
    when: dt.datetime | None = None,
) -> None:
    await ledger_service.create_transaction(
        session,
        user_id=TEST_USER,
        data=TransactionCreate(
            account_id=account_id,
            type=TransactionType.EXPENSE,
            amount=_money(minor),
            occurred_at=when or CLOCK.now(),
            category_id=category_id,
            merchant_id=merchant_id,
        ),
        clock=CLOCK,
    )
    await session.commit()


# --------------------------------------------------------------------------- #
# Goals
# --------------------------------------------------------------------------- #
async def test_goal_progress_and_projection(session: AsyncSession) -> None:
    goal = await goals_service.create_goal(
        session,
        user_id=TEST_USER,
        data=GoalCreate(
            name="Emergency",
            goal_type=GoalType.EMERGENCY_FUND,
            target_amount_minor=1_000_000,
            currency="INR",
        ),
    )
    await session.commit()
    await goals_service.add_contribution(
        session,
        user_id=TEST_USER,
        goal_id=goal.id,
        data=ContributionCreate(amount=_money(500_000)),
        clock=CLOCK,
    )
    await session.commit()

    projection, current = await goals_service.get_projection(
        session, user_id=TEST_USER, goal=goal, clock=CLOCK
    )
    assert current == Money(500_000, "INR")
    assert projection.remaining == Money(500_000, "INR")
    assert projection.progress_ratio == 0.5


async def test_goal_milestone_and_achievement(session: AsyncSession) -> None:
    goal = await goals_service.create_goal(
        session,
        user_id=TEST_USER,
        data=GoalCreate(
            name="Laptop", goal_type=GoalType.PURCHASE, target_amount_minor=500_000, currency="INR"
        ),
    )
    await session.commit()
    await goals_service.add_milestone(
        session,
        user_id=TEST_USER,
        goal_id=goal.id,
        data=MilestoneCreate(name="Halfway", target_amount_minor=250_000),
    )
    await session.commit()

    await goals_service.add_contribution(
        session,
        user_id=TEST_USER,
        goal_id=goal.id,
        data=ContributionCreate(amount=_money(500_000)),
        clock=CLOCK,
    )
    await session.commit()

    milestones = await goals_repo.list_milestones(session, TEST_USER, goal.id)
    assert milestones[0].reached_at is not None
    refreshed = await goals_repo.get(session, TEST_USER, goal.id)
    assert refreshed is not None
    assert refreshed.status is GoalStatus.ACHIEVED


# --------------------------------------------------------------------------- #
# Budgets
# --------------------------------------------------------------------------- #
async def test_budget_status_matches_example(session: AsyncSession) -> None:
    acc = await _account(session)
    food = await _category(session, "Food")
    budget = await budgets_service.create_budget(
        session,
        user_id=TEST_USER,
        data=BudgetCreate(
            name="Monthly",
            period_type=BudgetPeriodType.MONTHLY,
            currency="INR",
            allocations=[AllocationInput(category_id=food, amount_minor=500_000)],  # ₹5000
        ),
    )
    await session.commit()
    await _expense(session, acc, 420_000, category_id=food)  # ₹4200

    status = await budgets_service.get_status(
        session, user_id=TEST_USER, budget=budget, as_of=CLOCK.now().date()
    )
    line = status.lines[0]
    assert line.spent == Money(420_000, "INR")
    assert line.remaining == Money(80_000, "INR")
    assert line.utilization_ratio is not None
    assert round(line.utilization_ratio, 2) == 0.84
    assert line.health is BudgetHealth.WARNING


async def test_budget_overspend_flag(session: AsyncSession) -> None:
    acc = await _account(session)
    food = await _category(session, "Food")
    budget = await budgets_service.create_budget(
        session,
        user_id=TEST_USER,
        data=BudgetCreate(
            name="Monthly",
            period_type=BudgetPeriodType.MONTHLY,
            currency="INR",
            allocations=[AllocationInput(category_id=food, amount_minor=500_000)],
        ),
    )
    await session.commit()
    await _expense(session, acc, 600_000, category_id=food)

    status = await budgets_service.get_status(
        session, user_id=TEST_USER, budget=budget, as_of=CLOCK.now().date()
    )
    assert status.lines[0].health is BudgetHealth.OVER
    assert status.total_remaining == Money(-100_000, "INR")


# --------------------------------------------------------------------------- #
# Event integration: budget alerts
# --------------------------------------------------------------------------- #
async def test_transaction_created_triggers_budget_alert(session: AsyncSession) -> None:
    acc = await _account(session)
    food = await _category(session, "Food")
    budget = await budgets_service.create_budget(
        session,
        user_id=TEST_USER,
        data=BudgetCreate(
            name="Monthly",
            period_type=BudgetPeriodType.MONTHLY,
            currency="INR",
            allocations=[AllocationInput(category_id=food, amount_minor=500_000)],
        ),
    )
    await session.commit()
    await _expense(session, acc, 600_000, category_id=food)  # enqueues TransactionCreated

    bus = Dispatcher()
    register_all(bus)
    processed = await bus.dispatch_pending(session, clock=CLOCK)
    await session.commit()

    assert processed >= 1
    alerts = await budgets_repo.list_alerts(session, TEST_USER, budget_id=budget.id)
    assert any(a.level == "over" for a in alerts)

    # Idempotent: dispatching again creates no duplicate alert.
    again = Dispatcher()
    register_all(again)
    await again.dispatch_pending(session, clock=CLOCK)
    await session.commit()
    alerts_after = await budgets_repo.list_alerts(session, TEST_USER, budget_id=budget.id)
    assert len([a for a in alerts_after if a.level == "over"]) == 1


# --------------------------------------------------------------------------- #
# Recurring detection + subscriptions
# --------------------------------------------------------------------------- #
async def test_recurring_detection_and_approval(session: AsyncSession) -> None:
    acc = await _account(session)
    netflix = await merchants_service.create_merchant(
        session, user_id=TEST_USER, data=MerchantCreate(name="Netflix")
    )
    await session.commit()
    for month in (2, 3, 4, 5, 6):
        await _expense(
            session,
            acc,
            64_900,
            merchant_id=netflix.id,
            when=dt.datetime(2026, month, 5, 9, tzinfo=dt.UTC),
        )

    created, patterns = await recurring_service.detect(
        session, user_id=TEST_USER, currency="INR", clock=CLOCK
    )
    await session.commit()
    assert len(created) == 1
    assert created[0].status is RecurringStatus.PENDING_APPROVAL
    assert patterns[0].confidence >= 50

    approved = await recurring_service.set_status(
        session,
        user_id=TEST_USER,
        series_id=created[0].id,
        status=RecurringStatus.ACTIVE,
        clock=CLOCK,
    )
    assert approved.status is RecurringStatus.ACTIVE

    # Re-running detection does not duplicate the series.
    created_again, _ = await recurring_service.detect(
        session, user_id=TEST_USER, currency="INR", clock=CLOCK
    )
    assert created_again == []


async def test_subscription_summary(session: AsyncSession) -> None:
    for name, amount in (("Netflix", 64_900), ("Spotify", 11_900)):
        await recurring_service.create_series(
            session,
            user_id=TEST_USER,
            data=SeriesCreate(
                name=name,
                kind=RecurringKind.SUBSCRIPTION,
                direction=RecurringDirection.OUTFLOW,
                amount=_money(amount),
                interval=RecurrenceInterval.MONTHLY,
                anchor_at=CLOCK.now(),
                is_subscription=True,
            ),
            clock=CLOCK,
        )
    await session.commit()

    cost, count = await subscriptions_service.summary(session, user_id=TEST_USER, currency="INR")
    assert count == 2
    assert cost.monthly == Money(76_800, "INR")  # 649 + 119
    assert cost.annual == Money(76_800 * 12, "INR")


# --------------------------------------------------------------------------- #
# Forecasting + simulation
# --------------------------------------------------------------------------- #
async def test_forecast_declines_with_recurring_outflow(session: AsyncSession) -> None:
    await _account(session, opening=10_000_000)  # ₹1,00,000
    await recurring_service.create_series(
        session,
        user_id=TEST_USER,
        data=SeriesCreate(
            name="Rent",
            kind=RecurringKind.RENT,
            direction=RecurringDirection.OUTFLOW,
            amount=_money(1_200_000),
            interval=RecurrenceInterval.MONTHLY,
            anchor_at=CLOCK.now(),
        ),
        clock=CLOCK,
    )
    await session.commit()

    bundle = await forecasting_service.build_forecast(
        session, user_id=TEST_USER, currency="INR", horizon=ForecastHorizon.D90, clock=CLOCK
    )
    assert bundle.cash.starting_balance == Money(10_000_000, "INR")
    assert bundle.cash.ending_balance.amount_minor < bundle.cash.starting_balance.amount_minor
    assert len(bundle.cash.timeline) >= 2
    assert bundle.cash.assumptions  # transparent assumptions returned


async def test_purchase_simulation_from_cash(session: AsyncSession) -> None:
    await _account(session, opening=20_000_000)  # ₹2,00,000
    sim, funding = await simulation_service.simulate_purchase_scenario(
        session,
        user_id=TEST_USER,
        amount=Money(9_500_000, "INR"),
        funding="cash",
        emi_annual_rate_bps=None,
        emi_months=None,
        clock=CLOCK,
    )
    assert funding == "cash"
    assert sim.cash_before == Money(20_000_000, "INR")
    assert sim.cash_after == Money(10_500_000, "INR")
    assert sim.affordable_from_cash is True


async def test_purchase_simulation_emi_financed(session: AsyncSession) -> None:
    await _account(session, opening=20_000_000)
    sim, _ = await simulation_service.simulate_purchase_scenario(
        session,
        user_id=TEST_USER,
        amount=Money(9_500_000, "INR"),
        funding="emi",
        emi_annual_rate_bps=1500,
        emi_months=12,
        clock=CLOCK,
    )
    assert sim.cash_after == Money(20_000_000, "INR")  # cash untouched
    assert sim.emi is not None
    assert sim.emi.monthly_payment.amount_minor > 0
