"""Recurring series use cases: CRUD, approval, detection, and occurrence expansion.

Detection reuses the pure `app.domain.detection` engine over ledger history and produces
*pending-approval* series — nothing becomes an obligation without user confirmation.
Occurrences are expanded on read via the recurrence engine (never stored).
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.sequence import next_server_seq
from app.domain.clock import Clock
from app.domain.detection import DetectedPattern, RecurringObservation, detect_patterns
from app.domain.enums import RecurringDirection, RecurringKind, RecurringStatus, TransactionType
from app.domain.ids import new_id
from app.domain.recurrence import RecurrenceSpec, next_occurrence, occurrences_between
from app.modules.audit.repository import record as audit_record
from app.modules.ledger.records import reporting_records
from app.modules.recurring import repository as repo
from app.modules.recurring.models import RecurringSeries
from app.modules.recurring.schemas import SeriesCreate, SeriesUpdate

_DETECTION_LOOKBACK_DAYS = 400


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.UTC)


def _compute_next_due(interval_anchor: RecurrenceSpec, now: dt.datetime) -> dt.datetime:
    if interval_anchor.anchor > now:
        return interval_anchor.anchor
    return next_occurrence(interval_anchor, now)


async def create_series(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: SeriesCreate,
    clock: Clock,
    correlation_id: str | None = None,
) -> RecurringSeries:
    series_id = data.id or new_id()
    existing = await repo.get(session, user_id, series_id)
    if existing is not None:
        return existing
    money = data.amount.to_money()
    anchor = _aware(data.anchor_at)
    spec = RecurrenceSpec(data.interval, anchor)
    series = RecurringSeries(
        id=series_id,
        user_id=user_id,
        name=data.name,
        kind=data.kind,
        direction=data.direction,
        amount_minor=money.amount_minor,
        currency=money.currency,
        interval=data.interval,
        anchor_at=anchor,
        next_due_at=_compute_next_due(spec, clock.now()),
        end_at=_aware(data.end_at) if data.end_at else None,
        account_id=data.account_id,
        category_id=data.category_id,
        merchant_id=data.merchant_id,
        status=RecurringStatus.ACTIVE,
        detected=False,
        is_subscription=data.is_subscription,
        vendor=data.vendor,
        billing_cycle=data.billing_cycle,
        auto_renew=data.auto_renew,
        version=1,
        server_seq=await next_server_seq(session, user_id),
    )
    repo.add(session, series)
    audit_record(
        session,
        user_id=user_id,
        action="create",
        entity_type="recurring_series",
        entity_id=series_id,
        actor_id=user_id,
        correlation_id=correlation_id,
        diff={"name": data.name},
    )
    await session.flush()
    return series


async def update_series(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    series_id: uuid.UUID,
    data: SeriesUpdate,
    clock: Clock,
    correlation_id: str | None = None,
) -> RecurringSeries:
    series = await repo.get(session, user_id, series_id)
    if series is None:
        raise NotFoundError("recurring series not found")
    fields = data.model_dump(exclude_unset=True)
    changed: dict[str, object] = {}
    if data.amount is not None:
        series.amount_minor = data.amount.amount_minor
        series.currency = data.amount.currency
        changed["amount_minor"] = series.amount_minor
    for key in ("name", "category_id", "vendor", "auto_renew"):
        if key in fields and getattr(series, key) != fields[key]:
            setattr(series, key, fields[key])
            changed[key] = fields[key]
    if data.end_at is not None:
        series.end_at = _aware(data.end_at)
        changed["end_at"] = series.end_at.isoformat()
    if data.status is not None and data.status != series.status:
        series.status = data.status
        changed["status"] = data.status.value
        if data.status is RecurringStatus.CANCELLED:
            series.cancelled_at = clock.now()

    if changed:
        series.version += 1
        series.server_seq = await next_server_seq(session, user_id)
        audit_record(
            session,
            user_id=user_id,
            action="update",
            entity_type="recurring_series",
            entity_id=series_id,
            actor_id=user_id,
            correlation_id=correlation_id,
            diff=changed,
        )
        await session.flush()
    return series


async def set_status(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    series_id: uuid.UUID,
    status: RecurringStatus,
    clock: Clock,
    correlation_id: str | None = None,
) -> RecurringSeries:
    series = await repo.get(session, user_id, series_id)
    if series is None:
        raise NotFoundError("recurring series not found")
    series.status = status
    if status is RecurringStatus.CANCELLED:
        series.cancelled_at = clock.now()
    series.version += 1
    series.server_seq = await next_server_seq(session, user_id)
    audit_record(
        session,
        user_id=user_id,
        action="status",
        entity_type="recurring_series",
        entity_id=series_id,
        actor_id=user_id,
        correlation_id=correlation_id,
        diff={"status": status.value},
    )
    await session.flush()
    return series


async def delete_series(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    series_id: uuid.UUID,
    clock: Clock,
    correlation_id: str | None = None,
) -> None:
    series = await repo.get(session, user_id, series_id)
    if series is None:
        raise NotFoundError("recurring series not found")
    series.deleted_at = clock.now()
    series.version += 1
    series.server_seq = await next_server_seq(session, user_id)
    audit_record(
        session,
        user_id=user_id,
        action="delete",
        entity_type="recurring_series",
        entity_id=series_id,
        actor_id=user_id,
        correlation_id=correlation_id,
    )
    await session.flush()


async def detect(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    currency: str,
    clock: Clock,
    correlation_id: str | None = None,
) -> tuple[list[RecurringSeries], list[DetectedPattern]]:
    """Scan ledger history for recurring patterns; create pending-approval series."""
    since = clock.now() - dt.timedelta(days=_DETECTION_LOOKBACK_DAYS)
    records = await reporting_records(session, user_id, currency=currency, date_from=since)
    observations = [
        RecurringObservation(
            key=str(r.merchant_id),
            amount_minor=r.amount.amount_minor,
            occurred_at=_aware(r.occurred_at),  # persisted times are naive on SQLite
        )
        for r in records
        if r.merchant_id is not None and r.type is TransactionType.EXPENSE
    ]
    patterns = detect_patterns(observations, currency=currency)

    created: list[RecurringSeries] = []
    for pattern in patterns:
        merchant_id = uuid.UUID(pattern.key)
        if await repo.exists_similar(session, user_id, merchant_id, pattern.amount_minor):
            continue
        spec = RecurrenceSpec(pattern.interval, _aware(pattern.last_seen))
        series = RecurringSeries(
            id=new_id(),
            user_id=user_id,
            name=f"Detected series ({pattern.interval.value})",
            kind=RecurringKind.OTHER,
            direction=RecurringDirection.OUTFLOW,
            amount_minor=pattern.amount_minor,
            currency=pattern.currency,
            interval=pattern.interval,
            anchor_at=pattern.last_seen,
            next_due_at=_compute_next_due(spec, clock.now()),
            merchant_id=merchant_id,
            status=RecurringStatus.PENDING_APPROVAL,
            detected=True,
            confidence=pattern.confidence,
            version=1,
            server_seq=await next_server_seq(session, user_id),
        )
        repo.add(session, series)
        created.append(series)

    if created:
        audit_record(
            session,
            user_id=user_id,
            action="detect",
            entity_type="recurring_series",
            entity_id=user_id,
            actor_id=user_id,
            correlation_id=correlation_id,
            diff={"detected": len(created)},
        )
        await session.flush()
    return created, patterns


def occurrences_for_series(
    series: RecurringSeries, start: dt.datetime, end: dt.datetime
) -> list[dt.datetime]:
    if series.status is not RecurringStatus.ACTIVE:
        return []
    # Persisted datetimes come back naive on SQLite; coerce before comparing/expanding.
    upper = min(end, _aware(series.end_at)) if series.end_at else end
    return occurrences_between(
        RecurrenceSpec(series.interval, _aware(series.anchor_at)), start, upper
    )
