"""Test the schema"""

import logging
from copy import deepcopy
from typing import Literal, get_args, get_origin

import pytest
from pydantic import ValidationError

from fmu.dataio._models import FmuResults, FmuResultsSchema
from fmu.dataio._models.fmu_results import data, enums

from ..utils import _get_pydantic_models_from_annotation, _metadata_examples

# pylint: disable=no-member

logger = logging.getLogger(__name__)


@pytest.mark.parametrize("file, example", _metadata_examples().items())
def test_schema_example_filenames(file, example):
    """Assert that all examples are .yml, not .yaml"""
    assert file.endswith(".yml")


# ======================================================================================
# 0.8.0
# ======================================================================================


@pytest.mark.parametrize("file, example", _metadata_examples().items())
def test_validate(file, example):
    """Confirm that examples are valid against the schema"""
    FmuResults.model_validate(example)


def test_for_optional_fields_without_default(pydantic_models_from_root):
    """Test that all optional fields have a default value"""
    optionals_without_default = []
    for model in pydantic_models_from_root:
        for field_name, field_info in model.model_fields.items():
            if (
                type(None) in get_args(field_info.annotation)
                and field_info.is_required()
            ):
                optionals_without_default.append(
                    f"{model.__module__}.{model.__name__}.{field_name}"
                )

    assert not optionals_without_default


def test_all_content_enums_in_anydata():
    """Test that all content enums are represented with a model in AnyData"""
    anydata_models = _get_pydantic_models_from_annotation(
        data.AnyData.model_fields["root"].annotation
    )

    content_enums_in_anydata = []
    for model in anydata_models:
        # content is used as discriminator in AnyData and
        # should be present for all models
        assert "content" in model.model_fields
        content_annotation = model.model_fields["content"].annotation

        # check that the annotation is a Literal
        assert get_origin(content_annotation) == Literal

        # get_args will unpack the enum from the Literal
        # into a tuple, should only be one Literal value
        assert len(get_args(content_annotation)) == 1

        # the literal value should be an enum
        content_enum = get_args(content_annotation)[0]
        assert isinstance(content_enum, enums.Content)

        content_enums_in_anydata.append(content_enum)

    # finally check that all content enums are represented
    for content_enum in enums.Content:
        assert content_enum in content_enums_in_anydata

    # and that number of models in AnyData matches number of content enums
    assert len(anydata_models) == len(enums.Content)


def test_schema_file_block(metadata_examples):
    """Test variations on the file block."""

    # get a specific example
    example = metadata_examples["surface_depth.yml"]

    # FmuResults.model_validate(example)
    # shall validate as-is
    FmuResults.model_validate(example)

    # shall validate without absolute_path
    _example = deepcopy(example)
    del _example["file"]["absolute_path"]
    FmuResults.model_validate(_example)

    # md5 checksum shall be a string
    _example["file"]["checksum_md5"] = 123.4
    with pytest.raises(ValidationError):
        FmuResults.model_validate(_example)

    # shall not validate without checksum_md5
    del _example["file"]["checksum_md5"]
    with pytest.raises(ValidationError):
        FmuResults.model_validate(_example)

    # shall validate when checksum is put back in
    _example["file"]["checksum_md5"] = "fa4d055b113ae5282796e328cde0ffa4"
    FmuResults.model_validate(_example)

    # shall not validate without relative_path
    del _example["file"]["relative_path"]
    with pytest.raises(ValidationError):
        FmuResults.model_validate(_example)


def test_case(metadata_examples):
    """Asserting validation failure when illegal contents in case example"""

    example = metadata_examples["fmu_case.yml"]

    # assert validation with no changes
    FmuResults.model_validate(example)

    # assert validation error when "fmu" is missing
    _example = deepcopy(example)
    del _example["fmu"]

    with pytest.raises(ValidationError):
        FmuResults.model_validate(_example)

    # assert validation error when "fmu.model" is missing
    _example = deepcopy(example)
    del _example["fmu"]["model"]

    with pytest.raises(ValidationError):
        FmuResults.model_validate(_example)


