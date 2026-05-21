"""Public API for the merkmal package."""

__version__ = "0.5.0"

from merkmal.analysis import (
    FeatureMatrix,
    derive_class_features,
    distance,
    features_to_graphemes,
    minimal_matrix,
    tabulate_matrix,
    valued_distance,
    valued_matches,
)
from merkmal.engines.categorical import CategoricalEngine
from merkmal.engines.trained import TrainedEngine
from merkmal.engines.valued import ValuedEngine
from merkmal.geometry import FeatureNode, Geometry, GeometryNode, load_geometry
from merkmal.grapheme import normalize_sequences
from merkmal.model import ModelConfig, load_model, load_model_config
from merkmal.protocol import FeatureSystem
from merkmal.registry import (
    Registry,
    add_features,
    create_registry,
    feature_distance,
    features_to_grapheme,
    get_class_features,
    get_class_representation,
    get_features,
    get_registry,
    get_representation,
    get_system,
    is_class,
    list_systems,
    matches,
    partial_match,
    register,
    reset_registry,
    segment_distance,
    set_default,
    set_registry,
    sound_distance,
)
from merkmal.representations import (
    CategoricalFeatures,
    FeatureRepresentation,
    FeatureState,
    ValuedFeatures,
)
from merkmal.segmentation import merge_tone_digits, parse_chao_digits

__all__ = [
    "__version__",
    "CategoricalEngine",
    "CategoricalFeatures",
    "FeatureMatrix",
    "FeatureNode",
    "FeatureRepresentation",
    "FeatureState",
    "FeatureSystem",
    "Geometry",
    "GeometryNode",
    "ModelConfig",
    "Registry",
    "TrainedEngine",
    "ValuedEngine",
    "ValuedFeatures",
    "add_features",
    "create_registry",
    "derive_class_features",
    "distance",
    "feature_distance",
    "features_to_grapheme",
    "features_to_graphemes",
    "get_class_features",
    "get_class_representation",
    "get_features",
    "get_registry",
    "get_representation",
    "get_system",
    "is_class",
    "list_systems",
    "load_geometry",
    "load_model",
    "load_model_config",
    "matches",
    "merge_tone_digits",
    "minimal_matrix",
    "normalize_sequences",
    "parse_chao_digits",
    "partial_match",
    "register",
    "reset_registry",
    "segment_distance",
    "set_default",
    "set_registry",
    "sound_distance",
    "tabulate_matrix",
    "valued_distance",
    "valued_matches",
]
