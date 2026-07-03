"""Simulation REST API — the financial decision engine surface."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ClockDep, CurrentUserId, DbSession
from app.api.schemas import MoneySchema
from app.domain.simulation import EmiPlan, compute_emi
from app.modules.simulation import service
from app.modules.simulation.schemas import (
    EmiPlanOut,
    EmiSimRequest,
    GoalImpactOut,
    PurchaseSimRequest,
    PurchaseSimResponse,
)

router = APIRouter(prefix="/simulations", tags=["simulations"])


def _emi_out(plan: EmiPlan) -> EmiPlanOut:
    return EmiPlanOut(
        principal=MoneySchema.from_money(plan.principal),
        annual_rate_bps=plan.annual_rate_bps,
        months=plan.months,
        monthly_payment=MoneySchema.from_money(plan.monthly_payment),
        total_payment=MoneySchema.from_money(plan.total_payment),
        total_interest=MoneySchema.from_money(plan.total_interest),
    )


@router.post("/emi", response_model=EmiPlanOut)
async def emi(body: EmiSimRequest) -> EmiPlanOut:
    """Deterministic loan amortization (no account context required)."""
    plan = compute_emi(
        principal=body.principal.to_money(),
        annual_rate_bps=body.annual_rate_bps,
        months=body.months,
    )
    return _emi_out(plan)


@router.post("/purchase", response_model=PurchaseSimResponse)
async def purchase(
    body: PurchaseSimRequest, session: DbSession, user_id: CurrentUserId, clock: ClockDep
) -> PurchaseSimResponse:
    """Can I afford this? Cash, emergency-fund, goal, and financing impact."""
    sim, funding = await service.simulate_purchase_scenario(
        session,
        user_id=user_id,
        amount=body.amount.to_money(),
        funding=body.funding,
        emi_annual_rate_bps=body.emi_annual_rate_bps,
        emi_months=body.emi_months,
        clock=clock,
    )
    return PurchaseSimResponse(
        amount=MoneySchema.from_money(sim.amount),
        funding=body.funding,
        cash_before=MoneySchema.from_money(sim.cash_before),
        cash_after=MoneySchema.from_money(sim.cash_after),
        affordable_from_cash=sim.affordable_from_cash,
        emergency_floor=MoneySchema.from_money(sim.emergency_floor),
        monthly_surplus_before=MoneySchema.from_money(sim.monthly_surplus_before),
        monthly_surplus_after=MoneySchema.from_money(sim.monthly_surplus_after),
        goal_impacts=[
            GoalImpactOut(
                goal_id=g.goal_id,
                name=g.name,
                baseline_completion=g.baseline_completion,
                impacted_completion=g.impacted_completion,
                delay_months=g.delay_months,
            )
            for g in sim.goal_impacts
        ],
        emi=_emi_out(sim.emi) if sim.emi is not None else None,
    )
