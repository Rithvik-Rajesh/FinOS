"""The `/me` endpoint — the authenticated user's profile.

On first authenticated request this is where a local `users` row is JIT-provisioned
from the Supabase identity (ADR-003). Persistence lands with the identity module in
Phase 1; for now it echoes the verified principal so auth is testable end-to-end.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentPrincipal

router = APIRouter(tags=["identity"])


class MeResponse(BaseModel):
    user_id: str
    email: str | None
    is_dev: bool
    base_currency: str = "INR"


@router.get("/me", response_model=MeResponse, summary="Current user profile")
async def get_me(principal: CurrentPrincipal) -> MeResponse:
    return MeResponse(
        user_id=principal.user_id,
        email=principal.email,
        is_dev=principal.is_dev,
    )
