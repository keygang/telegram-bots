import contextlib
import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

from aiogram import Bot

from platform_core.bot.keyboards import get_star_packages_keyboard
from platform_core.bot.states import GenerationStateData
from platform_core.db import db
from platform_core.events import (
    GenerationEvent,
    MessageSentEvent,
    get_tracker,
)
from platform_core.generators import (
    GenerationRequest,
    GenerationStatus,
    GeneratorFactory,
)
from platform_core.i18n import i18n
from platform_core.payments.packages import STAR_PACKAGES
from platform_core.queue import GenerationJob, task_broker
from platform_core.storage.media import MediaStorageManager, media_storage

logger = logging.getLogger(__name__)


def _resolve_gettext(_: Callable[..., str] | None) -> Callable[..., str]:
    return _ if _ is not None else i18n.get


def get_translator(data_dict: dict[str, Any]) -> Callable[..., str]:
    """Helper to extract translation function from handler data or fallback to default."""
    if "_" in data_dict and callable(data_dict["_"]):
        return data_dict["_"]
    user_lang = data_dict.get("user_lang", "en")

    def _tr(key: str, **kwargs: Any) -> str:
        return i18n.get(key, lang=user_lang, **kwargs)

    return _tr


async def _resolve_reference_photo(
    bot: Bot, state_data: dict[str, Any] | GenerationStateData
) -> bytes | None:
    """
    Resolves photo bytes from FSM state data.
    Supports lightweight reference_file_id (downloaded on demand) and legacy reference_photo_bytes.
    """
    if isinstance(state_data, GenerationStateData):
        ref_bytes = state_data.reference_photo_bytes
        ref_file_id = state_data.reference_file_id
    else:
        ref_bytes = state_data.get("reference_photo_bytes")
        ref_file_id = state_data.get("reference_file_id")

    if ref_bytes:
        return ref_bytes
    if ref_file_id:
        file_info = await bot.get_file(ref_file_id)
        photo_bytes_io = await bot.download_file(file_info.file_path)
        return photo_bytes_io.read()
    return None


async def run_generation_job(
    bot: Bot,
    chat_id: int,
    user_id: int,
    prompt: str,
    preset_id: str | None = None,
    reference_photo_bytes: bytes | None = None,
    media_type: str = "image",
    model_name: str = "google/gemini-2.5-flash-image",
    bot_id: str = "default_bot",
    force_mock: bool = False,
    use_queue: bool = True,
    _: Callable[..., str] | None = None,
) -> None:
    """Executes AI generation workflow, checks credits, delivers media, and logs history."""
    gettext = _resolve_gettext(_)
    tracker = get_tracker(bot_id)

    # 1. Credit Check
    has_credit = await db.deduct_user_credit(user_id, amount=1)
    if not has_credit:
        kb = get_star_packages_keyboard(STAR_PACKAGES, _=gettext)
        await bot.send_message(
            chat_id=chat_id,
            text=gettext("out_of_credits"),
            reply_markup=kb,
            parse_mode="Markdown",
        )
        await tracker.track(
            MessageSentEvent(
                distinct_id=user_id,
                bot_id=bot_id,
                message_type="out_of_credits",
                has_reply_markup=True,
            )
        )
        return

    status_msg = await bot.send_message(
        chat_id=chat_id,
        text=gettext("generating_creation"),
        parse_mode="Markdown",
    )

    if use_queue:
        photo_path = None
        if reference_photo_bytes:
            photo_path = media_storage.save_bytes(
                reference_photo_bytes, extension="jpg", filename_prefix="ref"
            )

        job = GenerationJob(
            job_id=str(uuid.uuid4()),
            bot_id=bot_id,
            user_id=user_id,
            chat_id=chat_id,
            status_message_id=status_msg.message_id,
            prompt=prompt,
            preset_id=preset_id,
            model_name=model_name,
            media_type=media_type,
            cost=1,
            photo_path=photo_path,
        )
        await task_broker.enqueue_job(job)
        return

    start_time = time.time()
    generator = GeneratorFactory.get_generator(force_mock=force_mock)

    req = GenerationRequest(
        prompt=prompt,
        model_name=model_name,
        reference_photo_bytes=reference_photo_bytes,
        media_type=media_type,
    )

    res = await generator.generate(req)
    duration_ms = res.duration_ms or int((time.time() - start_time) * 1000)

    if res.status == GenerationStatus.SUCCESS and res.media_urls:
        # Deliver generated result
        first_url = res.media_urls[0]
        input_file = MediaStorageManager.get_input_file(first_url)
        await bot.send_photo(
            chat_id=chat_id,
            photo=input_file,
            caption=gettext(
                "generation_complete", prompt=prompt[:100], latency=duration_ms / 1000.0
            ),
            parse_mode="Markdown",
        )

        with contextlib.suppress(Exception):
            await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)

        # Explicitly track generation and message sent
        await tracker.track(
            GenerationEvent(
                distinct_id=user_id,
                bot_id=bot_id,
                model_name=model_name,
                prompt=prompt,
                preset_id=preset_id,
                media_url=res.media_urls[0] if res.media_urls else None,
                status="success",
                duration_ms=duration_ms,
            )
        )
        await tracker.track(
            MessageSentEvent(
                distinct_id=user_id,
                bot_id=bot_id,
                message_type="photo",
                has_reply_markup=False,
            )
        )
    else:
        # Failure
        await status_msg.edit_text(
            gettext("generation_failed", error=res.error_message or "Unknown error"),
            parse_mode="Markdown",
        )
        # Refund credit on engine failure
        await db.add_user_credits(
            user_id=user_id,
            bot_id=bot_id,
            stars_paid=0,
            credits_to_add=1,
            telegram_charge_id="refund",
        )

        await tracker.track(
            GenerationEvent(
                distinct_id=user_id,
                bot_id=bot_id,
                model_name=model_name,
                prompt=prompt,
                preset_id=preset_id,
                status="failed",
                duration_ms=duration_ms,
                error_message=res.error_message,
            )
        )
