# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2026 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------

import signal
from unittest.mock import call, patch

from ms_service_profiler.tracer.perfetto_forward_service import PerfettoForwarderService


@patch("ms_service_profiler.tracer.perfetto_forward_service.signal.signal")
@patch("ms_service_profiler.tracer.perfetto_forward_service.AbstractSocketServer")
@patch("ms_service_profiler.tracer.perfetto_forward_service.PerfettoTraceExporter")
def test_perfetto_forwarder_uses_independent_socket(mock_exporter, mock_socket, mock_signal):
    service = PerfettoForwarderService("hook_trace.json")

    mock_exporter.assert_called_once_with("hook_trace.json")
    mock_socket.assert_called_once_with(
        socket_name="MSP_PERFETTO_SOCKET",
        buffer_size=4096,
        max_listen_num=8,
        socket_timeout=1,
        max_queue_size=100000,
        warning_queue_size=10000,
    )
    mock_signal.assert_has_calls(
        [
            call(signal.SIGINT, service._handle_signal),
            call(signal.SIGTERM, service._handle_signal),
        ]
    )


@patch("ms_service_profiler.tracer.perfetto_forward_service.signal.signal")
@patch("ms_service_profiler.tracer.perfetto_forward_service.AbstractSocketServer")
@patch("ms_service_profiler.tracer.perfetto_forward_service.PerfettoTraceExporter")
def test_perfetto_forwarder_exports_hook_packets_and_closes(mock_exporter, mock_socket, _):
    socket_instance = mock_socket.return_value
    exporter_instance = mock_exporter.return_value
    service = PerfettoForwarderService("hook_trace.json")
    packet = b"hook-packet"
    reads = iter([packet, None])

    def get_data():
        value = next(reads)
        if value == packet:
            service._stop_event.set()
        return value

    socket_instance.get_data.side_effect = get_data
    service.start()

    socket_instance.start.assert_called_once()
    exporter_instance.export.assert_called_once_with(packet)
    socket_instance.stop.assert_called_once()
    exporter_instance.close.assert_called_once()
