from __future__ import annotations

from enum import Enum

# TODO: rename _enums.py to _enums_inplace_volumes.py: to make space for more


class EnumsVertices3D:
    """Enumerations relevant to vertex3D tables."""
    # Note: this class is a preliminary solution while using xtgeo.Points
    # for export of triangulated surfaces.
    # Optimally, triangulated surfaces should be exported in a standard format (e.g. TSURF)
    # For Points files, ["X_UTME", "Y_UTMN", "Z_TVDSS"] are required as column names

    class Vertex3DTableIndexColumns(str, Enum):
        """
        The index columns for a table of 3D vertices.
        """

        # TODO: may now work without X_UTME etc.?
        X_VAL = "X_UTME"
        Y_VAL = "Y_UTMN"
        Z_VAL = "Z_TVDSS"

    @staticmethod
    def table_columns() -> list[str]:
        """Returns a list of the index columns for 3D vertices."""
        return [k.value for k in EnumsVertices3D.Vertex3DTableIndexColumns]
