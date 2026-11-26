"""Python interface to the merkmal C library.

Most functions are the C API's, called through the native extension. Unless a
docstring says otherwise, they take ``system=None`` for the default system
(``DEFAULT_SYSTEM``), raise ``KeyError`` for an unknown system, ``ValueError``
for a grapheme the system cannot resolve (``ParseError``, a subclass of both
``ValueError`` and ``NativeError``, for a malformed one such as ``a¹²³⁴``),
``NotImplementedError`` where the system does not support the operation, and
``NativeError`` for any other failure of the C library.
"""

from __future__ import annotations

import hashlib
import json
import re
import warnings
from collections.abc import Mapping
from pathlib import Path  # noqa: TC003
from typing import Any, NamedTuple, cast

from .geometry import Geometry, GeometryError

__version__ = "0.11.0"

try:
    from merkmal import _native as _native  # type: ignore[attr-defined]
except ImportError as exc:  # pragma: no cover - exercised before extension build
    raise ImportError(
        "merkmal requires its native C extension. Install the package from a built "
        "wheel or run `python -m pip install -e .` from the repository root."
    ) from exc

NativeError = _native.NativeError
ParseError = _native.ParseError
# Raised for CLDF/CLTS markup (`<?>`, `<<...>>`, boundary markers), which is
# not a sound and must not resolve. A ValueError subclass, so code that catches
# ValueError also catches it; catching this one alone skips the source's own
# marked gaps without also skipping segments the library cannot resolve.
SourceMarkerError = _native.SourceMarkerError
# The Unicode version of the compiled-in NFC/NFD tables. Every build of one
# commit normalizes identically. A cache of merkmal output should be keyed on
# the system's semantic fingerprint (system_fingerprint), which identifies the
# data and policies behind a result; the package version does not.
UNICODE_VERSION: str = _native.UNICODE_VERSION
# The built-in data this build carries: "full", or "cc-by" for a build made
# with MERKMAL_DATA_PROFILE=cc-by, which omits the PHOIBLE and P-base tables
# because of their share-alike and non-commercial terms. See NOTICE.
DATA_PROFILE: str = _native.DATA_PROFILE
# The system every call uses when it names none.
DEFAULT_SYSTEM: str = _native.DEFAULT_SYSTEM
# Deprecated; True in every build, because Unicode normalization is compiled
# in. Retained so that code which checks it keeps working. Key caches on
# UNICODE_VERSION instead.
HAVE_UTF8PROC = True
diagnose = _native.diagnose
distance = _native.distance


class Comparison(NamedTuple):
    """A dissimilarity with the evidence needed to interpret it.

    ``coverage`` is the share, in ``[0, 1]``, of the system's declared
    dimensions on which both segments have a value. ``comparability`` is
    ``"ok"``; ``"cross-tier"`` when one argument is a tone and the other a
    segment, in which case ``score`` is the geometry's declared cross-tier
    cost, not a measurement, and ``coverage`` is 0.0; or
    ``"no-shared-dimension"`` when no dimension has a value in both, in which
    case a score of 0.0 means "nothing to compare", not "identical".
    """

    score: float
    coverage: float
    comparability: str


def distance_with_coverage(*args: Any, **kwargs: Any) -> Comparison:
    """Return the dissimilarity of two graphemes with its coverage.

    Takes ``(a, b, system=None, node_weights=None)``, as ``distance`` does.
    The library sets no coverage threshold; see ``Comparison``.
    """
    return Comparison(*_native.distance_with_coverage(*args, **kwargs))


def fixed_space_distance(
    a: str, b: str, *, system: str | None = None
) -> float:
    """Return the mean absolute difference of two graphemes' feature vectors.

    The vectors are those of ``feature_vector``. The mean is over the segment
    columns, and also over the cluster columns (``components`` and the part
    blocks) when either grapheme is a synthesized cluster, so the value for two
    segments does not depend on the width the cluster columns add. A ``0``
    cell ("does not apply") counts as a value like any other, so this is not
    the pairwise-complete score of ``distance_with_coverage``; a ``NaN`` cell
    (a valued system's unknown) makes the result ``NaN``.
    """
    left = feature_vector(a, system=system)
    right = feature_vector(b, system=system)
    if len(left) != len(right):
        raise ValueError("feature vectors have different widths")
    labels = vector_labels(system=system)
    if "components" in labels:
        parts = labels.index("components")
        if left[parts] == 0.0 and right[parts] == 0.0:
            left, right = left[:parts], right[:parts]
    return float(sum(abs(x - y) for x, y in zip(left, right, strict=True)) / len(left))
