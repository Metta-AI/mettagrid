"""Core base classes for CoGame missions and variants."""

from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from pydantic import Field, PrivateAttr
from typing_extensions import Self

from mettagrid.base_config import Config
from mettagrid.cogame.variants import VariantRegistry
from mettagrid.config.mettagrid_config import GridObjectConfig, MettaGridConfig
from mettagrid.map_builder.map_builder import AnyMapBuilderConfig

if TYPE_CHECKING:
    from mettagrid.cogame.variants import ResolvedDeps

T = TypeVar("T", bound="CoGameMissionVariant")


@dataclass
class Deps:
    """Declared dependencies for a variant, resolved before configure runs."""

    required: list[type[CoGameMissionVariant]] = field(default_factory=list)
    optional: list[type[CoGameMissionVariant]] = field(default_factory=list)


class CvCStationConfig(Config):
    def station_cfg(self) -> GridObjectConfig:
        raise NotImplementedError("Subclasses must implement this method")


class CoGameMissionVariant(Config, ABC):
    name: str
    description: str = Field(default="")

    _type_registry: ClassVar[dict[str, type[CoGameMissionVariant]]] = {}
    _type_candidates: ClassVar[dict[str, list[type[CoGameMissionVariant]]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        name_val = cls.__dict__.get("name")
        if isinstance(name_val, str) and name_val:
            CoGameMissionVariant._type_registry[name_val] = cls
            CoGameMissionVariant._type_candidates.setdefault(name_val, []).append(cls)

    @classmethod
    def create(cls, name: str, preferred_modules: Sequence[str] | None = None) -> CoGameMissionVariant:
        candidates = cls._type_candidates.get(name)
        assert candidates is not None, f"Unknown variant '{name}'. Available: {sorted(cls._type_registry)}"
        if preferred_modules:
            for prefix in preferred_modules:
                for candidate in reversed(candidates):
                    if candidate.__module__.startswith(prefix):
                        return candidate()  # pyright: ignore[reportCallIssue]
        variant_cls = cls._type_registry.get(name)
        assert variant_cls is not None, f"Unknown variant '{name}'. Available: {sorted(cls._type_registry)}"
        return variant_cls()  # pyright: ignore[reportCallIssue]

    def dependencies(self) -> Deps:
        """Declare required and optional variant dependencies.

        Called before configure to build the full dependency graph. The registry
        auto-creates missing required deps and repeats until stable.
        """
        return Deps()

    def configure(self, deps: ResolvedDeps) -> None:
        """Cross-configure with other active variants via resolved deps.

        Called after dependency resolution. Only declared deps are accessible.
        """

    def modify_env(self, mission: CoGameMission, env: MettaGridConfig) -> None:
        pass

    def compat(self, mission: CoGameMission) -> bool:
        return True


class CoGameMission(Config, ABC):
    """Base class for Mission configurations with common fields and methods."""

    name: str
    description: str
    map_builder: AnyMapBuilderConfig
    num_cogs: int | None = None
    min_cogs: int = Field(default=1, ge=1)
    max_cogs: int = Field(default=1000, ge=1)

    default_variant: str | None = None
    sub_missions: list[str] = Field(default_factory=list)

    max_steps: int = Field(default=10000)

    _base_variants: dict[str, CoGameMissionVariant] = PrivateAttr(default_factory=dict)
    _variant_registry: VariantRegistry = PrivateAttr(default_factory=VariantRegistry)

    def required_variant(self, variant_type: type[T]) -> T:
        """Look up a configured variant by type. Only valid after configure phase."""
        return self._variant_registry.required(variant_type)

    def optional_variant(self, variant_type: type[T]) -> T | None:
        """Look up an optional variant by type. Returns None if not active."""
        return self._variant_registry.optional(variant_type)

    def has_variant(self, name: str) -> bool:
        return self._variant_registry.has(name)

    @classmethod
    def variant_module_prefixes(cls) -> tuple[str, ...]:
        """Module prefixes for variant resolution. Defaults to the mission's own package."""
        module = cls.__module__
        # e.g. "metta.games.territories.game" -> "metta.games.territories."
        last_dot = module.rfind(".")
        if last_dot > 0:
            return (module[: last_dot + 1],)
        return ()

    @classmethod
    def _ensure_variant_modules_loaded(cls) -> None:
        """Auto-import variant modules from variant_module_prefixes so variant
        classes are registered before resolution.  Tries ``{prefix}variants``
        for each prefix (e.g. ``metta.games.hunger.variants``)."""
        for prefix in cls.variant_module_prefixes():
            module_name = prefix.rstrip(".") + ".variants" if not prefix.endswith("variants.") else prefix.rstrip(".")
            try:
                importlib.import_module(module_name)
            except ModuleNotFoundError as e:
                # Only suppress if the variants module itself doesn't exist.
                # Re-raise if it exists but has a broken import inside it.
                if e.name == module_name:
                    continue
                raise

    def with_variants(self, variants: Sequence[str | CoGameMissionVariant]) -> Self:
        copy = self.model_copy(deep=True)
        # Import variant modules before resolving string names so the correct
        # game-specific classes are registered (not same-named variants from
        # other games that happened to be imported first).
        copy._ensure_variant_modules_loaded()
        preferred_modules = copy.variant_module_prefixes()
        for v in variants:
            if isinstance(v, CoGameMissionVariant):
                copy._base_variants[v.name] = v.model_copy(deep=True)
            else:
                copy._base_variants[v] = CoGameMissionVariant.create(v, preferred_modules=preferred_modules)
        return copy

    def with_cogs(self, cogs: int) -> Self:
        return self.model_copy(deep=True, update={"num_cogs": cogs})

    @abstractmethod
    def make_base_env(self) -> MettaGridConfig:
        """Create the initial env config before variants are applied. Subclasses must implement."""
        ...

    def make_env(self) -> MettaGridConfig:
        """Create a complete env config: base env + all variants applied."""
        self._variant_registry = VariantRegistry(list(self._base_variants.values()))
        extra_names = [n for n in self._variant_registry._variants if n != self.default_variant]
        default = [self.default_variant] if self.default_variant else []
        self._variant_registry.run_configure(
            [*default, *extra_names],
            preferred_modules=self.variant_module_prefixes(),
        )

        env = self.make_base_env()
        self._variant_registry.apply_to_env(self, env)

        env.label = self.full_name()
        return env

    def full_name(self) -> str:
        return self.name
