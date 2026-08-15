import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from platform_core.config import settings
from platform_core.presets.base import PromptPreset
from platform_core.presets.default_presets import DEFAULT_IMAGE_PRESETS
from platform_core.presets.loader import (
    load_presets_from_json_file,
    load_presets_from_yaml_file,
)

if TYPE_CHECKING:
    from platform_core.db.nosql import SupabaseNoSQLManager

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
        self._cached_presets: list[PromptPreset] = []
        self._custom_presets: list[PromptPreset] = []
        self._bot_promoted_preset_ids: dict[str, list[str]] = {}
        self._last_fetch_time: float = 0.0

    @property
    def _nosql(self) -> "SupabaseNoSQLManager":
        from platform_core.db.nosql import nosql_manager

        return nosql_manager

    def set_bot_promoted_preset_ids(self, bot_id: str, preset_ids: list[str]) -> None:
        """Sets the list of promoted/priority preset IDs for a specific bot."""
        self._bot_promoted_preset_ids[bot_id] = list(preset_ids)

    def register_bot_promoted_presets(self, bot_id: str, preset_ids: list[str]) -> None:
        """Appends preset IDs to the promoted list for a specific bot."""
        if bot_id not in self._bot_promoted_preset_ids:
            self._bot_promoted_preset_ids[bot_id] = []
        for pid in preset_ids:
            if pid not in self._bot_promoted_preset_ids[bot_id]:
                self._bot_promoted_preset_ids[bot_id].append(pid)

    def register_preset(
        self, preset: PromptPreset, bot_id: str | None = None, promote: bool = False
    ) -> None:
        """Registers a custom preset to the local preset registry and optionally promotes it for a bot."""
        self._custom_presets = [p for p in self._custom_presets if p.id != preset.id]
        self._custom_presets.append(preset)
        if bot_id and promote:
            self.register_bot_promoted_presets(bot_id, [preset.id])
        self._last_fetch_time = 0  # Invalidate cache

    def register_presets(
        self, presets: list[PromptPreset], bot_id: str | None = None, promote: bool = False
    ) -> None:
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
            len(self._cached_presets) > 0
            and (time.time() - self._last_fetch_time) < settings.PRESETS_CACHE_TTL_SECONDS
        )

    async def fetch_presets(
        self, bot_id: str | None = None, force_reload: bool = False, include_inactive: bool = False
    ) -> list[PromptPreset]:
        """Loads active presets exclusively from the database store and custom registry, updating cache."""
        if not force_reload and self._is_cache_valid() and not include_inactive and not bot_id:
            return self._cached_presets

        presets_dict: dict[str, PromptPreset] = {}

        # 1. Supabase NoSQL `preset_prompts` JSONB document store (database)
        try:
            nosql_presets = await self._nosql.get_presets(
                bot_id=bot_id, include_inactive=include_inactive
            )
            if nosql_presets:
                for p in nosql_presets:
                    presets_dict[p.id] = p
                logger.info(f"Loaded {len(nosql_presets)} presets from database store.")
        except Exception as e:
            logger.warning(f"Failed to fetch presets from database store: {e}")

        # 2. Remote JSON HTTP URL (optional fallback/remote sync)
        if settings.PRESETS_REMOTE_URL:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(settings.PRESETS_REMOTE_URL)
                    if resp.status_code == 200:
                        data = resp.json()
                        remote_items = data.get("presets", []) if isinstance(data, dict) else data
                        for item in remote_items:
                            preset = PromptPreset(**item)
                            presets_dict[preset.id] = preset
                        logger.info(f"Loaded {len(remote_items)} presets from remote URL.")
            except Exception as e:
                logger.warning(f"Failed to fetch presets from {settings.PRESETS_REMOTE_URL}: {e}")

        # 3. Custom module registered presets (in-memory programmatic overrides if any)
        for cp in self._custom_presets:
            presets_dict[cp.id] = cp

        result = list(presets_dict.values())
        if not include_inactive:
            result = [p for p in result if p.is_active]

        if not bot_id and not include_inactive:
            self._cached_presets = result
            self._last_fetch_time = time.time()

        return result

    async def get_presets(
        self,
        media_type: str | None = None,
        bot_id: str | None = None,
        include_inactive: bool = False,
        force_reload: bool = False,
    ) -> list[PromptPreset]:
        """
        Retrieves presets filtered by media_type with bot-specific promotions applied.
        Promoted presets for `bot_id` are surfaced at the beginning of the list.
        """
        all_presets = await self.fetch_presets(
            bot_id=bot_id, include_inactive=include_inactive, force_reload=force_reload
        )

        if media_type:
            all_presets = [p for p in all_presets if p.media_type == media_type]

        if bot_id:
            promoted_ids = self._bot_promoted_preset_ids.get(bot_id, [])

            targeted = [p.id for p in all_presets if p.target_bot_id == bot_id]
            for t_id in targeted:
                if t_id not in promoted_ids:
                    promoted_ids.append(t_id)

            if promoted_ids:
                preset_map = {p.id: p for p in all_presets}
                promoted = [preset_map[pid] for pid in promoted_ids if pid in preset_map]
                others = [p for p in all_presets if p.id not in set(promoted_ids)]
                return promoted + others

        return all_presets

    async def get_preset_by_id(self, preset_id: str) -> PromptPreset | None:
        """Finds a preset by ID from current cache/remote/NoSQL."""
        preset = await self._nosql.get_preset_by_id(preset_id)
        if preset:
            return preset
        all_presets = await self.fetch_presets(include_inactive=True)
        for p in all_presets:
            if p.id == preset_id:
                return p
        return None

    async def save_preset(self, preset: PromptPreset) -> PromptPreset:
        """Saves a preset to NoSQL DB and invalidates memory cache."""
        saved = await self._nosql.save_preset(preset)
        self._last_fetch_time = 0
        return saved

    async def toggle_preset_active(self, preset_id: str, is_active: bool) -> PromptPreset | None:
        """Toggles active state of a preset in NoSQL DB."""
        updated = await self._nosql.toggle_preset_active(preset_id, is_active)
        self._last_fetch_time = 0
        return updated

    async def delete_preset(self, preset_id: str) -> bool:
        """Deletes a preset from NoSQL DB."""
        self._custom_presets = [p for p in self._custom_presets if p.id != preset_id]
        res = await self._nosql.delete_preset(preset_id)
        self._last_fetch_time = 0
        return res

    async def seed_presets_from_file(self, file_path: str | Path) -> int:
        """Seeds presets from a YAML or JSON file into the database."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Presets file not found: {path}")

        if path.suffix in [".yaml", ".yml"]:
            presets = load_presets_from_yaml_file(path)
        elif path.suffix == ".json":
            presets = load_presets_from_json_file(path)
        else:
            presets = load_presets_from_yaml_file(path)

        count = 0
        for preset in presets:
            await self._nosql.save_preset(preset)
            count += 1

        self._last_fetch_time = 0
        logger.info(f"Seeded {count} presets from '{path}' into the database.")
        return count

    async def sync_defaults_to_supabase(self, file_path: str | Path | None = None) -> int:
        """Seeds default presets from file or built-ins into Supabase NoSQL DB table."""
        if file_path:
            return await self.seed_presets_from_file(file_path)

        default_yaml = Path("bots/image_bot/presets.yaml")
        if default_yaml.exists():
            return await self.seed_presets_from_file(default_yaml)

        count = await self._nosql.seed_default_presets(list(DEFAULT_IMAGE_PRESETS))
        self._last_fetch_time = 0
        return count


# Global PresetManager singleton
preset_manager = PresetManager()
