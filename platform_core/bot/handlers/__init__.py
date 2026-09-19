from aiogram import Router

from platform_core.events import (
    CommandEvent,
    GenerationEvent,
    MessageSentEvent,
    get_tracker,
)

from .common import (
    _resolve_gettext,
    _resolve_reference_photo,
    get_translator,
    run_generation_job,
)
from .help import handle_help_command, help_router
from .menu import (
    handle_buy_menu,
    handle_presets_menu,
    handle_reload_presets_command,
    handle_start_command,
    menu_router,
)
from .models import handle_models_menu, handle_set_model, models_router
from .photo import handle_photo_upload, photo_router
from .presets import (
    handle_cancel_action,
    handle_preset_selection,
    presets_router,
)
from .prompt import handle_custom_text_prompt, prompt_router
from .settings import (
    handle_change_language_menu,
    handle_set_language,
    handle_settings_menu,
    settings_router,
)

core_router = Router(name="core_router")
core_router.include_router(menu_router)
core_router.include_router(help_router)
core_router.include_router(settings_router)
core_router.include_router(models_router)
core_router.include_router(presets_router)
core_router.include_router(photo_router)
core_router.include_router(prompt_router)

__all__ = [
    "CommandEvent",
    "GenerationEvent",
    "MessageSentEvent",
    "_resolve_gettext",
    "_resolve_reference_photo",
    "core_router",
    "get_tracker",
    "get_translator",
    "handle_buy_menu",
    "handle_cancel_action",
    "handle_change_language_menu",
    "handle_custom_text_prompt",
    "handle_help_command",
    "handle_models_menu",
    "handle_photo_upload",
    "handle_preset_selection",
    "handle_presets_menu",
    "handle_reload_presets_command",
    "handle_set_language",
    "handle_set_model",
    "handle_settings_menu",
    "handle_start_command",
    "help_router",
    "menu_router",
    "models_router",
    "photo_router",
    "presets_router",
    "prompt_router",
    "run_generation_job",
    "settings_router",
]
