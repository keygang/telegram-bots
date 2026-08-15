import base64
import logging
import os
import re
import time
from typing import Any

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
    Routes requests to OpenRouter (FLUX, Imagen 3, Stable Diffusion, Recraft, Gemini),
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

        # 1. Try standard aimage_generation
        try:
            gen_kwargs: dict[str, Any] = {
                "model": target_model,
                "prompt": request.prompt,
                "n": 1,
                "size": f"{request.width}x{request.height}",
            }

            if target_model.lower().startswith("openrouter/") and openrouter_api_key:
                gen_kwargs["api_key"] = openrouter_api_key

            if request.reference_photo_bytes:
                gen_kwargs["image"] = request.reference_photo_bytes

            if request.extra_params:
                gen_kwargs.update(request.extra_params)

            response = await litellm.aimage_generation(**gen_kwargs)

            urls: list[str] = []
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
                            metadata={"provider": "openrouter", "model": target_model},
                        )

            if urls:
                duration_ms = int((time.time() - start_time) * 1000)
                return GenerationResponse(
                    status="success",
                    media_urls=urls,
                    duration_ms=duration_ms,
                    metadata={"provider": "openrouter", "model": target_model},
                )

        except Exception as e:
            logger.info(
                f"aimage_generation direct call failed for {target_model} ({e}), trying chat completion fallback..."
            )

        # 2. Fallback to acompletion for multimodal/chat-based image models (e.g. OpenRouter Gemini)
        try:
            if request.reference_photo_bytes:
                ref_b64 = base64.b64encode(request.reference_photo_bytes).decode("utf-8")
                user_content: Any = [
                    {
                        "type": "text",
                        "text": f"Transform the person/subject in the provided reference photo according to this description: {request.prompt}",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{ref_b64}"},
                    },
                ]
            else:
                user_content = f"Generate an image based on this description: {request.prompt}"

            comp_kwargs: dict[str, Any] = {
                "model": target_model,
                "messages": [{"role": "user", "content": user_content}],
            }
            if target_model.lower().startswith("openrouter/") and openrouter_api_key:
                comp_kwargs["api_key"] = openrouter_api_key

            comp = await litellm.acompletion(**comp_kwargs)
            if comp.choices and comp.choices[0].message:
                msg = comp.choices[0].message

                # Check message.images
                images = getattr(msg, "images", None) or []
                if images:
                    for img_item in images:
                        url = None
                        if isinstance(img_item, dict):
                            url = img_item.get("image_url", {}).get("url") or img_item.get("url")
                        elif hasattr(img_item, "image_url"):
                            url = getattr(img_item.image_url, "url", None)
                        if url:
                            if url.startswith("data:image/"):
                                b64_str = url.split(",", 1)[1]
                                duration_ms = int((time.time() - start_time) * 1000)
                                return GenerationResponse(
                                    status="success",
                                    media_bytes=base64.b64decode(b64_str),
                                    duration_ms=duration_ms,
                                    metadata={"provider": "openrouter", "model": target_model},
                                )
                            elif url.startswith("http"):
                                duration_ms = int((time.time() - start_time) * 1000)
                                return GenerationResponse(
                                    status="success",
                                    media_urls=[url],
                                    duration_ms=duration_ms,
                                    metadata={"provider": "openrouter", "model": target_model},
                                )

                # Check message.content for base64 or HTTP URL
                content = msg.content or ""
                match = re.search(r"data:image/[^;]+;base64,([A-Za-z0-9+/=]+)", content)
                if match:
                    duration_ms = int((time.time() - start_time) * 1000)
                    return GenerationResponse(
                        status="success",
                        media_bytes=base64.b64decode(match.group(1)),
                        duration_ms=duration_ms,
                        metadata={"provider": "openrouter", "model": target_model},
                    )

                url_match = re.search(r"https?://[^\s\"\')]+\.(?:png|jpg|jpeg|webp)", content)
                if url_match:
                    duration_ms = int((time.time() - start_time) * 1000)
                    return GenerationResponse(
                        status="success",
                        media_urls=[url_match.group(0)],
                        duration_ms=duration_ms,
                        metadata={"provider": "openrouter", "model": target_model},
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

        duration_ms = int((time.time() - start_time) * 1000)
        return GenerationResponse(
            status="failed",
            error_message=f"No image data returned from provider for model '{target_model}'",
            duration_ms=duration_ms,
            metadata={"provider": "openrouter", "model": target_model},
        )
