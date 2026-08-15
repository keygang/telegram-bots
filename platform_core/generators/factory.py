import logging
from collections.abc import Callable

from platform_core.config import settings
from platform_core.generators.base import BaseMediaGenerator
from platform_core.generators.mock import MockMediaGenerator
from platform_core.generators.unified import UnifiedMediaGenerator

logger = logging.getLogger(__name__)


class GeneratorFactory:
    """
    Factory pattern for dynamically obtaining and registering media generator instances.
    Enables zero-friction switching between AI generation providers (LiteLLM, Mock, ComfyUI, Fal, etc.).
    """

    _registry: dict[str, type[BaseMediaGenerator] | Callable[[], BaseMediaGenerator]] = {
        "unified": UnifiedMediaGenerator,
        "litellm": UnifiedMediaGenerator,
        "mock": MockMediaGenerator,
    }

    @classmethod
    def register_generator(
        cls,
        name: str,
        generator: type[BaseMediaGenerator] | Callable[[], BaseMediaGenerator],
    ) -> None:
        """Registers a new media generator backend provider."""
        cls._registry[name.lower()] = generator
        logger.info(f"Registered custom media generator provider: '{name}'")

    @classmethod
    def get_generator(
        cls, provider: str | None = None, force_mock: bool = False
    ) -> BaseMediaGenerator:
        """
        Returns an instance of BaseMediaGenerator based on configuration or explicit provider name.
        """
        if force_mock or settings.USE_MOCK_GENERATOR:
            logger.info("Using MockMediaGenerator for generation jobs.")
            return MockMediaGenerator()

        target_provider = (provider or "unified").lower()
        if target_provider in cls._registry:
            generator_cls_or_factory = cls._registry[target_provider]
            return generator_cls_or_factory()

        logger.info("Defaulting to UnifiedMediaGenerator (LiteLLM Gateway) for generation jobs.")
        return UnifiedMediaGenerator()

    @classmethod
    def create_generator(
        cls, provider: str | None = None, force_mock: bool = False
    ) -> BaseMediaGenerator:
        """Alias for get_generator."""
        return cls.get_generator(provider=provider, force_mock=force_mock)
