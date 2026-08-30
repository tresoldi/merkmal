"""Native C-backed Python wrapper for merkmal."""

from __future__ import annotations

from typing import Any, cast
import hashlib
import json

__version__ = "0.9.0"

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
diagnose = _native.diagnose
distance = _native.distance
distance_with_coverage = _native.distance_with_coverage
# Explicit name for the valued scorer's pairwise-complete semantics. This is
# an alias rather than a new calculation: callers should not mistake the
# coverage-normalized score for a fixed-space metric.
compatibility_dissimilarity = distance_with_coverage
feature_vector = _native.feature_vector
vector_labels = _native.vector_labels
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
system_fingerprint = _native.system_fingerprint
split_tone = _native.split_tone


def _operation_fingerprint_from_payload(
    system_payload: str,
    *,
    node_weights: str | None = None,
    tokenization_policy: str = "default",
    tone_policy: str = "default",
    comparison_policy: str = "default",
    missingness_policy: str = "default",
    options: dict[str, Any] | None = None,
) -> tuple[str, str]:
    operation = {
        "system_payload": system_payload,
        "node_weights": node_weights,
        "tokenization_policy": tokenization_policy,
        "tone_policy": tone_policy,
        "comparison_policy": comparison_policy,
        "missingness_policy": missingness_policy,
        "options": options or {},
    }
    payload = "schema=merkmal-operation-fingerprint-v1\n" + json.dumps(
        operation, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) + "\n"
    return payload, hashlib.sha256(payload.encode("utf-8")).hexdigest()


def operation_fingerprint(
    *,
    system: str | None = None,
    node_weights: str | None = None,
    tokenization_policy: str = "default",
    tone_policy: str = "default",
    comparison_policy: str = "default",
    missingness_policy: str = "default",
    **options: Any,
) -> tuple[str, str]:
    """Return canonical provenance for one result-producing operation.

    The system fingerprint identifies model data; this adds caller-selected
    operation settings so cached distances and downstream analyses can be
    compared safely. Extra options are serialized with sorted keys.
    """
    system_payload, _ = system_fingerprint(system=system)
    return _operation_fingerprint_from_payload(
        system_payload,
        node_weights=node_weights,
        tokenization_policy=tokenization_policy,
        tone_policy=tone_policy,
        comparison_policy=comparison_policy,
        missingness_policy=missingness_policy,
        options=options,
    )


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

    def system_fingerprint(self, *, system: str | None = None) -> tuple[str, str]:
        """Return the canonical semantic payload and SHA-256 for ``system``."""
        return cast(
            "tuple[str, str]",
            _native.system_fingerprint(system=system, registry=self._handle),
        )

    def operation_fingerprint(
        self,
        *,
        system: str | None = None,
        node_weights: str | None = None,
        tokenization_policy: str = "default",
        tone_policy: str = "default",
        comparison_policy: str = "default",
        missingness_policy: str = "default",
        **options: Any,
    ) -> tuple[str, str]:
        """Return operation provenance for a system in this registry."""
        payload, _ = self.system_fingerprint(system=system)
        return _operation_fingerprint_from_payload(
            payload,
            node_weights=node_weights,
            tokenization_policy=tokenization_policy,
            tone_policy=tone_policy,
            comparison_policy=comparison_policy,
            missingness_policy=missingness_policy,
            options=options,
        )

__all__ = [
    "NativeError",
    "compatibility_dissimilarity",
    "SourceMarkerError",
    "Registry",
    "__version__",
    "diagnose",
    "distance",
    "distance_with_coverage",
    "feature_distance",
    "feature_vector",
    "get_features",
    "is_segment",
    "list_systems",
    "merge_tone_digits",
    "normalize",
    "operation_fingerprint",
    "segment_ipa",
    "segment_ipa_merged",
    "sound_distance",
    "split_tone",
    "system_segment_ipa",
    "system_fingerprint",
    "vector_labels",
]
