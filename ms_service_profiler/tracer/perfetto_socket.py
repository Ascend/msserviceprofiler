# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2026 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------

"""Non-blocking OpenTelemetry Span delivery to the Perfetto forwarder."""

import json
import os
import queue
import socket
import threading
from typing import Any, Dict, Optional

from ms_service_profiler.utils.log import logger


PERFETTO_SOCKET_NAME = "MSP_PERFETTO_SOCKET"
PERFETTO_EVENT_MAGIC = b"MSPF_PERFETTO_V1\n"
HOOK_SCOPE_PREFIX = "ms_service_profiler.hook"
MAX_QUEUE_SIZE = 10000
MAX_ATTRIBUTE_COUNT = 64
MAX_ATTRIBUTE_LENGTH = 2048


def _safe_value(value: Any):
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    if isinstance(value, str):
        return value[:MAX_ATTRIBUTE_LENGTH]
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value[:MAX_ATTRIBUTE_COUNT]]
    return str(value)[:MAX_ATTRIBUTE_LENGTH]


def _span_context_ids(span_context) -> Dict[str, str]:
    if span_context is None or not getattr(span_context, "is_valid", False):
        return {"trace_id": "", "span_id": ""}
    return {
        "trace_id": format(span_context.trace_id, "032x"),
        "span_id": format(span_context.span_id, "016x"),
    }


def serialize_readable_span(span) -> bytes:
    """Serialize only the stable ReadableSpan surface used by Perfetto."""
    context_ids = _span_context_ids(span.get_span_context())
    parent_ids = _span_context_ids(getattr(span, "parent", None))
    attributes = {
        str(key)[:MAX_ATTRIBUTE_LENGTH]: _safe_value(value)
        for key, value in list((getattr(span, "attributes", None) or {}).items())[:MAX_ATTRIBUTE_COUNT]
    }
    resource_attributes = {
        str(key)[:MAX_ATTRIBUTE_LENGTH]: _safe_value(value)
        for key, value in list((getattr(getattr(span, "resource", None), "attributes", None) or {}).items())[
            :MAX_ATTRIBUTE_COUNT
        ]
    }
    links = []
    for link in list(getattr(span, "links", None) or [])[:MAX_ATTRIBUTE_COUNT]:
        link_ids = _span_context_ids(getattr(link, "context", None))
        if link_ids["trace_id"] and link_ids["span_id"]:
            links.append(link_ids)
    instrumentation_scope = getattr(span, "instrumentation_scope", None)
    status = getattr(getattr(span, "status", None), "status_code", None)
    kind = getattr(span, "kind", None)
    payload = {
        "name": str(getattr(span, "name", ""))[:MAX_ATTRIBUTE_LENGTH],
        "category": str(getattr(instrumentation_scope, "name", "Tracing"))[:MAX_ATTRIBUTE_LENGTH],
        "trace_id": context_ids["trace_id"],
        "span_id": context_ids["span_id"],
        "parent_span_id": parent_ids["span_id"],
        "start_time_ns": int(getattr(span, "start_time", 0) or 0),
        "end_time_ns": int(getattr(span, "end_time", 0) or 0),
        "kind": int(getattr(kind, "value", kind) or 0),
        "status": int(getattr(status, "value", status) or 0),
        "attributes": attributes,
        "resource_attributes": resource_attributes,
        "links": links,
    }
    return PERFETTO_EVENT_MAGIC + json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class PerfettoSocketSender:
    """Queue Span packets so tracing failures and socket I/O never block inference."""

    def __init__(self, socket_name: str = PERFETTO_SOCKET_NAME):
        self._address = "\0" + socket_name
        self._queue = queue.Queue(MAX_QUEUE_SIZE)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, name="perfetto-span-sender", daemon=True)
        self._thread.start()

    @classmethod
    def is_available(cls, socket_name: str = PERFETTO_SOCKET_NAME) -> bool:
        if os.name != "posix" or not hasattr(socket, "AF_UNIX"):
            return False
        probe = socket.socket(getattr(socket, "AF_UNIX"), socket.SOCK_STREAM)
        probe.settimeout(0.05)
        try:
            probe.connect("\0" + socket_name)
            return True
        except OSError:
            return False
        finally:
            probe.close()

    def submit(self, payload: bytes) -> None:
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            logger.warning("Perfetto tracing queue is full; one Span was discarded")

    def _send(self, payload: bytes) -> None:
        client = socket.socket(getattr(socket, "AF_UNIX"), socket.SOCK_STREAM)
        client.settimeout(0.2)
        try:
            client.connect(self._address)
            client.sendall(len(payload).to_bytes(4, byteorder="big") + payload)
        finally:
            client.close()

    def _run(self) -> None:
        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                payload = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self._send(payload)
            except OSError as exc:
                logger.debug("Perfetto forwarder is unavailable; discarded one Span: %s", exc)

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)


try:
    from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor

    class PerfettoSpanProcessor(SpanProcessor):
        def __init__(self, sender: Optional[PerfettoSocketSender] = None):
            self._sender = sender or PerfettoSocketSender()

        def on_start(self, span, parent_context=None) -> None:
            return None

        def on_end(self, span: ReadableSpan) -> None:
            if os.environ.get("MS_TRACE_ENABLE") != "1":
                return
            scope_name = str(getattr(getattr(span, "instrumentation_scope", None), "name", ""))
            if not scope_name.startswith(HOOK_SCOPE_PREFIX):
                return
            try:
                self._sender.submit(serialize_readable_span(span))
            except Exception as exc:
                logger.debug("Failed to serialize Span for Perfetto: %s", exc)

        def shutdown(self) -> None:
            self._sender.shutdown()

        def force_flush(self, timeout_millis: int = 30000) -> bool:
            return True

except ImportError:
    PerfettoSpanProcessor = None
