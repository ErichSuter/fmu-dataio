from .fmu_results import FmuResults, FmuResultsSchema
from .products import (
    InplaceVolumesResult,
    InplaceVolumesSchema,
    IndexTripletsResult,
    IndexTripletsSchema,
    Vertices3DResult,
    Vertices3DSchema,
)

__all__ = [
    "FmuResults",
    "FmuResultsSchema",
    "InplaceVolumesResult",
    "InplaceVolumesSchema",
    "Vertices3DResult",
    "Vertices3DSchema",
    "IndexTripletsResult",
    "IndexTripletsSchema",
]

schemas = [FmuResultsSchema, InplaceVolumesSchema, Vertices3DSchema, IndexTripletsSchema]
