from aiogram import Router

from platform_core.bot import (
    core_router,
    help_router,
    menu_router,
    models_router,
    photo_router,
    presets_router,
    prompt_router,
    settings_router,
)
from platform_core.bot.handlers import (
    _resolve_gettext,
    _resolve_reference_photo,
    get_translator,
    handle_buy_menu,
    handle_cancel_action,
    handle_change_language_menu,
    handle_custom_text_prompt,
    handle_help_command,
    handle_models_menu,
    handle_photo_upload,
    handle_preset_selection,
    handle_presets_menu,
    handle_reload_presets_command,
    handle_set_language,
    handle_set_model,
    handle_settings_menu,
    handle_start_command,
    run_generation_job,
)
from platform_core.bot.handlers.common import (
    _resolve_gettext as common_resolve_gettext,
)
from platform_core.bot.handlers.common import (
    _resolve_reference_photo as common_resolve_ref_photo,
)
from platform_core.bot.handlers.common import (
    get_translator as common_get_translator,
)
from platform_core.bot.handlers.common import (
    run_generation_job as common_run_generation_job,
)
from platform_core.bot.handlers.help import (
    handle_help_command as mod_handle_help_command,
)
from platform_core.bot.handlers.help import (
    help_router as mod_help_router,
)
from platform_core.bot.handlers.menu import (
    handle_buy_menu as mod_handle_buy_menu,
)
from platform_core.bot.handlers.menu import (
    handle_presets_menu as mod_handle_presets_menu,
)
from platform_core.bot.handlers.menu import (
    handle_reload_presets_command as mod_handle_reload_presets_command,
)
from platform_core.bot.handlers.menu import (
    handle_start_command as mod_handle_start_command,
)
from platform_core.bot.handlers.menu import (
    menu_router as mod_menu_router,
)
from platform_core.bot.handlers.models import (
    handle_models_menu as mod_handle_models_menu,
)
from platform_core.bot.handlers.models import (
    handle_set_model as mod_handle_set_model,
)
from platform_core.bot.handlers.models import (
    models_router as mod_models_router,
)
from platform_core.bot.handlers.photo import (
    handle_photo_upload as mod_handle_photo_upload,
)
from platform_core.bot.handlers.photo import (
    photo_router as mod_photo_router,
)
from platform_core.bot.handlers.presets import (
    handle_cancel_action as mod_handle_cancel_action,
)
from platform_core.bot.handlers.presets import (
    handle_preset_selection as mod_handle_preset_selection,
)
from platform_core.bot.handlers.presets import (
    presets_router as mod_presets_router,
)
from platform_core.bot.handlers.prompt import (
    handle_custom_text_prompt as mod_handle_custom_text_prompt,
)
from platform_core.bot.handlers.prompt import (
    prompt_router as mod_prompt_router,
)
from platform_core.bot.handlers.settings import (
    handle_change_language_menu as mod_handle_change_language_menu,
)
from platform_core.bot.handlers.settings import (
    handle_set_language as mod_handle_set_language,
)
from platform_core.bot.handlers.settings import (
    handle_settings_menu as mod_handle_settings_menu,
)
from platform_core.bot.handlers.settings import (
    settings_router as mod_settings_router,
)


def test_handlers_package_exports():
    """Verify that all handlers and common functions are re-exported correctly from platform_core.bot.handlers."""
    assert callable(handle_start_command)
    assert callable(handle_presets_menu)
    assert callable(handle_reload_presets_command)
    assert callable(handle_buy_menu)
    assert callable(handle_help_command)
    assert callable(handle_settings_menu)
    assert callable(handle_change_language_menu)
    assert callable(handle_set_language)
    assert callable(handle_models_menu)
    assert callable(handle_set_model)
    assert callable(handle_cancel_action)
    assert callable(handle_preset_selection)
    assert callable(handle_photo_upload)
    assert callable(handle_custom_text_prompt)
    assert callable(run_generation_job)
    assert callable(_resolve_gettext)
    assert callable(_resolve_reference_photo)
    assert callable(get_translator)


def test_direct_submodule_identities():
    """Verify that imports from dedicated handler files match the re-exported package symbols."""
    assert handle_start_command is mod_handle_start_command
    assert handle_presets_menu is mod_handle_presets_menu
    assert handle_reload_presets_command is mod_handle_reload_presets_command
    assert handle_buy_menu is mod_handle_buy_menu

    assert handle_help_command is mod_handle_help_command

    assert handle_settings_menu is mod_handle_settings_menu
    assert handle_change_language_menu is mod_handle_change_language_menu
    assert handle_set_language is mod_handle_set_language

    assert handle_models_menu is mod_handle_models_menu
    assert handle_set_model is mod_handle_set_model

    assert handle_cancel_action is mod_handle_cancel_action
    assert handle_preset_selection is mod_handle_preset_selection

    assert handle_photo_upload is mod_handle_photo_upload
    assert handle_custom_text_prompt is mod_handle_custom_text_prompt

    assert run_generation_job is common_run_generation_job
    assert _resolve_gettext is common_resolve_gettext
    assert _resolve_reference_photo is common_resolve_ref_photo
    assert get_translator is common_get_translator


def test_subrouters_included_in_core_router():
    """Verify that core_router includes all 7 modular sub-routers."""
    assert isinstance(core_router, Router)
    assert isinstance(menu_router, Router)
    assert isinstance(help_router, Router)
    assert isinstance(settings_router, Router)
    assert isinstance(models_router, Router)
    assert isinstance(presets_router, Router)
    assert isinstance(photo_router, Router)
    assert isinstance(prompt_router, Router)

    sub_router_names = {r.name for r in core_router.sub_routers}
    expected_names = {
        "menu_router",
        "help_router",
        "settings_router",
        "models_router",
        "presets_router",
        "photo_router",
        "prompt_router",
    }
    assert expected_names.issubset(sub_router_names)
