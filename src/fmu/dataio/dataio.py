"""Module for DataIO class.

The metadata spec is documented as a JSON schema, stored under schema/.
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Final, Literal
from warnings import warn

from fmu.dataio.aggregation import AggregatedData

from ._logging import null_logger
from ._metadata import generate_export_metadata
from ._models.fmu_results import enums, global_configuration
from ._models.fmu_results.global_configuration import GlobalConfiguration
from ._runcontext import RunContext, get_fmu_context_from_environment
from ._utils import (
    export_metadata_file,
    export_object_to_file,
    read_metadata_from_file,
    some_config_from_env,
)
from .case import CreateCaseMetadata
from .exceptions import ValidationError
from .manifest._manifest import update_export_manifest
from .preprocessed import ExportPreprocessedData
from .providers._fmu import FmuProvider
from .providers.objectdata._provider import (
    ObjectDataProvider,
    objectdata_provider_factory,
)

if TYPE_CHECKING:
    from . import types
    from ._models.fmu_results.standard_result import StandardResult


GLOBAL_ENVNAME: Final = "FMU_GLOBAL_CONFIG"
SETTINGS_ENVNAME: Final = (
    "FMU_DATAIO_CONFIG"  # Feature deprecated, still used for user warning.
)

logger: Final = null_logger(__name__)

AggregatedData: Final = AggregatedData  # Backwards compatibility alias
CreateCaseMetadata: Final = CreateCaseMetadata  # Backwards compatibility alias


# ======================================================================================
# Private functions
# ======================================================================================


def _future_warning_preprocessed() -> None:
    warnings.warn(
        "Using the ExportData class for re-exporting preprocessed data is no "
        "longer supported. Use the dedicated ExportPreprocessedData class "
        "instead. In a deprecation period the ExportPreprocessedData is used "
        "under the hood when a filepath is input to ExportData. "
        "Please update your script, as this will be discontinued in the future.",
        FutureWarning,
    )


# ======================================================================================
# Public function to read/load assosiated metadata given a file (e.g. a map file)
# ======================================================================================


def read_metadata(filename: str | Path) -> dict:
    """Read the metadata as a dictionary given a filename.

    If the filename is e.g. /some/path/mymap.gri, the assosiated metafile
    will be /some/path/.mymap.gri.yml (or json?)

    Args:
        filename: The full path filename to the data-object.

    Returns:
        A dictionary with metadata read from the assiated metadata file.
    """
    return read_metadata_from_file(filename)


# ======================================================================================
# ExportData, public class
# ======================================================================================


@dataclass
class ExportData:
    """Class for exporting data with rich metadata in FMU.

    This class sets up the general metadata content to be applied in export.
    For example::

        for name in ["TopOne", TopTwo", "TopThree"]:
            poly = xtgeo.polygons_from_roxar(PRJ, hname, POL_FOLDER)

            ed = dataio.ExportData(
                config=CFG,
                content="depth",
                unit="m",
                vertical_domain="depth",
                domain_reference="msl",
                timedata=None,
                is_prediction=True,
                is_observation=False,
                tagname="faultlines",
                workflow="rms structural model",
                name=name
            )
            out = ed.export(poly)

    A note on 'pwd' and 'rootpath' and 'casepath': The 'pwd' is the process working
    directory, which is folder where the process (script) starts. The 'rootpath' is the
    folder from which relative file names are relative to and is normally auto-detected.
    The user can however force set the 'actual' rootpath by providing the input
    `casepath`. In case of running a RMS project interactive on disk::

        /project/foo/resmod/ff/2022.1.0/rms/model                   << pwd
        /project/foo/resmod/ff/2022.1.0/                            << rootpath

        A file:

        /project/foo/resmod/ff/2022.1.0/share/results/maps/xx.gri   << example absolute
                                        share/results/maps/xx.gri   << example relative

    When running an ERT forward job using a normal ERT job (e.g. a script)::

        /scratch/nn/case/realization-44/iter-2                      << pwd
        /scratch/nn/case                                            << rootpath

        A file:

        /scratch/nn/case/realization-44/iter-2/share/results/maps/xx.gri  << absolute
                         realization-44/iter-2/share/results/maps/xx.gri  << relative

    When running an ERT forward job but here executed from RMS::

        /scratch/nn/case/realization-44/iter-2/rms/model            << pwd
        /scratch/nn/case                                            << rootpath

        A file:

        /scratch/nn/case/realization-44/iter-2/share/results/maps/xx.gri  << absolute
                         realization-44/iter-2/share/results/maps/xx.gri  << relative


    Args:
        access_ssdl: Optional. A dictionary that will overwrite or append
            to the default ssdl settings read from the config. Example:
            ``{"access_level": "restricted", "rep_include": False}``
            Deprecated and replaced by 'classification' and 'rep_include' arguments.

        casepath: Optional path to a case directory that contains valid case metadata
            "fmu_case.yml" in folder "<casepath>/share/metadata/".
            Note for the fmu_context ``case`` the ``casepath`` is required, while
            for fmu_context ``realization`` it will be attempted inferred from
            an ERT environment variable.

        classification: Optional. Security classification level of the data object.
            If present it will override the default found in the config.
            Valid values are either "restricted" or "internal".

        config: Required in order to produce valid metadata, either as key (here) or
            through an environment variable. A dictionary with static settings.
            In the standard case this is read from FMU global variables
            (via fmuconfig). The dictionary must contain some
            predefined main level keys to work with fmu-dataio. If the key is missing or
            key value is None, then it will look for the environment variable
            FMU_GLOBAL_CONFIG to detect the file. If no success in finding the file, a
            UserWarning is made. If both a valid config is provided and
            FMU_GLOBAL_CONFIG is provided in addition, the latter will be used.
            Note that this key shall be set while initializing the instance, ie. it
            cannot be used in ``generate_metadata()`` or ``export()``.
            Note also: If missing or empty, export() may still be done, but without a
            metadata file (this feature may change in future releases).

        content: A required string describing the content of the data e.g. 'volumes'.
            Content is checked agains a white-list for validation!
            Some contents like 'seismic' requires additional information. This
            should be provided through the 'content_metadata' argument.

        content_metadata: Optional. Dictionary with additional information about the
            provided content. Only required for some contents, e.g. 'seismic'.
            Example {"attribute": "amplitude", "calculation": "mean"}.

        fmu_context: Optional string with value ``realization`` or ``case``. If not
            explicitly given it will be inferred based on the presence of ERT
            environment variables.
            The fmu_context ``realization`` will export data per realization, and should
            be used in normal ERT forward models, while the fmu_context ``case``
            will export data relative to the case directory. Note that for the
            fmu_context ``case`` the case directory needs to be provided through the
            argument ``casepath``.

        domain_reference: Optional, reference for the vertical scale of the data.
            Valid references are "msl"/"sb"/"rkb", and the default is "msl".
            Note use the ``vertical_domain`` key to set the domain (depth or time).

        description: A multiline description of the data either as a string or a list
            of strings.

        display_name: Optional, set name for clients to use when visualizing.

        forcefolder: This setting shall only be used as exception, and will make it
            possible to output to a non-standard folder relative to casepath/rootpath,
            as dependent on the both fmu_context and the is_observations boolean value.
            A typical use-case is forcefolder="seismic" which will replace the "cubes"
            standard folder for Cube output with "seismic". Use with care and avoid if
            possible!

        geometry: Optional, and for grid properties only, which may need a
            reference to the 3D grid geometry object. The value shall
            point to an existing file which is already exported with dataio,
            and hence has an assosiated metadata file. The grid name will be derived
            from the grid metadata, if present, and applied as part of the gridproperty
            file name (same behaviour as the `parent` key; replacing this).
            Note that this key may replace the usage of both the `parent` key and the
            `grid_model` key in the near future.

        grid_model: Currently allowed but planned for deprecation. See `geometry`.

        table_index: This applies to tabular data and is a list of the column names
            to use as index columns e.g. ["ZONE", "REGION"]. This can also be applied
            to points or polygons objects that are exported in table format to specify
            attributes that should act as index columns.

        is_prediction: True (default) if model prediction data

        is_observation: Default is False. If True, then disk storage will be on the
            "share/observations" folder, otherwise on "share/result". An exception arise
            if ``preprocessed=True``, then the folder will be set to
            "share/preprocessed" irrespective the value of ``is_observation``.

        name: Optional but recommended. The name of the object. If not set it is tried
            to be inferred from the xtgeo/pandas/... object. The name is then checked
            towards the stratigraphy list, and name is replaced with official
            stratigraphic name if found in static metadata `stratigraphy`. For example,
            if "TopValysar" is the model name and the actual name is "Valysar Top Fm."
            that latter name will be used.

        parent: Optional. This key is required for datatype GridProperty, unless the
            `geometry` is given, and refers to the name of the grid geometry. It will
            only be added in the filename, and not as genuine metadata entry.
            This key is a candidate for deprecation, and users shall use the
            `geometry` key instead. If both `parent` and `geometry` is given, the grid
            name derived from the `geometry` object will have predence.

        preprocessed: Default is False. If True, the data exported are output to a
            dedicated "share/preprocessed" folder, and metadata can be partially re-used
            in an ERT model run using the ``ExportPreprocessedData`` class.

        rep_include: Optional. If True then the data object will be available in REP.
            Default is False.

        runpath: TODO! Optional and deprecated. The relative location of the current run
            root. Optional and will in most cases be auto-detected, assuming that FMU
            folder conventions are followed. For an ERT run e.g.
            /scratch/xx/nn/case/realization-0/iter-0/. while in a revision at project
            disc it will the revision root e.g. /project/xx/resmod/ff/21.1.0/.

        subfolder: It is possible to set one level of subfolders for file output.
            The input should only accept a single folder name, i.e. no paths. If paths
            are present, a deprecation warning will be raised.

        tagname: This is a short tag description which be be a part of file name.

        timedata: Optional. List of dates, where the dates are strings on form
            'YYYYMMDD', example ['20200101']. A maximum of two dates can be input,
            the oldest date will be set as t0 in the metadata and the latest date will
            be t1. Note it is also possible to provide a label to each date by using
            a list of lists, .e.g. [[20200101, "monitor"], [20180101, "base"]].

        vertical_domain: Optional. String with vertical domain either "time" or "depth"
            (default). It is also possible to provide a reference for the vertical
            scale, see the domain_reference key. Note that if the ``content`` is "depth"
            or "time" the vertical_domain will be set accordingly.

        workflow: Short tag desciption of workflow (as description)

        undef_is_zero: Flags that nans should be considered as zero in aggregations

    """

    # ----------------------------------------------------------------------------------
    # This role for this class is to be:
    # - public (end user) interface
    # - collect the full settings from global config, user keys and class variables
    # - process and validate these settings
    # - establish PWD and rootpath
    #
    # Then other classes will further do the detailed metadata processing, cf _MetaData
    # and subsequent classes called by _MetaData
    # ----------------------------------------------------------------------------------

    # class variables
    allow_forcefolder_absolute: ClassVar[bool] = False  # deprecated
    arrow_fformat: ClassVar[str | None] = None  # deprecated and no effect
    case_folder: ClassVar[str] = "share/metadata"
    createfolder: ClassVar[bool] = True  # deprecated
    cube_fformat: ClassVar[str | None] = None  # deprecated and no effect
    filename_timedata_reverse: ClassVar[bool] = False  # reverse order output file name
    grid_fformat: ClassVar[str | None] = None  # deprecated and no effect
    include_ertjobs: ClassVar[bool] = False  # deprecated
    legacy_time_format: ClassVar[bool] = False  # deprecated
    meta_format: ClassVar[Literal["yaml", "json"] | None] = None  # deprecated
    polygons_fformat: ClassVar[str] = "csv"  # or use "csv|xtgeo"
    points_fformat: ClassVar[str] = "csv"  # or use "csv|xtgeo"
    surface_fformat: ClassVar[str | None] = None  # deprecated and no effect
    table_fformat: ClassVar[str] = "csv"
    dict_fformat: ClassVar[str | None] = None  # deprecated and no effect
    table_include_index: ClassVar[bool] = False  # deprecated
    verifyfolder: ClassVar[bool] = True  # deprecated

    # input keys (alphabetic)
    access_ssdl: dict = field(default_factory=dict)
    aggregation: bool = False
    casepath: str | Path | None = None
    classification: str | None = None
    config: dict | GlobalConfiguration = field(default_factory=dict)
    content: dict | str | None = None
    content_metadata: dict | None = None
    depth_reference: str | None = None  # deprecated
    domain_reference: str = "msl"
    description: str | list = ""
    display_name: str | None = None
    fmu_context: str | None = None
    forcefolder: str = ""
    geometry: str | None = None
    grid_model: str | None = None
    is_observation: bool = False
    is_prediction: bool = True
    name: str = ""
    undef_is_zero: bool = False
    parent: str = ""
    preprocessed: bool = False
    realization: int | None = None  # deprecated
    rep_include: bool | None = None
    reuse_metadata_rule: str | None = None  # deprecated
    runpath: str | Path | None = None
    subfolder: str = ""
    tagname: str = ""
    timedata: list[str] | list[list[str]] | None = None
    unit: str | None = ""
    verbosity: str = "DEPRECATED"  # remove in version 2
    vertical_domain: str | dict = "depth"  # dict input is deprecated
    workflow: str | dict[str, str] | None = None  # dict input is deprecated
    table_index: list | None = None

    # Need to store these temporarily in variables until we stop
    # updating state of the class also on export and generate_metadata
    _classification: enums.Classification = enums.Classification.internal
    _rep_include: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        logger.info("Running __post_init__ ExportData")
        self._show_deprecations_or_notimplemented()

        # if input is provided as an ENV variable pointing to a YAML file; will override
        if SETTINGS_ENVNAME in os.environ:
            warnings.warn(
                "Providing input settings through environment variables is deprecated, "
                "use ExportData(**yaml_load(<your_file>)) instead. To "
                "disable this warning, remove the 'FMU_DATAIO_CONFIG' env.",
            )

        # global config which may be given as env variable
        # will only be used if not explicitly given as input
        if not self.config and GLOBAL_ENVNAME in os.environ:
            self.config = some_config_from_env(GLOBAL_ENVNAME) or {}

        self._validate_and_establish_fmucontext()

        try:
            self.config = GlobalConfiguration.model_validate(self.config)
        except global_configuration.ValidationError as e:
            if "masterdata" not in self.config:
                warnings.warn(
                    "The global config file is lacking masterdata definitions, hence "
                    "no metadata will be exported. Follow the simple 'Getting started' "
                    "steps to do necessary preparations and enable metadata export: "
                    "https://fmu-dataio.readthedocs.io/en/latest/preparations.html ",
                    UserWarning,
                )
            else:
                global_configuration.validation_error_warning(e)
            self.config = {}

        self._classification = self._get_classification()
        self._rep_include = self._get_rep_include()

        self._runcontext = self._get_runcontext()
        logger.info("Ran __post_init__")

    def _get_runcontext(self) -> RunContext:
        """Get the run context for this ExportData instance."""
        assert isinstance(self.fmu_context, enums.FMUContext | None)
        casepath_proposed = Path(self.casepath) if self.casepath else None
        return RunContext(casepath_proposed, fmu_context=self.fmu_context)

    def _get_classification(self) -> enums.Classification:
        """
        Get the security classification.
        The order of how the classification is set is:
        1. from classification argument if present
        2. from access_ssdl argument (deprecated) if present
        3. from access.classification in config (has been mirrored from
        access.ssdl.access_level if not present)

        """
        if self.classification is not None:
            logger.info("Classification is set from input")
            classification = self.classification

        elif self.access_ssdl and self.access_ssdl.get("access_level"):
            logger.info("Classification is set from access_ssdl input")
            classification = self.access_ssdl["access_level"]

        elif isinstance(self.config, GlobalConfiguration):
            logger.info("Classification is set from config")
            assert self.config.access.classification
            classification = self.config.access.classification
        else:
            # note the one below here will never be used, because that
            # means the config is invalid and no metadata will be produced
            logger.info("Using default classification 'internal'")
            classification = enums.Classification.internal

        if enums.Classification(classification) == enums.Classification.asset:
            warnings.warn(
                "The value 'asset' for access.ssdl.access_level is deprecated. "
                "Please use 'restricted' in input arguments or global variables "
                "to silence this warning.",
                FutureWarning,
            )
            return enums.Classification.restricted
        return enums.Classification(classification)

    def _get_rep_include(self) -> bool:
        """
        Get the rep_include status.
        The order of how the staus is set is:
        1. from rep_include argument if present
        2. from access_ssdl argument (deprecated) if present
        3. from access.ssdl.rep_include in config
        4. default to False if not found
        """
        if self.rep_include is not None:
            logger.debug("rep_include is set from input")
            return self.rep_include

        if self.access_ssdl and self.access_ssdl.get("rep_include"):
            logger.debug("rep_include is set from access_ssdl input")
            return self.access_ssdl["rep_include"]

        if (
            isinstance(self.config, GlobalConfiguration)
            and (ssdl := self.config.access.ssdl)
            and ssdl.rep_include is not None
        ):
            warn(
                "Setting 'rep_include' from the config is deprecated. Use the "
                "'rep_include' argument instead (default value is False). To silence "
                "this warning remove the 'access.ssdl.rep_include' from the config.",
                FutureWarning,
            )
            logger.debug("rep_include is set from config")
            return ssdl.rep_include

        logger.debug("Using default 'rep_include'=False")
        return False

    def _get_content_enum(self) -> enums.Content | None:
        """Get the content enum."""
        if self.content is None:
            logger.debug("content not set from input, returning None'")
            return None

        if isinstance(self.content, str):
            logger.debug("content is set from string input")
            return enums.Content(self.content)

        if isinstance(self.content, dict):
            logger.debug("content is set from dict input")
            return enums.Content(next(iter(self.content)))

        raise ValueError(
            "Incorrect format found for 'content'. It should be a valid "
            f"content string: {[m.value for m in enums.Content]}"
        )

    def _get_content_metadata(self) -> dict | None:
        """
        Get the content metadata if provided by as input, else return None.
        Validation takes place in the objectdata provider.
        """
        if self.content_metadata:
            logger.debug("content_metadata is set from content_metadata argument")
            return self.content_metadata

        if isinstance(self.content, dict):
            logger.debug("content_metadata is set from content argument")
            content_enum = self._get_content_enum()
            return self.content[content_enum]

        logger.debug("Found no content_metadata, returning None")
        return None

    def _show_deprecations_or_notimplemented(self) -> None:
        """Warn on deprecated keys or on stuff not implemented yet."""

        if self.access_ssdl:
            warn(
                "The 'access_ssdl' argument is deprecated and will be removed in the "
                "future. Use the more explicit 'classification' and 'rep_include' "
                "arguments instead.",
                FutureWarning,
            )
            if self.classification is not None or self.rep_include is not None:
                raise ValueError(
                    "Using the 'classification' and/or 'rep_include' arguments, "
                    "in combination with the (legacy) 'access_ssdl' argument "
                    "is not supported."
                )

        if isinstance(self.content, dict):
            warn(
                "Using the 'content' argument to set both the content and "
                "and the content metadata will be deprecated. Set the 'content' "
                "argument to a valid content string, and provide the extra "
                "information through the 'content_metadata' argument instead.",
                FutureWarning,
            )

        if self.runpath:
            warn(
                "The 'runpath' key has currently no function. It will be evaluated for "
                "removal in fmu-dataio version 2. Use 'casepath' instead!",
                UserWarning,
            )
        if isinstance(self.vertical_domain, dict):
            warn(
                "Using the 'vertical_domain' argument to set both the vertical domain "
                "and the reference will be deprecated. Set the 'vertical_domain' "
                "argument to a string with value either 'time'/'depth', and provide "
                "the domain reference through the 'domain_reference' argument instead.",
                FutureWarning,
            )
            self.vertical_domain, self.domain_reference = list(
                self.vertical_domain.items()
            )[0]

        if self.grid_model:
            warn(
                "The 'grid_model' key has currently no function. It will be evaluated "
                "for removal in fmu-dataio version 2.",
                UserWarning,
            )

        if self.legacy_time_format:
            warn(
                "Using the 'legacy_time_format=True' option to create metadata files "
                "with the old format for time is now deprecated. This option has no "
                "longer an effect and will be removed in the near future.",
                UserWarning,
            )
        if not self.createfolder:
            warn(
                "Using the 'createfolder=False' option is now deprecated. "
                "This option has no longer an effect and can safely be removed",
                UserWarning,
            )
        if not self.verifyfolder:
            warn(
                "Using the 'verifyfolder=False' option to create metadata files "
                "This option has no longer an effect and can safely be removed",
                UserWarning,
            )
        if self.reuse_metadata_rule:
            warn(
                "The 'reuse_metadata_rule' key is deprecated and has no effect. "
                "Please remove it from the argument list.",
                UserWarning,
            )
        if self.realization:
            warn(
                "The 'realization' key is deprecated and has no effect. "
                "Please remove it from the argument list.",
                UserWarning,
            )
        if self.table_include_index:
            warn(
                "The 'table_include_index' option is deprecated and has no effect. "
                "To get the index included in your dataframe, reset the index "
                "before exporting the dataframe with dataio i.e. df = df.reset_index()",
                UserWarning,
            )
        if self.verbosity != "DEPRECATED":
            warn(
                "Using the 'verbosity' key is now deprecated and will have no "
                "effect and will be removed in near future. Please remove it from the "
                "argument list. Set logging level from client script in the standard "
                "manner instead.",
                UserWarning,
            )
        if isinstance(self.workflow, dict):
            warn(
                "The 'workflow' argument should be given as a string. "
                "Support for dictionary will be deprecated.",
                FutureWarning,
            )
        if self.allow_forcefolder_absolute:
            warn(
                "Support for using an absolute path as 'forcefolder' is deprecated. "
                "Please remove it from the argument list.",
                UserWarning,
            )
        if self.include_ertjobs:
            warn(
                "The 'include_ertjobs' option is deprecated and should be removed.",
                UserWarning,
            )
        if self.depth_reference:
            warn(
                "The 'depth_reference' key has no function. Use the 'domain_reference' "
                "key instead to set the reference for the given 'vertical_domain'.",
                UserWarning,
            )
        if self.meta_format:
            warn(
                "The 'meta_format' option is deprecated and should be removed. "
                "Metadata will only be exported in yaml format.",
                UserWarning,
            )

        if any(
            (
                self.arrow_fformat,
                self.cube_fformat,
                self.grid_fformat,
                self.surface_fformat,
                self.dict_fformat,
            )
        ):
            warn(
                "The options 'arrow_fformat', 'cube_fformat', 'grid_fformat', "
                "'surface_fformat', and 'dict_fformat' are deprecated. These options "
                "no longer affect the exported file format and can safely be removed.",
                UserWarning,
            )

    def _validate_and_establish_fmucontext(self) -> None:
        """
        Validate the given 'fmu_context' input. if not explicitly given it
        will be established based on the presence of ERT environment variables.
        """

        if self.fmu_context and self.fmu_context.lower() == "case_symlink_realization":
            raise ValueError(
                "fmu_context is set to 'case_symlink_realization', which is no "
                "longer a supported option. Recommended workflow is to export "
                "your data as preprocessed ouside of FMU, and re-export the data "
                "with fmu_context='case' using a PRE_SIMULATION ERT workflow. "
                "If needed, forward_models in ERT can be set-up to create symlinks "
                "out into the individual realizations.",
                UserWarning,
            )

        if self.fmu_context == "preprocessed":
            warnings.warn(
                "Using the 'fmu_context' argument with value 'preprocessed' is "
                "deprecated and will be removed in the future. Use the more explicit "
                "'preprocessed' argument instead: ExportData(preprocessed=True)",
                FutureWarning,
            )
            self.preprocessed = True
            self.fmu_context = None

        env_fmu_context = get_fmu_context_from_environment()
        logger.debug("fmu context from input is %s", self.fmu_context)
        logger.debug("fmu context from environment is %s", env_fmu_context)

        # use fmu_context from environment if not explicitly set
        if self.fmu_context is None:
            logger.info(
                "fmu_context is established from environment variables %s",
                env_fmu_context,
            )
            self.fmu_context = env_fmu_context

        elif not env_fmu_context:
            logger.warning(
                "Requested fmu_context is <%s> but since this is detected as a non "
                "FMU run, the actual context is force set to None",
                self.fmu_context,
            )
            self.fmu_context = None

        else:
            self.fmu_context = enums.FMUContext(self.fmu_context.lower())
            logger.info("FMU context is %s", self.fmu_context)

        if self.preprocessed and self.fmu_context == enums.FMUContext.realization:
            raise ValueError(
                "Can't export preprocessed data in a fmu_context='realization'."
            )

        if (
            self.fmu_context != enums.FMUContext.case
            and env_fmu_context == enums.FMUContext.case
        ):
            warn(
                "fmu_context is set to 'realization', but unable to detect "
                "ERT runpath from environment variable. "
                "Did you mean fmu_context='case'?",
                UserWarning,
            )

    def _update_check_settings(self, newsettings: dict) -> None:
        """Update instance settings (properties) from other routines."""
        # if no newsettings (kwargs) this rutine is not needed
        if not newsettings:
            return

        warnings.warn(
            "In the future it will not be possible to enter following arguments "
            f"inside the export() / generate_metadata() methods: {list(newsettings)}. "
            "Please move them up to initialization of the ExportData instance.",
            FutureWarning,
        )
        logger.info("Try new settings %s", newsettings)

        if "config" in newsettings:
            raise ValueError("Cannot have 'config' outside instance initialization")

        available_arguments = [field.name for field in fields(ExportData)]
        for setting, value in newsettings.items():
            if setting not in available_arguments:
                logger.warning("Unsupported key, raise an error")
                raise ValidationError(f"The input key '{setting}' is not supported")

            setattr(self, setting, value)
            logger.info("New setting OK for %s", setting)

        self._show_deprecations_or_notimplemented()
        self._validate_and_establish_fmucontext()

        self._runcontext = self._get_runcontext()
        self._classification = self._get_classification()
        self._rep_include = self._get_rep_include()

    def _export_without_metadata(self, obj: types.Inferrable) -> str:
        """
        Export the object without a metadata file. The absolute export path
        is found using the FileDataProvider directly.
        A string with full path to the exported item is returned.
        """
        objdata = objectdata_provider_factory(obj, self)

        absolute_path = self._runcontext.exportroot / objdata.share_path

        export_object_to_file(absolute_path, objdata.export_to_file)
        return str(absolute_path)

    def _export_with_standard_result(
        self, obj: types.Inferrable, standard_result: StandardResult
    ) -> str:
        """Export the object with standard result information in the metadata."""

        if not isinstance(self.config, GlobalConfiguration):
            raise ValidationError(
                "When exporting standard_results it is required to have a valid config."
            )

        objdata = objectdata_provider_factory(obj, self, standard_result)
        metadata = self._generate_export_metadata(objdata)

        outfile = Path(metadata["file"]["absolute_path"])
        metafile = outfile.parent / f".{outfile.name}.yml"

        export_object_to_file(outfile, objdata.export_to_file)
        logger.info("Actual file is:   %s", outfile)

        export_metadata_file(metafile, metadata)

        if self._runcontext.inside_fmu:
            update_export_manifest(outfile, casepath=self._runcontext.casepath)

        return str(outfile)

    def _generate_export_metadata(self, objdata: ObjectDataProvider) -> dict[str, Any]:
        """Generate metadata for the provided ObjectDataProvider"""
        fmudata = (
            FmuProvider(
                runcontext=self._runcontext,
                model=(
                    self.config.model
                    if isinstance(self.config, GlobalConfiguration)
                    else None
                ),
                workflow=self.workflow,
                object_share_path=objdata.share_path,
            )
            if self._runcontext.inside_fmu
            else None
        )

        return generate_export_metadata(
            objdata=objdata,
            dataio=self,
            fmudata=fmudata,
        ).model_dump(mode="json", exclude_none=True, by_alias=True)

    # ==================================================================================
    # Public methods:
    # ==================================================================================

    def generate_metadata(
        self,
        obj: types.Inferrable,
        compute_md5: bool = True,
        **kwargs: object,
    ) -> dict:
        """Generate and return the complete metadata for a provided object.

        An object may be a map, 3D grid, cube, table, etc which is of a known and
        supported type.

        Examples of such known types are XTGeo objects (e.g. a RegularSurface),
        a Pandas Dataframe, a PyArrow table, etc.

        Args:
            obj: XTGeo instance, a Pandas Dataframe instance or other supported object.
            compute_md5: Deprecated, a MD5 checksum will always be computed.
            **kwargs: Using other ExportData() input keys is now deprecated, input the
                arguments when initializing the ExportData() instance instead.

        Returns:
            A dictionary with all metadata.
        """

        logger.info("Generate metadata...")
        logger.info("KW args %s", kwargs)

        if not isinstance(self.config, GlobalConfiguration):
            warnings.warn(
                "From fmu.dataio version 3.0 it will not be possible to produce "
                "metadata when the global config is invalid.",
                FutureWarning,
            )

        if not compute_md5:
            warnings.warn(
                "Using the 'compute_md5=False' option to prevent an MD5 checksum "
                "from being computed is now deprecated. This option has no longer "
                "an effect and will be removed in the near future.",
                UserWarning,
            )

        self._update_check_settings(kwargs)

        if isinstance(obj, str | Path):
            if self.casepath is None:
                raise TypeError("No 'casepath' argument provided")
            _future_warning_preprocessed()
            return ExportPreprocessedData(
                casepath=self.casepath,
                is_observation=self.is_observation,
            ).generate_metadata(obj)

        objdata = objectdata_provider_factory(obj, self)
        return self._generate_export_metadata(objdata)

    def export(
        self,
        obj: types.Inferrable,
        return_symlink: bool = False,
        **kwargs: Any,
    ) -> str:
        """Export data objects of 'known' type to FMU storage solution with metadata.

        This function will also collect the data spesific class metadata. For "classic"
        files, the metadata will be stored i a YAML file with same name stem as the
        data, but with a . in front and "yml" and suffix, e.g.::

            top_volantis--depth.gri
            .top_volantis--depth.gri.yml

        Args:
            obj: XTGeo instance, a Pandas Dataframe instance or other supported object.
            **kwargs: Using other ExportData() input keys is now deprecated, input the
                arguments when initializing the ExportData() instance instead.

        Returns:
            String: full path to exported item.
        """
        if return_symlink:
            warnings.warn(
                "The return_symlink option is deprecated and can safely be removed."
            )
        if isinstance(obj, str | Path):
            self._update_check_settings(kwargs)
            if self.casepath is None:
                raise TypeError("No 'casepath' argument provided")
            _future_warning_preprocessed()
            return ExportPreprocessedData(
                casepath=self.casepath,
                is_observation=self.is_observation,
            ).export(obj)

        logger.info("Object type is: %s", type(obj))
        self._update_check_settings(kwargs)

        # should only export object if config is not valid
        if not isinstance(self.config, GlobalConfiguration):
            warnings.warn("Data will be exported, but without metadata.", UserWarning)
            return self._export_without_metadata(obj)

        objdata = objectdata_provider_factory(obj, self)
        metadata = self._generate_export_metadata(objdata)

        outfile = Path(metadata["file"]["absolute_path"])
        metafile = outfile.parent / f".{outfile.name}.yml"

        export_object_to_file(outfile, objdata.export_to_file)
        logger.info("Actual file is:   %s", outfile)

        export_metadata_file(metafile, metadata)
        logger.info("Metadata file is: %s", metafile)

        if self._runcontext.inside_fmu:
            update_export_manifest(outfile, casepath=self._runcontext.casepath)

        return str(outfile)
