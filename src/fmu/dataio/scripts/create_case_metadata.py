#!/usr/bin/env python

"""Create FMU case metadata and register case on Sumo (optional).

This script is intended to be run through an ERT HOOK PRESIM workflow.

Script will parse global variables from the template location. If
pointed towards the produced global_variables, fmu-config should run
before this script to make sure global_variables is updated."""

from __future__ import annotations

import argparse
import logging
import warnings
from pathlib import Path
from typing import Final

import ert
import yaml

from fmu.dataio import CreateCaseMetadata

logger: Final = logging.getLogger(__name__)
logger.setLevel(logging.CRITICAL)

# This documentation is compiled into ert's internal docs
DESCRIPTION = """
WF_CREATE_CASE_METADATA will create case metadata with fmu-dataio for storing on disk
and on Sumo.
"""

EXAMPLES = """
Create an ERT workflow e.g. called ``ert/bin/workflows/create_case_metadata`` with the
contents::
  WF_CREATE_CASE_METADATA <caseroot> <casename> <username> <sumo> <sumo_env>
  ...where
    <ert_caseroot> (Path): Absolute path to root of the case, typically <SCRATCH>/<US...
    <ert_config_path> (Path): Absolute path to ERT config, typically /project/etc/etc
    <ert_casename> (str): The ERT case name, typically <CASE_DIR>
    <sumo> (optional) (bool): If passed, do not register case on Sumo. Default: False
    <sumo_env> (str) (optional): Sumo environment to use. Default: "prod"
    <global_variables_path> (str): Path to global_variables relative to config path
    <verbosity> (str): Set log level. Default: WARNING
"""


def main() -> None:
    """Entry point from command line

    When script is called from an ERT workflow, it will be called through the 'run'
    method on the WfCreateCaseMetadata class. This context is the intended usage.
    The command line entry point is still included, to clarify the difference and
    for debugging purposes.
    """
    parser = get_parser()
    commandline_args = parser.parse_args()
    create_case_metadata_main(commandline_args)


class WfCreateCaseMetadata(ert.ErtScript):
    """A class with a run() function that can be registered as an ERT plugin.

    This is used for the ERT workflow context. It is prefixed 'Wf' to avoid a
    potential naming collisions in fmu-dataio."""

    # pylint: disable=too-few-public-methods
    def run(self, *args: str) -> None:
        # pylint: disable=no-self-use
        """Parse arguments and call _create_case_metadata_main()"""
        parser = get_parser()
        workflow_args = parser.parse_args(args)
        create_case_metadata_main(workflow_args)


def create_case_metadata_main(args: argparse.Namespace) -> None:
    """Create the case metadata and register case on Sumo."""
    check_arguments(args)
    logger.setLevel(args.verbosity)

    case_metadata_path = create_metadata(args)
    if args.sumo:
        logger.info("Registering case on Sumo (%s)", args.sumo_env)
        register_on_sumo(args.sumo_env, case_metadata_path)

    logger.debug("create_case_metadata.py has finished.")


def check_arguments(args: argparse.Namespace) -> None:
    """Do basic sanity checks of input"""
    logger.debug("Checking input arguments")
    logger.debug("Arguments: %s", args)

    if not Path(args.ert_caseroot).is_absolute():
        logger.debug("Argument ert_caseroot was not absolute: %s", args.ert_caseroot)
        raise ValueError("ert_caseroot must be an absolute path")

    if args.ert_username:
        warnings.warn(
            "The argument 'ert_username' is deprecated. It is no "
            "longer used and can safely be removed.",
            FutureWarning,
        )


def create_metadata(args: argparse.Namespace) -> str:
    """Create the case metadata and print them to the disk"""
    with open(
        Path(args.ert_config_path) / args.global_variables_path, encoding="utf-8"
    ) as f:
        global_variables = yaml.safe_load(f)

    return CreateCaseMetadata(
        config=global_variables,
        rootfolder=args.ert_caseroot,
        casename=args.ert_casename,
    ).export()


def register_on_sumo(
    sumo_env: str,
    case_metadata_path: str,
) -> str:
    """Register the case on Sumo by sending the case metadata"""
    from fmu.sumo.uploader import CaseOnDisk, SumoConnection

    sumo_conn = SumoConnection(sumo_env)
    logger.debug("Sumo connection established")
    case = CaseOnDisk(case_metadata_path, sumo_conn)
    sumo_id = case.register()

    logger.info("Case registered on Sumo with ID: %s", sumo_id)
    return sumo_id


def get_parser() -> argparse.ArgumentParser:
    """Construct parser object."""
    parser = argparse.ArgumentParser()
    parser.add_argument("ert_caseroot", type=str, help="Absolute path to the case root")
    parser.add_argument(
        "ert_config_path", type=str, help="ERT config path (<CONFIG_PATH>)"
    )
    parser.add_argument("ert_casename", type=str, help="ERT case name (<CASE>)")
    parser.add_argument(
        "ert_username",
        type=str,
        help="Deprecated and can safely be removed",
    )
    parser.add_argument(
        "--sumo",
        action="store_true",
        help="If passed, register the case on Sumo.",
    )
    parser.add_argument("--sumo_env", type=str, help="Sumo environment", default="prod")
    parser.add_argument(
        "--global_variables_path",
        type=str,
        help="Directly specify path to global variables relative to ert config path",
        default="../../fmuconfig/output/global_variables.yml",
    )
    parser.add_argument(
        "--verbosity", type=str, help="Set log level", default="WARNING"
    )
    return parser


@ert.plugin(name="fmu_dataio")
def legacy_ertscript_workflow(config: ert.WorkflowConfigs) -> None:
    """Hook the WfCreateCaseMetadata class with documentation into ERT."""
    workflow = config.add_workflow(WfCreateCaseMetadata, "WF_CREATE_CASE_METADATA")
    workflow.parser = get_parser
    workflow.description = DESCRIPTION
    workflow.examples = EXAMPLES
    workflow.category = "export"


if __name__ == "__main__":
    main()
