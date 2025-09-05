from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from settings import Settings, get_settings

router = APIRouter(prefix="/notifications", tags=["notifications"])

class PushRegisterRequest(BaseModel):
    device_token: str = Field(..., min_length=10)
    platform: str = Field(..., pattern="^(expo|ios|android)$")

class PushRegisterResponse(BaseModel):
    ok: bool
    token_saved: bool

@router.post("/push/register", response_model=PushRegisterResponse)
def register_push(
    req: PushRegisterRequest,
    cfg: Settings = Depends(get_settings),
) -> PushRegisterResponse:
    # TODO: persist token by tenant/user
    return PushRegisterResponse(ok=True, token_saved=True)
