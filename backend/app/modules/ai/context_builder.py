"""AssistantContextBuilder — structures gathered data into a compact, JSON-safe fact set.

The output is exactly what the model would be shown: labelled, pre-computed numbers. No
arithmetic happens here; values are passed through from the deterministic engines so the
model can quote them but never invent them.
"""

from __future__ import annotations

from typing import Any

from app.modules.ai.data_provider import AssistantData


class AssistantContextBuilder:
    def build(self, data: AssistantData) -> dict[str, Any]:
        return {
            "currency": data.currency,
            "preferences": {
                "financial_priority": data.profile.financial_priority.value,
                "risk_profile": data.profile.risk_profile.value,
                "monthly_income_minor": data.profile.monthly_income_minor,
            },
            "insights": [
                {
                    "category": i.category.value,
                    "severity": i.severity.value,
                    "title": i.title,
                    "detail": i.detail,
                    "change_pct": str(i.change_pct) if i.change_pct is not None else None,
                }
                for i in data.insights
            ],
            "forecast": {
                "horizon_days": data.forecast.cash.horizon_days,
                "ending_balance_minor": data.forecast.cash.ending_balance.amount_minor,
                "min_balance_minor": data.forecast.cash.min_balance.amount_minor,
                "min_balance_date": data.forecast.cash.min_balance_date.isoformat(),
                "projected_negative": data.forecast.cash.projected_negative,
                "assumptions": list(data.forecast.cash.assumptions),
            },
            "goals": [
                {
                    "name": goal.name,
                    "target_minor": projection.target.amount_minor,
                    "current_minor": current.amount_minor,
                    "progress_ratio": projection.progress_ratio,
                    "health": projection.health.value,
                    "required_monthly_minor": (
                        projection.required_monthly.amount_minor
                        if projection.required_monthly is not None
                        else None
                    ),
                    "projected_completion": (
                        projection.projected_completion.isoformat()
                        if projection.projected_completion is not None
                        else None
                    ),
                }
                for goal, projection, current in data.goal_projections
            ],
            "budgets": [
                {
                    "name": budget.name,
                    "health": status.health.value,
                    "spent_minor": status.total_spent.amount_minor,
                    "allocated_minor": status.total_allocated.amount_minor,
                }
                for budget, status in data.budget_statuses
            ],
            "subscriptions": {"monthly_minor": data.subscription_monthly.amount_minor},
            "recent_reviews": [
                {
                    "period": r.period.value,
                    "period_start": r.period_start.isoformat(),
                    "total_spent_minor": r.total_spent_minor,
                    "savings_rate_bps": r.savings_rate_bps,
                }
                for r in data.reviews
            ],
        }
