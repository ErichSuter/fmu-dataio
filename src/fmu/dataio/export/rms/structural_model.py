# Adapted from inplace_volumes.py
# Process:
# - Extract triangulations for all fault surfaces from RMS via rmsapi
# - TODO: only faults or also horizons?
# - TODO: export "project.structural_models", is that OK? Is this before or after
#   creating the geomodel?
#
# Output format:
# - A triangulation is often represented as a list of vertices and a list of triangles,
#   where each triangle is a list of three indices in the list of vertices.
# - There exist many different formats for triangulations, e.g. TSurf.
# - Currently, Sumo and xtgeo do not support any triangulation formats.
# - As a workaround, a triangulation is exported as a list of vertices and
#   a list of triangles in two separate files.
# - Both files are using the xtgeo.Points format
# - And both files are CSV files with columns ["X_UTME", "Y_UTMN", "Z_TVDSS"]
# - Each vertex is stored as three floats, each triangle is stored as three integers.
# - A triangle is represented by the indices of the three vertices in the vertex list.
# - The vertices and triangles are stored in the same order as exported from RMS.
# - Hence, a triangulation is reconstructed by reading both the vertices and triangles.


# Differences:
# - Export is done via rmsapi, not via an RMS job
#   - No need to specify a grid name or job name
#   - All surfaces in the structural model are exported (selections could be supported)


from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd
import pyarrow as pa

# OBS: import statement to be updated to StructuralModelTriangulations
import xtgeo
import fmu.dataio as dio
from fmu.dataio._logging import null_logger
from fmu.dataio._models import Vertex3DResult, TrianglesResult
from fmu.dataio._models.fmu_results import product
from fmu.dataio._models.fmu_results.enums import Classification, ProductName
from fmu.dataio.export import _enums_vertices3D, _enums_triangles
from fmu.dataio.export._decorators import experimental
from fmu.dataio.export._export_result import ExportResult, ExportResultItem
from fmu.dataio.export.rms._conditional_rms_imports import import_rms_package

from fmu.dataio.export.rms._utils import (
    check_rmsapi_version,
    get_rms_project_units,
    load_global_config,
)

rmsapi, rmsjobs = import_rms_package()

_logger: Final = null_logger(__name__)

_VerticesColumns = _enums_vertices3D.EnumsVertices3D.table_columns()
_TrianglesColumns = _enums_triangles.EnumsTriangles.table_columns()

# rename columns to FMU standard
# _RENAME_COLUMNS_FROM_RMS: Final = {
#     "Proj. real.": "REAL",
#     "Zone": _TableIndexColumns.ZONE.value,
#     "Segment": _TableIndexColumns.REGION.value,
#     "Boundary": _TableIndexColumns.LICENSE.value,
#     "Facies": _TableIndexColumns.FACIES.value,
#     "BulkOil": _VolumetricColumns.BULK.value + "_OIL",
#     "NetOil": _VolumetricColumns.NET.value + "_OIL",
#     "PoreOil": _VolumetricColumns.PORV.value + "_OIL",
#     "HCPVOil": _VolumetricColumns.HCPV.value + "_OIL",
#     "STOIIP": _VolumetricColumns.STOIIP.value + "_OIL",
#     "AssociatedGas": _VolumetricColumns.ASSOCIATEDGAS.value + "_OIL",
#     "BulkGas": _VolumetricColumns.BULK.value + "_GAS",
#     "NetGas": _VolumetricColumns.NET.value + "_GAS",
#     "PoreGas": _VolumetricColumns.PORV.value + "_GAS",
#     "HCPVGas": _VolumetricColumns.HCPV.value + "_GAS",
#     "GIIP": _VolumetricColumns.GIIP.value + "_GAS",
#     "AssociatedLiquid": _VolumetricColumns.ASSOCIATEDOIL.value + "_GAS",
#     "Bulk": _VolumetricColumns.BULK.value + "_TOTAL",
#     "Net": _VolumetricColumns.NET.value + "_TOTAL",
#     "Pore": _VolumetricColumns.PORV.value + "_TOTAL",
# }


