# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2026 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------

"""Hook tracing that reuses only the active vLLM OpenTelemetry provider."""

import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Tuple

from ms_service_profiler.tracer.perfetto_socket import HOOK_SCOPE_PREFIX, PerfettoSocketSender, PerfettoSpanProcessor
from ms_service_profiler.utils.log import logger


MAX_ATTRIBUTE_COUNT = 32
MAX_ATTRIBUTE_KEY_LENGTH = 128
MAX_ATTRIBUTE_VALUE_LENGTH = 1024
PERFETTO_REGISTRATION_RETRY_INTERVAL_SECONDS = 5.0


try:
    from opentelemetry import context as otel_context
    from opentelemetry import trace
    from opentelemetry.trace import Link, NonRecordingSpan, SpanKind, Status, StatusCode
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    _OTEL_AVAILABLE = True
except ImportError:
    otel_context = None
    trace = None
    Link = None
    NonRecordingSpan = None
    SpanKind = None
    Status = None
    StatusCode = None
    TraceContextTextMapPropagator = None
    _OTEL_AVAILABLE = False


SPAN_KINDS = {
    "INTERNAL": "INTERNAL",
    "SERVER": "SERVER",
    "CLIENT": "CLIENT",
    "PRODUCER": "PRODUCER",
    "CONSUMER": "CONSUMER",
}


@dataclass(frozen=True)
class HookSpanContext:
    native: Any = None

    @property
    def is_valid(self) -> bool:
        return bool(self.native is not None and getattr(self.native, "is_valid", False))

    @property
    def trace_id(self) -> str:
        return format(self.native.trace_id, "032x") if self.is_valid else ""

    @property
    def span_id(self) -> str:
        return format(self.native.span_id, "016x") if self.is_valid else ""


class HookTraceSpan:
    """Fail-open facade over an OTel span owned by vLLM's provider."""

    def __init__(self, span=None):
        self._span = span
        native_context = span.get_span_context() if span is not None else None
        self.context = HookSpanContext(native_context)
        self._ended = False
        self._attribute_count = 0
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return bool(self._span is not None and not self._ended and self._span.is_recording())

    def set_attribute(self, key, value) -> None:
        if not self.is_recording or self._attribute_count >= MAX_ATTRIBUTE_COUNT:
            return
        if not isinstance(key, str) or not key or len(key) > MAX_ATTRIBUTE_KEY_LENGTH:
            return
        safe_value = _safe_attribute(value)
        if safe_value is None:
            return
        try:
            self._span.set_attribute(key, safe_value)
            self._attribute_count += 1
        except Exception as exc:
            logger.debug("Failed to set Hook tracing attribute: %s", exc)

    def activate(self):
        if not self.is_recording or not _OTEL_AVAILABLE:
            return None
        try:
            return otel_context.attach(trace.set_span_in_context(self._span))
        except Exception as exc:
            logger.debug("Failed to activate Hook tracing span: %s", exc)
            return None

    @staticmethod
    def deactivate(token) -> None:
        if token is None or not _OTEL_AVAILABLE:
            return
        try:
            otel_context.detach(token)
        except Exception as exc:
            logger.debug("Failed to deactivate Hook tracing span: %s", exc)

    def end(self, success: bool = True, message: str = "", end_time_ns: Optional[int] = None) -> None:
        with self._lock:
            if self._span is None or self._ended:
                return
            span = self._span
            self._ended = True
        try:
            status_code = StatusCode.OK if success else StatusCode.ERROR
            span.set_status(Status(status_code, str(message)[:MAX_ATTRIBUTE_VALUE_LENGTH] or None))
            span.end(end_time=end_time_ns)
        except Exception as exc:
            logger.debug("Failed to end Hook tracing span: %s", exc)


def new_noop_hook_span() -> HookTraceSpan:
    return HookTraceSpan()


def _safe_attribute(value):
    if isinstance(value, (str, bool, int, float)):
        return value[:MAX_ATTRIBUTE_VALUE_LENGTH] if isinstance(value, str) else value
    if isinstance(value, (list, tuple)):
        values = []
        for item in value[:MAX_ATTRIBUTE_COUNT]:
            if not isinstance(item, (str, bool, int, float)):
                return None
            values.append(item[:MAX_ATTRIBUTE_VALUE_LENGTH] if isinstance(item, str) else item)
        return values
    return None


