import logging
from abc import ABC, abstractmethod
from typing import Optional

from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage

from platform_core.config import settings

logger = logging.getLogger(__name__)


class BaseFSMStorageProvider(ABC):
    """
    Abstract base class for Telegram Bot FSM storage providers.
    Allows easy switching between Redis-backed storage for distributed multi-replica
    deployments and In-Memory storage for local development / testing.
    """

    @abstractmethod
    def create_storage(self) -> BaseStorage:
        """Create and return an initialized aiogram BaseStorage instance."""
        pass


class MemoryFSMStorageProvider(BaseFSMStorageProvider):
    """
    In-memory FSM storage provider.
    Ideal for single-instance local runs, unit testing, and offline environments.
    """

    def create_storage(self) -> BaseStorage:
        logger.info("Initializing MemoryStorage for FSM state.")
        return MemoryStorage()


class RedisFSMStorageProvider(BaseFSMStorageProvider):
    """
    Redis-backed FSM storage provider.
    Enables distributed FSM state across multiple bot replicas with automatic key TTL.
    """

    def __init__(self, redis_url: str, key_prefix: str = "fsm"):
        self.redis_url = redis_url
        self.key_prefix = key_prefix

    def create_storage(self) -> BaseStorage:
        try:
            from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
            import redis.asyncio as aioredis

            logger.info(f"Connecting to Redis at {self.redis_url} for distributed FSM storage (prefix={self.key_prefix})...")
            redis_client = aioredis.from_url(
                self.redis_url,
                decode_responses=False,
            )
            key_builder = DefaultKeyBuilder(prefix=self.key_prefix)
            return RedisStorage(redis=redis_client, key_builder=key_builder)
        except Exception as e:
            logger.warning(
                f"Failed to initialize RedisStorage with URL '{self.redis_url}' ({e}). "
                "Falling back to MemoryStorage."
            )
            return MemoryStorage()


class FSMStorageFactory:
    """
    Factory to resolve and create the appropriate BaseFSMStorageProvider
    based on configuration and runtime arguments.
    """

    @staticmethod
    def get_provider(
        redis_url: Optional[str] = None,
        force_memory: bool = False,
        key_prefix: str = "fsm",
    ) -> BaseFSMStorageProvider:
        """Resolves the storage provider strategy."""
        url = redis_url if redis_url is not None else settings.REDIS_URL
        if not force_memory and url and url.strip():
            return RedisFSMStorageProvider(redis_url=url.strip(), key_prefix=key_prefix)
        return MemoryFSMStorageProvider()

    @classmethod
    def create_storage(
        cls,
        redis_url: Optional[str] = None,
        force_memory: bool = False,
        key_prefix: str = "fsm",
    ) -> BaseStorage:
        """Creates an initialized BaseStorage instance using the resolved provider."""
        provider = cls.get_provider(
            redis_url=redis_url,
            force_memory=force_memory,
            key_prefix=key_prefix,
        )
        return provider.create_storage()


def get_fsm_storage(
    redis_url: Optional[str] = None,
    force_memory: bool = False,
    key_prefix: str = "fsm",
) -> BaseStorage:
    """
    Convenience function to get the configured aiogram FSM storage.
    """
    return FSMStorageFactory.create_storage(
        redis_url=redis_url,
        force_memory=force_memory,
        key_prefix=key_prefix,
    )
