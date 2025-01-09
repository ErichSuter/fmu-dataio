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

import fmu.dataio as dio
from fmu.dataio._logging import null_logger
from fmu.dataio._model import product
from fmu.dataio._model.enums import Classification, ProductName
from fmu.dataio._products.inplace_volumes import InplaceVolumesResult
from fmu.dataio.export import _enums
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


_VolumetricColumns = _enums.InplaceVolumes.VolumetricColumns
_TableIndexColumns = _enums.InplaceVolumes.TableIndexColumns

# rename columns to FMU standard
_RENAME_COLUMNS_FROM_RMS: Final = {
    "Proj. real.": "REAL",
    "Zone": _TableIndexColumns.ZONE.value,
    "Segment": _TableIndexColumns.REGION.value,
    "Boundary": _TableIndexColumns.LICENSE.value,
    "Facies": _TableIndexColumns.FACIES.value,
    "BulkOil": _VolumetricColumns.BULK.value + "_OIL",
    "NetOil": _VolumetricColumns.NET.value + "_OIL",
    "PoreOil": _VolumetricColumns.PORV.value + "_OIL",
    "HCPVOil": _VolumetricColumns.HCPV.value + "_OIL",
    "STOIIP": _VolumetricColumns.STOIIP.value + "_OIL",
    "AssociatedGas": _VolumetricColumns.ASSOCIATEDGAS.value + "_OIL",
    "BulkGas": _VolumetricColumns.BULK.value + "_GAS",
    "NetGas": _VolumetricColumns.NET.value + "_GAS",
    "PoreGas": _VolumetricColumns.PORV.value + "_GAS",
    "HCPVGas": _VolumetricColumns.HCPV.value + "_GAS",
    "GIIP": _VolumetricColumns.GIIP.value + "_GAS",
    "AssociatedLiquid": _VolumetricColumns.ASSOCIATEDOIL.value + "_GAS",
    "Bulk": _VolumetricColumns.BULK.value + "_TOTAL",
    "Net": _VolumetricColumns.NET.value + "_TOTAL",
    "Pore": _VolumetricColumns.PORV.value + "_TOTAL",
}


