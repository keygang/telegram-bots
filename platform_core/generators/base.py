from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GenerationRequest(BaseModel):
    """Encapsulates all parameters for an image or video generation job."""
    prompt: str
    negative_prompt: Optional[str] = None
    model_name: str = "google/gemini-2.5-flash-image"
    reference_photo_bytes: Optional[bytes] = None
    reference_photo_url: Optional[str] = None
    media_type: str = "image"  # "image" or "video"
    width: int = 1024
    height: int = 1024
    extra_params: Dict[str, Any] = Field(default_factory=dict)


class GenerationResponse(BaseModel):
    """Standardized response from any media generation provider."""
    status: str = "success"  # "success" or "failed"
    media_urls: List[str] = Field(default_factory=list)
    media_bytes: Optional[bytes] = None
    duration_ms: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseMediaGenerator(ABC):
    """Abstract interface for AI media generators (Replicate, Fal.ai, Mock, etc.)."""

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Execute media generation asynchronously."""
        pass
