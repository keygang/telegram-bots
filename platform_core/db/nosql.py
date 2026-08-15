import asyncio
import logging
from typing import Any

from platform_core.db.supabase_client import db
from platform_core.presets.base import PromptPreset

logger = logging.getLogger(__name__)


class SupabaseNoSQLManager:
    """
    NoSQL Document Repository powered by Supabase PostgreSQL (JSONB column `data`).
    Provides full CRUD operations for schemaless presets with automatic
    in-memory document fallback when Supabase is offline or unconfigured.
    All synchronous PostgREST client operations are dispatched to worker threads
    via asyncio.to_thread to prevent blocking the asyncio event loop.
    """

    def __init__(self):
        self._in_memory_presets: dict[str, PromptPreset] = {}

    def _parse_preset_from_row(self, row: dict[str, Any]) -> PromptPreset:
        """Parses a Supabase row (with JSONB data column) into a PromptPreset object."""
        data_doc = row.get("data") or {}
        if isinstance(data_doc, dict):
            # Combine root columns and JSONB document fields
            merged = {**data_doc, **row}
            # Remove JSONB raw field key if present
            merged.pop("data", None)
            return PromptPreset(**merged)
        return PromptPreset(**row)

    async def get_presets(
        self,
        bot_id: str | None = None,
        media_type: str | None = None,
        include_inactive: bool = False,
    ) -> list[PromptPreset]:
        """Retrieves presets from Supabase NoSQL store or in-memory fallback."""
        presets: list[PromptPreset] = []

        if db.client:
            try:

                def _fetch():
                    query = db.client.table("preset_prompts").select("*")
                    if not include_inactive:
                        query = query.eq("is_active", True)
                    return query.execute()

                res = await asyncio.to_thread(_fetch)

                if res.data:
                    for row in res.data:
                        preset = self._parse_preset_from_row(row)
                        presets.append(preset)
                    logger.info(f"Retrieved {len(presets)} presets from Supabase NoSQL store.")
            except Exception as e:
                logger.warning(
                    f"Failed to fetch presets from Supabase NoSQL store ({e}). Using in-memory store."
                )

        if not presets and self._in_memory_presets:
            presets = list(self._in_memory_presets.values())

        # Filtering logic
        if not include_inactive:
            presets = [p for p in presets if p.is_active]

        if media_type:
            presets = [p for p in presets if p.media_type == media_type]

        if bot_id:
            # Reorder so presets specifically targeted for this bot appear at the beginning (promoted)
            targeted = [p for p in presets if p.target_bot_id == bot_id]
            others = [p for p in presets if p.target_bot_id != bot_id]
            presets = targeted + others

        return presets

    async def get_preset_by_id(self, preset_id: str) -> PromptPreset | None:
        """Fetches a single preset by ID."""
        if db.client:
            try:
                res = await asyncio.to_thread(
                    lambda: (
                        db.client.table("preset_prompts").select("*").eq("id", preset_id).execute()
                    )
                )
                if res.data and len(res.data) > 0:
                    return self._parse_preset_from_row(res.data[0])
            except Exception as e:
                logger.warning(f"Error fetching preset {preset_id} from Supabase: {e}")

        return self._in_memory_presets.get(preset_id)

    async def save_preset(self, preset: PromptPreset) -> PromptPreset:
        """Saves or updates a preset document in Supabase NoSQL store."""
        doc = preset.model_dump(mode="json")
        self._in_memory_presets[preset.id] = preset

        if db.client:
            try:
                row_data = {
                    "id": preset.id,
                    "title": preset.title,
                    "description": preset.description,
                    "icon": preset.icon,
                    "prompt_template": preset.prompt_template,
                    "category": preset.category,
                    "media_type": preset.media_type,
                    "default_model": preset.default_model,
                    "supports_reference_photo": preset.supports_reference_photo,
                    "is_active": preset.is_active,
                    "target_bot_id": preset.target_bot_id or "all",
                    "data": doc,  # Full document stored as JSONB
                }
                await asyncio.to_thread(
                    lambda: db.client.table("preset_prompts").upsert(row_data).execute()
                )
                logger.info(f"Saved preset '{preset.id}' into Supabase NoSQL store.")
            except Exception as e:
                logger.warning(
                    f"Could not sync preset '{preset.id}' to Supabase ({e}). Saved to in-memory store."
                )

        return preset

    async def update_preset(self, preset_id: str, updates: dict[str, Any]) -> PromptPreset | None:
        """Updates specific fields of an existing preset document."""
        existing = await self.get_preset_by_id(preset_id)
        if not existing:
            return None

        current_dict = existing.model_dump(mode="json")
        current_dict.update(updates)
        updated_preset = PromptPreset(**current_dict)
        return await self.save_preset(updated_preset)

    async def toggle_preset_active(self, preset_id: str, is_active: bool) -> PromptPreset | None:
        """Toggles the is_active status of a preset."""
        return await self.update_preset(preset_id, {"is_active": is_active})

    async def delete_preset(self, preset_id: str) -> bool:
        """Deletes a preset document from Supabase NoSQL store."""
        deleted_in_memory = False
        if preset_id in self._in_memory_presets:
            del self._in_memory_presets[preset_id]
            deleted_in_memory = True

        if db.client:
            try:
                await asyncio.to_thread(
                    lambda: db.client.table("preset_prompts").delete().eq("id", preset_id).execute()
                )
                logger.info(f"Deleted preset '{preset_id}' from Supabase NoSQL store.")
                return True
            except Exception as e:
                logger.warning(
                    f"Could not delete preset '{preset_id}' from Supabase ({e}). Deleted from in-memory store."
                )

        return deleted_in_memory or True

    async def seed_default_presets(self, default_presets: list[PromptPreset]) -> int:
        """Seeds built-in default presets into Supabase NoSQL store if empty."""
        existing = await self.get_presets(include_inactive=True)
        count = 0
        for preset in default_presets:
            if not any(p.id == preset.id for p in existing):
                await self.save_preset(preset)
                count += 1
        logger.info(f"Seeded {count} new default presets into NoSQL database store.")
        return count


# Singleton instance
nosql_manager = SupabaseNoSQLManager()
