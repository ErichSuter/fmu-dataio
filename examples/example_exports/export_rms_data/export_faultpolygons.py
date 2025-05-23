"""Export faultpolygons via dataio with metadata."""

import logging
from pathlib import Path

import xtgeo

from fmu import dataio
from fmu.config import utilities as utils

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

CFG = utils.yaml_load("../../fmuconfig/output/global_variables.yml")

HORISONNAMES = CFG["rms"]["horizons"]["TOP_RES"]

# if inside RMS
RMS_POL_CATEGORY = "GL_faultlines_extract_postprocess"

# if running outside RMS using files that are stored e.g. on rms/output
FILEROOT = Path("../output/polygons")


def export_faultlines():
    """Return faultlines as both dataframe and original (xyz)"""

    ed = dataio.ExportData(
        config=CFG,
        content="fault_lines",
        unit="m",
        vertical_domain="depth",
        domain_reference="msl",
        timedata=None,
        is_prediction=True,
        is_observation=False,
        tagname="faultlines",
        workflow="rms structural model",
    )

    for hname in HORISONNAMES:
        # RMS version for reading polygons from a project:
        # poly = xtgeo.polygons_from_roxar(project, hname, RMS_POL_CATEGORY)

        # File version:
        poly = xtgeo.polygons_from_file((FILEROOT / hname.lower()).with_suffix(".pol"))

        poly.name = hname

        # Export both csv (keeping xtgeo column names) and irap text format
        # The difference bewtween "csv" and "csv|xtgeo" is that the latter will keep
        # xtgeo column names as-is while "csv" will force column names to "X Y Z ID"
        for fmt in ["csv|xtgeo", "irap_ascii"]:
            ed.polygons_fformat = fmt
            ed.export(poly)


def main():
    print("\nExporting faultpolygons and metadata...")
    export_faultlines()
    print("Done exporting faultpolygons and metadata.")


if __name__ == "__main__":
    main()
