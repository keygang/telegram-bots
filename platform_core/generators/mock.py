import asyncio
import io
import time
from PIL import Image, ImageDraw, ImageFont
from platform_core.generators.base import BaseMediaGenerator, GenerationRequest, GenerationResponse


class MockMediaGenerator(BaseMediaGenerator):
    """
    Mock AI Generator for local testing and offline development.
    Renders styled placeholder images with request details embedded.
    """

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        start_time = time.time()
        # Simulate short processing delay
        await asyncio.sleep(0.5)

        # Generate a stylized PIL image for photo requests
        img = Image.new("RGB", (request.width, request.height), color=(20, 25, 40))
        draw = ImageDraw.Draw(img)

        # Draw decorative background elements
        draw.rectangle([(20, 20), (request.width - 20, request.height - 20)], outline=(100, 150, 255), width=4)
        draw.ellipse([(request.width // 4, request.height // 4), (3 * request.width // 4, 3 * request.height // 4)], outline=(255, 100, 200), width=2)

        # Text banner
        title_text = "AI GENERATED MOCK PHOTO"
        prompt_text = f"Prompt: {request.prompt[:60]}..."
        model_text = f"Model: {request.model_name}"
        ref_text = "Photo Reference: YES" if request.reference_photo_bytes else "Photo Reference: NO"

        draw.text((50, 80), title_text, fill=(255, 255, 255))
        draw.text((50, 140), prompt_text, fill=(200, 220, 255))
        draw.text((50, 180), model_text, fill=(180, 180, 180))
        draw.text((50, 220), ref_text, fill=(150, 255, 150))

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        image_bytes = buffer.getvalue()

        duration_ms = int((time.time() - start_time) * 1000)

        return GenerationResponse(
            status="success",
            media_bytes=image_bytes,
            media_urls=[],
            duration_ms=duration_ms,
            metadata={
                "provider": "mock",
                "type": "image",
                "prompt": request.prompt,
                "has_reference_photo": bool(request.reference_photo_bytes),
            }
        )
