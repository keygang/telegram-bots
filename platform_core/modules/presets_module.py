from pathlib import Path
from typing import Any

from platform_core.modules.base import BaseBotModule, ModuleInfo
from platform_core.presets.base import PromptPreset
from platform_core.presets.loader import (
    load_presets_from_dict,
    load_presets_from_json_file,
    load_presets_from_yaml_file,
    load_presets_from_yaml_string,
)


class PresetsModule(BaseBotModule):
    """
    Pluggable Presets Module.
    Allows easy loading and dynamic registration of prompt presets from
    YAML files, JSON files, dictionaries, or raw YAML strings.
    """

    name: str = "presets"

    def __init__(self, presets: list[PromptPreset]):
        self._presets = presets

    def get_presets(self) -> list[PromptPreset]:
        return self._presets

    @classmethod
    def from_yaml_file(cls, file_path: str | Path) -> "PresetsModule":
        """Instantiates PresetsModule by loading presets from a YAML file."""
        loaded = load_presets_from_yaml_file(file_path)
        return cls(presets=loaded)

    @classmethod
    def from_yaml_string(cls, yaml_str: str) -> "PresetsModule":
        """Instantiates PresetsModule by loading presets from a YAML string."""
        loaded = load_presets_from_yaml_string(yaml_str)
        return cls(presets=loaded)

    @classmethod
    def from_json_file(cls, file_path: str | Path) -> "PresetsModule":
        """Instantiates PresetsModule by loading presets from a JSON file."""
        loaded = load_presets_from_json_file(file_path)
        return cls(presets=loaded)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | list[dict[str, Any]]) -> "PresetsModule":
        """Instantiates PresetsModule by loading presets from dict data."""
        loaded = load_presets_from_dict(data)
        return cls(presets=loaded)

    def get_module_info(self) -> ModuleInfo:
        return ModuleInfo(
            name=self.name,
            details={
                "presets_count": len(self._presets),
            },
        )
