import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import CallbackQuery, Chat, File, Message, PhotoSize, User

from platform_core.bot.handlers import (
    handle_cancel_action,
    handle_custom_text_prompt,
    handle_photo_upload,
    handle_preset_selection,
    handle_presets_menu,
)
from platform_core.bot.states import GenerationStates


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    bot.token = "123456:MOCK_TOKEN"
    file_obj = File(file_id="photo_123", file_unique_id="uniq_123", file_path="photos/sample.jpg")
    bot.get_file = AsyncMock(return_value=file_obj)

    photo_stream = io.BytesIO(b"FAKE_PHOTO_BYTES_DATA_12345")
    bot.download_file = AsyncMock(return_value=photo_stream)
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))
    bot.send_photo = AsyncMock()
    return bot


@pytest.fixture
def memory_fsm_context():
    storage = MemoryStorage()
    key = StorageKey(bot_id=123456, chat_id=1001, user_id=2001)
    return FSMContext(storage=storage, key=key)


@pytest.mark.asyncio
async def test_flow_a_photo_first_then_preset(mock_bot, memory_fsm_context):
    """
    Flow A:
    1. User uploads photo -> saved in state, transitions to selecting_preset.
    2. User selects preset -> generates image with reference photo bytes.
    """
    user = User(id=2001, is_bot=False, first_name="Alice")
    chat = Chat(id=1001, type="private")
    photo_sizes = [
        PhotoSize(file_id="thumb_1", file_unique_id="u1", width=100, height=100),
        PhotoSize(file_id="photo_123", file_unique_id="u2", width=800, height=800),
    ]

    photo_msg = MagicMock(spec=Message)
    photo_msg.message_id = 10
    photo_msg.chat = chat
    photo_msg.from_user = user
    photo_msg.photo = photo_sizes
    photo_msg.caption = None
    photo_msg.answer = AsyncMock()

    await handle_photo_upload(
        message=photo_msg,
        state=memory_fsm_context,
        bot=mock_bot,
        bot_id="image_bot",
    )

    state_name = await memory_fsm_context.get_state()
    assert state_name == GenerationStates.selecting_preset.state
    state_data = await memory_fsm_context.get_data()
    assert state_data.get("reference_file_id") == "photo_123"
    assert photo_msg.answer.called

    # 2. User selects a preset
    cb_msg = MagicMock(spec=Message)
    cb_msg.chat = chat
    cb_msg.message_id = 11

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "preset:cyberpunk"
    callback.from_user = user
    callback.message = cb_msg
    callback.answer = AsyncMock()

    with patch(
        "platform_core.bot.handlers.run_generation_job", new_callable=AsyncMock
    ) as mock_run_gen:
        await handle_preset_selection(
            callback=callback,
            state=memory_fsm_context,
            bot=mock_bot,
            bot_id="image_bot",
        )

        assert mock_run_gen.called
        call_kwargs = mock_run_gen.call_args.kwargs
        assert call_kwargs["reference_photo_bytes"] == b"FAKE_PHOTO_BYTES_DATA_12345"
        assert call_kwargs["preset_id"] == "cyberpunk"
        assert "Cyberpunk" in call_kwargs["prompt"]

    # FSM state should now be cleared
    assert await memory_fsm_context.get_state() is None


@pytest.mark.asyncio
async def test_flow_b_preset_first_then_photo(mock_bot, memory_fsm_context):
    """
    Flow B:
    1. User selects preset first -> state enters waiting_for_photo.
    2. User uploads photo -> generates image with selected preset + photo.
    """
    user = User(id=2001, is_bot=False, first_name="Alice")
    chat = Chat(id=1001, type="private")

    # 1. User selects preset
    cb_msg = MagicMock(spec=Message)
    cb_msg.chat = chat
    cb_msg.message_id = 11
    cb_msg.answer = AsyncMock()

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "preset:renaissance"
    callback.from_user = user
    callback.message = cb_msg
    callback.answer = AsyncMock()

    await handle_preset_selection(
        callback=callback,
        state=memory_fsm_context,
        bot=mock_bot,
        bot_id="image_bot",
    )

    state_name = await memory_fsm_context.get_state()
    assert state_name == GenerationStates.waiting_for_photo.state
    state_data = await memory_fsm_context.get_data()
    assert state_data.get("selected_preset_id") == "renaissance"
    assert cb_msg.answer.called

    # 2. User uploads photo
    photo_sizes = [PhotoSize(file_id="photo_123", file_unique_id="u2", width=800, height=800)]
    photo_msg = MagicMock(spec=Message)
    photo_msg.message_id = 12
    photo_msg.chat = chat
    photo_msg.from_user = user
    photo_msg.photo = photo_sizes
    photo_msg.caption = None
    photo_msg.answer = AsyncMock()

    with patch(
        "platform_core.bot.handlers.run_generation_job", new_callable=AsyncMock
    ) as mock_run_gen:
        await handle_photo_upload(
            message=photo_msg,
            state=memory_fsm_context,
            bot=mock_bot,
            bot_id="image_bot",
        )

        assert mock_run_gen.called
        call_kwargs = mock_run_gen.call_args.kwargs
        assert call_kwargs["reference_photo_bytes"] == b"FAKE_PHOTO_BYTES_DATA_12345"
        assert call_kwargs["preset_id"] == "renaissance"
        assert "Renaissance" in call_kwargs["prompt"]

    # FSM state should now be cleared
    assert await memory_fsm_context.get_state() is None


