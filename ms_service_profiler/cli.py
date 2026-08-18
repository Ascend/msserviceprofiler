# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2026 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------

import argparse
import os
import sys
from importlib import metadata
from pathlib import Path


TOOL_NAME = "msserviceprofiler"
PACKAGE_NAME = "ms_service_profiler"
REPO_URL = "https://gitcode.com/Ascend/msserviceprofiler"


ROOT_HELP = """Description:
  Analyze, split, compare, and parse MindStudio Service Profiler data for
  service-oriented inference performance tuning.

Usage:
  msserviceprofiler <command> [options]
  msserviceprofiler --help
  msserviceprofiler --version

Commands:
  analyze    Analyze service profiler data and export summary results
  parse      Parse profiler data into db, csv, or json outputs
  split      Split prefill/decode request data for targeted analysis
  compare    Compare performance profiles between two runs

Optional arguments:
  -h, --help       Show this help message and exit
  -V, --version    Show version information and exit

Examples:
  # Parse profiler data into the default ./output directory
  msserviceprofiler parse --input-path ./profiling_data

  # Analyze profiler data and save csv/json/db results
  msserviceprofiler analyze --input-path ./profiling_data --output-path ./output

  # Compare two profiling runs
  msserviceprofiler compare ./profiling_data/before ./profiling_data/after

Output:
  <output-path>/profiler.db
  <output-path>/*.csv
  <output-path>/*.json

Troubleshooting:
  - Use 'msserviceprofiler <command> --help' to view command-specific options.
  - If input data is not found, check that --input-path points to the directory
    containing profiler output files.
  See also: docs/zh/msserviceprofiler_serving_tuning_instruct.md
"""


class RootHelpParser(argparse.ArgumentParser):
    def format_help(self):
        if self.prog == TOOL_NAME:
            return ROOT_HELP
        return super().format_help()


class VersionAction(argparse.Action):
    def __init__(self, option_strings, dest=argparse.SUPPRESS, default=argparse.SUPPRESS, **kwargs):
        help_text = kwargs.pop("help", None)
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=0,
            default=default,
            help=help_text,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        parser._print_message(f"{get_version_text()}\n", sys.stdout)
        parser.exit()


def create_parser():
    parser = RootHelpParser(
        prog=TOOL_NAME,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="[MindStudio] msserviceprofiler command line tool",
    )
    parser.add_argument("-V", "--version", action=VersionAction, help="Show version information and exit")
    return parser


def is_root_cli_request(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    return not argv or argv[0] in ("-h", "--help", "-V", "--version")


def create_subcommand_parser():
    parser = create_parser()
    if is_root_cli_request():
        run_parser(parser)
        return parser, None
    return parser, parser.add_subparsers(help="sub-command help")


def get_version_text():
    dependencies = _format_dependencies()
    if dependencies:
        dependencies = "\n\nDependencies:\n" + dependencies

    return (
        "=================================================================\n"
        "                   >>>>>   MindStudio   <<<<<\n"
        "    THE END-TO-END TOOLCHAIN TO UNLEASH HUAWEI ASCEND COMPUTE\n"
        "=================================================================\n"
        f"{TOOL_NAME} {_get_package_version()} ({_get_git_commit()})\n"
        "Copyright (C) 2026 Huawei Technologies Co., Ltd.\n"
        "License: Mulan PSL v2.\n\n"
        "Build Info:\n"
        f"  Date : {_get_build_date()}\n"
        f"  Repo : {REPO_URL}"
        f"{dependencies}"
    )


def _get_package_version():
    try:
        return metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return _read_pyproject_version()


def _read_pyproject_version():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    try:
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("version"):
                return stripped.split("=", 1)[1].strip().strip("\"'")
    except OSError:
        pass
    return "unknown"


def _get_git_commit():
    repo_dir = Path(__file__).resolve().parents[1]
    try:
        head = (repo_dir / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref_path = repo_dir / ".git" / head.split(" ", 1)[1]
            commit = ref_path.read_text(encoding="utf-8").strip()
        else:
            commit = head
    except (IndexError, OSError):
        return "unknown"
    return commit[:12] if len(commit) >= 7 else "unknown"


def _get_build_date():
    return os.environ.get("MS_SERVICE_PROFILER_BUILD_DATE", "unknown")


def _format_dependencies():
    deps = [
        ("Pandas", "pandas"),
        ("NumPy", "numpy"),
        ("OpenTelemetry", "opentelemetry-api"),
        ("PyYAML", "PyYAML"),
    ]
    lines = []
    for display_name, package_name in deps:
        try:
            dep_version = metadata.version(package_name)
        except metadata.PackageNotFoundError:
            continue
        lines.append(f"  {display_name:<13}: {dep_version}")
    return "\n".join(lines)


def run_parser(parser):
    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args=args)
        return
    parser.print_help(sys.stdout)
