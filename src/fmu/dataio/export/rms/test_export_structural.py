# TODO: For developing purposes only, file to be deleted

# To run script:
# source /prog/res/roxapi/aux/roxenvbash 14.2.1
# source ~/venv/fmu-dataio/bin/activate

# TODO: find out, do I need to use rmsapi in the export class?
# Should work anyway, assuming it works for Therese


def test1():
    import rmsapi

    # import importlib
    #import fmu.dataio.export.rms.structural_model
    from fmu.dataio.export.rms.structural_model import export_triangulations
    # importlib.reload(fmu.dataio.export.rms.structural_model)

    project_path = "/private/esut/drogon_20240815_10-06/resmod/ff/24.3.1/rms/model/drogon.rms14.2.1"

    try:
        with rmsapi.Project.open(project_path, readonly=True) as project:
            export_triangulations(project)
    except Exception as e:
        print("Error: %s" % e)


def test2():
    # import rmsapi
    print("in test2()")

    # import importlib
    import fmu.dataio.export.rms.structural_model
    from fmu.dataio.export.rms.structural_model import export_triangulations
    # importlib.reload(fmu.dataio.export.rms.structural_model)

    project_path = "/private/esut/drogon_20240815_10-06/resmod/ff/24.3.1/rms/model/drogon.rms14.2.1"

    try:
        export_triangulations(project_path)
    except Exception as e:
        print(f"Error: {e}")

def test3():
    print("In test_export_structural.test3()")
    import inplace_volumes
    inplace_volumes.export_inplace_volumes()

if __name__ == "__main__":
    test1()