@pytest.mark.asyncio
async def test_flow_c_text_to_image_without_photo(mock_bot, memory_fsm_context):
    """
    Flow C:
    User types custom text prompt directly -> Generates text-to-image without photo bytes.
    """
    user = User(id=2001, is_bot=False, first_name="Alice")
    chat = Chat(id=1001, type="private")

    text_msg = MagicMock(spec=Message)
    text_msg.message_id = 20
    text_msg.chat = chat
    text_msg.from_user = user
    text_msg.text = "A futuristic flying cyber car over Tokyo skyline"
    text_msg.answer = AsyncMock()

    with patch(
        "platform_core.bot.handlers.run_generation_job", new_callable=AsyncMock
    ) as mock_run_gen:
        await handle_custom_text_prompt(
            message=text_msg,
            state=memory_fsm_context,
            bot=mock_bot,
            bot_id="image_bot",
        )

        assert mock_run_gen.called
        call_kwargs = mock_run_gen.call_args.kwargs
        assert call_kwargs["reference_photo_bytes"] is None
        assert call_kwargs["prompt"] == "A futuristic flying cyber car over Tokyo skyline"

    assert await memory_fsm_context.get_state() is None


@pytest.mark.asyncio
async def test_flow_d_photo_with_caption(mock_bot, memory_fsm_context):
    """
    Flow D:
    User uploads photo with a caption -> Generates directly with caption prompt + photo.
    """
    user = User(id=2001, is_bot=False, first_name="Alice")
    chat = Chat(id=1001, type="private")

    photo_sizes = [PhotoSize(file_id="photo_123", file_unique_id="u2", width=800, height=800)]
    photo_msg = MagicMock(spec=Message)
    photo_msg.message_id = 30
    photo_msg.chat = chat
    photo_msg.from_user = user
    photo_msg.photo = photo_sizes
    photo_msg.caption = "Turn me into an ancient samurai warrior"
    photo_msg.answer = AsyncMock()

    with patch(
        "platform_core.bot.handlers.run_generation_job", new_callable=AsyncMock
    ) as mock_run_gen:
        await handle_photo_upload(
            message=photo_msg,
            state=memory_fsm_context,
            bot=mock_bot,
            bot_id="image_bot",
        )

        assert mock_run_gen.called
        call_kwargs = mock_run_gen.call_args.kwargs
        assert call_kwargs["reference_photo_bytes"] == b"FAKE_PHOTO_BYTES_DATA_12345"
        assert call_kwargs["prompt"] == "Turn me into an ancient samurai warrior"

    assert await memory_fsm_context.get_state() is None


@pytest.mark.asyncio
async def test_cancel_action(mock_bot, memory_fsm_context):
    """
    Test cancel button or command resets FSM state cleanly.
    """
    await memory_fsm_context.set_state(GenerationStates.waiting_for_photo)
    await memory_fsm_context.update_data(selected_preset_id="cyberpunk")

    user = User(id=2001, is_bot=False, first_name="Alice")
    chat = Chat(id=1001, type="private")
    cb_msg = MagicMock(spec=Message)
    cb_msg.chat = chat
    cb_msg.edit_text = AsyncMock()

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "cancel_action"
    callback.from_user = user
    callback.message = cb_msg
    callback.answer = AsyncMock()

    await handle_cancel_action(
        event=callback,
        state=memory_fsm_context,
        bot_id="image_bot",
    )

    assert await memory_fsm_context.get_state() is None
    assert (await memory_fsm_context.get_data()) == {}
    assert cb_msg.edit_text.called


