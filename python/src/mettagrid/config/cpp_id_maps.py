"""Name-to-ID mappings for Python-to-C++ config conversion."""

from dataclasses import dataclass, field


@dataclass
class CppIdMaps:
    """All name-to-ID mappings needed during Python-to-C++ config conversion.

    Built once in convert_to_cpp_game_config() and threaded through all
    filter, mutation, query, and game-value conversion functions.
    """

    resource_name_to_id: dict[str, int] = field(default_factory=dict)
    tag_name_to_id: dict[str, int] = field(default_factory=dict)
    vibe_name_to_id: dict[str, int] = field(default_factory=dict)
    collective_name_to_id: dict[str, int] = field(default_factory=dict)
    limit_name_to_resource_ids: dict[str, list[int]] = field(default_factory=dict)
