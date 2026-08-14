from pathlib import Path
from typing import Any, Dict, List, Union
from platform_core.modules.base import BaseBotModule
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

    def __init__(self, presets: List[PromptPreset]):
        self._presets = presets

    def get_presets(self) -> List[PromptPreset]:
        return self._presets

    @classmethod
    def from_yaml_file(cls, file_path: Union[str, Path]) -> "PresetsModule":
        """Instantiates PresetsModule by loading presets from a YAML file."""
        loaded = load_presets_from_yaml_file(file_path)
        return cls(presets=loaded)

    @classmethod
    def from_yaml_string(cls, yaml_str: str) -> "PresetsModule":
        """Instantiates PresetsModule by loading presets from a YAML string."""
        loaded = load_presets_from_yaml_string(yaml_str)
        return cls(presets=loaded)

    @classmethod
    def from_json_file(cls, file_path: Union[str, Path]) -> "PresetsModule":
        """Instantiates PresetsModule by loading presets from a JSON file."""
        loaded = load_presets_from_json_file(file_path)
        return cls(presets=loaded)

    @classmethod
    def from_dict(cls, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> "PresetsModule":
        """Instantiates PresetsModule by loading presets from dict data."""
        loaded = load_presets_from_dict(data)
        return cls(presets=loaded)
