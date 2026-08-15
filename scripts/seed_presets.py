#!/usr/bin/env python3
"""
Seed Prompt Presets Script.

Loads AI prompt presets from a YAML or JSON file and populates/updates
the database store (Supabase NoSQL `preset_prompts` JSONB table).

Usage:
    python scripts/seed_presets.py
    python scripts/seed_presets.py --file bots/image_bot/presets.yaml
    python scripts/seed_presets.py --file path/to/custom_presets.json
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path if running as standalone script
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from platform_core.db.nosql import nosql_manager  # noqa: E402
from platform_core.db.supabase_client import db  # noqa: E402
from platform_core.logging_config import setup_logging  # noqa: E402
from platform_core.presets.loader import (  # noqa: E402
    load_presets_from_json_file,
    load_presets_from_yaml_file,
)


async def seed_presets(file_path: Path) -> int:
    """Loads presets from file and saves/upserts each into the database."""
    if not file_path.exists():
        print(f"❌ Error: Presets file not found at: {file_path}")
        return 0

    print(f"📂 Reading presets from: {file_path.resolve()}")

    if file_path.suffix in [".yaml", ".yml"]:
        presets = load_presets_from_yaml_file(file_path)
    elif file_path.suffix == ".json":
        presets = load_presets_from_json_file(file_path)
    else:
        presets = load_presets_from_yaml_file(file_path)

    if not presets:
        print("⚠️ No valid presets found in file.")
        return 0

    print(f"🔍 Found {len(presets)} preset(s) to seed into database.")
    print("─" * 75)

    db_status = "Supabase PostgreSQL" if db.client else "In-Memory Store (DB client offline/unconfigured)"
    print(f"💾 Target Database: {db_status}")
    print("─" * 75)

    count = 0
    for preset in presets:
        try:
            saved = await nosql_manager.save_preset(preset)
            status = "🟢 Active" if saved.is_active else "🔴 Inactive"
            target = saved.target_bot_id or "all"
            print(
                f"  ✅ [{saved.id}] {saved.icon} {saved.title:<28} "
                f"| Category: {saved.category:<15} | Target: {target:<8} | {status}"
            )
            count += 1
        except Exception as e:
            print(f"  ❌ Error saving preset '{preset.id}': {e}")

    print("─" * 75)
    print(f"🎉 Successfully seeded {count}/{len(presets)} presets into the database!\n")
    return count


def main():
    parser = argparse.ArgumentParser(
        description="Fills the database with prompt presets from a YAML or JSON file."
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        default="bots/image_bot/presets.yaml",
        help="Path to presets YAML or JSON file (default: bots/image_bot/presets.yaml)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug logging",
    )

    args = parser.parse_args()

    setup_logging()
    if not args.verbose:
        logging.getLogger("platform_core").setLevel(logging.WARNING)

    file_path = Path(args.file)
    if not file_path.is_absolute():
        file_path = project_root / file_path

    seeded_count = asyncio.run(seed_presets(file_path))
    if seeded_count == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
