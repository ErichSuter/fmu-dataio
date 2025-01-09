# Job in RMS to extract fault surface points and triangulations.
# Not intended to be part of fmu-dataio, but kept for reference.


"""Export fault surface points using fmu-dataio.
 
Script adapted from Drogon/.../pythoncomp/export_fault_polygons.py
 
"""
 
# see demo_export_with_fmudataio_readme.py for further hints
 
import fmu.dataio as dataio
import xtgeo
from fmu.config import utilities as utils
import pandas as pd
 
PRJ = project
 
CFG = utils.yaml_load("../../fmuconfig/output/global_variables.yml")
 
fault_points_RMS_folder = "ExtractedFaultPoints"

# TODO: faults are not described in global variables, so just do it here for now
fault_names = ["F1", "F2", "F3", "F4", "F5", "F6"]
 
def export_fault_points():
    """Return fault points as both dataframe and original (xyz)"""
 
    # see script demo_export_with_fmudataio_readme.py for more details
    edata = dataio.ExportData(
        config=CFG,
        content="depth",
        unit="m",
        vertical_domain={"depth": "msl"},
        workflow="rms structural model",
    )
 
    for fault_name in fault_names:
 
        # "Faults -> Input data -> fault_points_RMS_folder"
        if project.faults[fault_name][fault_points_RMS_folder].is_empty():
            print(f"No data for {fault_name}: {fault_points_RMS_folder}, will skip")
            continue
       
        fault_points = xtgeo.points_from_roxar(
            project = PRJ,
            name = fault_name,
            category = fault_points_RMS_folder,
            stype = "faults")
        print(fault_points.dataframe)
 
        # TODO: is suggested tagname OK?
        for fmt in ["csv", "irap_ascii"]:
            edata.polygons_fformat = fmt
            out = edata.export(fault_points, name=fault_name, tagname=fault_points_RMS_folder + "_pts")
            print(f"Export fault points with metadata to: {out}")
 
        break   # Only need single object for prototyping


def export_fault_triangulation():
    """
    Return triangulation.
    Topology is represented in Sumo as a point set where (X, Y, Z) are replaced
    with the three vertex indices for each triangle.
    """
 
    edata = dataio.ExportData(
        config=CFG,
        content="depth",
        unit="m",
        vertical_domain={"depth": "msl"},
        workflow="rms structural model",
    )
 
    tagname = fault_points_RMS_folder
    realization = 0

    for fault_name in fault_names:

        # Get desired structural model
        triang = project.structural_models["DepthModel"].fault_model.get_fault_triangle_surface(fault_name, realization)
        print("Fault surface vertices:", triang.get_vertices())
        print("Fault surface triangles:", triang.get_triangles())
 
        xtgeo_obj = xtgeo.points_from_roxar(
            project = PRJ,
            name = fault_name,
            category = fault_points_RMS_folder,
            stype = "faults")


        ############################
        #####  Export points  ######
        ############################

        # Column names matter
        df = pd.DataFrame(triang.get_vertices(), columns=["X_UTME", "Y_UTMN", "Z_TVDSS"])
        print(df)
        xtgeo_obj.dataframe = df

        # TODO: is suggested tagname OK?
        for fmt in ["csv", "irap_ascii"]:
            edata.polygons_fformat = fmt
            out = edata.export(xtgeo_obj, name=fault_name, tagname=tagname + "_tri_nodes")
            print(f"Export triangulation points with metadata to: {out}")


        ############################
        ##### Export vertices ######
        ############################

        # Column names matter
        df = pd.DataFrame(triang.get_triangles(), columns=["X_UTME", "Y_UTMN", "Z_TVDSS"])
        print(df)
        xtgeo_obj.dataframe = df
 
        # TODO: is suggested tagname OK?
        for fmt in ["csv", "irap_ascii"]:
            edata.polygons_fformat = fmt
            out = edata.export(xtgeo_obj, name=fault_name, tagname=tagname + "_tri_triang")
            print(f"Export triangulation topology with metadata to: {out}")
 
        break   # Only need single object for prototyping
 

if __name__ == "__main__":
    # Separate handling, just to emphasize the difference
    export_fault_points()
    export_fault_triangulation()
    print()
    print(" ------------------------- Done! --------------------------")
    print()
    print()
 