@dataclass
class _ExportTriangulationsRMS:
    project: Any

    def __post_init__(self) -> None:
        _logger.debug("Process data, establish state prior to export.")

        print("Now in _ExportTriangulationsRMS.__post_init__()")
        # TODO:
        # The processing is copied from a test setup.
        # But instead of adapting the test setup from export_volumetrics,
        # I started with a simple script.
        # (Will go back to the real test setup later on, after having
        # verified that it works.)
        # But then I don't have the test setup available.
        # So I tried with a hack to get global_variables.yml
        # May easily fail, e.g. if needed also later on in the processing.
        # global variables exist here: tests/data/drogon/global_config2/global_variables.yml
        # Assume processing is started from '/private/esut/src/fmu-dataio'

        apply_config_hack = True
        if apply_config_hack:
            CONFIG_PATH = Path("tests/data/drogon/global_config2/global_variables.yml")
            from fmu.dataio._utils import load_config_from_path
            self._config = load_config_from_path(CONFIG_PATH)
            print("global_variables hack worked")
        else:
            self._config = load_global_config()

        self._dataframes = self._export_structural_model_as_triangulations_RMS()
        _logger.debug("Process data... DONE")

    @property
    def _product(self) -> product.InplaceVolumesProduct:
        """Product type for the exported data."""
        return product.InplaceVolumesProduct(name=ProductName.inplace_volumes)

    @property
    def _classification(self) -> Classification:
        """Get default classification."""
        return Classification.restricted

    # TODO: allows selection of structural model surfaces
    def _export_structural_model_as_triangulations_RMS(self) -> list[pd.DataFrame]:
        """Fetch triangulations from RMS and convert to pandas dataframe"""
        _logger.debug("Read all structural surfaces as triangulations, ")
        _logger.debug("   and convert to pandas dataframes")

        # from fmu.config import utilities as utils
        # import pandas as pd

        # TODO: use rmsapi
        # PRJ = project

        # CFG = utils.yaml_load("../../fmuconfig/output/global_variables.yml")

        # TODO: use rmsapi to get list of faults
        fault_names = ["F1", "F2", "F3", "F4", "F5", "F6"]
        fault_names = ["F1"]

        # TODO: dataio.ExportData() is the old method.
        # Use my own version of export_inplace_volumes (in inplace_volumes.py)
        # edata = dataio.ExportData(
        #         config=CFG,
        #         content="depth",
        #         unit="m",
        #         vertical_domain={"depth": "msl"},
        #         workflow="rms structural model",
        #     )

        # TODO: not entirely clear what this is, but works when using the name of
        # a specific folder
        # tagname = "DL_depth"
        # tagname = "faults"
        print("TODO: OK tagname?")
        tagname = "ExtractedFaultPoints"
        realization = 0

        dataframes = []
        for fault_name in fault_names:

            # TODO: make function to get the data, and function to insert into df
            triang = self.project.structural_models["DepthModel"].fault_model.get_fault_triangle_surface(fault_name, realization)
            #print("Fault surface vertices:", triang.get_vertices())
            #print("Fault surface triangles:", triang.get_triangles())


            xtgeo_obj_vertices = xtgeo.points_from_roxar(
                project = self.project,
                name = fault_name,
                category = tagname,
                stype = "faults")

            # Column names matter
            xtgeo_obj_vertices.dataframe = pd.DataFrame(
                triang.get_vertices(),
                columns=_VerticesColumns
                )
            # TODO: is the xtgeo object needed at all?
            dataframes.append(xtgeo_obj_vertices.dataframe)

            xtgeo_obj_triangles = xtgeo.points_from_roxar(
                project = self.project,
                name = fault_name,
                category = tagname,
                stype = "faults")

            # Column names matter
            xtgeo_obj_triangles.dataframe = pd.DataFrame(
                triang.get_triangles(),
                columns=_TrianglesColumns
                )
            # TODO: is the xtgeo object needed at all?
            dataframes.append(xtgeo_obj_triangles.dataframe)

            print("Finished retrieving the triangulations")


        return dataframes


    ##########################################################################
    def _export_triangs(self) -> ExportResult:
        """Do the actual export using dataio setup."""

        # Probably export the Point dataframes or Point class objects:
        # TODO: Check how the Point class is exported in fmu-dataio
        # TODO: Have to repeat for each dataframe

        # TODO: this function to export a triangulation with two dataframes
        # TODO: a function on top of that to export triangulations for each fault (and horizon)

        edata = dio.ExportData(
            config=self._config,
            # TODO: content is checked agains a white-list for validation!
            # TODO: whitelist must be enhanced
            content="parameters",
            unit="m3" if get_rms_project_units(self.project) == "metric" else "ft3",
            vertical_domain="depth",
            domain_reference="msl",
            subfolder="points",
            classification=self._classification,
            # TODO: get the name
            name="Name of structural model",
            # name=self.grid_name,
            rep_include=False,
            # TODO: fix next line
            table_index=_enums_triangles.EnumsStructModelTriangulations.vertex_columns(),
        )

        print("In _export_triangs() - 2")

        print("Num dataframes: ", len(self._dataframes))
        single_df = self._dataframes[0]
        print(single_df)



        # TODO: handle more tables
        # vertices_table = pa.Table.from_pandas(self._dataframes[0])
        vertices_table = pa.Table.from_pandas(single_df)

        print("In _export_triangs() - 3")

        # export the volume table with product info in the metadata
        absolute_export_path = edata._export_with_product(
            vertices_table,
            product=self._product,
        )

        print("In _export_triangs() - 4")

        _logger.debug("Structural model surfaces result to: %s", absolute_export_path)
        return ExportResult(
            items=[
                ExportResultItem(
                    absolute_path=Path(absolute_export_path),
                )
            ],
        )

    def export(self) -> ExportResult:
        """Export the triangulations."""

        print("Now in export(self)")


        return self._export_triangs()




