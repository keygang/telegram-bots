import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, File, Message, PhotoSize, User

from platform_core.bot.handlers import (
    handle_cancel_action,
    handle_custom_text_prompt,
    handle_photo_upload,
    handle_preset_selection,
)
from platform_core.bot.states import GenerationStates
from platform_core.fsm_storage import (
    BaseFSMStorageProvider,
    FSMStorageFactory,
    MemoryFSMStorageProvider,
    RedisFSMStorageProvider,
    get_fsm_storage,
)
from platform_core.modules.builder import ModularBotBuilder


@pytest.mark.asyncio
async def test_fsm_storage_providers_and_factory():
    """Test the abstract storage provider hierarchy and factory resolution."""
    # 1. Memory provider
    mem_provider = MemoryFSMStorageProvider()
    assert isinstance(mem_provider, BaseFSMStorageProvider)
    mem_storage = mem_provider.create_storage()
    assert isinstance(mem_storage, MemoryStorage)

    # 2. Factory with force_memory=True
    storage_forced = FSMStorageFactory.create_storage(force_memory=True)
    assert isinstance(storage_forced, MemoryStorage)

    # 3. Factory with empty / None url
    storage_none = FSMStorageFactory.create_storage(redis_url="")
    assert isinstance(storage_none, MemoryStorage)

    # 4. Redis provider with simulated valid redis
    redis_provider = RedisFSMStorageProvider(redis_url="redis://localhost:6379/0", key_prefix="test_fsm")
    assert isinstance(redis_provider, BaseFSMStorageProvider)

    # 5. Redis fallback to memory when redis connection fails
    with patch("aiogram.fsm.storage.redis.RedisStorage.__init__", side_effect=Exception("Redis connection error")):
        fallback_storage = redis_provider.create_storage()
        assert isinstance(fallback_storage, MemoryStorage)

    # 6. Convenience function
    default_storage = get_fsm_storage(force_memory=True)
    assert isinstance(default_storage, BaseStorage)


@pytest.mark.asyncio
async def test_modular_bot_builder_with_custom_storage():
    """Test ModularBotBuilder accepts custom storage and uses factory by default."""
    custom_storage = MemoryStorage()
    bot_builder = ModularBotBuilder(bot_id="replica_bot", token="123456:FAKE_TOKEN")
    modular_bot = bot_builder.build(storage=custom_storage)

    assert modular_bot.dp.fsm.storage == custom_storage


@pytest.mark.asyncio
async def test_multi_replica_state_synchronization():
    """
    Simulates a 3-replica cluster sharing the same FSM storage backend:
    - Replica A receives user's photo upload.
    - Replica B receives user's callback query selecting a style preset.
    - Replica B resolves the photo via Bot API and starts generation with photo reference.
    - State is cleanly cleared across all replicas.
    """
    shared_storage = MemoryStorage()
    key = StorageKey(bot_id=123456, chat_id=5001, user_id=9001)

    # Contexts representing 3 different worker replicas connected to shared storage
    replica_a_context = FSMContext(storage=shared_storage, key=key)
    replica_b_context = FSMContext(storage=shared_storage, key=key)
    replica_c_context = FSMContext(storage=shared_storage, key=key)

    user = User(id=9001, is_bot=False, first_name="Bob")
    chat = Chat(id=5001, type="private")

    mock_bot = AsyncMock()
    mock_bot.token = "123456:MOCK_TOKEN"
    file_obj = File(file_id="distributed_photo_999", file_unique_id="u999", file_path="photos/bob.jpg")
    mock_bot.get_file = AsyncMock(return_value=file_obj)
    mock_bot.download_file = AsyncMock(return_value=io.BytesIO(b"BOB_PHOTO_BINARY_DATA"))
    mock_bot.send_message = AsyncMock(return_value=MagicMock(message_id=101))

    # Step 1: User uploads photo to Replica A
    photo_msg = MagicMock(spec=Message)
    photo_msg.message_id = 50
    photo_msg.chat = chat
    photo_msg.from_user = user
    photo_msg.photo = [PhotoSize(file_id="distributed_photo_999", file_unique_id="u999", width=640, height=640)]
    photo_msg.caption = None
    photo_msg.answer = AsyncMock()

    await handle_photo_upload(
        message=photo_msg,
        state=replica_a_context,
        bot=mock_bot,
        bot_id="image_bot",
    )

    # Verify Replica A saved lightweight reference_file_id into shared state
    assert await replica_a_context.get_state() == GenerationStates.selecting_preset.state
    shared_data = await shared_storage.get_data(key=key)
    assert shared_data.get("reference_file_id") == "distributed_photo_999"
    # Ensure heavy raw bytes were not saved to shared storage
    assert "reference_photo_bytes" not in shared_data

    # Step 2: Next user interaction (preset click) hits Replica B
    cb_msg = MagicMock(spec=Message)
    cb_msg.chat = chat
    cb_msg.message_id = 51

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "preset:cyberpunk"
    callback.from_user = user
    callback.message = cb_msg
    callback.answer = AsyncMock()

    with patch("platform_core.bot.handlers.run_generation_job", new_callable=AsyncMock) as mock_run_gen:
        await handle_preset_selection(
            callback=callback,
            state=replica_b_context,
            bot=mock_bot,
            bot_id="image_bot",
        )

        assert mock_run_gen.called
        call_kwargs = mock_run_gen.call_args.kwargs
        # Replica B successfully fetched the photo via Telegram file_id from shared state
        assert call_kwargs["reference_photo_bytes"] == b"BOB_PHOTO_BINARY_DATA"
        assert call_kwargs["preset_id"] == "cyberpunk"

    # Step 3: Verify state is cleared across all replicas (e.g. Replica C)
    assert await replica_c_context.get_state() is None
    assert await replica_c_context.get_data() == {}