@pytest.mark.asyncio
async def test_legacy_reference_photo_bytes_compatibility(mock_bot, memory_fsm_context):
    """
    Test backwards compatibility when raw reference_photo_bytes are already present in FSM state.
    """
    user = User(id=2001, is_bot=False, first_name="Alice")
    chat = Chat(id=1001, type="private")

    await memory_fsm_context.set_state(GenerationStates.selecting_preset)
    await memory_fsm_context.update_data(reference_photo_bytes=b"LEGACY_RAW_BYTES_999")

    cb_msg = MagicMock(spec=Message)
    cb_msg.chat = chat
    cb_msg.message_id = 11

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "preset:cyberpunk"
    callback.from_user = user
    callback.message = cb_msg
    callback.answer = AsyncMock()

    with patch(
        "platform_core.bot.handlers.run_generation_job", new_callable=AsyncMock
    ) as mock_run_gen:
        await handle_preset_selection(
            callback=callback,
            state=memory_fsm_context,
            bot=mock_bot,
            bot_id="image_bot",
        )

        assert mock_run_gen.called
        call_kwargs = mock_run_gen.call_args.kwargs
        assert call_kwargs["reference_photo_bytes"] == b"LEGACY_RAW_BYTES_999"


@pytest.mark.asyncio
async def test_preset_rejects_text_prompt_and_requires_photo(mock_bot, memory_fsm_context):
    """
    When a preset is chosen, the bot enters waiting_for_photo state.
    Sending a text prompt must be rejected, prompting the user to upload a photo or cancel.
    """
    await memory_fsm_context.set_state(GenerationStates.waiting_for_photo)
    await memory_fsm_context.update_data(selected_preset_id="cyberpunk")

    user = User(id=2001, is_bot=False, first_name="Alice")
    chat = Chat(id=1001, type="private")

    text_msg = MagicMock(spec=Message)
    text_msg.message_id = 45
    text_msg.chat = chat
    text_msg.from_user = user
    text_msg.text = "Just create a cyberpunk robot without photo"
    text_msg.answer = AsyncMock()

    with patch(
        "platform_core.bot.handlers.run_generation_job", new_callable=AsyncMock
    ) as mock_run_gen:
        await handle_custom_text_prompt(
            message=text_msg,
            state=memory_fsm_context,
            bot=mock_bot,
            bot_id="image_bot",
        )

        # Generation must NOT be executed
        assert not mock_run_gen.called
        # Must answer with photo requirement notification
        assert text_msg.answer.called
        answer_call_args = text_msg.answer.call_args
        assert "Photo" in answer_call_args[0][0] or "photo" in answer_call_args[0][0]

    # State must remain waiting_for_photo so the user can upload a photo
    assert await memory_fsm_context.get_state() == GenerationStates.waiting_for_photo.state


@pytest.mark.asyncio
async def test_custom_prompt_flow_text_only(mock_bot, memory_fsm_context):
    """
    User clicks Custom Prompt -> enters entering_custom_prompt -> sends text prompt -> generates text-to-image.
    """
    user = User(id=2001, is_bot=False, first_name="Alice")
    chat = Chat(id=1001, type="private")

    # 1. User clicks Custom Prompt
    cb_msg = MagicMock(spec=Message)
    cb_msg.chat = chat
    cb_msg.message_id = 50
    cb_msg.answer = AsyncMock()

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "preset:custom"
    callback.from_user = user
    callback.message = cb_msg
    callback.answer = AsyncMock()

    await handle_preset_selection(
        callback=callback,
        state=memory_fsm_context,
        bot=mock_bot,
        bot_id="image_bot",
    )

    assert await memory_fsm_context.get_state() == GenerationStates.entering_custom_prompt.state
    assert cb_msg.answer.called

    # 2. User sends text prompt
    text_msg = MagicMock(spec=Message)
    text_msg.message_id = 51
    text_msg.chat = chat
    text_msg.from_user = user
    text_msg.text = "Mystical enchanted forest with glowing mushrooms"
    text_msg.answer = AsyncMock()

    with patch(
        "platform_core.bot.handlers.run_generation_job", new_callable=AsyncMock
    ) as mock_run_gen:
        await handle_custom_text_prompt(
            message=text_msg,
            state=memory_fsm_context,
            bot=mock_bot,
            bot_id="image_bot",
        )

        assert mock_run_gen.called
        call_kwargs = mock_run_gen.call_args.kwargs
        assert call_kwargs["reference_photo_bytes"] is None
        assert call_kwargs["prompt"] == "Mystical enchanted forest with glowing mushrooms"

    assert await memory_fsm_context.get_state() is None


