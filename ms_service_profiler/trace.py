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

import argparse
import os
from ms_service_profiler.utils.log import logger, set_log_level
from ms_service_profiler.tracer.otlp_forward_service import OTLPForwarderService


def main():
    parser = argparse.ArgumentParser(description='MS Server Profiler Trace')
    parser.add_argument(
        '--log-level',
        type=str,
        default='info',
        choices=['debug', 'info', 'warning', 'error', 'fatal', 'critical'],
        help='Log level to print',
    )
    parser.add_argument(
        '--perfetto-output',
        type=str,
        default=None,
        help='Optional Chrome Trace JSON file for Hook spans. vLLM OTLP tracing must also be enabled.',
    )
    args = parser.parse_args()
    set_log_level(args.log_level)

    get_uid = getattr(os, "getuid", lambda: -1)
    if os.name != "nt" and get_uid() == 0:
        logger.warning(
            "Security Warning: Running with root privileges may compromise system security. "
            "Run the program as the user who runs MindIE."
        )

    try:
        if args.perfetto_output:
            from ms_service_profiler.tracer.perfetto_forward_service import PerfettoForwarderService

            service = PerfettoForwarderService(args.perfetto_output)
        else:
            service = OTLPForwarderService()
        service.start()
    except Exception as e:
        logger.error("Start trace service failed: %s", e)


if __name__ == '__main__':
    main()
