from __future__ import annotations

import copy
import warnings
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import ClassVar, Final, Literal

from pydantic import ValidationError

from fmu.dataio._models.fmu_results.enums import FMUContext
from fmu.dataio._models.fmu_results.fields import Tracklog

from . import _utils, dataio, types
from ._logging import null_logger
from ._metadata import ObjectMetadataExport
from .exceptions import InvalidMetadataError
from .providers.objectdata._provider import objectdata_provider_factory

logger: Final = null_logger(__name__)

# ######################################################################################
# AggregatedData
#
# The AggregatedData is used for making the aggregations from existing data that already
# have valid metadata, i.e. made from ExportData.
#
# Hence this is actually quite different and simpler than ExportData(), which
# needed a lot of info as FmuProvider, FileProvider, ObjectData etc. Here most these
# already known from the input.
#
# For aggregations, the id is normally given as an argument by the external process, and
# by that, be able to give a group of aggregations the same id.
#
# ######################################################################################


@dataclass
class AggregatedData:
    """Instantate AggregatedData object.

    Args:
        aggregation_id: Give an explicit ID for the aggregation. If None, an ID will be
        made based on existing realization uuids.
        casepath: The root folder to the case, default is None. If None, the casepath
            is derived from the first input metadata paths (cf. ``source_metadata``) if
            possible. If given explicitly, the physical casepath folder must exist in
            advance, otherwise a ValueError will be raised.
        source_metadata: A list of individual metadata dictionarys, coming from the
            valid metadata per input element that forms the aggregation.
        operation: A string that describes the operation, e.g. "mean". This is
            mandatory and there is no default.
        tagname: Additional name, as part of file name
    """

    # class variable(s)
    meta_format: ClassVar[Literal["yaml", "json"] | None] = None  # deprecated

    # instance
    aggregation_id: str | None = None
    casepath: str | Path | None = None
    source_metadata: list = field(default_factory=list)
    name: str = ""
    operation: str = ""
    tagname: str = ""
    verbosity: str = "DEPRECATED"  # keep for while

    _metadata: ObjectMetadataExport = field(init=False)
    _metafile: Path = field(default_factory=Path, init=False)

    def __post_init__(self) -> None:
        if self.verbosity != "DEPRECATED":
            warnings.warn(
                "Using the 'verbosity' key is now deprecated and will have no "
                "effect and will be removed in near future. Please remove it from the "
                "argument list. Set logging level from client script in the standard "
                "manner instead.",
                UserWarning,
            )
        if self.meta_format:
            warnings.warn(
                "The 'meta_format' option is deprecated and should be removed. "
                "Metadata will only be exported in yaml format.",
                UserWarning,
            )

    @staticmethod
    def _generate_aggr_uuid(uuids: list[str]) -> str:
        """Unless aggregation_id; use existing UUIDs to generate a new UUID."""
        return str(_utils.uuid_from_string("".join(sorted(uuids))))

    def _update_settings(self, newsettings: dict) -> None:
        """Update instance settings (properties) from other routines."""
        logger.info("Try new settings %s", newsettings)

        available_arguments = [field.name for field in fields(AggregatedData)]

        for setting, value in newsettings.items():
            if setting not in available_arguments:
                logger.warning("Unsupported key, raise an error")
                raise ValidationError(f"The input key '{setting}' is not supported")

            setattr(self, setting, value)
            logger.info("New setting OK for %s", setting)

    def _construct_filename(self, template: dict) -> tuple[Path, Path | None]:
        """Construct the paths/filenames for aggregated data.

        These filenames are constructed a bit different than in a forward job, since we
        do not now which folder we 'are in' when doing aggregations. Could possibly also
        be in a cloud setting.

        Hence we use the first input realization as template, e.g.:

        file:
           relative_path: realization-33/iter-0/share/results/maps/x.gri
           absolute_path: /scratch/f/case/realization-33/iter-0/share/results/maps/x.gri

        And from thet we derive/compose the relative and absolute path for the
        aggregated data:

        file:
           relative_path: iter-0/share/results/maps/aggr.gri
           absolute_path: /scratch/f/case/iter-0/share/results/maps/aggr.gri

        The trick is to replace 'realization-*' with nothing and create a new file
        name.

        -----
        However, there are also the scenario that absolute_path are missing (e.g. all
        input realizations are directly made in cloud setting), and we need to
        account for that:

        infile:
           relative_path: realization-33/iter-0/share/results/maps/x.gri
           absolute_path: none

        file:
           relative_path: iter-0/share/results/maps/aggr.gri
           absolute_path: none

        -----
        Finally, a user given casepath (casepath is not None) should replace the current
        root part in the files. Like this:

        infile:
           relative_path: realization-33/iter-0/share/results/maps/x.gri
           absolute_path: /scratch/f/case/realization-33/iter-0/share/results/maps/x.gri

        casepath = /scratch/f/othercase

        result:
           relative_path: iter-0/share/results/maps/aggr.gri
           absolute_path: /scratch/f/othercase/iter-0/share/results/maps/aggrd.gri

        """
        logger.info("Construct file name for the aggregation...")
        realiname = template["fmu"]["realization"]["name"]
        relpath = template["file"]["relative_path"]

        if template["file"].get("absolute_path", None):
            abspath = template["file"]["absolute_path"]
        else:
            abspath = None

        logger.info("First input realization relpath is: %s ", relpath)
        logger.info("First input realization abspath is: %s ", abspath)

        if self.casepath:
            casepath = Path(self.casepath)
            if not casepath.exists():
                raise ValueError(
                    f"The given casepath {casepath} does not exist. "
                    "It must exist in advance!"
                )
            abspath = str(casepath / relpath)

        relpath = relpath.replace(realiname + "/", "")
        relpath = Path(relpath)
        if abspath:
            abspath = abspath.replace(realiname + "/", "")
            abspath = Path(abspath)

        suffix = relpath.suffix
        stem = relpath.stem

        usename = stem + "--" + self.operation
        if not self.name:
            warnings.warn("Input name is not given, will assume <usename>", UserWarning)
        else:
            usename = self.name

        if self.tagname:
            usename = usename + "--" + self.tagname

        relname = (relpath.parent / usename).with_suffix(suffix)

        absname = None
        if abspath:
            absname = (abspath.parent / usename).with_suffix(suffix)

        logger.info("New relpath is: %s ", relname)
        logger.info("New abspath is: %s ", absname)

        return relname, absname

    def _set_metadata(
        self,
        obj: types.Inferrable,
        real_ids: list[int],
        uuids: list[str],
        compute_md5: bool = True,
    ) -> None:
        logger.info(
            "self.aggregation is %s (%s)",
            self.aggregation_id,
            type(self.aggregation_id),
        )

        if not compute_md5:
            warnings.warn(
                "Using the 'compute_md5=False' option to prevent an MD5 checksum "
                "from being computed is now deprecated. This option has no longer "
                "an effect and will be removed in the near future.",
                UserWarning,
            )

        if self.aggregation_id is None:
            self.aggregation_id = self._generate_aggr_uuid(uuids)
        elif not isinstance(self.aggregation_id, str):
            raise ValueError("aggregation_id must be a string")

        if not self.operation:
            raise ValueError("The 'operation' key has no value")

        # use first as template
        template = copy.deepcopy(self.source_metadata[0])

        relpath, abspath = self._construct_filename(template)

        # fmu.realization shall not be used
        del template["fmu"]["realization"]

        template["fmu"]["aggregation"] = {}
        template["fmu"]["aggregation"]["operation"] = self.operation
        template["fmu"]["aggregation"]["realization_ids"] = real_ids
        template["fmu"]["aggregation"]["id"] = self.aggregation_id

        # fmu.context.stage should be 'ensemble'
        template["fmu"]["context"]["stage"] = FMUContext.ensemble.value

        # next, the new object will trigger update of: 'file', 'data' (some fields) and
        # 'tracklog'.

        # Make a temporary config from template to be allowed to
        # initialize a temporary ExportData without warnings so that we can get to the
        # objectdata_provider
        config = {
            "access": {  # only asset and classification should be picked up
                "asset": template["access"]["asset"],
                "classification": template["access"]["classification"],
            },
            "masterdata": template["masterdata"],
            "model": template["fmu"]["model"],
        }
        dummy_content = "depth"  # will not be used, but will silence warning
        etemp = dataio.ExportData(config=config, name=self.name, content=dummy_content)

        objdata = objectdata_provider_factory(obj=obj, dataio=etemp)

        checksum_md5, size = _utils.compute_md5_and_size_from_objdata(objdata)

        template["tracklog"] = [Tracklog.initialize()[0]]
        template["file"] = {
            "relative_path": str(relpath),
            "absolute_path": str(abspath) if abspath else None,
            "checksum_md5": checksum_md5,
            "size_bytes": size,
        }

        # data section
        if self.name:
            template["data"]["name"] = self.name
        if self.tagname:
            template["data"]["tagname"] = self.tagname
        if bbox := objdata.get_bbox():
            template["data"]["bbox"] = bbox

        try:
            self._metadata = ObjectMetadataExport.model_validate(template)
        except ValidationError as err:
            raise InvalidMetadataError(
                f"The existing metadata for the aggregated data is invalid. "
                f"Detailed information: \n{str(err)}"
            ) from err

    # ==================================================================================
    # Public methods:
    # ==================================================================================

    def generate_metadata(
        self,
        obj: types.Inferrable,
        compute_md5: bool = True,
        skip_null: bool = True,
        **kwargs: object,
    ) -> dict:
        """Generate metadata for the aggregated data.

        This is a quite different and much simpler operation than the ExportData()
        version, as here most metadata for each input element are already known. Hence,
        the metadata for the first element in the input list is used as template.

        Args:

            obj: The map, 3D grid, table, etc instance.

            compute_md5: If True, an md5 sum for the file will be created. This involves
                a temporary export of the data, and may be time consuming for large
                data.

            skip_null: This input parameter has been deprecated. If set to False,
              a deprecation warning will be raised.
            **kwargs: See AggregatedData() arguments; initial will be overridden by
                settings here.
        """
        logger.info("Generate metadata for class")
        self._update_settings(kwargs)

        if not skip_null:
            warnings.warn(
                "The input parameter 'skip_null' has been deprecated. "
                "Setting this to False will not have any effect."
            )

        # get input realization numbers:
        real_ids = []
        uuids = []
        for conf in self.source_metadata:
            try:
                rid = conf["fmu"]["realization"]["id"]
                xuuid = conf["fmu"]["realization"]["uuid"]
            except Exception as e:
                raise ValidationError(
                    f"Seems that input config are not valid: {e}"
                ) from e

            real_ids.append(rid)
            uuids.append(xuuid)

        # first config file as template
        self._set_metadata(obj, real_ids, uuids, compute_md5)

        return self._metadata.model_dump(mode="json", exclude_none=True, by_alias=True)

    def generate_aggregation_metadata(
        self,
        obj: types.Inferrable,
        compute_md5: bool = True,
        skip_null: bool = True,
        **kwargs: object,
    ) -> dict:
        """Alias method name, see ``generate_metadata``"""
        warnings.warn(
            "This method is deprecated and will be removed in the future. "
            "Use the 'generate_metadata()' method directly instead.",
            FutureWarning,
        )
        return self.generate_metadata(
            obj, compute_md5=compute_md5, skip_null=skip_null, **kwargs
        )

    def export(self, obj: types.Inferrable, **kwargs: object) -> str:
        """Export aggregated file with metadata to file.

        Args:
            obj: Aggregated object to export, e.g. a XTGeo RegularSurface
            **kwargs: See AggregatedData() arguments; initial will be overridden by
                settings here.
        Returns:
            String: full path to exported item.
        """
        self._update_settings(kwargs)

        metadata = self.generate_metadata(obj, compute_md5=True)

        abspath = metadata["file"].get("absolute_path", None)

        if not abspath:
            raise OSError(
                "The absolute_path is None, hence no export is possible. "
                "Use the ``casepath`` key to provide a valid absolute path."
            )

        outfile = Path(abspath)
        outfile.parent.mkdir(parents=True, exist_ok=True)
        metafile = outfile.parent / ("." + str(outfile.name) + ".yml")

        logger.info("Export to file and export metadata file.")
        _utils.export_file(obj, outfile)

        _utils.export_metadata_file(metafile, metadata)
        logger.info("Actual file is:   %s", outfile)
        logger.info("Metadata file is: %s", metafile)

        return str(outfile)