def test_fmu_block_aggr_real(metadata_examples):
    """Test that fmu.realization and fmu.aggregation are not allowed at the same time"""

    metadata = deepcopy(metadata_examples["surface_depth.yml"])
    # check that assumptions for the test is true
    assert "realization" in metadata["fmu"]
    assert "aggregation" not in metadata["fmu"]

    # assert validation as-is
    FmuResults.model_validate(metadata)

    # add aggregation, shall fail. Get this from an actual example that validates.
    _metadata_aggregation = metadata_examples["aggregated_surface_depth.yml"]
    metadata["fmu"]["aggregation"] = _metadata_aggregation["fmu"]["aggregation"]

    with pytest.raises(ValidationError):
        FmuResults.model_validate(metadata)


def test_data_top_base(metadata_examples):
    """Test require data.top and data.base.

    * Require both data.top and data.base, or none.
    """

    metadata = metadata_examples["surface_seismic_amplitude.yml"]

    # check that assumptions for the test is true
    assert "top" in metadata["data"]
    assert "base" in metadata["data"]

    # assert validation as-is
    FmuResults.model_validate(metadata)

    # remove "top" - shall fail
    _metadata = deepcopy(metadata)
    del _metadata["data"]["top"]
    with pytest.raises(ValidationError):
        FmuResults.model_validate(_metadata)

    # remove "base" - shall fail
    _metadata = deepcopy(metadata)
    del _metadata["data"]["base"]
    with pytest.raises(ValidationError):
        FmuResults.model_validate(_metadata)

    # remove both - shall pass
    del _metadata["data"]["top"]
    assert "top" not in _metadata["data"]  # test assumption
    assert "base" not in _metadata["data"]  # test assumption
    FmuResults.model_validate(_metadata)


def test_field_outline(metadata_examples):
    """Test content-specific rule.

    When content == field_outline, require the field_outline field
    """

    metadata = metadata_examples["polygons_field_outline.yml"]

    # check that assumptions for the test is true
    assert metadata["data"]["content"] == "field_outline"
    assert "field_outline" in metadata["data"]

    # assert validation as-is
    FmuResults.model_validate(metadata)

    # assert failure when content is field_outline and fluid_contact is missing
    _metadata = deepcopy(metadata)
    del _metadata["data"]["field_outline"]
    with pytest.raises(ValidationError):
        FmuResults.model_validate(_metadata)


def test_field_region(metadata_examples):
    """Test content-specific rule: field_region

    When content == field_outline, require the data.field_region field.
    """

    metadata = metadata_examples["polygons_field_region.yml"]

    # check assumptions
    assert metadata["data"]["content"] == "field_region"
    assert "field_region" in metadata["data"]
    assert "id" in metadata["data"]["field_region"]
    FmuResults.model_validate(metadata)

    # assert that data.field_region is required
    _metadata = deepcopy(metadata)
    del _metadata["data"]["field_region"]
    with pytest.raises(ValidationError):
        FmuResults.model_validate(_metadata)

    # validation of data.field_region
    _metadata = deepcopy(metadata)
    del _metadata["data"]["field_region"]["id"]
    with pytest.raises(ValidationError):
        FmuResults.model_validate(_metadata)

    _metadata = deepcopy(metadata)
    _metadata["data"]["field_region"]["id"] = "NotANumber"
    with pytest.raises(ValidationError):
        FmuResults.model_validate(_metadata)


def test_fluid_contact(metadata_examples):
    """Test content-specific rule.

    When content == fluid_contact, require the fluid_contact field
    """

    # parse the schema and polygons
    metadata = metadata_examples["surface_fluid_contact.yml"]

    # check that assumptions for the test is true
    assert metadata["data"]["content"] == "fluid_contact"
    assert "fluid_contact" in metadata["data"]

    # assert failure when content is fluid_contact and fluid_contact block missing
    _metadata = deepcopy(metadata)
    del _metadata["data"]["fluid_contact"]
    with pytest.raises(ValidationError):
        FmuResults.model_validate(_metadata)


