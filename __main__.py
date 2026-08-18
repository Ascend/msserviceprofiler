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

from ms_service_profiler.cli import create_subcommand_parser, run_parser


def main():
    parser, subparsers = create_subcommand_parser()
    if subparsers is None:
        return

    from msservice_advisor.msservice_advisor import advisor
    from ms_serviceparam_optimizer.ms_serviceparam_optimizer.optimizer import optimizer
    from ms_serviceparam_optimizer.ms_serviceparam_optimizer.train import source_to_train
    from ms_service_profiler import compare, split, analyze, parse

    source_to_train.arg_parse(subparsers)
    optimizer.arg_parse(subparsers)
    advisor.arg_parse(subparsers)
    analyze.arg_parse(subparsers)
    parse.arg_parse(subparsers)
    split.arg_parse(subparsers)
    compare.arg_parse(subparsers)
    run_parser(parser)


if __name__ == "__main__":
    main()
