"""Native C-backed Python wrapper for merkmal."""

from __future__ import annotations

from typing import cast

__version__ = "1.0.0"

try:
    from merkmal import _native as _native  # type: ignore[attr-defined]
except ImportError as exc:  # pragma: no cover - exercised before extension build
    raise ImportError(
        "merkmal requires its native C extension. Install the package from a built "
        "wheel or run `python -m pip install -e .` from the repository root."
    ) from exc

NativeError = _native.NativeError
# Raised for CLDF/CLTS markup -- `<?>`, `<<...>>`, boundary markers -- which is
# not a sound and must not resolve. A ValueError subclass, so code that already
# catches ValueError is unaffected; catch this one to skip the source's own
# known gaps without also swallowing segments the library genuinely lacks.
SourceMarkerError = _native.SourceMarkerError
distance = _native.distance
feature_distance = _native.feature_distance
get_features = _native.get_features
is_segment = _native.is_segment
list_systems = _native.list_systems
merge_tone_digits = _native.merge_tone_digits
normalize = _native.normalize
segment_ipa = _native.segment_ipa
segment_ipa_merged = _native.segment_ipa_merged
sound_distance = _native.sound_distance
system_segment_ipa = _native.system_segment_ipa
split_tone = _native.split_tone


class Registry:
    """Owns built-in systems and caller-supplied categorical models.

    The registry keeps the native handle alive for the lifetime of this
    object. Methods raise ``KeyError`` for unknown systems and ``ValueError``
    for invalid or unknown graphemes.

    Each method is the module-level function of the same name, pointed at this
    registry instead of the shared default one. Passing ``system=None`` uses
    the default system, which the native module defines.
    """

    def __init__(self) -> None:
        """Create a registry containing the built-in systems."""
        self._handle = _native.registry_new()

    def add_model_text(self, model_text: str) -> None:
        """Add a categorical model using the documented text format."""
        _native.add_model_text(model_text, registry=self._handle)

    def list_systems(self) -> list[str]:
        """Return the names of built-in and registered systems."""
        return cast("list[str]", _native.list_systems(registry=self._handle))

    def get_features(self, grapheme: str, *, system: str | None = None) -> frozenset[str]:
        """Return the feature set for ``grapheme`` in ``system``."""
        return cast(
            "frozenset[str]",
            _native.get_features(grapheme, system=system, registry=self._handle),
        )

    def is_segment(self, grapheme: str, *, system: str | None = None) -> bool:
        """Return whether ``grapheme`` is a valid segment in ``system``."""
        return cast(
            "bool",
            _native.is_segment(grapheme, system=system, registry=self._handle),
        )

    def distance(
        self,
        a: str,
        b: str,
        *,
        system: str | None = None,
        node_weights: str | None = None,
    ) -> float:
        """Return the geometry-weighted distance between two graphemes."""
        return cast(
            "float",
            _native.distance(
                a, b, system=system, node_weights=node_weights, registry=self._handle
            ),
        )

    def system_segment_ipa(self, ipa: str, *, system: str | None = None) -> list[str]:
        """Segment ``ipa`` by longest match against ``system``'s inventory."""
        return cast(
            "list[str]",
            _native.system_segment_ipa(ipa, system=system, registry=self._handle),
        )

__all__ = [
    "NativeError",
    "SourceMarkerError",
    "Registry",
    "__version__",
    "distance",
    "feature_distance",
    "get_features",
    "is_segment",
    "list_systems",
    "merge_tone_digits",
    "normalize",
    "segment_ipa",
    "segment_ipa_merged",
    "sound_distance",
    "split_tone",
    "system_segment_ipa",
]
