from aiogram.types import InlineKeyboardMarkup

from platform_core.bot.keyboards import (
    _resolve_gettext,
    get_cancel_keyboard,
    get_help_keyboard,
    get_language_keyboard,
    get_main_action_keyboard,
    get_models_keyboard,
    get_presets_keyboard,
    get_settings_keyboard,
    get_star_packages_keyboard,
    get_waiting_for_photo_keyboard,
)
from platform_core.bot.keyboards.common import (
    _resolve_gettext as mod_resolve_gettext,
)
from platform_core.bot.keyboards.common import (
    get_cancel_keyboard as mod_get_cancel_keyboard,
)
from platform_core.bot.keyboards.help import (
    get_help_keyboard as mod_get_help_keyboard,
)
from platform_core.bot.keyboards.menu import (
    get_main_action_keyboard as mod_get_main_action_keyboard,
)
from platform_core.bot.keyboards.models import (
    get_models_keyboard as mod_get_models_keyboard,
)
from platform_core.bot.keyboards.packages import (
    get_star_packages_keyboard as mod_get_star_packages_keyboard,
)
from platform_core.bot.keyboards.presets import (
    get_presets_keyboard as mod_get_presets_keyboard,
)
from platform_core.bot.keyboards.presets import (
    get_waiting_for_photo_keyboard as mod_get_waiting_for_photo_keyboard,
)
from platform_core.bot.keyboards.settings import (
    get_language_keyboard as mod_get_language_keyboard,
)
from platform_core.bot.keyboards.settings import (
    get_settings_keyboard as mod_get_settings_keyboard,
)
from platform_core.payments.packages import StarPackage
from platform_core.presets.base import PromptPreset


def test_keyboards_package_exports():
    """Verify that all keyboard builder functions are re-exported correctly from platform_core.bot.keyboards."""
    assert callable(_resolve_gettext)
    assert callable(get_cancel_keyboard)
    assert callable(get_help_keyboard)
    assert callable(get_language_keyboard)
    assert callable(get_main_action_keyboard)
    assert callable(get_models_keyboard)
    assert callable(get_presets_keyboard)
    assert callable(get_settings_keyboard)
    assert callable(get_star_packages_keyboard)
    assert callable(get_waiting_for_photo_keyboard)


def test_direct_submodule_identities():
    """Verify that imports from dedicated keyboard files match the re-exported package symbols."""
    assert _resolve_gettext is mod_resolve_gettext
    assert get_cancel_keyboard is mod_get_cancel_keyboard
    assert get_help_keyboard is mod_get_help_keyboard
    assert get_language_keyboard is mod_get_language_keyboard
    assert get_main_action_keyboard is mod_get_main_action_keyboard
    assert get_models_keyboard is mod_get_models_keyboard
    assert get_presets_keyboard is mod_get_presets_keyboard
    assert get_settings_keyboard is mod_get_settings_keyboard
    assert get_star_packages_keyboard is mod_get_star_packages_keyboard
    assert get_waiting_for_photo_keyboard is mod_get_waiting_for_photo_keyboard


def test_keyboard_rendering():
    """Verify that each submodule renders a valid aiogram InlineKeyboardMarkup."""
    # Cancel keyboard
    kb_cancel = get_cancel_keyboard()
    assert isinstance(kb_cancel, InlineKeyboardMarkup)
    assert len(kb_cancel.inline_keyboard) == 1

    # Help keyboard
    kb_help = get_help_keyboard()
    assert isinstance(kb_help, InlineKeyboardMarkup)
    assert len(kb_help.inline_keyboard) >= 2

    # Language keyboard
    kb_lang = get_language_keyboard(current_lang="en")
    assert isinstance(kb_lang, InlineKeyboardMarkup)
    assert len(kb_lang.inline_keyboard) >= 2

    # Main action keyboard
    kb_main = get_main_action_keyboard(user_credits=5)
    assert isinstance(kb_main, InlineKeyboardMarkup)
    assert len(kb_main.inline_keyboard) == 2

    # Models keyboard
    kb_models = get_models_keyboard(models=["model/a", "model/b"], current_model="model/a")
    assert isinstance(kb_models, InlineKeyboardMarkup)
    assert len(kb_models.inline_keyboard) == 3

    # Presets keyboard
    sample_preset = PromptPreset(
        id="test_preset",
        title="Test Preset",
        description="Testing",
        prompt_template="{user_prompt}",
        icon="🎨",
    )
    kb_presets = get_presets_keyboard(presets=[sample_preset], has_photo=False)
    assert isinstance(kb_presets, InlineKeyboardMarkup)
    assert len(kb_presets.inline_keyboard) >= 2

    # Waiting for photo keyboard
    kb_waiting = get_waiting_for_photo_keyboard(preset_id="test_preset")
    assert isinstance(kb_waiting, InlineKeyboardMarkup)
    assert len(kb_waiting.inline_keyboard) == 2

    # Star packages keyboard
    sample_pkg = StarPackage(
        id="pkg_test",
        title="Test Pack",
        description="Test Pack Desc",
        stars_amount=10,
        credits_count=5,
        icon="⭐️",
    )
    kb_stars = get_star_packages_keyboard(packages=[sample_pkg])
    assert isinstance(kb_stars, InlineKeyboardMarkup)
    assert len(kb_stars.inline_keyboard) == 2

    # Settings keyboard
    kb_settings = get_settings_keyboard()
    assert isinstance(kb_settings, InlineKeyboardMarkup)
    assert len(kb_settings.inline_keyboard) == 4
