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

from unittest.mock import patch, MagicMock
from ms_service_profiler.trace import main


class TestMain:
    @patch('ms_service_profiler.trace.argparse.ArgumentParser')
    @patch('ms_service_profiler.trace.set_log_level')
    @patch('ms_service_profiler.trace.OTLPForwarderService')
    def test_main_without_perfetto_keeps_legacy_otlp_service(
        self, mock_otlp_service, mock_set_log_level, mock_arg_parser
    ):
        mock_args = MagicMock(log_level='info', perfetto_output=None)
        mock_arg_parser.return_value.parse_args.return_value = mock_args
        mock_service_instance = MagicMock()
        mock_otlp_service.return_value = mock_service_instance
        main()
        mock_set_log_level.assert_called_once_with('info')
        mock_otlp_service.assert_called_once_with()
        mock_service_instance.start.assert_called_once()

    @patch('ms_service_profiler.trace.argparse.ArgumentParser')
    @patch('ms_service_profiler.trace.set_log_level')
    @patch('ms_service_profiler.trace.OTLPForwarderService')
    @patch('ms_service_profiler.tracer.perfetto_forward_service.PerfettoForwarderService')
    def test_main_with_perfetto_uses_independent_hook_service(
        self, mock_perfetto_service, mock_otlp_service, mock_set_log_level, mock_arg_parser
    ):
        mock_args = MagicMock(log_level='debug', perfetto_output='/tmp/hook_trace.json')
        mock_arg_parser.return_value.parse_args.return_value = mock_args
        main()

        mock_set_log_level.assert_called_once_with('debug')
        mock_perfetto_service.assert_called_once_with('/tmp/hook_trace.json')
        mock_perfetto_service.return_value.start.assert_called_once()
        mock_otlp_service.assert_not_called()