@pytest.mark.asyncio
async def test_multi_replica_custom_text_prompt():
    """
    Test Replica A receiving photo and Replica B receiving custom text prompt.
    """
    shared_storage = MemoryStorage()
    key = StorageKey(bot_id=123456, chat_id=5002, user_id=9002)

    replica_a_context = FSMContext(storage=shared_storage, key=key)
    replica_b_context = FSMContext(storage=shared_storage, key=key)

    user = User(id=9002, is_bot=False, first_name="Charlie")
    chat = Chat(id=5002, type="private")

    mock_bot = AsyncMock()
    mock_bot.token = "123456:MOCK_TOKEN"
    file_obj = File(file_id="photo_custom_777", file_unique_id="u777", file_path="photos/charlie.jpg")
    mock_bot.get_file = AsyncMock(return_value=file_obj)
    mock_bot.download_file = AsyncMock(return_value=io.BytesIO(b"CHARLIE_RAW_PHOTO_DATA"))
    mock_bot.send_message = AsyncMock(return_value=MagicMock(message_id=102))

    # Replica A receives photo
    photo_msg = MagicMock(spec=Message)
    photo_msg.message_id = 60
    photo_msg.chat = chat
    photo_msg.from_user = user
    photo_msg.photo = [PhotoSize(file_id="photo_custom_777", file_unique_id="u777", width=640, height=640)]
    photo_msg.caption = None
    photo_msg.answer = AsyncMock()

    await handle_photo_upload(
        message=photo_msg,
        state=replica_a_context,
        bot=mock_bot,
        bot_id="image_bot",
    )

    # Replica B receives custom text prompt
    text_msg = MagicMock(spec=Message)
    text_msg.message_id = 61
    text_msg.chat = chat
    text_msg.from_user = user
    text_msg.text = "Paint in watercolor style"
    text_msg.answer = AsyncMock()

    with patch("platform_core.bot.handlers.run_generation_job", new_callable=AsyncMock) as mock_run_gen:
        await handle_custom_text_prompt(
            message=text_msg,
            state=replica_b_context,
            bot=mock_bot,
            bot_id="image_bot",
        )

        assert mock_run_gen.called
        call_kwargs = mock_run_gen.call_args.kwargs
        assert call_kwargs["reference_photo_bytes"] == b"CHARLIE_RAW_PHOTO_DATA"
        assert call_kwargs["prompt"] == "Paint in watercolor style"

    assert await replica_a_context.get_state() is None


@pytest.mark.asyncio
async def test_multi_replica_cancel_action():
    """
    Test cancel action clears shared state across all replicas.
    """
    shared_storage = MemoryStorage()
    key = StorageKey(bot_id=123456, chat_id=5003, user_id=9003)

    replica_a = FSMContext(storage=shared_storage, key=key)
    replica_b = FSMContext(storage=shared_storage, key=key)

    await replica_a.set_state(GenerationStates.waiting_for_photo)
    await replica_a.update_data(selected_preset_id="cyberpunk", reference_file_id="file_abc")

    user = User(id=9003, is_bot=False, first_name="Dan")
    chat = Chat(id=5003, type="private")

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
        state=replica_b,
        bot_id="image_bot",
    )

    assert await replica_a.get_state() is None
    assert await replica_a.get_data() == {}
