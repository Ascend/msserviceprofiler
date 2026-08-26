# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2026 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------

"""Standalone receiver for Hook span packets; independent of legacy OTLP."""

import signal
import threading

from ms_service_profiler.tracer.perfetto_exporter import PerfettoTraceExporter
from ms_service_profiler.tracer.perfetto_socket import PERFETTO_SOCKET_NAME
from ms_service_profiler.tracer.socket_server import AbstractSocketServer
from ms_service_profiler.utils.log import logger


SOCKET_BUFFER_SIZE = 4096
SOCKET_TIMEOUT = 1
MAX_LISTEN_NUM = 8
MAX_QUEUE_SIZE = 100000
WARNING_QUEUE_SIZE = 10000
POLL_INTERVAL_SECONDS = 0.05


class PerfettoForwarderService:
    """Receive only msserviceprofiler Hook spans and write Chrome Trace JSON."""

    def __init__(self, output_path: str):
        self._stop_event = threading.Event()
        self._stopped = False
        self._exporter = PerfettoTraceExporter(output_path)
        self._socket_server = AbstractSocketServer(
            socket_name=PERFETTO_SOCKET_NAME,
            buffer_size=SOCKET_BUFFER_SIZE,
            max_listen_num=MAX_LISTEN_NUM,
            socket_timeout=SOCKET_TIMEOUT,
            max_queue_size=MAX_QUEUE_SIZE,
            warning_queue_size=WARNING_QUEUE_SIZE,
        )
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        logger.info("Receive signal %s, quit...", signum)
        self._stop_event.set()

    def _drain(self) -> None:
        while True:
            data = self._socket_server.get_data()
            if not data:
                return
            self._exporter.export(data)

    def start(self) -> None:
        try:
            self._socket_server.start()
            logger.info("Start PerfettoForwarderService success, running...")
            while not self._stop_event.is_set():
                data = self._socket_server.get_data()
                if data:
                    self._exporter.export(data)
                else:
                    self._stop_event.wait(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            logger.info("Receive KeyboardInterrupt, quit...")
        except Exception as exc:
            logger.error("Unexpected Perfetto forwarder error: %s", exc)
        finally:
            self.stop()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._stop_event.set()
        self._socket_server.stop()
        self._drain()
        self._exporter.close()
        logger.info("Stop PerfettoForwarderService success.")
