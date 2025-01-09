# For developing purposes only, file to be deleted


import fmu.dataio

import fmu.dataio.export.rms.structural_model_triangulations as structural_model_triangulations


import rmsapi

try:
    # Open Emerald and print its wells
    with rmsapi.Project.open("Emerald.pro") as project:
        for well in project.wells:
            print(well)
except Exception as e:
    print("Error: %s" % e)