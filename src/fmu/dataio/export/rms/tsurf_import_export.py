from pathlib import Path
import pandas as pd


class TSurf:
    """Export triangulated surface on TSurf format"""

    # Prototype adapted from
    # https://github.com/OPM/ResInsight/blob/9b11539353d3ca0aff24d6949f1a88383b55ba47/ApplicationLibCode/FileInterface/RifSurfaceExporter.cpp
    # TODO: could use an existing open-source package
    # TODO: attribute the source

    @staticmethod
    def export_tsurf(
        filename: Path,
        header_text: str,
        vertices_df: pd.DataFrame,
        triangles_df: pd.DataFrame
    ) -> None:

        lines = []

        header_for_export = "surface"
        if len(header_text) > 0:
            header_for_export = header_text

        lines.append("GOCAD TSurf 1")
        lines.append("HEADER {")
        lines.append("name: " + header_for_export)
        lines.append("}")
        lines.append("GOCAD_ORIGINAL_COORDINATE_SYSTEM")
        lines.append("NAME Default  ")
        lines.append('AXIS_NAME "X" "Y" "Z"')
        lines.append('AXIS_UNIT "m" "m" "m"')
        lines.append("ZPOSITIVE Depth  ")
        lines.append("END_ORIGINAL_COORDINATE_SYSTEM")

        vertices = vertices_df.to_numpy()
        lines.append("TFACE")

        i = 1
        for vtx in vertices:
            lines.append(
                "VRTX " + str(i) + " " +
                str(vtx[0]) + " " +
                str(vtx[1]) + " " +
                str(vtx[2]) + " " +
                "CNXYZ"
            )
            i += 1

        triangles = triangles_df.to_numpy()
        for tri in triangles:
            lines.append(
                "TRGL " +
                str(1 + tri[0]) + " " +
                str(1 + tri[1]) + " " +
                str(1 + tri[2])
            )

        lines.append("END")


        try:
            with open(filename, "w+") as f:
                for line in lines:
                    f.write( f"{line}\n" )
        except FileExistsError:
            print("File already exists.")


    @staticmethod
    def import_tsurf(filename: Path) -> tuple[pd.DataFrame, pd.DataFrame]:

        lines = []
        vertices = []
        triangles = []

        try:
            with open(filename, "w+") as f:
                lines = [line.rstrip() for line in f]
        except FileExistsError:
            print("File already exists.")

        # Header info
        # TODO: can only read files written by the exporter, too specific on the header
        name = "not set"
        axis_name = "not set"
        axis_unit = "not set"
        for line in lines:
            if line.__contains__("GOCAD TSurf 1"):
                continue
            if line.__contains__("HEADER {"):
                continue
            if line.__contains__("name:"):
                name = line.replace("name:", "").removeprefix(" ")
            if line.__contains__("}"):
                continue
            if line.__contains__("GOCAD_ORIGINAL_COORDINATE_SYSTEM"):
                continue
            if line.__contains__("NAME Default"):
                continue
            if line.__contains__("AXIS_NAME"):
                l1 = line.replace('"', "")
                l2 = l1.split(" ")
                axis_name = l2[1:3]
            if line.__contains__("AXIS_UNIT"):
                l1 = line.replace('"', "")
                l2 = l1.split(" ")
                axis_unit = l2[1:3]
            if line.__contains__("ZPOSITIVE Depth"):
                continue
            if line.__contains__("END_ORIGINAL_COORDINATE_SYSTEM"):
                continue
            if line.__contains__("TFACE"):
                continue

            # Vertices
            if line.startswith("VRTX"):
                l1 = line.split(" ")
                # ignore the index for now
                # TODO: verify that elements are floats
                vertices.append([float(l1[2]), float(l1[3]), float(l1[4])])
            
            # Triangles
            if line.startswith("TRGL"):
                l1 = line.split(" ")
                # TODO: verify that elements are integers
                triangles.append([int(l1[1]), int(l1[2]), int(l1[3])])
        
            if line.__contains__("END"):
                continue

            return (pd.DataFrame(vertices), pd.DataFrame(triangles))


if __name__ == "__main__":

    # Dummy triangulation
    vertices = []
    for i in range(3):
        vertices.append([i + 0.1 , i + 0.2, i + 0.3])
    vertices_df = pd.DataFrame(vertices)
    triangles = []
    for i in range(0, 18, 3):
        triangles.append([i, i + 1, i + 2])
    triangles_df = pd.DataFrame(triangles)

    path = Path("/private/esut/temp/triang.txt")
    #tsurf_exporter = TSurf()
    #tsurf_exporter.export(path, "Fault F1", vertices_df, triangles_df)
    
    # Works
    #TSurf().export_tsurf(path, "Fault F1", vertices_df, triangles_df)

    print("Importing...")
    
    (vertices_imported_df, triangles_imported_df) = TSurf().import_tsurf(path)
    print(vertices_imported_df)
    print(triangles_imported_df)