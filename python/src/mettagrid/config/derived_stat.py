from __future__ import annotations

from typing import Literal, Union

from mettagrid.base_config import Config


class TagCountDerivedStat(Config):
    stat_type: Literal["tag_count"] = "tag_count"
    name: str
    tag: str
    offset: int = 0


class TagInventoryDerivedStat(Config):
    stat_type: Literal["tag_inventory"] = "tag_inventory"
    name: str
    tag: str
    resource: str
    require_tag: str = ""


class CumulativeDerivedStat(Config):
    stat_type: Literal["cumulative"] = "cumulative"
    name: str
    source_stat: str


AnyDerivedStat = Union[TagCountDerivedStat, TagInventoryDerivedStat, CumulativeDerivedStat]