@experimental
def export_triangulations(project: Any) -> ExportResult:
    """Simplified interface when exporting structural model as triangulations from RMS.

    Args:
        project: The 'magic' project variable in RMS.
        # Maybe TODO: which structural model
        # TODO: list of surfaces

    Note:
        This function is experimental and may change in future versions.
    """

    print(project.wells)

    check_rmsapi_version(minimum_version="1.7")

    print("Now in export_triangulations()")

    return _ExportTriangulationsRMS(project).export()


# TODO: delete function, project is assumed opened when running interactively from RMS as a job
# @experimental
# def export_structural_model(project_path: str) -> ExportResult:
#     """Simplified interface when exporting volume tables (and assosiated data) from RMS.

#     Args:
#         project: The 'magic' project variable in RMS.

#     Note:
#         This function is experimental and may change in future versions.
#     """

#     # TODO: this function only exists to open the RMS project.
#     # Can that be done in the caller?
#     # Not done here because of problems with sourcing both roxenvbash and fmu-dataio:
#     # source /prog/res/roxapi/aux/roxenvbash 14.2.1
#     # source ~/venv/fmu-dataio/bin/activate
#     # Cannot do both lines, in either ordering, in the bash shell on TGX

#     with rmsapi.Project.open(project_path, readonly=True) as project:
#         return export_triangulations(project)


# # TODO: delete, this is new functionality so don't need a deprecated API
# # keep the old name for now but not log (will be removed soon as we expect close to
# # zero usage so far)
# def export_rms_volumetrics(*args, **kwargs) -> ExportResult:  # type: ignore
#     """Deprecated function. Use export_inplace_volumes instead."""
#     warnings.warn(
#         "export_rms_volumetrics is deprecated and will be removed in a future release. "
#         "Use export_inplace_volumes instead.",
#         FutureWarning,
#         stacklevel=2,
#     )
#     return export_inplace_volumes(*args, **kwargs)
