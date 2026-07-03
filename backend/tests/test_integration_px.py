"""Integration tests for the Product Experience layer (real services on SQLite)."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import MoneySchema
from app.domain.enums import (
    AccountType,
    FinancialPriority,
    InsightCategory,
    NotificationType,
    RecurrenceInterval,
    RecurringDirection,
    RecurringKind,
    ReviewPeriod,
    TransactionType,
)
from app.modules.accounts import service as accounts_service
from app.modules.accounts.schemas import AccountCreate
from app.modules.ai.context_builder import AssistantContextBuilder
from app.modules.ai.data_provider import AssistantDataProvider
from app.modules.ai.prompt_assembler import AssistantPromptAssembler
from app.modules.categories import service as categories_service
from app.modules.categories.schemas import CategoryCreate
from app.modules.dashboard import service as dashboard_service
from app.modules.goals import service as goals_service
from app.modules.goals.schemas import GoalCreate
from app.modules.identity import service as identity_service
from app.modules.identity.schemas import PreferencesUpdate, ProfileUpdate
from app.modules.insights import service as insights_service
from app.modules.ledger import service as ledger_service
from app.modules.ledger.schemas import TransactionCreate
from app.modules.merchants import service as merchants_service
from app.modules.merchants.schemas import MerchantCreate
from app.modules.notifications import service as notifications_service
from app.modules.recurring import service as recurring_service
from app.modules.recurring.schemas import SeriesCreate
from app.modules.reviews import service as reviews_service
from app.modules.sync import service as sync_service
from app.modules.sync.schemas import SyncMutation
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
# Profile & preferences
# --------------------------------------------------------------------------- #
async def test_profile_get_or_create_and_update(session: AsyncSession) -> None:
    profile = await identity_service.get_or_create(session, user_id=TEST_USER)
    assert profile.currency == "INR"
    await session.commit()
    updated = await identity_service.update_profile(
        session, user_id=TEST_USER, data=ProfileUpdate(display_name="Aksay", currency="usd")
    )
    assert updated.display_name == "Aksay"
    assert updated.currency == "USD"  # normalized
    prefs = await identity_service.update_preferences(
        session,
        user_id=TEST_USER,
        data=PreferencesUpdate(financial_priority=FinancialPriority.GOAL_FIRST),
    )
    assert prefs.financial_priority is FinancialPriority.GOAL_FIRST


# --------------------------------------------------------------------------- #
# Insights
# --------------------------------------------------------------------------- #
async def test_spending_insight_generated_with_driver(session: AsyncSession) -> None:
    acc = await _account(session)
    food = await categories_service.create_category(
        session, user_id=TEST_USER, data=CategoryCreate(name="Food")
    )
    swiggy = await merchants_service.create_merchant(
        session, user_id=TEST_USER, data=MerchantCreate(name="Swiggy")
    )
    await session.commit()
    # Previous period (June 1-3) smaller; current (July 1-3) larger -> rise.
    await _expense(
        session,
        acc,
        20000,
        category_id=food.id,
        merchant_id=swiggy.id,
        when=dt.datetime(2026, 6, 2, 9, tzinfo=dt.UTC),
    )
    await _expense(
        session,
        acc,
        40000,
        category_id=food.id,
        merchant_id=swiggy.id,
        when=dt.datetime(2026, 7, 2, 9, tzinfo=dt.UTC),
    )

    insights = await insights_service.generate(
        session, user_id=TEST_USER, currency="INR", clock=CLOCK
    )
    spending = [i for i in insights if i.category is InsightCategory.SPENDING]
    assert spending
    assert "Swiggy" in spending[0].detail


async def test_goal_insight_when_behind(session: AsyncSession) -> None:
    await goals_service.create_goal(
        session,
        user_id=TEST_USER,
        data=GoalCreate(
            name="Masters",
            target_amount_minor=150_000_000,
            currency="INR",
            deadline=dt.date(2026, 9, 1),
        ),
    )
    await session.commit()
    insights = await insights_service.generate(
        session, user_id=TEST_USER, currency="INR", clock=CLOCK
    )
    assert any(i.category is InsightCategory.GOAL for i in insights)


# --------------------------------------------------------------------------- #
# Reviews
# --------------------------------------------------------------------------- #
async def test_weekly_review_snapshot(session: AsyncSession) -> None:
    acc = await _account(session)
    await _expense(session, acc, 30000, when=CLOCK.now())
    review = await reviews_service.generate(
        session, user_id=TEST_USER, period=ReviewPeriod.WEEKLY, currency="INR", clock=CLOCK
    )
    await session.commit()
    assert review.total_spent_minor == 30000
    assert review.period is ReviewPeriod.WEEKLY
    # Idempotent per period.
    again = await reviews_service.generate(
        session, user_id=TEST_USER, period=ReviewPeriod.WEEKLY, currency="INR", clock=CLOCK
    )
    assert again.id == review.id


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #
async def test_notification_scan_bill_and_idempotent(session: AsyncSession) -> None:
    await recurring_service.create_series(
        session,
        user_id=TEST_USER,
        data=SeriesCreate(
            name="Rent",
            kind=RecurringKind.RENT,
            direction=RecurringDirection.OUTFLOW,
            amount=_money(1_200_000),
            interval=RecurrenceInterval.MONTHLY,
            anchor_at=CLOCK.now() + dt.timedelta(days=1),
        ),
        clock=CLOCK,
    )
    await session.commit()

    created = await notifications_service.scan(
        session, user_id=TEST_USER, currency="INR", clock=CLOCK
    )
    await session.commit()
    assert created >= 1
    events = await notifications_service.repo.list_events(session, TEST_USER)  # type: ignore[attr-defined]
    assert any(e.type is NotificationType.UPCOMING_BILL for e in events)

    # Re-scan is idempotent.
    again = await notifications_service.scan(
        session, user_id=TEST_USER, currency="INR", clock=CLOCK
    )
    assert again == 0


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
async def test_dashboard_aggregates_sections(session: AsyncSession) -> None:
    acc = await _account(session, opening=10_000_000)
    await goals_service.create_goal(
        session,
        user_id=TEST_USER,
        data=GoalCreate(name="Trip", target_amount_minor=1_000_000, currency="INR"),
    )
    await session.commit()
    await _expense(session, acc, 50000, when=CLOCK.now())

    dash = await dashboard_service.build_dashboard(
        session, user_id=TEST_USER, currency="INR", clock=CLOCK
    )
    assert dash.overview.current_balance == MoneySchema(amount_minor=9_950_000, currency="INR")
    assert dash.overview.active_goals == 1
    assert dash.forecast.horizon.value == "30d"
    assert len(dash.forecast.timeline) >= 2


# --------------------------------------------------------------------------- #
# Sync of planning entities
# --------------------------------------------------------------------------- #
async def test_goal_sync_push_and_pull(session: AsyncSession) -> None:
    goal_id = uuid.uuid4()
    push = await sync_service.push(
        session,
        TEST_USER,
        mutations=[
            SyncMutation(
                op="upsert",
                entity="goals",
                id=goal_id,
                base_version=None,
                data={"name": "Emergency", "target_amount_minor": 500000, "currency": "INR"},
            )
        ],
        clock=CLOCK,
        correlation_id=None,
    )
    await session.commit()
    assert push.results[0].status == "applied"

    pulled = await sync_service.pull(session, TEST_USER, since=0, limit=500)
    assert any(c.entity == "goals" and c.id == goal_id for c in pulled.changes)


# --------------------------------------------------------------------------- #
# AI copilot foundation
# --------------------------------------------------------------------------- #
async def test_ai_context_consumes_deterministic_outputs(session: AsyncSession) -> None:
    acc = await _account(session, opening=5_000_000)
    await goals_service.create_goal(
        session,
        user_id=TEST_USER,
        data=GoalCreate(name="Trip", target_amount_minor=1_000_000, currency="INR"),
    )
    await session.commit()
    await _expense(session, acc, 30000, when=CLOCK.now())

    data = await AssistantDataProvider().gather(
        session, user_id=TEST_USER, currency="INR", clock=CLOCK
    )
    context = AssistantContextBuilder().build(data)
    prompt = AssistantPromptAssembler().assemble(context, "Where am I overspending?")

    assert "goals" in context
    assert "forecast" in context
    assert prompt.user == "Where am I overspending?"
    # The system prompt forbids the model from computing values.
    assert "NEVER perform arithmetic" in prompt.system
    messages = prompt.to_messages()
    assert messages[0]["role"] == "system"
