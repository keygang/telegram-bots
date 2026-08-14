import asyncio
import base64
import logging
import os
import time
from typing import Any, Dict, List, Optional
import litellm
from platform_core.config import settings
from platform_core.generators.base import BaseMediaGenerator, GenerationRequest, GenerationResponse

logger = logging.getLogger(__name__)

# Silence verbose LiteLLM logging in dev
litellm.suppress_debug_info = True


class UnifiedMediaGenerator(BaseMediaGenerator):
    """
    Unified Multi-Provider Media Generator powered by LiteLLM gateway.
    Primary image generation provider is OpenRouter via LiteLLM.
    Routes requests to OpenRouter (FLUX, Imagen 3, Stable Diffusion, Recraft),
    OpenAI (DALL-E 3), Fal.ai, or custom LiteLLM proxy endpoints.
    """

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        start_time = time.time()
        model_name = request.model_name.strip()
        lower_model = model_name.lower()

        # Determine target model for LiteLLM / OpenRouter
        if lower_model.startswith("openrouter/"):
            target_model = model_name
        else:
            # Default provider for un-prefixed models is OpenRouter via LiteLLM
            target_model = f"openrouter/{model_name}"

        # Resolve OpenRouter API Key
        openrouter_api_key = settings.OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY")

        try:
            gen_kwargs: Dict[str, Any] = {
                "model": target_model,
                "prompt": request.prompt,
                "n": 1,
                "size": f"{request.width}x{request.height}",
            }

            if target_model.lower().startswith("openrouter/") and openrouter_api_key:
                gen_kwargs["api_key"] = openrouter_api_key

            if request.extra_params:
                gen_kwargs.update(request.extra_params)

            # Execute unified image generation via LiteLLM API
            response = await litellm.aimage_generation(**gen_kwargs)

            urls: List[str] = []
            if hasattr(response, "data") and response.data:
                for item in response.data:
                    if hasattr(item, "url") and item.url:
                        urls.append(item.url)
                    elif hasattr(item, "b64_json") and item.b64_json:
                        b64_data = base64.b64decode(item.b64_json)
                        duration_ms = int((time.time() - start_time) * 1000)
                        return GenerationResponse(
                            status="success",
                            media_bytes=b64_data,
                            duration_ms=duration_ms,
                            metadata={"provider": "openrouter", "model": target_model}
                        )

            duration_ms = int((time.time() - start_time) * 1000)
            return GenerationResponse(
                status="success" if urls else "failed",
                media_urls=urls,
                duration_ms=duration_ms,
                metadata={"provider": "openrouter", "model": target_model}
            )

        except Exception as e:
            logger.error(
                f"LiteLLM image generation failed for model {target_model}: {e}",
                exc_info=True,
            )
            duration_ms = int((time.time() - start_time) * 1000)
            return GenerationResponse(
                status="failed",
                error_message=str(e),
                duration_ms=duration_ms,
                metadata={"provider": "openrouter", "model": target_model},
            )
