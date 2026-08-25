# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2026 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------

"""Thin around-call adapters that add business semantics to vLLM OTel spans."""

import functools
import inspect
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterable

from ms_service_profiler.tracer.hook_runtime import get_hook_trace_runtime


SUPPORTED_KINDS = {"INTERNAL", "SERVER", "CLIENT", "PRODUCER", "CONSUMER"}
SUPPORTED_ADAPTERS = {"call", "request", "request_context", "schedule", "model", "output"}


@dataclass(frozen=True)
class HookTraceSpec:
    name: str
    domain: str
    kind: str = "INTERNAL"
    adapter: str = "call"


@dataclass
class _TraceInvocation:
    args: tuple
    kwargs: dict
    return_value: Any = None


def parse_hook_trace_spec(item: Dict[str, Any], method_name: str):
    raw = item.get("trace")
    if raw is None or raw is False:
        return None
    if raw is True:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("trace must be a mapping, true, false, or omitted")
    name = raw.get("name", item.get("name", method_name))
    domain = raw.get("domain", item.get("domain", "Tracing"))
    kind = str(raw.get("kind", "INTERNAL")).upper()
    adapter = raw.get("adapter", "call")
    if not isinstance(name, str) or not name:
        raise ValueError("trace.name must be a non-empty string")
    if not isinstance(domain, str) or not domain:
        raise ValueError("trace.domain must be a non-empty string")
    if kind not in SUPPORTED_KINDS:
        raise ValueError("trace.kind is unsupported")
    if adapter not in SUPPORTED_ADAPTERS:
        raise ValueError("trace.adapter is unsupported")
    return HookTraceSpec(name, domain, kind, adapter)


def _request_id_from_call(invocation: _TraceInvocation) -> str:
    if "request_id" in invocation.kwargs:
        return str(invocation.kwargs["request_id"])
    if len(invocation.args) > 1:
        candidate = invocation.args[1]
        request_id = getattr(candidate, "request_id", candidate)
        if isinstance(request_id, (str, int)):
            return str(request_id)
    return ""


def _trace_headers_from_call(invocation: _TraceInvocation):
    headers = invocation.kwargs.get("trace_headers")
    if headers:
        return headers
    for candidate in invocation.args[1:]:
        headers = getattr(candidate, "trace_headers", None)
        if headers:
            return headers
    return None


def _request_ids_from_scheduler_output(output) -> Iterable[str]:
    return list((getattr(output, "num_scheduled_tokens", None) or {}).keys())


def _request_ids_from_engine_outputs(outputs) -> Iterable[str]:
    result = []
    for output in outputs or []:
        request_id = getattr(output, "request_id", None)
        if request_id is not None:
            result.append(str(request_id))
    return result


def _request_ids_on_enter(spec: HookTraceSpec, invocation: _TraceInvocation) -> Iterable[str]:
    if spec.adapter == "model" and len(invocation.args) > 1:
        return _request_ids_from_scheduler_output(invocation.args[1])
    if spec.adapter == "output" and len(invocation.args) > 1:
        return _request_ids_from_engine_outputs(invocation.args[1])
    return []


def _add_exit_semantics(runtime, span, spec: HookTraceSpec, invocation: _TraceInvocation) -> None:
    if spec.adapter == "schedule":
        request_ids = list(_request_ids_from_scheduler_output(invocation.return_value))
        span.set_attribute("batch.request_count", len(request_ids))
        total_tokens = getattr(invocation.return_value, "total_num_scheduled_tokens", None)
        if total_tokens is not None:
            span.set_attribute("batch.scheduled_tokens", total_tokens)

    if spec.adapter == "output" and len(invocation.args) > 1:
        for output in invocation.args[1] or []:
            if getattr(output, "finish_reason", None) is not None:
                runtime.finish_request(getattr(output, "request_id", ""), True)


@contextmanager
def _trace_scope(spec: HookTraceSpec, invocation: _TraceInvocation):
    """Surround one call without using the profiling context-hook engine."""
    runtime = get_hook_trace_runtime()
    if not runtime.enabled:
        yield
        return

    if spec.adapter == "request":
        request_id = _request_id_from_call(invocation)
        if request_id:
            runtime.start_request(request_id, _trace_headers_from_call(invocation))
        try:
            yield
        except BaseException:
            if request_id:
                runtime.finish_request(request_id)
            raise
        return

    if spec.adapter == "request_context":
        request_id = _request_id_from_call(invocation)
        if request_id:
            runtime.register_request_context(request_id, _trace_headers_from_call(invocation))
        yield
        return

    # OTel links are immutable. Scheduler request IDs are available only in
    # its return value, so create the completed span after the call.
    if spec.adapter == "schedule":
        start_time_ns = time.time_ns()
        try:
            yield
        except BaseException as exception:
            span = runtime.start_span(spec.name, spec.domain, spec.kind, start_time_ns=start_time_ns)
            span.end(False, str(exception), time.time_ns())
            raise
        else:
            request_ids = list(_request_ids_from_scheduler_output(invocation.return_value))
            span = runtime.start_span(
                spec.name,
                spec.domain,
                spec.kind,
                request_ids=request_ids,
                start_time_ns=start_time_ns,
            )
            _add_exit_semantics(runtime, span, spec, invocation)
            span.end(True, end_time_ns=time.time_ns())
        return

    request_ids = list(_request_ids_on_enter(spec, invocation))
    span = runtime.start_span(spec.name, spec.domain, spec.kind, request_ids=request_ids)
    token = runtime.activate(span)
    try:
        yield
    except BaseException as exception:
        span.end(False, str(exception))
        raise
    else:
        _add_exit_semantics(runtime, span, spec, invocation)
        span.end(True)
    finally:
        runtime.deactivate(token)


def make_trace_around_factory(spec: HookTraceSpec):
    """Create one outer wrapper factory; it never changes profiling handlers."""

    def factory(next_func, original_func):
        if inspect.iscoroutinefunction(original_func):

            @functools.wraps(original_func)
            async def async_wrapper(*args, **kwargs):
                invocation = _TraceInvocation(args, kwargs)
                with _trace_scope(spec, invocation):
                    invocation.return_value = await next_func(*args, **kwargs)
                return invocation.return_value

            return async_wrapper

        @functools.wraps(original_func)
        def sync_wrapper(*args, **kwargs):
            invocation = _TraceInvocation(args, kwargs)
            with _trace_scope(spec, invocation):
                invocation.return_value = next_func(*args, **kwargs)
            return invocation.return_value

        return sync_wrapper

    factory.__name__ = "trace_around_{}_{}".format(spec.domain, spec.name).replace(".", "_")
    return factory
