import json
import logging
from pathlib import Path
from typing import Any

import yaml

from platform_core.presets.base import PresetCollection, PromptPreset

logger = logging.getLogger(__name__)


def load_presets_from_dict(
    data: dict[str, Any] | list[dict[str, Any]] | PresetCollection,
) -> list[PromptPreset]:
    """
    Parses a dictionary, list of dictionaries, or PresetCollection into a list of PromptPreset instances.
    Supports top-level dict with key 'presets' or direct list.
    """
    if isinstance(data, PresetCollection):
        return list(data.presets)

    if isinstance(data, dict):
        if "presets" in data:
            try:
                collection = PresetCollection.model_validate(data)
                return collection.presets
            except Exception as e:
                logger.debug(f"PresetCollection validation fallback: {e}")
        items = data.get("presets", [])
    elif isinstance(data, list):
        items = data
    else:
        logger.warning(f"Unexpected data type for presets loading: {type(data)}")
        return []

    presets: list[PromptPreset] = []
    for item in items:
        try:
            if isinstance(item, PromptPreset):
                presets.append(item)
            elif isinstance(item, dict):
                presets.append(PromptPreset.model_validate(item))
        except Exception as e:
            logger.error(f"Failed to parse PromptPreset item {item}: {e}")

    return presets


def load_presets_from_yaml_string(yaml_str: str) -> list[PromptPreset]:
    """Parses a YAML string into a list of PromptPreset objects."""
    data = yaml.safe_load(yaml_str) or {}
    return load_presets_from_dict(data)


def load_presets_from_yaml_file(file_path: str | Path) -> list[PromptPreset]:
    """Loads presets from a YAML file path."""
    path = Path(file_path)
    if not path.exists():
        logger.error(f"Presets YAML file not found: {path}")
        return []

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        presets = load_presets_from_dict(data)
        logger.info(f"Loaded {len(presets)} presets from YAML file: {path}")
        return presets
    except Exception as e:
        logger.error(f"Error reading presets YAML file {path}: {e}")
        return []


def load_presets_from_json_file(file_path: str | Path) -> list[PromptPreset]:
    """Loads presets from a JSON file path."""
    path = Path(file_path)
    if not path.exists():
        logger.error(f"Presets JSON file not found: {path}")
        return []

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        presets = load_presets_from_dict(data)
        logger.info(f"Loaded {len(presets)} presets from JSON file: {path}")
        return presets
    except Exception as e:
        logger.error(f"Error reading presets JSON file {path}: {e}")
        return []
