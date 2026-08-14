import logging
import time
from typing import Dict, List, Optional
import httpx
from platform_core.config import settings
from platform_core.db import db, nosql_manager
from platform_core.presets.base import PromptPreset
from platform_core.presets.default_presets import DEFAULT_IMAGE_PRESETS

logger = logging.getLogger(__name__)


class PresetManager:
    """
    Remote & NoSQL Configuration Manager for AI Prompt Presets.
    Supports dynamic remote fetching from:
    1. Supabase NoSQL `preset_prompts` JSONB document store (`nosql_manager`)
    2. Remote JSON HTTP endpoint / GitHub Gist (`PRESETS_REMOTE_URL`)
    3. Local fallback default presets
    Uses TTL caching for ultra-fast response times.
    """

    def __init__(self):
        self._cached_presets: List[PromptPreset] = []
        self._custom_presets: List[PromptPreset] = []
        self._last_fetch_time: float = 0.0

    def register_preset(self, preset: PromptPreset) -> None:
        """Registers a custom preset to the local preset registry."""
        self._custom_presets = [p for p in self._custom_presets if p.id != preset.id]
        self._custom_presets.append(preset)
        self._last_fetch_time = 0  # Invalidate cache

    def register_presets(self, presets: List[PromptPreset]) -> None:
        """Registers a list of custom presets."""
        for p in presets:
            self.register_preset(p)

    def clear_custom_presets(self) -> None:
        """Clears registered custom presets."""
        self._custom_presets.clear()
        self._last_fetch_time = 0

    def _is_cache_valid(self) -> bool:
        return (
            len(self._cached_presets) > 0 and
            (time.time() - self._last_fetch_time) < settings.PRESETS_CACHE_TTL_SECONDS
        )

    async def fetch_presets(self, bot_id: Optional[str] = None, force_reload: bool = False, include_inactive: bool = False) -> List[PromptPreset]:
        """Loads active presets from NoSQL store, remote JSON, or defaults, updating cache."""
        if not force_reload and self._is_cache_valid() and not include_inactive and not bot_id:
            return self._cached_presets

        fetched_presets: List[PromptPreset] = []

        # 1. Try Supabase NoSQL `preset_prompts` JSONB document store
        try:
            nosql_presets = await nosql_manager.get_presets(bot_id=bot_id, include_inactive=include_inactive)
            if nosql_presets:
                fetched_presets = nosql_presets
                logger.info(f"Loaded {len(fetched_presets)} presets from Supabase NoSQL document store.")
        except Exception as e:
            logger.warning(f"Failed to fetch presets from Supabase NoSQL store: {e}")

        # 2. Try Remote JSON URL (if set and NoSQL had no items)
        if not fetched_presets and settings.PRESETS_REMOTE_URL:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(settings.PRESETS_REMOTE_URL)
                    if resp.status_code == 200:
                        data = resp.json()
                        preset_list = data.get("presets", data) if isinstance(data, dict) else data
                        fetched_presets = [PromptPreset(**item) for item in preset_list]
                        logger.info(f"Loaded {len(fetched_presets)} remote presets from JSON URL.")
            except Exception as e:
                logger.warning(f"Failed to fetch presets from PRESETS_REMOTE_URL: {e}")

        # 3. Fallback to default built-in presets
        if not fetched_presets:
            fetched_presets = list(DEFAULT_IMAGE_PRESETS)
            logger.info(f"Using {len(fetched_presets)} built-in default presets.")

        # 4. Merge custom registered presets (custom presets override remote/built-in with matching IDs)
        if self._custom_presets:
            custom_ids = {p.id for p in self._custom_presets}
            fetched_presets = self._custom_presets + [p for p in fetched_presets if p.id not in custom_ids]

        if not include_inactive and not bot_id:
            self._cached_presets = fetched_presets
            self._last_fetch_time = time.time()
        return fetched_presets

    async def get_presets(self, media_type: Optional[str] = None, bot_id: Optional[str] = None, force_reload: bool = False, include_inactive: bool = False) -> List[PromptPreset]:
        """Returns presets filtered by media_type ('image' or 'video') and bot_id."""
        all_presets = await self.fetch_presets(bot_id=bot_id, force_reload=force_reload, include_inactive=include_inactive)
        if media_type:
            return [p for p in all_presets if p.media_type == media_type]
        return all_presets

    async def get_preset_by_id(self, preset_id: str) -> Optional[PromptPreset]:
        """Finds a preset by ID from current cache/remote/NoSQL."""
        preset = await nosql_manager.get_preset_by_id(preset_id)
        if preset:
            return preset
        all_presets = await self.fetch_presets(include_inactive=True)
        for p in all_presets:
            if p.id == preset_id:
                return p
        return None

    async def save_preset(self, preset: PromptPreset) -> PromptPreset:
        """Saves a preset to NoSQL DB and invalidates memory cache."""
        saved = await nosql_manager.save_preset(preset)
        self._last_fetch_time = 0
        return saved

    async def toggle_preset_active(self, preset_id: str, is_active: bool) -> Optional[PromptPreset]:
        """Toggles active state of a preset in NoSQL DB."""
        updated = await nosql_manager.toggle_preset_active(preset_id, is_active)
        self._last_fetch_time = 0
        return updated

    async def delete_preset(self, preset_id: str) -> bool:
        """Deletes a preset from NoSQL DB."""
        res = await nosql_manager.delete_preset(preset_id)
        self._last_fetch_time = 0
        return res

    async def sync_defaults_to_supabase(self) -> int:
        """Seeds built-in default presets into Supabase NoSQL DB table."""
        count = await nosql_manager.seed_default_presets(list(DEFAULT_IMAGE_PRESETS))
        self._last_fetch_time = 0
        return count


# Global PresetManager singleton
preset_manager = PresetManager()
