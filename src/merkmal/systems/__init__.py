"""Built-in feature-system implementations."""

from merkmal.systems.broad import BroadFeatureSystem
from merkmal.systems.categorical import CategoricalFeatureSystem
from merkmal.systems.descriptive import DescriptiveFeatureSystem
from merkmal.systems.distinctive import DistinctiveFeatureSystem
from merkmal.systems.classfeat import ClassFeatFeatureSystem
from merkmal.systems.pbase import PBaseFeatureSystem
from merkmal.systems.phoible import PhoibleFeatureSystem

__all__ = [
    "BroadFeatureSystem",
    "CategoricalFeatureSystem",
    "DescriptiveFeatureSystem",
    "DistinctiveFeatureSystem",
    "ClassFeatFeatureSystem",
    "PBaseFeatureSystem",
    "PhoibleFeatureSystem",
]
