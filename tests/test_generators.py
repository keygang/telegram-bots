from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from platform_core.config import settings
from platform_core.generators import (
    GenerationRequest,
    GenerationStatus,
    GeneratorFactory,
    MockMediaGenerator,
    UnifiedMediaGenerator,
)


@pytest.mark.asyncio
async def test_mock_generator_image():
    generator = GeneratorFactory.get_generator(force_mock=True)
    assert isinstance(generator, MockMediaGenerator)

    req = GenerationRequest(prompt="Cyberpunk warrior in neon city", media_type="image")
    res = await generator.generate(req)

    assert res.status == GenerationStatus.SUCCESS
    assert len(res.media_urls) == 1
    assert res.media_urls[0].startswith("file://")
    assert res.duration_ms >= 0


@pytest.mark.asyncio
async def test_unified_generator_initialization():
    unified_gen = UnifiedMediaGenerator()
    assert unified_gen is not None


@pytest.mark.asyncio
async def test_unified_generator_openrouter():
    unified_gen = UnifiedMediaGenerator()

    mock_item = MagicMock()
    mock_item.url = "https://openrouter.ai/generated_image.png"
    mock_response = MagicMock()
    mock_response.data = [mock_item]

    with (
        patch("litellm.aimage_generation", new_callable=AsyncMock) as mock_aimage_gen,
        patch.object(settings, "OPENROUTER_API_KEY", "test_key"),
    ):
        mock_aimage_gen.return_value = mock_response

        req = GenerationRequest(
            prompt="A majestic lion on a cliff",
            model_name="openrouter/google/gemini-2.5-flash-image",
            width=1024,
            height=1024,
        )
        res = await unified_gen.generate(req)

        assert res.status == GenerationStatus.SUCCESS
        assert res.media_urls == ["https://openrouter.ai/generated_image.png"]
        assert res.metadata["provider"] == "openrouter"
        assert res.metadata["model"] == "openrouter/google/gemini-2.5-flash-image"

        mock_aimage_gen.assert_called_once_with(
            model="openrouter/google/gemini-2.5-flash-image",
            prompt="A majestic lion on a cliff",
            n=1,
            size="1024x1024",
            api_key="test_key",
        )


@pytest.mark.asyncio
async def test_unified_generator_auto_prefixes_openrouter():
    unified_gen = UnifiedMediaGenerator()

    mock_item = MagicMock()
    mock_item.url = "https://openrouter.ai/image.png"
    mock_response = MagicMock()
    mock_response.data = [mock_item]

    with (
        patch("litellm.aimage_generation", new_callable=AsyncMock) as mock_aimage_gen,
        patch.object(settings, "OPENROUTER_API_KEY", "test_key"),
    ):
        mock_aimage_gen.return_value = mock_response

        req = GenerationRequest(
            prompt="Futuristic car",
            model_name="google/imagen-3-fast",
        )
        res = await unified_gen.generate(req)

        assert res.status == GenerationStatus.SUCCESS
        assert res.metadata["model"] == "openrouter/google/imagen-3-fast"
        mock_aimage_gen.assert_called_once_with(
            model="openrouter/google/imagen-3-fast",
            prompt="Futuristic car",
            n=1,
            size="1024x1024",
            api_key="test_key",
        )


@pytest.mark.asyncio
async def test_unified_generator_chat_completion_fallback():
    unified_gen = UnifiedMediaGenerator()

    mock_msg = MagicMock()
    mock_msg.images = [
        {
            "image_url": {
                "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            }
        }
    ]
    mock_msg.content = "Here is your generated image"
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with (
        patch("litellm.aimage_generation", side_effect=RuntimeError("Endpoint not supported")),
        patch("litellm.acompletion", return_value=mock_response) as mock_acompletion,
    ):
        req = GenerationRequest(
            prompt="Heroic Greek warrior",
            model_name="google/gemini-2.5-flash-image",
        )
        res = await unified_gen.generate(req)

        assert res.status == GenerationStatus.SUCCESS
        assert len(res.media_urls) == 1
        assert res.media_urls[0].startswith("file://")
        assert res.metadata["model"] == "openrouter/google/gemini-2.5-flash-image"
        mock_acompletion.assert_called_once()


def test_media_storage_manager(tmp_path):
    from aiogram.types import FSInputFile, URLInputFile

    from platform_core.storage.media import MediaStorageManager

    storage = MediaStorageManager(base_dir=tmp_path)
    sample_data = b"fake_jpeg_image_binary_data"
    file_url = storage.save_bytes(sample_data, extension="jpg")

    assert file_url.startswith("file://")

    input_file = MediaStorageManager.get_input_file(file_url)
    assert isinstance(input_file, FSInputFile)

    web_input = MediaStorageManager.get_input_file("https://example.com/image.png")
    assert isinstance(web_input, URLInputFile)