def test_schema_masterdata_smda(metadata_examples):
    """Test schema logic for masterdata.smda."""

    example = metadata_examples["fmu_case.yml"]

    # assert validation with no changes
    FmuResults.model_validate(example)

    # assert validation error when masterdata block is missing
    _example = deepcopy(example)
    del _example["masterdata"]
    with pytest.raises(ValidationError):
        FmuResults.model_validate(_example)

    # assert validation error when masterdata.smda is missing
    # print(example["masterdata"])
    _example = deepcopy(example)
    del _example["masterdata"]["smda"]
    with pytest.raises(ValidationError):
        FmuResults.model_validate(_example)

    # assert validation error when missing attribute
    for block in [
        "country",
        "discovery",
        "field",
        "coordinate_system",
        "stratigraphic_column",
    ]:
        _example = deepcopy(example)
        del _example["masterdata"]["smda"][block]
        with pytest.raises(ValidationError):
            FmuResults.model_validate(_example)

    # assert validation error if not correct type
    for block, type_ in [
        ("country", list),
        ("discovery", list),
        ("coordinate_system", dict),
        ("stratigraphic_column", dict),
    ]:
        _example = deepcopy(example)
        assert isinstance(_example["masterdata"]["smda"][block], type_)

        _example["masterdata"]["smda"][block] = "somestring"

        with pytest.raises(ValidationError):
            FmuResults.model_validate(_example)


def test_schema_data_time(metadata_examples):
    """Test schema logic for data.time."""

    # fetch one example that contains the data.time element
    example = metadata_examples["surface_seismic_amplitude.yml"]
    assert "time" in example["data"]

    # assert validation with no changes
    FmuResults.model_validate(example)

    # valid when data.time is missing
    _example = deepcopy(example)
    del _example["data"]["time"]
    FmuResults.model_validate(_example)

    # valid when only t0
    _example = deepcopy(example)
    del _example["data"]["time"]["t1"]
    assert "t0" in _example["data"]["time"]  # test assumption
    FmuResults.model_validate(_example)

    # valid without labels
    _example = deepcopy(example)
    del _example["data"]["time"]["t0"]["label"]
    FmuResults.model_validate(_example)

    # NOT valid when other types
    for testvalue in [
        [{"t0": "2020-10-28T14:28:02", "label": "mylabel"}],
        "2020-10-28T14:28:02",
        123,
        123.4,
    ]:
        _example = deepcopy(example)
        _example["data"]["time"] = testvalue
        with pytest.raises(ValidationError):
            FmuResults.model_validate(_example)


def test_classification(metadata_examples):
    """Test the classification of individual files."""

    # fetch example
    example = deepcopy(metadata_examples["surface_depth.yml"])

    # assert validation with no changes
    FmuResults.model_validate(example)

    # assert "internal" and "restricted" validates
    example["access"]["classification"] = "internal"
    FmuResults.model_validate(example)

    example["access"]["classification"] = "restricted"
    FmuResults.model_validate(example)

    # assert erroneous value does not validate
    example["access"]["classification"] = "open"
    with pytest.raises(ValidationError):
        FmuResults.model_validate(example)


def test_data_spec(metadata_examples):
    """Test schema logic for data.spec"""

    # fetch surface example
    example_surface = deepcopy(metadata_examples["surface_depth.yml"])

    # assert validation with no changes
    FmuResults.model_validate(example_surface)

    # assert data.spec required when class == surface
    del example_surface["data"]["spec"]
    with pytest.raises(ValidationError):
        FmuResults.model_validate(example_surface)

    # fetch table example
    example_table = deepcopy(metadata_examples["table_inplace_volumes.yml"])

    # assert validation with no changes
    FmuResults.model_validate(example_table)

    # assert data.spec required when class == table
    del example_table["data"]["spec"]
    with pytest.raises(ValidationError):
        FmuResults.model_validate(example_table)

    # fetch case example
    example_case = deepcopy(metadata_examples["fmu_case.yml"])

    # assert data.spec is not present
    with pytest.raises(KeyError):
        example_case["data"]["spec"]

    # assert data.spec not required when class === case
    FmuResults.model_validate(example_case)


def test_content_whitelist(metadata_examples):
    """Test that validation fails when value of data.content is not in
    the whitelist."""

    # fetch surface example
    example_surface = deepcopy(metadata_examples["surface_depth.yml"])

    # assert validation with no changes
    FmuResults.model_validate(example_surface)

    # shall fail when content is not in whitelist
    example_surface["data"]["content"] = "not_valid_content"
    with pytest.raises(ValidationError):
        FmuResults.model_validate(example_surface)


