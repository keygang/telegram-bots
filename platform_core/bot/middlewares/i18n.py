import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from platform_core.bot.middlewares.common import _get_user_from_event
from platform_core.db import UserProfile
from platform_core.i18n import i18n

logger = logging.getLogger(__name__)


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
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = _get_user_from_event(event, data)
        user_profile: UserProfile | None = data.get("user_profile")
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
