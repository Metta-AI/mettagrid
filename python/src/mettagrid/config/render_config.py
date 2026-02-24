from typing import Optional, Union

from pydantic import Field, model_validator

from mettagrid.base_config import Config


class RenderHudConfig(Config):
    """Configuration for a single HUD bar in MettaScope."""

    resource: str = Field(description="Inventory resource name to display")
    short_name: Optional[str] = Field(default=None, description="Short display name for MettaScope center bar")
    max: int = Field(default=100, description="Max value used to normalize the bar")

    @model_validator(mode="after")
    def _default_short_name(self) -> "RenderHudConfig":
        if not self.short_name:
            self.short_name = self.resource.upper()
        return self


class RenderAsset(Config):
    """Conditional asset selection rule for MettaScope rendering."""

    asset: str = Field(description="Asset base name used by MettaScope")
    resources: list[str] = Field(default_factory=list, description="Required inventory resources")
    tags: list[str] = Field(default_factory=list, description="Required entity tags")


RenderAssetValue = Union[str, RenderAsset, list[RenderAsset]]


class RenderConfig(Config):
    """MettaScope rendering hints embedded in the game config."""

    hud1: RenderHudConfig = Field(
        default_factory=lambda: RenderHudConfig(resource="hp", max=400),
        description="Primary HUD bar configuration",
    )
    hud2: RenderHudConfig = Field(
        default_factory=lambda: RenderHudConfig(resource="energy", short_name="E", max=100),
        description="Secondary HUD bar configuration",
    )
    assets: dict[str, RenderAssetValue] = Field(
        default_factory=dict,
        description="Type-name to asset mapping, optionally with resource/tag conditions",
    )