class OpenTelemetryHookBackend:
    """Use vLLM's provider; never create or shut down a provider."""

    def __init__(self):
        self._lock = threading.RLock()
        self._perfetto_providers = set()
        self._perfetto_retry_after = {}
        self._warned_unavailable = False
        self._warned_provider_missing = False

    @property
    def enabled(self) -> bool:
        return os.environ.get("MS_TRACE_ENABLE") == "1"

    @staticmethod
    def _active_global_provider():
        if not _OTEL_AVAILABLE:
            return None
        provider = trace.get_tracer_provider()
        return provider if callable(getattr(provider, "add_span_processor", None)) else None

    @property
    def reuses_global_provider(self) -> bool:
        return self._active_global_provider() is not None

    def _get_provider(self):
        if not self.enabled:
            return None
        if not _OTEL_AVAILABLE:
            if not self._warned_unavailable:
                logger.warning("OpenTelemetry is unavailable; vLLM Hook tracing is disabled")
                self._warned_unavailable = True
            return None

        provider = self._active_global_provider()
        if provider is None:
            if not self._warned_provider_missing:
                logger.warning("vLLM OpenTelemetry provider is unavailable; start vLLM with --otlp-traces-endpoint")
                self._warned_provider_missing = True
            return None

        identity = id(provider)
        with self._lock:
            perfetto_registered = identity in self._perfetto_providers
        try:
            perfetto_available = PerfettoSpanProcessor is not None and PerfettoSocketSender.is_available()
        except Exception as exc:
            logger.debug("Failed to probe Perfetto forwarder: %s", exc)
            perfetto_available = False
        if not perfetto_registered and perfetto_available:
            now = time.monotonic()
            with self._lock:
                retry_after = self._perfetto_retry_after.get(identity, 0.0)
                if identity not in self._perfetto_providers and now >= retry_after:
                    processor = None
                    try:
                        processor = PerfettoSpanProcessor()
                        provider.add_span_processor(processor)
                    except Exception as exc:
                        self._perfetto_retry_after[identity] = now + PERFETTO_REGISTRATION_RETRY_INTERVAL_SECONDS
                        if processor is not None:
                            try:
                                processor.shutdown()
                            except Exception as shutdown_exc:
                                logger.debug("Failed to shut down Perfetto span processor: %s", shutdown_exc)
                        logger.debug("Failed to register Perfetto span processor: %s", exc)
                    else:
                        self._perfetto_providers.add(identity)
                        self._perfetto_retry_after.pop(identity, None)
        return provider

    @staticmethod
    def context_from_headers(headers) -> HookSpanContext:
        if not _OTEL_AVAILABLE or not headers:
            return HookSpanContext()
        try:
            extracted = TraceContextTextMapPropagator().extract(dict(headers), context=otel_context.Context())
            return HookSpanContext(trace.get_current_span(extracted).get_span_context())
        except Exception as exc:
            logger.debug("Failed to extract Hook tracing context: %s", exc)
            return HookSpanContext()

    @staticmethod
    def current_context() -> HookSpanContext:
        if not _OTEL_AVAILABLE:
            return HookSpanContext()
        try:
            return HookSpanContext(trace.get_current_span().get_span_context())
        except Exception as exc:
            logger.debug("Failed to read current Hook tracing context: %s", exc)
            return HookSpanContext()

    def start_span(
        self,
        name: str,
        domain: str,
        kind: str = "INTERNAL",
        parent: Optional[HookSpanContext] = None,
        links: Optional[Iterable[Tuple[HookSpanContext, str]]] = None,
        start_time_ns: Optional[int] = None,
    ) -> HookTraceSpan:
        provider = self._get_provider()
        if provider is None:
            return new_noop_hook_span()
        try:
            parent_context = None
            if parent is not None and parent.is_valid:
                parent_context = trace.set_span_in_context(NonRecordingSpan(parent.native))
            native_links = [
                Link(link_context.native, {"request.id": str(request_id)})
                for link_context, request_id in links or []
                if link_context is not None and link_context.is_valid
            ]
            native_kind = getattr(SpanKind, SPAN_KINDS.get(kind, "INTERNAL"))
            scope_name = "{}.{}".format(HOOK_SCOPE_PREFIX, domain or "tracing")
            span = provider.get_tracer(scope_name).start_span(
                name=name,
                context=parent_context,
                kind=native_kind,
                links=native_links,
                start_time=start_time_ns,
            )
            return HookTraceSpan(span)
        except Exception as exc:
            logger.debug("Failed to start Hook tracing span %s: %s", name, exc)
            return new_noop_hook_span()

    def shutdown(self) -> None:
        # The provider and its processors are owned by vLLM.
        return None


_HOOK_TRACER_BACKEND = OpenTelemetryHookBackend()


def get_hook_tracer_backend() -> OpenTelemetryHookBackend:
    return _HOOK_TRACER_BACKEND


def _set_hook_tracer_backend_for_test(backend) -> None:
    global _HOOK_TRACER_BACKEND
    _HOOK_TRACER_BACKEND = backend
