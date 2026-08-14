import logging
from typing import Any, Callable, Dict, Awaitable, Optional
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from platform_core.db import db, UserProfile
from platform_core.i18n import i18n

logger = logging.getLogger(__name__)


class UserSyncMiddleware(BaseMiddleware):
    """Middleware that synchronizes Telegram user profile into Supabase DB."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = None
        if isinstance(event, Message) and event.from_user:
            user = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            user = event.from_user

        if user:
            user_profile = await db.sync_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            data["user_profile"] = user_profile

        return await handler(event, data)


class I18nMiddleware(BaseMiddleware):
    """
    Middleware that resolves language code for incoming updates.
    Priority:
    1. Saved language preference in user_profile.language_code
    2. Telegram interface language from_user.language_code
    3. System default fallback ('en')
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = None
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            user = event.from_user

        user_profile: Optional[UserProfile] = data.get("user_profile")
        raw_lang = None

        if user_profile and user_profile.language_code:
            raw_lang = user_profile.language_code
        elif user and user.language_code:
            raw_lang = user.language_code

        user_lang = i18n.normalize_language_code(raw_lang)

        def translate(key: str, **kwargs: Any) -> str:
            return i18n.get(key, lang=user_lang, **kwargs)

        data["user_lang"] = user_lang
        data["_"] = translate
        data["i18n"] = i18n

        return await handler(event, data)


class CreditCheckMiddleware(BaseMiddleware):
    """Middleware that ensures user has available generation credits."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = None
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            user = event.from_user

        if user:
            balance = await db.get_user_balance(user.id)
            data["user_balance"] = balance

        return await handler(event, data)
