import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlatformSettings(BaseSettings):
    """
    Application & Platform Configuration managed via Environment Variables or .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Bot Tokens
    IMAGE_BOT_TOKEN: str = "123456789:mock_image_token"
    ADMIN_BOT_TOKEN: str = "123456789:mock_admin_token"
    ADMIN_USER_IDS_RAW: Optional[str] = None  # Comma-separated admin Telegram IDs e.g. "123456,789012"

    @property
    def admin_user_ids(self) -> list[int]:
        """Parses raw comma-separated ADMIN_USER_IDS_RAW into a list of integers."""
        if not self.ADMIN_USER_IDS_RAW:
            return []
        ids = []
        for item in str(self.ADMIN_USER_IDS_RAW).split(","):
            item_str = item.strip()
            if item_str.isdigit():
                ids.append(int(item_str))
        return ids

    # AI Model Generation API Keys
    OPENROUTER_API_KEY: Optional[str] = None

    # Supabase / PostgreSQL Configuration (Cloud or Self-Hosted)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None

    # Self-Hosted Direct PostgreSQL Credentials (Optional)
    POSTGRES_HOST: Optional[str] = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: Optional[str] = "postgres"
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = "postgres"
    DATABASE_URL: Optional[str] = None

    # Remote Config Settings
    PRESETS_REMOTE_URL: Optional[str] = None
    PRESETS_CACHE_TTL_SECONDS: int = 300

    # Monetization & Limits
    FREE_DAILY_CREDITS: int = 3
    DEFAULT_GENERATION_COST_CREDITS: int = 1

    # Dev / Debug Flags
    USE_MOCK_GENERATOR: bool = False
    METRICS_ENABLED: bool = True

    # Webhook Gateway & Redis Settings
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    WEBHOOK_BASE_URL: Optional[str] = None
    WEBHOOK_SECRET_TOKEN: Optional[str] = "secret_webhook_token_123"
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    QUEUE_NAME: str = "telegram_ai_tasks"


# Global configuration singleton
settings = PlatformSettings()
