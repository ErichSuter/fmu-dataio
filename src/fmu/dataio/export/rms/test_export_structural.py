# For developing purposes only, file to be deleted

# To run script:
# source /prog/res/roxapi/aux/roxenvbash 14.2.1
# source ~/venv/fmu-dataio/bin/activate

# TODO: find out, do I need to use rmsapi in the export class?
# Should work anyway, assuming it works for Therese


def test1():
    # WORKS if sourcing roxenvbash

    import rmsapi
    project_path = "/private/esut/drogon_20240815_10-06/resmod/ff/24.3.1/rms/model/drogon.rms14.2.1"

    try:
        # Open Emerald and print its wells
        with rmsapi.Project.open(project_path, readonly=True) as project:
            for well in project.wells:
                print(well)
    except Exception as e:
        print("Error: %s" % e)


def test2():
    # import rmsapi
    import fmu.dataio.export.rms.structural_model as structural_model
    project_path = "/private/esut/drogon_20240815_10-06/resmod/ff/24.3.1/rms/model/drogon.rms14.2.1"

    try:
        structural_model.export_triangulations(project_path)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test2()
