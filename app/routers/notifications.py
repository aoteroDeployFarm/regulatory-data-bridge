#!/usr/bin/env python3
"""
notifications.py — FastAPI routes for registering push notification tokens.

Place at: app/routers/notifications.py
Mount via: FastAPI(include_router(notifications.router)).

What this does:
  - POST /notifications/push/register
      Accepts device token + platform ("expo" | "ios" | "android").
      Returns JSON { ok, token_saved }.

Why it matters:
  - Establishes foundation for mobile push notifications.
  - Future work: persist tokens per tenant/user and integrate with
    providers (Expo, FCM, APNS).

Schemas:
  - PushRegisterRequest → validates input (device_token, platform).
  - PushRegisterResponse → API response format.

Common examples:
  curl -X POST "http://127.0.0.1:8000/notifications/push/register" \
       -H "Content-Type: application/json" \
       -d '{"device_token": "ExponentPushToken[abcd1234]", "platform": "expo"}'
"""
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
    """Register a push token for notifications (placeholder; persistence TODO)."""
    # TODO: persist token by tenant/user
    return PushRegisterResponse(ok=True, token_saved=True)
