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

from importlib.metadata import entry_points

from ms_service_profiler.cli import create_subcommand_parser, run_parser


def _load_entries():
    eps = entry_points()
    ep_group = 'ms_service_profiler_plugins'
    plugin_eps = eps.select(group=ep_group)

    if plugin_eps:
        yield from (ep.load() for ep in plugin_eps)
        return

    from ms_service_profiler import analyze, compare, parse, split

    yield analyze.arg_parse
    yield compare.arg_parse
    yield parse.arg_parse
    yield split.arg_parse


def main():
    parser, subparsers = create_subcommand_parser()
    if subparsers is None:
        return

    for entry_fn in _load_entries():
        entry_fn(subparsers)

    run_parser(parser)


if __name__ == "__main__":
    main()
