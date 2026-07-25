"""Native C-backed Python wrapper for merkmal."""

from __future__ import annotations

__version__ = "0.6.0"

try:
    from merkmal import _native as _native
except ImportError as exc:  # pragma: no cover - exercised before extension build
    raise ImportError(
        "merkmal requires its native C extension. Install the package from a built "
        "wheel or run `python -m pip install -e python` from the repository root."
    ) from exc

NativeError = _native.NativeError
distance = _native.distance
feature_distance = _native.feature_distance
get_features = _native.get_features
is_segment = _native.is_segment
list_systems = _native.list_systems
normalize = _native.normalize
segment_ipa = _native.segment_ipa

__all__ = [
    "NativeError",
    "__version__",
    "distance",
    "feature_distance",
    "get_features",
    "is_segment",
    "list_systems",
    "normalize",
    "segment_ipa",
]