@pytest.mark.asyncio
async def test_custom_prompt_flow_with_photo_upload_then_text(mock_bot, memory_fsm_context):
    """
    User clicks Custom Prompt -> uploads photo without caption -> sends text prompt -> generates photo-to-photo.
    """
    user = User(id=2001, is_bot=False, first_name="Alice")
    chat = Chat(id=1001, type="private")

    # 1. User clicks Custom Prompt
    await memory_fsm_context.set_state(GenerationStates.entering_custom_prompt)

    # 2. User uploads photo without caption
    photo_sizes = [
        PhotoSize(file_id="custom_photo_999", file_unique_id="u99", width=800, height=800)
    ]
    photo_msg = MagicMock(spec=Message)
    photo_msg.message_id = 60
    photo_msg.chat = chat
    photo_msg.from_user = user
    photo_msg.photo = photo_sizes
    photo_msg.caption = None
    photo_msg.answer = AsyncMock()

    await handle_photo_upload(
        message=photo_msg,
        state=memory_fsm_context,
        bot=mock_bot,
        bot_id="image_bot",
    )

    state_data = await memory_fsm_context.get_data()
    assert state_data.get("reference_file_id") == "custom_photo_999"
    assert photo_msg.answer.called

    # 3. User sends custom text prompt
    text_msg = MagicMock(spec=Message)
    text_msg.message_id = 61
    text_msg.chat = chat
    text_msg.from_user = user
    text_msg.text = "Add steampunk goggles and mechanical wings"
    text_msg.answer = AsyncMock()

    with patch(
        "platform_core.bot.handlers.run_generation_job", new_callable=AsyncMock
    ) as mock_run_gen:
        await handle_custom_text_prompt(
            message=text_msg,
            state=memory_fsm_context,
            bot=mock_bot,
            bot_id="image_bot",
        )

        assert mock_run_gen.called
        call_kwargs = mock_run_gen.call_args.kwargs
        assert call_kwargs["reference_photo_bytes"] == b"FAKE_PHOTO_BYTES_DATA_12345"
        assert call_kwargs["prompt"] == "Add steampunk goggles and mechanical wings"

    assert await memory_fsm_context.get_state() is None


@pytest.mark.asyncio
async def test_custom_prompt_flow_with_captioned_photo_upload(mock_bot, memory_fsm_context):
    """
    User clicks Custom Prompt -> uploads photo WITH caption -> immediately generates photo-to-photo.
    """
    user = User(id=2001, is_bot=False, first_name="Alice")
    chat = Chat(id=1001, type="private")

    # 1. In entering_custom_prompt state
    await memory_fsm_context.set_state(GenerationStates.entering_custom_prompt)

    # 2. Uploads photo with caption
    photo_sizes = [PhotoSize(file_id="photo_123", file_unique_id="u2", width=800, height=800)]
    photo_msg = MagicMock(spec=Message)
    photo_msg.message_id = 70
    photo_msg.chat = chat
    photo_msg.from_user = user
    photo_msg.photo = photo_sizes
    photo_msg.caption = "Transform into an oil painting"
    photo_msg.answer = AsyncMock()

    with patch(
        "platform_core.bot.handlers.run_generation_job", new_callable=AsyncMock
    ) as mock_run_gen:
        await handle_photo_upload(
            message=photo_msg,
            state=memory_fsm_context,
            bot=mock_bot,
            bot_id="image_bot",
        )

        assert mock_run_gen.called
        call_kwargs = mock_run_gen.call_args.kwargs
        assert call_kwargs["reference_photo_bytes"] == b"FAKE_PHOTO_BYTES_DATA_12345"
        assert call_kwargs["prompt"] == "Transform into an oil painting"

    assert await memory_fsm_context.get_state() is None


@pytest.mark.asyncio
async def test_generate_menu_command_and_callback(mock_bot):
    """
    Test /generate command and callback query renders presets menu.
    """
    user = User(id=2001, is_bot=False, first_name="Alice")
    chat = Chat(id=1001, type="private")

    # Test Message command
    msg = MagicMock(spec=Message)
    msg.chat = chat
    msg.from_user = user
    msg.answer = AsyncMock()

    await handle_presets_menu(event=msg, bot_id="image_bot")
    assert msg.answer.called

    # Test CallbackQuery
    cb_msg = MagicMock(spec=Message)
    cb_msg.chat = chat
    cb_msg.edit_text = AsyncMock()

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "generate_menu"
    callback.from_user = user
    callback.message = cb_msg
    callback.answer = AsyncMock()

    await handle_presets_menu(event=callback, bot_id="image_bot")
    assert callback.answer.called
    assert cb_msg.edit_text.called
