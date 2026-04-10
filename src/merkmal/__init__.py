"""Public API for the merkmal package."""

__version__ = "0.1.0"

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
from merkmal.audit import DatasetAuditReport, audit_dataset
from merkmal.dataset import FeatureDataset, dataset_from_rows, load_builtin_dataset, load_dataset
from merkmal.exporters import export_class_features, export_distances, export_matrix
from merkmal.geometry import DEFAULT_GEOMETRY, FeatureNode, GeometryNode
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
from merkmal.upa import adapt as adapt_upa
from merkmal.upa import adapt_segment as adapt_upa_segment
from merkmal.upa import segment_upa
from merkmal.systems.broad import BroadFeatureSystem
from merkmal.systems.descriptive import DescriptiveFeatureSystem
from merkmal.systems.distinctive import DistinctiveFeatureSystem
from merkmal.systems.pbase import PBaseFeatureSystem
from merkmal.systems.classfeat import ClassFeatFeatureSystem
from merkmal.systems.phoible import PhoibleFeatureSystem

__all__ = [
    "__version__",
    "DEFAULT_GEOMETRY",
    "BroadFeatureSystem",
    "DescriptiveFeatureSystem",
    "DistinctiveFeatureSystem",
    "ClassFeatFeatureSystem",
    "CategoricalFeatures",
    "DatasetAuditReport",
    "FeatureDataset",
    "FeatureMatrix",
    "FeatureNode",
    "FeatureRepresentation",
    "FeatureState",
    "FeatureSystem",
    "GeometryNode",
    "PBaseFeatureSystem",
    "PhoibleFeatureSystem",
    "Registry",
    "ValuedFeatures",
    "adapt_upa",
    "adapt_upa_segment",
    "add_features",
    "audit_dataset",
    "create_registry",
    "dataset_from_rows",
    "derive_class_features",
    "distance",
    "feature_distance",
    "export_class_features",
    "export_distances",
    "export_matrix",
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
    "matches",
    "merge_tone_digits",
    "load_builtin_dataset",
    "load_dataset",
    "minimal_matrix",
    "parse_chao_digits",
    "partial_match",
    "register",
    "reset_registry",
    "segment_distance",
    "set_default",
    "segment_upa",
    "set_registry",
    "sound_distance",
    "tabulate_matrix",
    "valued_distance",
    "valued_matches",
]
