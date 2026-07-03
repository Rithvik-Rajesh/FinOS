"""Tests for the deterministic cash forecasting engine."""

from __future__ import annotations

import datetime as dt

import pytest

from app.domain.forecasting import CashEvent, forecast_cash
from app.domain.money import Money

AS_OF = dt.date(2026, 7, 1)


def _m(rupees: int) -> Money:
    return Money(rupees * 100, "INR")


def test_single_outflow() -> None:
    result = forecast_cash(
        starting_balance=_m(100000),
        events=[CashEvent(dt.date(2026, 7, 16), -50000 * 100, "rent")],
        daily_discretionary_minor=0,
        as_of=AS_OF,
        horizon_days=30,
    )
    assert result.ending_balance == _m(50000)
    assert result.min_balance == _m(50000)
    assert result.min_balance_date == dt.date(2026, 7, 16)
    assert result.projected_negative is False
    assert result.total_outflows == _m(50000)


def test_projected_negative() -> None:
    result = forecast_cash(
        starting_balance=_m(10000),
        events=[CashEvent(dt.date(2026, 7, 11), -20000 * 100, "big bill")],
        daily_discretionary_minor=0,
        as_of=AS_OF,
        horizon_days=30,
    )
    assert result.projected_negative is True
    assert result.min_balance == Money(-10000 * 100, "INR")
    assert result.min_balance_date == dt.date(2026, 7, 11)


def test_discretionary_spend_accumulates() -> None:
    result = forecast_cash(
        starting_balance=_m(100000),
        events=[],
        daily_discretionary_minor=1000 * 100,
        as_of=AS_OF,
        horizon_days=30,
    )
    assert result.ending_balance == _m(70000)  # 100k - 30*1k
    assert result.total_outflows == _m(30000)


def test_inflow_and_timeline_bounds() -> None:
    result = forecast_cash(
        starting_balance=_m(10000),
        events=[CashEvent(dt.date(2026, 7, 15), 50000 * 100, "salary")],
        daily_discretionary_minor=0,
        as_of=AS_OF,
        horizon_days=30,
    )
    assert result.total_inflows == _m(50000)
    assert result.ending_balance == _m(60000)
    assert result.timeline[0].date == AS_OF
    assert result.timeline[-1].date == dt.date(2026, 7, 31)


def test_horizon_bounds_validated() -> None:
    with pytest.raises(ValueError):
        forecast_cash(
            starting_balance=_m(1000),
            events=[],
            daily_discretionary_minor=0,
            as_of=AS_OF,
            horizon_days=0,
        )


def test_negative_discretionary_rejected() -> None:
    with pytest.raises(ValueError):
        forecast_cash(
            starting_balance=_m(1000),
            events=[],
            daily_discretionary_minor=-1,
            as_of=AS_OF,
            horizon_days=30,
        )
