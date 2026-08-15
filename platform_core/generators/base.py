from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

DEFAULT_AVAILABLE_MODELS: list[str] = [
    "google/gemini-2.5-flash-image",
    "black-forest-labs/flux-1.1-pro",
    "openai/dall-e-3",
    "stabilityai/stable-diffusion-3.5-large",
    "recraft-ai/recraft-v3",
]


class GenerationRequest(BaseModel):
    """Encapsulates all parameters for an image or video generation job."""

    prompt: str
    negative_prompt: str | None = None
    model_name: str = "google/gemini-2.5-flash-image"
    reference_photo_bytes: bytes | None = None
    reference_photo_url: str | None = None
    media_type: str = "image"  # "image" or "video"
    width: int = 1024
    height: int = 1024
    extra_params: dict[str, Any] = Field(default_factory=dict)


class GenerationResponse(BaseModel):
    """Standardized response from any media generation provider."""

    status: str = "success"  # "success" or "failed"
    media_urls: list[str] = Field(default_factory=list)
    media_bytes: bytes | None = None
    duration_ms: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseMediaGenerator(ABC):
    """Abstract interface for AI media generators (Replicate, Fal.ai, Mock, etc.)."""

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Execute media generation asynchronously."""
        pass
