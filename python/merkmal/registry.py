"""Registry APIs for feature systems."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from merkmal.model import (
    list_available_models,
    load_model,
    load_model_from_dir,
)

if TYPE_CHECKING:
    from pathlib import Path

    from merkmal.protocol import FeatureSystem
    from merkmal.representations import FeatureRepresentation


@dataclass
class Registry:
    """Mutable registry of named feature systems."""

    systems: dict[str, FeatureSystem] = field(default_factory=dict)
    default_system: str = "descriptive"

    def register(self, name: str, system: FeatureSystem) -> None:
        self.systems[name] = system

    def register_dir(self, model_dir: Path | str, name: str | None = None) -> str:
        """Load a model from a directory and register it.

        The registered name defaults to the model's declared ``name``;
        pass *name* to override (e.g. to avoid clashing with a built-in).
        Returns the name under which it was registered.
        """
        system = load_model_from_dir(model_dir)
        key = name or system.name
        self.systems[key] = system
        return key

    def get_system(self, name: str | None = None) -> FeatureSystem:
        key = name or self.default_system
        if key not in self.systems:
            msg = f"Unknown feature system: {key!r}. Available: {list(self.systems)}"
            raise KeyError(msg)
        return self.systems[key]

    def list_systems(self) -> list[str]:
        return list(self.systems)

    def set_default(self, name: str) -> None:
        if name not in self.systems:
            msg = f"Unknown feature system: {name!r}. Available: {list(self.systems)}"
            raise KeyError(msg)
        self.default_system = name


def create_registry(
    *,
    register_builtin: bool = True,
    default_system: str = "descriptive",
    extra_model_dirs: list[Path] | list[str] | None = None,
) -> Registry:
    """Create a registry populated from the layered model search path.

    By default this registers every model discoverable on the search
    path (built-ins plus any ``MERKMAL_MODELS`` / *extra_model_dirs*
    layers, with earlier layers shadowing later ones by name). Pass
    ``register_builtin=False`` to register only models from
    *extra_model_dirs* / the environment, excluding the bundled set.
    """
    registry = Registry(default_system=default_system)
    names = list_available_models(
        extra_dirs=extra_model_dirs,
        include_builtin=register_builtin,
    )
    for name in names:
        registry.register(
            name,
            load_model(
                name,
                extra_dirs=extra_model_dirs,
                include_builtin=register_builtin,
            ),
        )
    return registry


_DEFAULT_REGISTRY: Registry | None = None


def get_registry() -> Registry:
    global _DEFAULT_REGISTRY  # noqa: PLW0603
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = create_registry()
    return _DEFAULT_REGISTRY


def set_registry(registry: Registry) -> None:
    global _DEFAULT_REGISTRY  # noqa: PLW0603
    _DEFAULT_REGISTRY = registry


def reset_registry() -> None:
    global _DEFAULT_REGISTRY  # noqa: PLW0603
    _DEFAULT_REGISTRY = None


def register(name: str, system: FeatureSystem) -> None:
    get_registry().register(name, system)


def get_system(name: str | None = None) -> FeatureSystem:
    return get_registry().get_system(name)


def list_systems() -> list[str]:
    return get_registry().list_systems()


def set_default(name: str) -> None:
    get_registry().set_default(name)


def get_features(
    grapheme: str,
    *,
    system: str | None = None,
) -> frozenset[str] | None:
    return get_system(system).grapheme_to_features(grapheme)


def get_representation(
    grapheme: str,
    *,
    system: str | None = None,
) -> FeatureRepresentation | None:
    return get_system(system).grapheme_to_representation(grapheme)


def is_segment(grapheme: str, *, system: str | None = None) -> bool:
    return get_system(system).is_segment(grapheme)


def get_class_features(grapheme: str, *, system: str | None = None) -> frozenset[str] | None:
    return get_system(system).class_features(grapheme)


def get_class_representation(
    grapheme: str,
    *,
    system: str | None = None,
) -> FeatureRepresentation | None:
    return get_system(system).class_representation(grapheme)


def is_class(grapheme: str, *, system: str | None = None) -> bool:
    return get_system(system).is_class(grapheme)


def features_to_grapheme(
    features: object,
    *,
    system: str | None = None,
) -> str | None:
    return get_system(system).features_to_grapheme(features)


def add_features(
    base: frozenset[str],
    added: frozenset[str],
    *,
    system: str | None = None,
) -> frozenset[str]:
    return get_system(system).add_features(base, added)


def partial_match(
    pattern: frozenset[str],
    target: frozenset[str],
    *,
    system: str | None = None,
) -> bool:
    return get_system(system).partial_match(pattern, target)


def matches(
    pattern: object,
    target: object,
    *,
    system: str | None = None,
) -> bool:
    return get_system(system).matches(pattern, target)


def feature_distance(
    feat_a: str,
    feat_b: str,
    *,
    system: str | None = None,
) -> float:
    return get_system(system).feature_distance(feat_a, feat_b)


def sound_distance(
    feats_a: frozenset[str],
    feats_b: frozenset[str],
    *,
    system: str | None = None,
    node_weights: dict[str, float] | str | None = None,
) -> float:
    return get_system(system).sound_distance(feats_a, feats_b, node_weights)


def segment_distance(
    a: object,
    b: object,
    *,
    system: str | None = None,
    node_weights: dict[str, float] | str | None = None,
) -> float:
    sys = get_system(system)
    return sys.segment_distance(a, b, node_weights)