# A name that states the scorer's pairwise-complete semantics, so that the
# coverage-normalized score is not mistaken for a fixed-space metric. An
# alias, not a separate calculation.
compatibility_dissimilarity = distance_with_coverage
feature_vector = _native.feature_vector
vector_labels = _native.vector_labels
feature_distance = _native.feature_distance
get_features = _native.get_features
is_segment = _native.is_segment
list_systems = _native.list_systems
merge_tone_digits = _native.merge_tone_digits
normalize = _native.normalize
ascii_chao_digits = _native.ascii_chao_digits
segment_ipa = _native.segment_ipa
segment_ipa_merged = _native.segment_ipa_merged
sound_distance = _native.sound_distance
system_segment_ipa = _native.system_segment_ipa
system_fingerprint = _native.system_fingerprint
split_tone = _native.split_tone


def load_geometry(path: str | Path) -> Geometry:
    """Load and validate a JSON geometry for experimental feature scoring.

    Raises ``OSError`` if the file cannot be read, ``json.JSONDecodeError``
    if it is not JSON, and ``GeometryError`` if it is not a valid geometry.
    """
    return Geometry.from_path(path)


def geometry_distance(
    a: str,
    b: str,
    *,
    geometry: Geometry,
    system: str | None = None,
    preset: str | None = None,
) -> float:
    """Return the distance of two graphemes under a loaded geometry.

    The feature sets come from ``system``; ``preset`` names one of the
    geometry's weight presets (``None``: no preset, every node weighted 1).
    Raises ``GeometryError`` for an unknown preset.
    """
    return float(
        geometry.distance(
            get_features(a, system=system),
            get_features(b, system=system),
            preset=preset,
        )
    )


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
    geometry: Geometry | None = None,
    node_weights: str | None = None,
    tokenization_policy: str = "default",
    tone_policy: str = "default",
    comparison_policy: str = "default",
    missingness_policy: str = "default",
    **options: Any,
) -> tuple[str, str]:
    """Return a canonical payload and its SHA-256 for one operation.

    The payload combines the system's semantic fingerprint with the
    caller-selected settings (geometry, node weights, policies and any extra
    keyword options), so that cached distances and analyses record exactly the
    settings that produced them. Extra options must be JSON-serializable and
    are serialized with sorted keys.
    """
    system_payload, _ = system_fingerprint(system=system)
    if geometry is not None:
        options = {
            **options,
            "geometry": {
                "name": geometry.name,
                "version": geometry.version,
                "sha256": geometry.digest,
            },
        }
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
    """A set of systems: the built-in ones and caller-supplied categorical models.

    The native registry lives as long as this object. Each method is the
    module-level function of the same name, applied to this registry instead
    of the shared default one, with the same exceptions. ``system=None`` means
    ``DEFAULT_SYSTEM``.
    """

    def __init__(self) -> None:
        """Create a registry containing the built-in systems."""
        self._handle = _native.registry_new()
        self._manifests: dict[str, dict[str, Any]] = {}

    def add_model_text(
        self, model_text: str, *, manifest: Mapping[str, Any] | None = None
    ) -> None:
        """Register a categorical model given in the runtime model format.

        ``manifest``, if given, is metadata recorded with the model and
        included in ``operation_fingerprint``: a mapping with at least
        ``name`` (equal to the model's ``@model`` name), ``version``,
        ``source``, ``interpretation`` and ``license``, serializable as JSON.
        Raises ``ParseError`` (a ``NativeError``) for a model that does not parse,
        ``ValueError`` for a name already registered or for an incomplete or
        mismatched manifest, and ``TypeError`` if ``manifest`` is not a
        mapping. The model is registered before the
        manifest is checked, so it stays registered when only the manifest is
        rejected.
        """
        _native.add_model_text(model_text, registry=self._handle)
        if manifest is not None:
            if not isinstance(manifest, Mapping):
                raise TypeError("manifest must be a mapping")
            required = {"name", "version", "source", "interpretation", "license"}
            missing = sorted(required - set(manifest))
            if missing:
                raise ValueError("manifest missing required fields: " + ", ".join(missing))
            match = re.search(r"(?m)^\s*@model\s+(\S+)", model_text)
            if match is None or manifest["name"] != match.group(1):
                raise ValueError("manifest name must match @model")
            self._manifests[str(manifest["name"])] = json.loads(
                json.dumps(manifest, ensure_ascii=False, sort_keys=True)
            )

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
        geometry: Geometry | None = None,
        node_weights: str | None = None,
        tokenization_policy: str = "default",
        tone_policy: str = "default",
        comparison_policy: str = "default",
        missingness_policy: str = "default",
        **options: Any,
    ) -> tuple[str, str]:
        """As the module-level ``operation_fingerprint``, for this registry.

        The manifest of a registered model, if one was given, is part of the
        payload.
        """
        payload, _ = self.system_fingerprint(system=system)
        if system is not None and system in self._manifests:
            options = {**options, "model_manifest": self._manifests[system]}
        if geometry is not None:
            options = {
                **options,
                "geometry": {
                    "name": geometry.name,
                    "version": geometry.version,
                    "sha256": geometry.digest,
                },
            }
        return _operation_fingerprint_from_payload(
            payload,
            node_weights=node_weights,
            tokenization_policy=tokenization_policy,
            tone_policy=tone_policy,
            comparison_policy=comparison_policy,
            missingness_policy=missingness_policy,
            options=options,
        )

    def model_manifest(self, *, system: str) -> dict[str, Any] | None:
        """Return a copy of the manifest given for ``system``, or ``None``."""
        manifest = self._manifests.get(system)
        return None if manifest is None else json.loads(json.dumps(manifest))

