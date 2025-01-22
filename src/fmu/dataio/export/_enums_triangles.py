from __future__ import annotations

from enum import Enum

# TODO: rename _enums.py to _enums_inplace_volumes.py: to make space for more


class EnumsTriangles:
    """Enumerations relevant to triangle tables."""
    # Note: this class is a preliminary solution while using xtgeo.Points
    # for export of triangulated surfaces.
    # Optimally, triangulated surfaces should be exported in a standard format (e.g. TSURF)
    # For Points files, ["X_UTME", "Y_UTMN", "Z_TVDSS"] are required as column names

    class TriangleTableIndexColumns(str, Enum):
        """
        The index columns for a table of 3D vertices.
        """

        # TODO: may now work without X_UTME etc.?
        FIRST = "X_UTME",
        SECOND = "Y_UTMN"
        THIRD = "Z_TVDSS"

    @staticmethod
    def table_columns() -> list[str]:
        """Returns a list of the index columns for triangles."""
        return [k.value for k in EnumsTriangles.TriangleTableIndexColumns]
