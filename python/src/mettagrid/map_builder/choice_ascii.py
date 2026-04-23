from __future__ import annotations

import numpy as np
from pydantic import Field, field_validator

from mettagrid.map_builder.map_builder import GameMap, MapBuilder, MapBuilderConfig
from mettagrid.mapgen.utils.ascii_grid import merge_with_global_defaults


class ChoiceAsciiMapBuilderConfig(MapBuilderConfig["ChoiceAsciiMapBuilder"]):
    map_options: list[list[list[str]]]
    char_to_map_name: dict[str, str]
    seed: int | None = Field(default=None, ge=0)

    @field_validator("map_options", mode="before")
    @classmethod
    def _normalize_map_options(cls, value: object) -> list[list[list[str]]]:
        if not isinstance(value, list) or not value:
            raise ValueError("map_options must be a non-empty list")

        normalized: list[list[list[str]]] = []
        for option in value:
            if isinstance(option, str):
                rows = [list(line) for line in option.splitlines() if line]
            elif isinstance(option, list) and option and isinstance(option[0], str):
                rows = [list(line) for line in option]
            elif isinstance(option, list) and option and isinstance(option[0], list):
                rows = option
            else:
                raise ValueError("Each map option must be a multiline string, list[str], or list[list[str]]")

            width = len(rows[0])
            for row in rows:
                if len(row) != width:
                    raise ValueError("All rows in each ASCII map option must have the same width")
            normalized.append(rows)
        return normalized

    @field_validator("char_to_map_name", mode="after")
    @classmethod
    def _normalize_char_map(cls, value: dict[str, str]) -> dict[str, str]:
        merged = merge_with_global_defaults(value)
        if not isinstance(merged, dict):
            raise TypeError("merge_with_global_defaults must return dict[str, str]")
        if not all(isinstance(char, str) and isinstance(name, str) for char, name in merged.items()):
            raise TypeError("merge_with_global_defaults must return dict[str, str]")
        return {char: name for char, name in merged.items()}


class ChoiceAsciiMapBuilder(MapBuilder[ChoiceAsciiMapBuilderConfig]):
    def build(self) -> GameMap:
        rng = np.random.default_rng(self.config.seed)
        option_index = int(rng.integers(0, len(self.config.map_options)))
        selected = np.array(self.config.map_options[option_index], dtype="U32")
        map_grid = np.vectorize(self._char_to_map_name)(selected)
        return GameMap(map_grid)

    def _char_to_map_name(self, char: str) -> str:
        if char in self.config.char_to_map_name:
            return self.config.char_to_map_name[char]
        raise ValueError(
            f"Unknown character {char!r} for ChoiceAsciiMapBuilder; available={sorted(self.config.char_to_map_name)}"
        )
