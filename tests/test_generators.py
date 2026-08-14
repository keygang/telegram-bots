import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from platform_core.generators import GeneratorFactory, GenerationRequest, MockMediaGenerator, UnifiedMediaGenerator
from platform_core.config import settings


@pytest.mark.asyncio
async def test_mock_generator_image():
    generator = GeneratorFactory.get_generator(force_mock=True)
    assert isinstance(generator, MockMediaGenerator)

    req = GenerationRequest(
        prompt="Cyberpunk warrior in neon city",
        media_type="image"
    )
    res = await generator.generate(req)

    assert res.status == "success"
    assert res.media_bytes is not None
    assert len(res.media_bytes) > 0
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

    with patch("litellm.aimage_generation", new_callable=AsyncMock) as mock_aimage_gen, \
         patch.object(settings, "OPENROUTER_API_KEY", "test_key"):
        mock_aimage_gen.return_value = mock_response

        req = GenerationRequest(
            prompt="A majestic lion on a cliff",
            model_name="openrouter/google/gemini-2.5-flash-image",
            width=1024,
            height=1024,
        )
        res = await unified_gen.generate(req)

        assert res.status == "success"
        assert res.media_urls == ["https://openrouter.ai/generated_image.png"]
        assert res.metadata["provider"] == "openrouter"
        assert res.metadata["model"] == "openrouter/google/gemini-2.5-flash-image"

        mock_aimage_gen.assert_called_once_with(
            model="openrouter/google/gemini-2.5-flash-image",
            prompt="A majestic lion on a cliff",
            n=1,
            size="1024x1024",
            api_key="test_key"
        )


@pytest.mark.asyncio
async def test_unified_generator_auto_prefixes_openrouter():
    unified_gen = UnifiedMediaGenerator()

    mock_item = MagicMock()
    mock_item.url = "https://openrouter.ai/image.png"
    mock_response = MagicMock()
    mock_response.data = [mock_item]

    with patch("litellm.aimage_generation", new_callable=AsyncMock) as mock_aimage_gen, \
         patch.object(settings, "OPENROUTER_API_KEY", "test_key"):
        mock_aimage_gen.return_value = mock_response

        req = GenerationRequest(
            prompt="Futuristic car",
            model_name="google/imagen-3-fast",
        )
        res = await unified_gen.generate(req)

        assert res.status == "success"
        assert res.metadata["model"] == "openrouter/google/imagen-3-fast"
        mock_aimage_gen.assert_called_once_with(
            model="openrouter/google/imagen-3-fast",
            prompt="Futuristic car",
            n=1,
            size="1024x1024",
            api_key="test_key"
        )


@pytest.mark.asyncio
async def test_unified_generator_chat_completion_fallback():
    unified_gen = UnifiedMediaGenerator()

    mock_msg = MagicMock()
    mock_msg.images = [{"image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="}}]
    mock_msg.content = "Here is your generated image"
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("litellm.aimage_generation", side_effect=RuntimeError("Endpoint not supported")), \
         patch("litellm.acompletion", return_value=mock_response) as mock_acompletion:

        req = GenerationRequest(
            prompt="Heroic Greek warrior",
            model_name="google/gemini-2.5-flash-image",
        )
        res = await unified_gen.generate(req)

        assert res.status == "success"
        assert res.media_bytes is not None
        assert res.metadata["model"] == "openrouter/google/gemini-2.5-flash-image"
        mock_acompletion.assert_called_once()