@dataclass
class _ExportTriangulationsRMS:
    project: Any

    def __post_init__(self) -> None:
        _logger.debug("Process data, establish state prior to export.")
        self._config = load_global_config()
        self._volume_job = self._get_rms_volume_job_settings()
        self._volume_table_name = self._read_volume_table_name_from_job()
        self._dataframe = self._get_table_with_volumes()

        # TODO self._triangulation_dataframes = self.get_the_triangulations()

        _logger.debug("Process data... DONE")

    # # TODO: export of structural model triangulations is not a product right now
    # @property
    # def _product(self) -> product.InplaceVolumesProduct:
    #     """Product type for the exported data."""
    #     return product.InplaceVolumesProduct(name=ProductName.inplace_volumes)

    @property
    def _classification(self) -> Classification:
        """Get default classification."""
        return Classification.restricted

    # TODO: allows selection of structural model surfaces
    def _export_structural_model_as_triangulations_RMS(self) -> pd.DataFrame:
        """Fetch triangulations from RMS and convert to pandas dataframe"""
        _logger.debug("Read all structural surfaces as triangulations, ")
        _logger.debug("   and convert to pandas dataframes")

        import xtgeo
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

        # TODO: different tagname
        tagname = "tagname"
        realization = 0

        for fault_name in fault_names:

            # TODO: make function to get the data, and function to insert into df
            triang = self.project.structural_models["DepthModel"].fault_model.get_fault_triangle_surface(fault_name, realization)
            print("Fault surface vertices:", triang.get_vertices())
            exit()
            #print("Fault surface triangles:", triang.get_triangles())

            xtgeo_obj = xtgeo.points_from_roxar(
                project = PRJ,
                name = fault_name,
                category = tagname,
                stype = "faults")


            ############################
            #####  Export points  ######
            ############################

            # Column names matter
            df = pd.DataFrame(triang.get_vertices(), columns=["X_UTME", "Y_UTMN", "Z_TVDSS"])
            # print(df)
            xtgeo_obj.dataframe = df

            # TODO: is suggested tagname OK?
            # TODO: either CSV or IRAP ASCII
            for fmt in ["csv", "irap_ascii"]:
                # TODO: update this
                edata.polygons_fformat = fmt
                out = edata.export(xtgeo_obj, name=fault_name, tagname=tagname + "_tri_nodes")
                print(f"Export triangulation points with metadata to: {out}")


            ############################
            ##### Export vertices ######
            ############################

            # Column names matter
            df = pd.DataFrame(triang.get_triangles(), columns=["X_UTME", "Y_UTMN", "Z_TVDSS"])
            # print(df)
            xtgeo_obj.dataframe = df

            # TODO: is suggested tagname OK?
            # TODO: either CSV or IRAP ASCII
            for fmt in ["csv", "irap_ascii"]:
                edata.polygons_fformat = fmt
                out = edata.export(xtgeo_obj, name=fault_name, tagname=tagname + "_tri_triang")
                print(f"Export triangulation topology with metadata to: {out}")


    ##########################################################################
    def _get_rms_volume_job_settings(self) -> dict:
        """Get information out from the RMS job API."""
        _logger.debug("RMS VOLJOB settings...")
        return rmsjobs.Job.get_job(
            owner=["Grid models", self.grid_name, "Grid"],
            type="Volumetrics",
            name=self.volume_job_name,
        ).get_arguments()

    def _read_volume_table_name_from_job(self) -> str:
        """Read the volume table name from RMS."""
        _logger.debug("Read volume table name from RMS...")
        voltable = self._volume_job.get("Report")
        if isinstance(voltable, list):
            voltable = voltable[0]

        volume_table_name = voltable.get("ReportTableName")
        if not volume_table_name:
            raise RuntimeError(
                "You need to configure output to Report file: Report table "
                "in the volumetric job. Provide a table name and rerun the job."
            )

        _logger.debug("The volume table name is %s", volume_table_name)
        return volume_table_name

    def _get_table_with_volumes(self) -> pd.DataFrame:
        """
        Get a volumetric table from RMS converted into a pandas
        dataframe on standard format for the inplace_volumes product.
        """
        table = self._get_table_from_rms()
        table = self._convert_table_from_rms_to_legacy_format(table)
        return self._convert_table_from_legacy_to_standard_format(table)

    def _get_table_from_rms(self) -> pd.DataFrame:
        """Fetch volumetric table from RMS and convert to pandas dataframe"""
        _logger.debug("Read values and convert to pandas dataframe...")
        return pd.DataFrame.from_dict(
            self.project.volumetric_tables[self._volume_table_name]
            .get_data_table()
            .to_dict()
        )

    @staticmethod
    def _convert_table_from_rms_to_legacy_format(table: pd.DataFrame) -> pd.DataFrame:
        """Rename columns to legacy naming standard and drop REAL column if present."""
        _logger.debug("Converting dataframe from RMS to legacy format...")
        return table.rename(columns=_RENAME_COLUMNS_FROM_RMS).drop(
            columns="REAL", errors="ignore"
        )

    @staticmethod
    def _compute_water_zone_volumes_from_totals(table: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate 'water' zone volumes by subtracting HC-zone volumes from 'Total'
        volumes which represents the entire zone. Total volumes are removed after
        'water' zone volumes have been added to the table.
        """
        _logger.debug("Computing water volumes from Totals...")

        total_suffix = "_TOTAL"
        total_columns = [col for col in table.columns if col.endswith(total_suffix)]

        if not total_columns:
            raise RuntimeError(
                "Found no 'Totals' volumes in the table. Please ensure 'Totals' "
                "are reported and rerun the volumetric job before export."
            )

        for total_col in total_columns:
            volumetric_col = total_col.replace(total_suffix, "")

            water_zone_col = f"{volumetric_col}_WATER"
            oil_zone_col = f"{volumetric_col}_OIL"
            gas_zone_col = f"{volumetric_col}_GAS"

            # first set water zone data equal to the Total
            # then subtract data from the oil/gas zone
            table[water_zone_col] = table[total_col]

            if oil_zone_col in table:
                table[water_zone_col] -= table[oil_zone_col]

            if gas_zone_col in table:
                table[water_zone_col] -= table[gas_zone_col]

        return table.drop(columns=total_columns)

    @staticmethod
    def _add_missing_columns_to_table(table: pd.DataFrame) -> pd.DataFrame:
        """Add columns with nan values if not present in table."""
        _logger.debug("Add table index columns to table if missing...")
        for col in _enums.InplaceVolumes.table_columns():
            if col not in table:
                table[col] = np.nan
        return table

    @staticmethod
    def _set_net_equal_to_bulk_if_missing_in_table(table: pd.DataFrame) -> pd.DataFrame:
        """
        Add a NET column to the table equal to the BULK column if NET is missing,
        since the absence implies a net-to-gross ratio of 1.
        """
        if _VolumetricColumns.NET.value not in table:
            _logger.debug("NET column missing, setting NET equal BULK...")
            table[_VolumetricColumns.NET.value] = table[_VolumetricColumns.BULK.value]
        return table

    @staticmethod
    def _set_table_column_order(table: pd.DataFrame) -> pd.DataFrame:
        """Set the column order in the table."""
        _logger.debug("Settting the table column order...")
        return table[_enums.InplaceVolumes.table_columns()]

    @staticmethod
    def _transform_and_add_fluid_column_to_table(
        table: pd.DataFrame, table_index: list[str]
    ) -> pd.DataFrame:
        """
        Transformation of a dataframe containing fluid-specific column data into a
        standardized format with unified column names, e.g. 'BULK_OIL' and 'PORV_OIL'
        are renamed into 'BULK' and 'PORV' columns. To separate the data an additional
        FLUID column is added that indicates the type of fluid the row represents.
        """

        tables = []
        for fluid in (
            _enums.InplaceVolumes.Fluid.gas.value,
            _enums.InplaceVolumes.Fluid.oil.value,
            _enums.InplaceVolumes.Fluid.water.value,
        ):
            fluid_suffix = fluid.upper()
            fluid_columns = [
                col for col in table.columns if col.endswith(f"_{fluid_suffix}")
            ]
            if fluid_columns:
                fluid_table = table[table_index + fluid_columns].copy()

                # drop fluid suffix from columns to get standard names
                fluid_table.columns = fluid_table.columns.str.replace(
                    f"_{fluid_suffix}", ""
                )

                # add the fluid as column entry instead
                fluid_table[_TableIndexColumns.FLUID.value] = fluid

                tables.append(fluid_table)

        return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()

    def _convert_table_from_legacy_to_standard_format(
        self, table: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Convert the table from legacy to standard format for the 'inplace_volumes'
        product. The standard format has a fluid column, and all table_index and
        volumetric columns are present with a standard order in the table.
        """
        table_index = [
            col for col in _enums.InplaceVolumes.index_columns() if col in table
        ]
        table = self._compute_water_zone_volumes_from_totals(table)
        table = self._transform_and_add_fluid_column_to_table(table, table_index)
        table = self._set_net_equal_to_bulk_if_missing_in_table(table)
        table = self._add_missing_columns_to_table(table)
        return self._set_table_column_order(table)

    def _is_column_missing_in_table(self, column: str) -> bool:
        """Check if a column is present in the final dataframe and has values"""
        return column not in self._dataframe or self._dataframe[column].isna().all()

    def _validate_table(self) -> None:
        """
        Validate that the final table with volumes is according to the standard
        defined for the inplace_volumes product. The table should have the required
        index and value columns, and at least one of the main types 'oil' or 'gas'.
        """
        _logger.debug("Validating the dataframe...")

        # check that all required index columns are present
        for col in _enums.InplaceVolumes.required_index_columns():
            if self._is_column_missing_in_table(col):
                raise RuntimeError(
                    f"Required index column {col} is missing in the volumetric table. "
                    "Please update and rerun the volumetric job before export."
                )

        has_oil = "oil" in self._dataframe[_TableIndexColumns.FLUID.value].values
        has_gas = "gas" in self._dataframe[_TableIndexColumns.FLUID.value].values

        # check that one of oil and gas fluids are present
        if not (has_oil or has_gas):
            raise RuntimeError(
                "One or both 'oil' and 'gas' needs to be selected as 'Main types'"
                "in the volumetric job. Please update and rerun the volumetric job "
                "before export."
            )

        # check that all required value columns are present
        missing_calculations = []
        for col in _enums.InplaceVolumes.required_value_columns():
            if self._is_column_missing_in_table(col):
                missing_calculations.append(col)

        if has_oil and self._is_column_missing_in_table(
            _VolumetricColumns.STOIIP.value
        ):
            missing_calculations.append(_VolumetricColumns.STOIIP.value)

        if has_gas and self._is_column_missing_in_table(_VolumetricColumns.GIIP.value):
            missing_calculations.append(_VolumetricColumns.GIIP.value)

        if missing_calculations:
            raise RuntimeError(
                f"Required calculations {missing_calculations} are missing "
                f"in the volumetric table {self._volume_table_name}. Please update and "
                "rerun the volumetric job before export."
            )

        df = self._dataframe.replace(np.nan, None).to_dict(orient="records")
        InplaceVolumesResult.model_validate(df)

    def _export_volume_table(self) -> ExportResult:
        """Do the actual volume table export using dataio setup."""

        edata = dio.ExportData(
            config=self._config,
            content="volumes",
            unit="m3" if get_rms_project_units(self.project) == "metric" else "ft3",
            vertical_domain="depth",
            domain_reference="msl",
            subfolder="volumes",
            classification=self._classification,
            name=self.grid_name,
            rep_include=False,
            table_index=_enums.InplaceVolumes.index_columns(),
        )

        volume_table = pa.Table.from_pandas(self._dataframe)

        # export the volume table with product info in the metadata
        absolute_export_path = edata._export_with_product(
            volume_table,
            product=self._product,
        )

        _logger.debug("Volume result to: %s", absolute_export_path)
        return ExportResult(
            items=[
                ExportResultItem(
                    absolute_path=Path(absolute_export_path),
                )
            ],
        )

    def export(self) -> ExportResult:
        """Validate and export the volume table."""
        # Validation needed because the job may be incorrectly defined by user.
        self._validate_table()
        # TODO: find out how point sets or general dataframes are exported
        return self._export_volume_table()


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

    check_rmsapi_version(minimum_version="1.7")

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
