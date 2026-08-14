import logging
from platform_core.config import settings
from platform_core.generators.base import BaseMediaGenerator
from platform_core.generators.mock import MockMediaGenerator
from platform_core.generators.unified import UnifiedMediaGenerator

logger = logging.getLogger(__name__)


class GeneratorFactory:
    """
    Factory pattern for dynamically obtaining media generator instances.
    """

    @staticmethod
    def get_generator(force_mock: bool = False) -> BaseMediaGenerator:
        """
        Returns an instance of BaseMediaGenerator based on configuration or flags.
        """
        if force_mock or settings.USE_MOCK_GENERATOR:
            logger.info("Using MockMediaGenerator for generation jobs.")
            return MockMediaGenerator()

        logger.info("Using UnifiedMediaGenerator (LiteLLM Gateway) for generation jobs.")
        return UnifiedMediaGenerator()

    @classmethod
    def create_generator(cls, force_mock: bool = False) -> BaseMediaGenerator:
        """
        Alias for get_generator.
        """
        return cls.get_generator(force_mock=force_mock)

