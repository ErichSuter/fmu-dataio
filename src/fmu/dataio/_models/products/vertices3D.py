from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List

from pydantic import BaseModel, Field, RootModel

from fmu.dataio._models._schema_base import FmuSchemas, SchemaBase

if TYPE_CHECKING:
    from typing import Any


# NOTE: this class is a preliminary solution while using xtgeo.Points
# for export of triangulated 3D surfaces - one for vertices and one for triangles.
# Optimally, triangulated surfaces should be exported in a standard format (e.g. TSURF)
# For Points files, ["X_UTME", "Y_UTMN", "Z_TVDSS"] are required as column names

class Vertices3DResultRow(BaseModel):
    """
    Represents a row in a static export of the 3D vertices of a 3D triangulation.

    These fields are the current agreed upon standard result. Changes to this model
    should increase the version number in a way that corresponds to the schema
    versioning specification (i.e. they are a patch, minor, or major change).
    """

    X_VAL: float = Field()
    Y_VAL: float = Field()
    Z_VAL: float = Field(ge=0.0)

class Vertices3DResult(RootModel):
    """
    Represents the resultant static vertices csv file, which is naturally a
    list of rows.

    Consumers who retrieve this csv file must read it into a json-dictionary
    equivalent format to validate it against the schema.
    """

    root: List[Vertices3DResultRow]


class Vertices3DSchema(SchemaBase):
    VERSION: str = "0.1.0"
    FILENAME: str = "vertices3D.json"
    PATH: Path = FmuSchemas.PATH / "file_formats" / VERSION / FILENAME

    @classmethod
    def dump(cls) -> dict[str, Any]:
        return Vertices3DResult.model_json_schema(
            schema_generator=cls.default_generator()
        )
