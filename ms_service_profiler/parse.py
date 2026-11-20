# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------
import os
import sys
import argparse


from ms_service_profiler.task.task import Task
from ms_service_profiler.exporters.factory import ExporterFactory
from ms_service_profiler.plugins import custom_plugins
from ms_service_profiler.utils.log import logger, set_log_level
from ms_service_profiler.exporters.utils import (
    create_sqlite_db,
    check_input_dir_valid,
    check_output_path_valid,
    is_root,
)
from ms_service_profiler.task.task_register import get_dag
from ms_service_profiler.task.task_manager import tasks_run
from ms_service_profiler.task.task import register


class CliLogo:
    """MindStudio CLI logo printer."""

    RESET = "\033[0m"
    DIM_GRAY = "\033[38;5;240m"
    BOLD_WHITE = "\033[1;97m"
    HIGHLIGHT = "\033[48;5;21;38;5;46m"  # green on blue

    def _should_use_color_logo(self) -> bool:
        """Check if we should use colored logo with ANSI escape codes."""
        if not sys.stderr.isatty():
            return False
        term = os.environ.get("TERM")
        return term is not None and term not in ("dumb", "unknown")

    def _render_simple(self) -> str:
        """Return the plain ASCII logo."""
        return (
            "================================================================="
            "\n"
            "                   >>>>>   MindStudio   <<<<<"
            "\n"
            "    THE END-TO-END TOOLCHAIN TO UNLEASH HUAWEI ASCEND COMPUTE"
            "\n"
            "================================================================="
            "\n\n"
        )

    def _render_colored(self) -> str:
        """Return the colored logo with ANSI escape codes."""
        return (
            f"{self.DIM_GRAY}================================================================="
            f"{self.RESET}\n"
            f"{self.BOLD_WHITE}                   >>>>>  "
            f"{self.HIGHLIGHT} MindStudio {self.RESET}{self.BOLD_WHITE}  <<<<<{self.RESET}\n"
            f"{self.BOLD_WHITE}    THE END-TO-END TOOLCHAIN TO UNLEASH HUAWEI ASCEND COMPUTE"
            f"{self.RESET}\n"
            f"{self.DIM_GRAY}================================================================="
            f"{self.RESET}\n\n"
        )

    def print_logo(self) -> None:
        """Print the MindStudio logo to stderr."""
        content = self._render_colored() if self._should_use_color_logo() else self._render_simple()
        sys.stderr.write(content)
        sys.stderr.flush()


def parse(input_path, plugins, exporters, **kwargs):
    # Compatible with blue zone calls
    if is_root():
        logger.warning(
            "Security Warning: Do not run this tool as root. "
            "Running with elevated privileges may compromise system security. "
            "Use a regular user account."
        )
    parse_run(input_path=input_path, exporters=exporters, args=kwargs.get("args"))


def parse_run(input_path, exporters, args=None):
    logger.info('Start to parse.')
    exporter_new = []
    for exporter in exporters:
        if exporter.is_provide(args.format):
            if isinstance(exporter, Task):
                exporter_new.append(exporter)
            else:
                exporter_new.append(exporter(args))
    exporters = exporter_new
    exporter_names = [exporter.name for exporter in exporters]
    for exporter in exporters:
        register(exporter.name)(exporter)

    task_dag, data_source_tasks = get_dag(exporter_names)

    tasks_run(data_source_tasks, task_dag, input_path, args)

    logger.info('Exporter done.')


def _setup_parser_arguments(parser):
    parser.add_argument(
        '--input-path', required=True, type=check_input_dir_valid, help='Path to the folder containing profile data.'
    )
    parser.add_argument(
        '--output-path',
        type=check_output_path_valid,
        default=os.path.join(os.getcwd(), 'output'),
        help='Output file path to save results.',
    )
    parser.add_argument(
        '--log-level',
        type=str,
        default='info',
        choices=['debug', 'info', 'warning', 'error', 'fatal', 'critical'],
        help='Log level to print',
    )
    parser.add_argument(
        '--format', nargs='+', default=['db', 'csv', 'json'], choices=['db', 'csv', 'json'], help='Format to save'
    )
    parser.add_argument('--span', nargs='*', default=None, help='Select target span info')


def arg_parse(subparsers):
    parser = subparsers.add_parser(
        "parse", formatter_class=argparse.ArgumentDefaultsHelpFormatter, help="MS Server Profiler"
    )
    _setup_parser_arguments(parser)
    parser.set_defaults(func=main)


def main(args=None):
    logo = CliLogo()
    logo.print_logo()
    if args is None:
        parser = argparse.ArgumentParser(description='MS Server Profiler')
        _setup_parser_arguments(parser)
        args = parser.parse_args()

    # 初始化日志等级
    set_log_level(args.log_level)

    exporters = ExporterFactory.create_exporters(args)
    if 'db' in args.format and args.span is None:
        create_sqlite_db(args.output_path)

    # 解析数据并导出
    parse(args.input_path, custom_plugins, exporters, args=args)


if __name__ == '__main__':
    main()
