from __future__ import annotations

from enum import Enum, IntEnum
from typing import Type


class ProductName(str, Enum):
    """The product name of a given data object."""

    inplace_volumes = "inplace_volumes"
    vertices3D = "vertices3D"
    index_triplets = "index_triplets"


class Classification(str, Enum):
    """The security classification for a given data object."""

    asset = "asset"
    internal = "internal"
    restricted = "restricted"


class AxisOrientation(IntEnum):
    """The axis orientation for a given data object."""

    normal = 1
    flipped = -1


class Content(str, Enum):
    """The content type of a given data object."""

    # TODO: need something for structural_model_triangulations?
    depth = "depth"
    facies_thickness = "facies_thickness"
    fault_lines = "fault_lines"
    fault_properties = "fault_properties"
    field_outline = "field_outline"
    field_region = "field_region"
    fluid_contact = "fluid_contact"
    khproduct = "khproduct"
    lift_curves = "lift_curves"
    named_area = "named_area"
    parameters = "parameters"
    pinchout = "pinchout"
    property = "property"
    pvt = "pvt"
    regions = "regions"
    relperm = "relperm"
    rft = "rft"
    seismic = "seismic"
    simulationtimeseries = "simulationtimeseries"
    subcrop = "subcrop"
    thickness = "thickness"
    time = "time"
    timeseries = "timeseries"
    transmissibilities = "transmissibilities"
    velocity = "velocity"
    volumes = "volumes"
    wellpicks = "wellpicks"

    @classmethod
    def _missing_(cls: Type[Content], value: object) -> None:
        raise ValueError(
            f"Invalid 'content' {value=}. Valid entries are {[m.value for m in cls]}"
        )


class ErtSimulationMode(str, Enum):
    """The simulation mode ert was run in. These definitions come from
    `ert.mode_definitions`."""

    ensemble_experiment = "ensemble_experiment"
    ensemble_smoother = "ensemble_smoother"
    es_mda = "es_mda"
    evaluate_ensemble = "evaluate_ensemble"
    iterative_ensemble_smoother = "iterative_ensemble_smoother"
    manual_update = "manual_update"
    test_run = "test_run"
    workflow = "workflow"


class FMUClass(str, Enum):
    """The class of a data object by FMU convention or standards."""

    # TODO: need something for structural_model_triangulations?
    case = "case"
    realization = "realization"
    iteration = "iteration"
    surface = "surface"
    table = "table"
    cpgrid = "cpgrid"
    cpgrid_property = "cpgrid_property"
    polygons = "polygons"
    cube = "cube"
    well = "well"
    points = "points"
    dictionary = "dictionary"


class Layout(str, Enum):
    """The layout of a given data object."""

    # TODO: need something for structural_model_triangulations?
    regular = "regular"
    unset = "unset"
    cornerpoint = "cornerpoint"
    table = "table"
    dictionary = "dictionary"
    faultroom_triangulated = "faultroom_triangulated"


class FMUContext(str, Enum):
    """The context in which FMU was being run when data were generated."""

    case = "case"
    iteration = "iteration"
    realization = "realization"


class VerticalDomain(str, Enum):
    depth = "depth"
    time = "time"


class DomainReference(str, Enum):
    msl = "msl"
    sb = "sb"
    rkb = "rkb"


class TrackLogEventType(str, Enum):
    """The type of event being logged"""

    created = "created"
    updated = "updated"
    merged = "merged"
