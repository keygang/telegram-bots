import pytest
from unittest.mock import MagicMock
from aiogram.types import Message, User
from platform_core.i18n import i18n, I18nManager
from platform_core.bot.middlewares import I18nMiddleware
from platform_core.db import db, UserProfile


def test_i18n_manager_translations_loaded():
    assert "en" in i18n.translations
    assert "ru" in i18n.translations
    assert "es" in i18n.translations
    assert "de" in i18n.translations

    # English translation test
    welcome_en = i18n.get("welcome_text", lang="en", credits=5)
    assert "Welcome to the AI Image Generation Bot!" in welcome_en
    assert "`5`" in welcome_en

    # Russian translation test
    welcome_ru = i18n.get("welcome_text", lang="ru", credits=5)
    assert "Добро пожаловать" in welcome_ru
    assert "`5`" in welcome_ru


def test_language_normalization():
    assert i18n.normalize_language_code("ru-RU") == "ru"
    assert i18n.normalize_language_code("es-MX") == "es"
    assert i18n.normalize_language_code("de_DE") == "de"
    assert i18n.normalize_language_code("fr-FR") == "en"  # unsupported falls back to en
    assert i18n.normalize_language_code(None) == "en"


def test_key_fallbacks():
    # Non-existent key should return key string itself
    assert i18n.get("non_existent_key_12345", lang="ru") == "non_existent_key_12345"


@pytest.mark.asyncio
async def test_i18n_middleware_telegram_lang():
    middleware = I18nMiddleware()
    user = User(id=12345, is_bot=False, first_name="John", language_code="ru-RU")
    event = MagicMock(spec=Message)
    event.from_user = user

    data = {}
    dummy_handler_called = False

    async def dummy_handler(evt, ctx):
        nonlocal dummy_handler_called
        dummy_handler_called = True
        assert ctx["user_lang"] == "ru"
        assert "Добро пожаловать" in ctx["_"]("welcome_text", credits=3)

    await middleware(dummy_handler, event, data)
    assert dummy_handler_called is True


@pytest.mark.asyncio
async def test_i18n_middleware_user_setting_override():
    middleware = I18nMiddleware()

    # User profile with explicit German setting
    user_id = 7771234
    profile = UserProfile(telegram_id=user_id, language_code="de")

    # Telegram client says language is Russian
    user = User(id=user_id, is_bot=False, first_name="Hans", language_code="ru")
    event = MagicMock(spec=Message)
    event.from_user = user

    data = {"user_profile": profile}
    dummy_handler_called = False

    async def dummy_handler(evt, ctx):
        nonlocal dummy_handler_called
        dummy_handler_called = True
        # Explicit saved user_profile setting (de) MUST take precedence over Telegram language (ru)
        assert ctx["user_lang"] == "de"
        assert "Willkommen" in ctx["_"]("welcome_text", credits=3)

    await middleware(dummy_handler, event, data)
    assert dummy_handler_called is True


@pytest.mark.asyncio
async def test_db_update_user_language():
    user_id = 999888777
    profile = await db.sync_user(telegram_id=user_id, language_code="en")
    assert profile.language_code == "en"

    updated = await db.update_user_language(telegram_id=user_id, language_code="es")
    assert updated is not None
    assert updated.language_code == "es"

    refetched = await db.sync_user(telegram_id=user_id)
    assert refetched.language_code == "es"
