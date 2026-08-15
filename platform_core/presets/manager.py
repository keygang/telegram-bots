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
        self._bot_promoted_preset_ids: Dict[str, List[str]] = {}
        self._last_fetch_time: float = 0.0

    def set_bot_promoted_preset_ids(self, bot_id: str, preset_ids: List[str]) -> None:
        """Sets the list of promoted/priority preset IDs for a specific bot."""
        self._bot_promoted_preset_ids[bot_id] = list(preset_ids)

    def register_bot_promoted_presets(self, bot_id: str, preset_ids: List[str]) -> None:
        """Appends preset IDs to the promoted list for a specific bot."""
        if bot_id not in self._bot_promoted_preset_ids:
            self._bot_promoted_preset_ids[bot_id] = []
        for pid in preset_ids:
            if pid not in self._bot_promoted_preset_ids[bot_id]:
                self._bot_promoted_preset_ids[bot_id].append(pid)

    def register_preset(self, preset: PromptPreset, bot_id: Optional[str] = None, promote: bool = False) -> None:
        """Registers a custom preset to the local preset registry and optionally promotes it for a bot."""
        self._custom_presets = [p for p in self._custom_presets if p.id != preset.id]
        self._custom_presets.append(preset)
        if bot_id and promote:
            self.register_bot_promoted_presets(bot_id, [preset.id])
        self._last_fetch_time = 0  # Invalidate cache

    def register_presets(self, presets: List[PromptPreset], bot_id: Optional[str] = None, promote: bool = False) -> None:
        """Registers a list of custom presets and optionally promotes them for a bot."""
        for p in presets:
            self.register_preset(p, bot_id=bot_id, promote=promote)

    def clear_custom_presets(self) -> None:
        """Clears registered custom presets and promoted mappings."""
        self._custom_presets.clear()
        self._bot_promoted_preset_ids.clear()
        self._last_fetch_time = 0

    def _is_cache_valid(self) -> bool:
        return (
            len(self._cached_presets) > 0 and
            (time.time() - self._last_fetch_time) < settings.PRESETS_CACHE_TTL_SECONDS
        )

    async def fetch_presets(self, bot_id: Optional[str] = None, force_reload: bool = False, include_inactive: bool = False) -> List[PromptPreset]:
        """Loads active presets from NoSQL store, remote JSON, defaults, and custom registry, updating cache."""
        if not force_reload and self._is_cache_valid() and not include_inactive and not bot_id:
            return self._cached_presets

        # 1. Base built-in presets
        presets_dict: Dict[str, PromptPreset] = {p.id: p for p in DEFAULT_IMAGE_PRESETS}

        # 2. Supabase NoSQL `preset_prompts` JSONB document store
        try:
            nosql_presets = await nosql_manager.get_presets(bot_id=bot_id, include_inactive=include_inactive)
            if nosql_presets:
                for p in nosql_presets:
                    presets_dict[p.id] = p
                logger.info(f"Loaded {len(nosql_presets)} presets from Supabase NoSQL document store.")
        except Exception as e:
            logger.warning(f"Failed to fetch presets from Supabase NoSQL store: {e}")

        # 3. Remote JSON URL (if set)
        if settings.PRESETS_REMOTE_URL:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(settings.PRESETS_REMOTE_URL)
                    if resp.status_code == 200:
                        data = resp.json()
                        preset_list = data.get("presets", data) if isinstance(data, dict) else data
                        for item in preset_list:
                            p = PromptPreset(**item)
                            presets_dict[p.id] = p
                        logger.info(f"Loaded remote presets from JSON URL.")
            except Exception as e:
                logger.warning(f"Failed to fetch presets from PRESETS_REMOTE_URL: {e}")

        # 4. Merge custom registered presets
        if self._custom_presets:
            for p in self._custom_presets:
                presets_dict[p.id] = p

        fetched_presets = list(presets_dict.values())

        if not include_inactive:
            fetched_presets = [p for p in fetched_presets if p.is_active]

        if not include_inactive and not bot_id:
            self._cached_presets = fetched_presets
            self._last_fetch_time = time.time()
        return fetched_presets

    async def get_presets(self, media_type: Optional[str] = None, bot_id: Optional[str] = None, force_reload: bool = False, include_inactive: bool = False) -> List[PromptPreset]:
        """
        Returns common presets filtered by media_type ('image' or 'video').
        If bot_id is provided, presets promoted for that bot (or targeted to it)
        appear at the beginning of the returned list.
        """
        all_presets = await self.fetch_presets(bot_id=bot_id, force_reload=force_reload, include_inactive=include_inactive)
        if media_type:
            all_presets = [p for p in all_presets if p.media_type == media_type]

        if bot_id:
            promoted_ids = list(self._bot_promoted_preset_ids.get(bot_id, []))
            # Also include presets explicitly marked with target_bot_id == bot_id
            for p in all_presets:
                if p.target_bot_id == bot_id and p.id not in promoted_ids:
                    promoted_ids.append(p.id)

            if promoted_ids:
                preset_map = {p.id: p for p in all_presets}
                promoted = [preset_map[pid] for pid in promoted_ids if pid in preset_map]
                others = [p for p in all_presets if p.id not in set(promoted_ids)]
                return promoted + others

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
        self._custom_presets = [p for p in self._custom_presets if p.id != preset_id]
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
