from .fmu_results import FmuResults, FmuResultsSchema
from .products import (
    InplaceVolumesResult,
    InplaceVolumesSchema,
    TrianglesResult,
    TrianglesSchema,
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
    "TrianglesResult",
    "TrianglesSchema",
]

schemas = [FmuResultsSchema, InplaceVolumesSchema, Vertices3DSchema, TrianglesSchema]