def test_zmin_zmax_not_present_for_surfaces(metadata_examples):
    """
    Test that the validation works for surface metadata without
    zmin/zmax info or with zmin/zmax = None.
    """

    # fetch surface example
    example_surface = deepcopy(metadata_examples["surface_depth.yml"])

    # assert validation with no changes and check that bbox is 3D
    model = FmuResults.model_validate(example_surface)
    assert isinstance(model.root.data.root.bbox, data.BoundingBox3D)

    # assert validation works with zmin/zmax = None, bbox should be 2D
    example_surface["data"]["bbox"]["zmin"] = None
    example_surface["data"]["bbox"]["zmax"] = None
    model = FmuResults.model_validate(example_surface)
    assert isinstance(model.root.data.root.bbox, data.BoundingBox2D)

    # assert validation works without zmin/zmax, bbox should be 2D
    del example_surface["data"]["bbox"]["zmin"]
    del example_surface["data"]["bbox"]["zmax"]
    model = FmuResults.model_validate(example_surface)
    assert isinstance(model.root.data.root.bbox, data.BoundingBox2D)


def test_sumo_ensemble(metadata_examples):
    """Asserting validation failure when illegal contents in case example"""

    example = metadata_examples["sumo_ensemble.yml"]

    # assert validation with no changes
    FmuResults.model_validate(example)

    # assert validation error when "fmu" is missing
    _example = deepcopy(example)
    del _example["fmu"]

    with pytest.raises(ValidationError):
        FmuResults.model_validate(_example)

    # assert validation error when "fmu.ensemble" is missing
    _example = deepcopy(example)
    del _example["fmu"]["ensemble"]

    with pytest.raises(ValidationError):
        FmuResults.model_validate(_example)

    # assert validation error when "fmu.context.stage" is not ensemble
    _example = deepcopy(example)
    _example["fmu"]["context"]["stage"] = "case"

    with pytest.raises(ValidationError):
        FmuResults.model_validate(_example)


def test_sumo_realization(metadata_examples):
    """Asserting validation failure when illegal contents in case example"""

    example = metadata_examples["sumo_realization.yml"]

    # assert validation with no changes
    FmuResults.model_validate(example)

    # assert validation error when "fmu" is missing
    _example = deepcopy(example)
    del _example["fmu"]

    with pytest.raises(ValidationError):
        FmuResults.model_validate(_example)

    # assert validation error when "fmu.realization" is missing
    _example = deepcopy(example)
    del _example["fmu"]["realization"]

    with pytest.raises(ValidationError):
        FmuResults.model_validate(_example)

    # assert validation error when "fmu.context.stage" is not realization
    _example = deepcopy(example)
    _example["fmu"]["context"]["stage"] = "iteration"

    with pytest.raises(ValidationError):
        FmuResults.model_validate(_example)


def test_fmu_iteration_set_from_fmu_ensemble(metadata_examples):
    """Test that fmu.iteration is set from the fmu.ensemble."""

    # fetch example
    example = metadata_examples["surface_depth.yml"]

    # assert validation with no changes
    FmuResults.model_validate(example)

    assert "iteration" in example["fmu"]
    assert "ensemble" in example["fmu"]

    # delete fmu.iteration and see that is set from the fmu.ensemble
    _example = deepcopy(example)
    del _example["fmu"]["iteration"]
    _example["fmu"]["ensemble"]["name"] = "pytest"

    model = FmuResults.model_validate(_example)

    assert hasattr(model.root.fmu, "iteration")
    assert model.root.fmu.iteration == model.root.fmu.ensemble
    assert model.root.fmu.iteration.name == "pytest"


def test_isodatetime_format_for_time():
    """Test that the format for timestamps is set to iso-date-time
    instead of datetime that pydantic resolves it to."""

    schema = FmuResultsSchema.dump()
    timestamp_value = schema["$defs"]["Timestamp"]["properties"]["value"]

    assert timestamp_value["format"] == "iso-date-time"
