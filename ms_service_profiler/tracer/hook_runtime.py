# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2026 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------

"""Request correlation and lifecycle for OpenTelemetry Hook spans."""

import os
import threading
from collections import OrderedDict
from dataclasses import dataclass
from itertools import islice
from typing import Iterable, Optional

from .otel_hook import HookSpanContext, HookTraceSpan, get_hook_tracer_backend, new_noop_hook_span


MAX_INFLIGHT_REQUESTS = 10000
MAX_LINKS_PER_SPAN = 128


@dataclass
class _RequestTrace:
    context: HookSpanContext


class HookTraceRuntime:
    def __init__(self, backend=None):
        self._backend = backend or get_hook_tracer_backend()
        self._requests = OrderedDict()
        self._lock = threading.RLock()

    @property
    def enabled(self) -> bool:
        return self._backend.enabled

    def start_span(
        self,
        name: str,
        domain: str,
        kind: str = "INTERNAL",
        attributes=None,
        request_ids: Optional[Iterable[str]] = None,
        start_time_ns: Optional[int] = None,
    ) -> HookTraceSpan:
        if not self.enabled:
            return new_noop_hook_span()
        normalized_request_ids = [str(item) for item in islice(request_ids or (), MAX_LINKS_PER_SPAN)]
        links = self.request_links(normalized_request_ids)
        span = self._backend.start_span(name, domain, kind, links=links, start_time_ns=start_time_ns)
        if span.is_recording:
            span.set_attribute("process.pid", os.getpid())
            native_id = getattr(threading, "get_native_id", threading.get_ident)()
            span.set_attribute("thread.id", native_id)
            if normalized_request_ids:
                span.set_attribute("request.ids", normalized_request_ids)
            for key, value in (attributes or {}).items():
                span.set_attribute(key, value)
        return span

    @staticmethod
    def activate(span: HookTraceSpan):
        return span.activate() if span is not None else None

    @staticmethod
    def deactivate(token) -> None:
        HookTraceSpan.deactivate(token)

    def _store_request(self, request_id: str, request_trace: _RequestTrace) -> None:
        with self._lock:
            self._requests.pop(request_id, None)
            self._requests[request_id] = request_trace
            if len(self._requests) > MAX_INFLIGHT_REQUESTS:
                self._requests.popitem(last=False)

    def register_request_context(self, request_id: str, trace_headers=None) -> bool:
        request_id = str(request_id)
        context = self._backend.context_from_headers(trace_headers)
        if not context.is_valid:
            context = self._backend.current_context()
        if not context.is_valid:
            return False
        self._store_request(request_id, _RequestTrace(context=context))
        return True

    def start_request(self, request_id: str, trace_headers=None) -> bool:
        """Register vLLM's real request context; never create a duplicate root span."""
        return self.register_request_context(request_id, trace_headers)

    def finish_request(self, request_id: str, success: bool = True, message: str = "") -> bool:
        with self._lock:
            request_trace = self._requests.pop(str(request_id), None)
        return request_trace is not None

    def request_links(self, request_ids: Iterable[str]):
        with self._lock:
            request_traces = [
                (str(request_id), self._requests.get(str(request_id)))
                for request_id in islice(request_ids, MAX_LINKS_PER_SPAN)
            ]
        return [
            (request_trace.context, request_id)
            for request_id, request_trace in request_traces
            if request_trace is not None and request_trace.context.is_valid
        ]

    def request_context(self, request_id: str) -> Optional[HookSpanContext]:
        with self._lock:
            request_trace = self._requests.get(str(request_id))
        return request_trace.context if request_trace is not None else None

    def clear(self) -> None:
        with self._lock:
            self._requests.clear()
        self._backend.shutdown()


_HOOK_TRACE_RUNTIME = HookTraceRuntime()


def get_hook_trace_runtime() -> HookTraceRuntime:
    return _HOOK_TRACE_RUNTIME


def _set_hook_trace_runtime_for_test(runtime) -> None:
    global _HOOK_TRACE_RUNTIME
    _HOOK_TRACE_RUNTIME = runtime
