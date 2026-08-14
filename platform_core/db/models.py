from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserProfile(BaseModel):
    """Telegram User Profile Schema"""
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    last_active_at: datetime = Field(default_factory=utc_now)


class UserBalance(BaseModel):
    """User Credits & Monetization Balance Schema"""
    user_id: int
    credits_remaining: int = 3
    total_stars_spent: int = 0
    free_credits_reset_at: datetime = Field(default_factory=utc_now)


class StarTransaction(BaseModel):
    """Telegram Stars Purchase Transaction Record"""
    id: Optional[str] = None
    user_id: int
    bot_id: str
    stars_amount: int
    credits_added: int
    telegram_payment_charge_id: str
    provider_payment_charge_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class BotEvent(BaseModel):
    """Metrics & Telemetry Event Schema"""
    id: Optional[str] = None
    bot_id: str
    user_id: int
    event_type: str  # 'command', 'click', 'generation_start', 'generation_success', 'generation_fail', 'payment'
    event_name: str  # e.g., '/start', 'preset:odyssey', 'model:flux'
    duration_ms: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class GenerationLog(BaseModel):
    """Media Generation Execution Record"""
    id: Optional[str] = None
    bot_id: str
    user_id: int
    model_name: str
    prompt: str
    preset_id: Optional[str] = None
    media_url: Optional[str] = None
    status: str = "pending"  # "pending", "success", "failed"
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
