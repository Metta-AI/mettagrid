from typing import Optional

from pydantic import Field, model_validator

from mettagrid.base_config import Config


class RenderHudConfig(Config):
    """Configuration for a single HUD bar in MettaScope."""

    resource: str = Field(description="Inventory resource name to display")
    short_name: Optional[str] = Field(default=None, description="Short display name for MettaScope center bar")
    max: int = Field(default=100, description="Max value used to normalize the bar")
    rank: int = Field(default=0, description="Sort order for custom top bars (ascending)")

    @model_validator(mode="after")
    def _default_short_name(self) -> "RenderHudConfig":
        if not self.short_name:
            self.short_name = self.resource.upper()
        return self


class RenderStatusBarConfig(Config):
    """Configuration for a status bar in the MettaScope center panel."""

    resource: str = Field(description="Inventory resource name to display")
    short_name: Optional[str] = Field(default=None, description="Short display name for the status panel")
    bar_type: str = Field(default="medium", description="Bar size: large, medium, or small")
    max: int = Field(default=100, description="Max value used to normalize the bar")
    divisions: int = Field(default=20, ge=1, description="Number of panel segments")
    rank: int = Field(default=0, description="Sort order for status bars (ascending)")

    @model_validator(mode="after")
    def _default_short_name(self) -> "RenderStatusBarConfig":
        if not self.short_name:
            self.short_name = self.resource.upper()
        return self


class RenderAsset(Config):
    """Conditional asset selection rule for MettaScope rendering."""

    asset: str = Field(description="Asset base name used by MettaScope")
    resources: list[str] = Field(default_factory=list, description="Required inventory resources")
    tags: list[str] = Field(default_factory=list, description="Required entity tags")


RenderAssetValue = list[RenderAsset]


class RenderConfig(Config):
    """MettaScope rendering hints embedded in the game config.

    Default behavior uses hud1/hud2 (hp + energy bars).
    Set agent_huds and/or object_status for custom multi-bar rendering.
    """

    hud1: RenderHudConfig = Field(
        default_factory=lambda: RenderHudConfig(resource="hp", max=400),
        description="Primary HUD bar (default behavior)",
    )
    hud2: RenderHudConfig = Field(
        default_factory=lambda: RenderHudConfig(resource="energy", short_name="E", max=100),
        description="Secondary HUD bar (default behavior)",
    )
    agent_huds: dict[str, RenderHudConfig] = Field(
        default_factory=dict,
        description="Custom top-bar HUD configs. When set, replaces hud1/hud2. Pre-sorted by rank.",
    )
    object_status: dict[str, dict[str, RenderStatusBarConfig]] = Field(
        default_factory=dict,
        description="Custom per-object status bars. When set, replaces default agent bars. Pre-sorted by rank.",
    )
    symbols: dict[str, str] = Field(
        default_factory=dict,
        description="Object name -> symbol (emoji) for text rendering",
    )
    assets: dict[str, RenderAssetValue] = Field(
        default_factory=dict,
        description="Type-name to asset mapping, optionally with resource/tag conditions",
    )

    @model_validator(mode="after")
    def _sort_by_rank(self) -> "RenderConfig":
        """Pre-sort custom HUD and status bar entries by rank."""
        self.agent_huds = dict(sorted(self.agent_huds.items(), key=lambda kv: (kv[1].rank, kv[0])))
        self.object_status = {
            obj_type: dict(sorted(bars.items(), key=lambda kv: (kv[1].rank, kv[0])))
            for obj_type, bars in self.object_status.items()
        }
        return self
