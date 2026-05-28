"""Variant lifecycle management for CoGame missions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, TypeVar

from mettagrid.config.mettagrid_config import MettaGridConfig

if TYPE_CHECKING:
    from mettagrid.cogame.core import CoGameMission, CoGameMissionVariant, Deps

T = TypeVar("T", bound="CoGameMissionVariant")


class ResolvedDeps:
    """Scoped view of resolved dependencies for a single variant's configure().

    Only dependencies declared via dependencies() are accessible.
    """

    def __init__(
        self,
        registry: VariantRegistry,
        declared_required: set[type[CoGameMissionVariant]],
        declared_optional: set[type[CoGameMissionVariant]],
    ) -> None:
        self._registry = registry
        self._declared_required = declared_required
        self._declared_optional = declared_optional

    def required(self, variant_type: type[T]) -> T:
        """Get a required dependency. Asserts it was declared and exists."""
        assert variant_type in self._declared_required, (
            f"required({variant_type.__name__}) not declared in dependencies(). "
            f"Declared required: {[t.__name__ for t in self._declared_required]}"
        )
        return self._registry.required(variant_type)

    def optional(self, variant_type: type[T]) -> T | None:
        """Get an optional dependency. Returns None if not included. Asserts it was declared."""
        assert variant_type in self._declared_optional, (
            f"optional({variant_type.__name__}) not declared in dependencies(). "
            f"Declared optional: {[t.__name__ for t in self._declared_optional]}"
        )
        return self._registry.optional(variant_type)


class VariantRegistry:
    """Manages variant registration, configuration, and env modification lifecycle.

    Lifecycle:
      1. Resolve variant names to objects
      2. Dependency resolution: call dependencies() on all variants, auto-create
         missing required deps, repeat until stable
      3. Topological sort: compute configure order (deps before dependents)
      4. Configure phase: call configure(resolved_deps) in order
      5. Apply phase: modify_env for all variants in configure order
    """

    def __init__(self, variants: list[CoGameMissionVariant] | None = None) -> None:
        self._variants: dict[str, CoGameMissionVariant] = {}
        self._configure_order: list[str] = []
        self._edges: list[tuple[str, str, str]] = []  # (from, to, kind)
        self._resolved_deps: dict[str, Deps] = {}
        if variants:
            for v in variants:
                self._variants[v.name] = v

    def get(self, name: str) -> CoGameMissionVariant | None:
        return self._variants.get(name)

    def all(self) -> list[CoGameMissionVariant]:
        return list(self._variants.values())

    def configured(self) -> list[CoGameMissionVariant]:
        """Return variants in configure order after run_configure()."""
        return [self._variants[name] for name in self._configure_order]

    def configured_names(self) -> list[str]:
        """Return variant names in configure order after run_configure()."""
        return list(self._configure_order)

    def required(self, variant_type: type[T]) -> T:
        """Get a variant by type. Asserts it exists."""
        for v in self._variants.values():
            if isinstance(v, variant_type):
                return v
        raise AssertionError(
            f"required({variant_type.__name__}) not found in registry. Available: {sorted(self._variants)}"
        )

    def optional(self, variant_type: type[T]) -> T | None:
        """Get a variant by type. Returns None if not present."""
        for v in self._variants.values():
            if isinstance(v, variant_type):
                return v
        return None

    def has(self, name: str) -> bool:
        return name in self._variants

    def _resolve_dependencies(self) -> None:
        """Call dependencies() on each variant, auto-create missing required deps,
        repeat until stable. Also computes dependency edges."""
        self._edges.clear()
        self._resolved_deps.clear()

        changed = True
        while changed:
            changed = False
            for name in list(self._variants):
                v = self._variants[name]
                deps: Deps = v.dependencies()
                self._resolved_deps[name] = deps

                for req_type in deps.required:
                    found = any(isinstance(existing, req_type) for existing in self._variants.values())
                    if not found:
                        new_v = req_type()  # pyright: ignore[reportCallIssue]
                        self._variants[new_v.name] = new_v
                        changed = True

        # Compute edges from resolved deps
        for name, deps in self._resolved_deps.items():
            for dep_type in deps.required:
                for v in self._variants.values():
                    if isinstance(v, dep_type):
                        self._edges.append((name, v.name, "required"))
                        break
            for dep_type in deps.optional:
                for v in self._variants.values():
                    if isinstance(v, dep_type):
                        self._edges.append((name, v.name, "optional"))
                        break

    def _topological_order(self) -> list[str]:
        """Compute a valid configuration order: dependencies before dependents."""
        dep_names: dict[str, list[str]] = {name: [] for name in self._variants}
        seen_dep_names: dict[str, set[str]] = {name: set() for name in self._variants}
        for from_name, to_name, _kind in self._edges:
            if to_name in seen_dep_names[from_name]:
                continue
            seen_dep_names[from_name].add(to_name)
            dep_names[from_name].append(to_name)

        variant_names = list(self._variants)
        order: list[str] = []
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(name: str) -> None:
            if name in visited:
                return
            assert name not in visiting, f"Circular dependency detected involving '{name}'"
            visiting.add(name)
            for dep in dep_names.get(name, ()):
                visit(dep)
            visiting.remove(name)
            visited.add(name)
            order.append(name)

        for name in variant_names:
            visit(name)

        return order

    def run_configure(self, variants: list[str], preferred_modules: Sequence[str] | None = None) -> None:
        """Resolve variant names to objects, resolve dependencies, configure in topological order."""
        # Lazy import to break the circular dependency between core.py and variants.py.
        # core.py must import this module at the top level (for VariantRegistry used in
        # CoGameMission._variant_registry), so this module defers its import of core to
        # avoid the import cycle.
        from mettagrid.cogame.core import CoGameMissionVariant, Deps  # noqa: PLC0415

        for name in variants:
            if name not in self._variants:
                self._variants[name] = CoGameMissionVariant.create(name, preferred_modules=preferred_modules)

        self._resolve_dependencies()
        self._configure_order = self._topological_order()

        for name in self._configure_order:
            v = self._variants[name]
            deps = self._resolved_deps.get(name, Deps())
            resolved = ResolvedDeps(self, set(deps.required), set(deps.optional))
            v.configure(resolved)

    def apply_to_env(self, mission: CoGameMission, env: MettaGridConfig) -> None:
        """Run modify_env for all configured variants in configure order."""
        for name in self._configure_order:
            self._variants[name].modify_env(mission, env)

    def build_dependency_graph(self) -> list[tuple[str, str, str]]:
        """Resolve dependencies and return the dependency edges.

        Returns a list of (from_variant, to_variant, kind) tuples where kind
        is "required" or "optional".
        """
        self._resolve_dependencies()
        self._configure_order = self._topological_order()
        return list(self._edges)