class BundleComparison(NamedTuple):
    """The comparison of two abstract segments.

    ``distance`` and ``coverage`` are the point values; ``minimum`` and
    ``maximum`` are the exact extremes of the distance over every completion
    of the unspecified cells. ``why`` is ``"ok"``, ``"cross-tier"`` or
    ``"no-shared-dimension"``, with the meanings given for ``Comparison``.
    """

    distance: float
    coverage: float
    minimum: float
    maximum: float
    why: str


def _node_weights_argument(
    node_weights: str | None, weights: str | None, method: str
) -> str | None:
    """The preset from `node_weights`, or from the deprecated `weights`."""
    if weights is None:
        return node_weights
    if node_weights is not None:
        raise TypeError(f"{method}: pass node_weights, not both node_weights and weights")
    warnings.warn(
        f"{method}(weights=...) is deprecated; use node_weights=..., as distance() does",
        DeprecationWarning,
        stacklevel=3,
    )
    return weights


class AbstractSegment:
    """A feature bundle whose identity is not a grapheme.

    Identity is the system and the canonical cell text. ``text`` is written
    ``column=cell;column=cell...`` as in the C API; columns left out are
    ``*``. Cells: ``0`` does not apply, ``?`` unknown and applies, ``*``
    unknown and may not apply; ``+``/``-`` for binary columns; a level or
    ``lo..hi`` on an ordered scale; a label, ``l1|l2`` (one of them) or
    ``l1&l2`` (one exact set) for a node group; ``|0`` adds "may not apply".
    See docs/method/abstract-segments.md.
    """

    __slots__ = ("system", "text")

    def __init__(self, text: str = "", *, system: str | None = None) -> None:
        self.system = system or DEFAULT_SYSTEM
        self.text = _native.bundle_parse(text, system=self.system)

    @classmethod
    def from_grapheme(cls, grapheme: str, *, system: str | None = None) -> AbstractSegment:
        """The fully specified bundle of a grapheme.

        Raises ``NotImplementedError`` for a tone or a synthesized cluster,
        neither of which is one feature set on the segmental tier.
        """
        segment = cls.__new__(cls)
        segment.system = system or DEFAULT_SYSTEM
        segment.text = _native.bundle_parse(grapheme, system=segment.system, from_grapheme=True)
        return segment

    @classmethod
    def covering(cls, graphemes: list[str], *, system: str | None = None) -> AbstractSegment:
        """The smallest bundle whose completions include every grapheme given.

        Per column, the union of the graphemes' values. A node group whose
        members carry several labels at once cannot be written as alternatives
        of single labels, so it becomes `?`. Graphemes the system cannot make a
        bundle of (unknown, clusters, tones) raise.
        """
        if not graphemes:
            raise ValueError("covering: no graphemes")
        system = system or DEFAULT_SYSTEM
        values = dict(cls.columns(system=system))
        members = [cls.from_grapheme(g, system=system).cells for g in graphemes]
        cells: dict[str, str] = {}
        for column, domain in values.items():
            applies: set[str] = set()
            na = unknown = multi = False
            for member in members:
                for part in member[column].split("|"):
                    if part == "0":
                        na = True
                    elif part in ("?", "*"):
                        unknown = True
                        na = na or part == "*"
                    elif ".." in part:
                        lo, hi = part.split("..")
                        applies.update(domain[domain.index(lo) : domain.index(hi) + 1])
                    elif "&" in part:
                        multi = True
                    else:
                        applies.add(part)
            if unknown or multi:
                cell = "?"
            elif applies:
                cell = "|".join(v for v in domain if v in applies)
            else:
                cell = ""
            if na:
                cell = f"{cell}|0" if cell else "0"
            cells[column] = cell
        return cls(";".join(f"{k}={v}" for k, v in cells.items()), system=system)

    @staticmethod
    def columns(*, system: str | None = None) -> list[tuple[str, list[str]]]:
        """Column names and the values each can take, in order."""
        return cast("list[tuple[str, list[str]]]", _native.bundle_columns(system=system))

    @property
    def cells(self) -> dict[str, str]:
        """Every column's cell, in column order."""
        return dict(item.split("=", 1) for item in self.text.split(";"))

    def with_cells(self, **cells: str) -> AbstractSegment:
        """A copy with some cells replaced (keyword names are column names)."""
        merged = self.cells | cells
        text = ";".join(f"{k}={v}" for k, v in merged.items())
        return AbstractSegment(text, system=self.system)

    def compare(
        self,
        other: AbstractSegment | str,
        *,
        node_weights: str | None = None,
        weights: str | None = None,
    ) -> BundleComparison:
        """Compare with another bundle, or with a grapheme's bundle.

        ``node_weights`` names a weight preset, as in ``distance``; ``weights``
        is its former name and is deprecated. Raises ``ValueError`` if the
        bundles belong to different systems.
        """
        node_weights = _node_weights_argument(node_weights, weights, "compare")
        if isinstance(other, str):
            other = AbstractSegment.from_grapheme(other, system=self.system)
        if other.system != self.system:
            raise ValueError("compare: abstract segments of different systems")
        return BundleComparison(
            *_native.bundle_compare(
                self.text, other.text, system=self.system, node_weights=node_weights
            )
        )

    def compatible(self, grapheme: str) -> bool:
        """Whether the grapheme is one of this bundle's completions."""
        return bool(_native.bundle_compatible(self.text, grapheme, system=self.system))

    def compatible_graphemes(
        self, *, node_weights: str | None = None, weights: str | None = None
    ) -> list[str]:
        """Compatible graphemes, nearest first. For display, never identity.

        ``node_weights`` names a weight preset; ``weights`` is its former name
        and is deprecated.
        """
        node_weights = _node_weights_argument(node_weights, weights, "compatible_graphemes")
        return cast(
            "list[str]",
            _native.bundle_compatible_graphemes(
                self.text, system=self.system, node_weights=node_weights
            ),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AbstractSegment):
            return False
        return (self.system, self.text) == (other.system, other.text)

    def __hash__(self) -> int:
        return hash((self.system, self.text))

    def __repr__(self) -> str:
        specified = {k: v for k, v in self.cells.items() if v != "*"}
        return f"AbstractSegment(system={self.system!r}, cells={specified!r})"


__all__ = [
    "AbstractSegment",
    "BundleComparison",
    "NativeError",
    "ParseError",
    "compatibility_dissimilarity",
    "Comparison",
    "SourceMarkerError",
    "Registry",
    "__version__",
    "diagnose",
    "distance",
    "distance_with_coverage",
    "feature_distance",
    "fixed_space_distance",
    "Geometry",
    "GeometryError",
    "feature_vector",
    "get_features",
    "HAVE_UTF8PROC",
    "UNICODE_VERSION",
    "DATA_PROFILE",
    "DEFAULT_SYSTEM",
    "is_segment",
    "list_systems",
    "load_geometry",
    "merge_tone_digits",
    "normalize",
    "ascii_chao_digits",
    "operation_fingerprint",
    "geometry_distance",
    "segment_ipa",
    "segment_ipa_merged",
    "sound_distance",
    "split_tone",
    "system_segment_ipa",
    "system_fingerprint",
    "vector_labels",
]
