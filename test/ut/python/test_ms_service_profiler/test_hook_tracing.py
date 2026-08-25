# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2026 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------

"""Unit tests for vLLM Hook tracing without importing vLLM handlers."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ms_service_profiler.patcher.core.config_loader import ConfigLoader
from ms_service_profiler.patcher.core.trace_hook import HookTraceSpec, make_trace_around_factory
from ms_service_profiler.patcher.vllm import register_service_profiler
from ms_service_profiler.patcher.vllm.service_patcher import VLLMProfiler
from ms_service_profiler.tracer.hook_runtime import MAX_LINKS_PER_SPAN, HookTraceRuntime
from ms_service_profiler.tracer.otel_hook import HookSpanContext


class FakeNativeContext:
    is_valid = True
    trace_id = int("1" * 32, 16)
    span_id = int("2" * 16, 16)


class FakeSpan:
    def __init__(self, context=None):
        self.context = context or HookSpanContext(FakeNativeContext())
        self.attributes = {}
        self.end_calls = []

    @property
    def is_recording(self):
        return not self.end_calls

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def activate(self):
        return "token"

    @staticmethod
    def deactivate(token):
        return None

    def end(self, success=True, message="", end_time_ns=None):
        self.end_calls.append((success, message, end_time_ns))


class FakeBackend:
    enabled = True

    def __init__(self):
        self.calls = []

    @staticmethod
    def context_from_headers(headers):
        return HookSpanContext(FakeNativeContext()) if headers else HookSpanContext()

    @staticmethod
    def current_context():
        return HookSpanContext(FakeNativeContext())

    def start_span(self, name, domain, kind, **kwargs):
        span = FakeSpan()
        self.calls.append((name, domain, kind, kwargs, span))
        return span

    def shutdown(self):
        return None


def _wrap(spec, original):
    return make_trace_around_factory(spec)(original, original)


def test_trace_only_config_does_not_resolve_profiling_handler():
    raw = [
        {
            "symbol": "vllm.v1.engine.async_llm:AsyncLLM.add_request",
            "handler": "ms_service_profiler.patcher.vllm.handlers.v1.request_handlers:add_request_async",
            "trace": {"adapter": "request", "kind": "SERVER"},
        }
    ]
    with (
        patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config", return_value=raw),
        patch("ms_service_profiler.patcher.core.config_loader._resolve_handler_func") as resolve_handler,
    ):
        config = ConfigLoader("unused.yaml", "0.15.0").load_profiling(
            enable_profiling=False,
            enable_tracing=True,
        )

    hooker = config.concrete[raw[0]["symbol"]][0]
    resolve_handler.assert_not_called()
    assert hooker.need_locals is False
    assert hooker.context_hook_funcs == []
    assert hooker.around_hook_factory is not None


def test_builtin_yaml_supplies_trace_hooks_without_vllm_ascend_provider():
    profiler = VLLMProfiler()
    profiler._profiling_active = False
    profiler._tracing_requested = True

    config = profiler._load_profiling_config()

    symbols = set(config.concrete)
    assert "vllm.v1.engine.async_llm:AsyncLLM.add_request" in symbols
    assert "vllm_ascend.core.scheduler:AscendScheduler.schedule" in symbols
    assert "vllm.engine.async_llm_engine:AsyncLLMEngine.add_request" not in symbols
    assert all(hooker.around_hook_factory is not None for hookers in config.concrete.values() for hooker in hookers)


def test_trace_only_plugin_registration_does_not_start_profiling_facilities():
    profiler = MagicMock()
    profiler.initialize.return_value = True
    profiler._profiling_requested = False
    profiler.get_callbacks.return_value = (MagicMock(), MagicMock())
    dynamic_result = SimpleNamespace(is_dynamic=True)
    with (
        patch("ms_service_profiler.patcher.vllm._vllm_profiler", profiler),
        patch(
            "ms_service_profiler.patcher.vllm.mstx_profiler.register_profiler_start_callback",
            return_value=dynamic_result,
        ) as start_callback,
        patch(
            "ms_service_profiler.patcher.vllm.mstx_profiler.register_profiler_stop_callback",
            return_value=dynamic_result,
        ) as stop_callback,
        patch("ms_service_profiler.patcher.vllm.register_torch_profiler") as torch_profiler,
    ):
        register_service_profiler()

    start_callback.assert_not_called()
    stop_callback.assert_not_called()
    torch_profiler.assert_not_called()


def test_trace_only_initialize_skips_metrics_and_profiling_handlers():
    profiler = VLLMProfiler()
    with (
        patch.dict("os.environ", {"MS_TRACE_ENABLE": "1"}, clear=True),
        patch("ms_service_profiler.patcher.vllm.service_patcher.check_profiling_enabled", return_value=False),
        patch("ms_service_profiler.patcher.vllm.service_patcher.setup_vllm_metrics") as setup_metrics,
        patch.object(profiler, "_import_handlers") as import_handlers,
        patch.object(profiler, "enable_hooks") as enable_hooks,
        patch("ms_service_profiler.patcher.vllm.service_patcher.install_symbol_watcher", return_value=True),
    ):
        assert profiler.initialize() is True

    assert profiler._tracing_requested is True
    setup_metrics.assert_not_called()
    import_handlers.assert_not_called()
    enable_hooks.assert_called_once()


def test_profiling_stop_keeps_trace_only_hooks_enabled():
    profiler = VLLMProfiler()
    profiler._profiling_requested = True
    profiler._profiling_active = True
    profiler._tracing_requested = True
    profiler._controller = MagicMock()
    trace_config = MagicMock()
    with patch.object(profiler, "_load_config", return_value=(trace_config, None)):
        _, on_stop = profiler.get_callbacks()
        on_stop()

    assert profiler._profiling_active is False
    profiler._controller.enable.assert_called_once_with(
        profiling_handlers=trace_config,
        metrics_handlers=None,
    )
    profiler._controller.disable.assert_not_called()


def test_profiling_only_keeps_original_controller_callbacks():
    profiler = VLLMProfiler()
    profiler._tracing_requested = False
    profiler._controller = MagicMock()
    expected = (MagicMock(), MagicMock())
    profiler._controller.get_callbacks.return_value = expected

    assert profiler.get_callbacks() == expected
    profiler._controller.get_callbacks.assert_called_once_with(profiler._load_config)


def test_combined_config_uses_one_hooker_with_profiling_and_trace():
    profiling_handler = MagicMock()
    raw = [{"symbol": "vllm.module:Engine.run", "handler": "allowed:handler", "trace": True}]
    with (
        patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config", return_value=raw),
        patch("ms_service_profiler.patcher.core.config_loader._resolve_handler_func", return_value=profiling_handler),
    ):
        config = ConfigLoader("unused.yaml").load_profiling(enable_profiling=True, enable_tracing=True)

    hookers = config.concrete[raw[0]["symbol"]]
    assert len(hookers) == 1
    assert hookers[0].wrap_hook_func is profiling_handler
    assert hookers[0].context_hook_funcs == []
    assert hookers[0].around_hook_factory is not None


def test_duplicate_trace_for_one_symbol_keeps_one_effective_hook():
    raw = [
        {"symbol": "vllm.module:Engine.run", "trace": {"name": "first"}},
        {"symbol": "vllm.module:Engine.run", "trace": {"name": "second"}},
    ]
    with patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config", return_value=raw):
        config = ConfigLoader("unused.yaml").load_profiling(enable_profiling=False, enable_tracing=True)

    assert len(config.concrete[raw[0]["symbol"]]) == 1


def test_runtime_registers_existing_context_and_links_child_span():
    backend = FakeBackend()
    runtime = HookTraceRuntime(backend)

    assert runtime.start_request("request-1", {"traceparent": "valid"}) is True
    schedule_span = runtime.start_span(
        "vllm.scheduler.schedule",
        "Schedule",
        request_ids=["request-1", "request-without-local-state"],
    )

    links = backend.calls[0][3]["links"]
    assert [request_id for _, request_id in links] == ["request-1"]
    assert runtime.finish_request("request-1") is True
    assert schedule_span.is_recording


def test_runtime_limits_iterable_consumption_before_materializing_request_ids():
    backend = FakeBackend()
    runtime = HookTraceRuntime(backend)
    start_consumed = []
    link_consumed = []

    def request_ids(consumed):
        for index in range(MAX_LINKS_PER_SPAN + 10):
            consumed.append(index)
            yield "request-{}".format(index)

    span = runtime.start_span("schedule", "Schedule", request_ids=request_ids(start_consumed))
    runtime.request_links(request_ids(link_consumed))

    assert len(start_consumed) == MAX_LINKS_PER_SPAN
    assert len(link_consumed) == MAX_LINKS_PER_SPAN
    assert len(span.attributes["request.ids"]) == MAX_LINKS_PER_SPAN


def test_schedule_adapter_adds_request_links_and_batch_attributes():
    runtime = MagicMock(enabled=True)
    span = FakeSpan()
    runtime.start_span.return_value = span
    scheduler_output = SimpleNamespace(
        num_scheduled_tokens={"request-1": 4, "request-2": 2},
        total_num_scheduled_tokens=6,
    )

    def original():
        return scheduler_output

    with (
        patch("ms_service_profiler.patcher.core.trace_hook.get_hook_trace_runtime", return_value=runtime),
        patch("ms_service_profiler.patcher.core.trace_hook.time.time_ns", side_effect=[100, 200]),
    ):
        assert _wrap(HookTraceSpec("schedule", "Schedule", adapter="schedule"), original)() is scheduler_output

    runtime.start_span.assert_called_once_with(
        "schedule", "Schedule", "INTERNAL", request_ids=["request-1", "request-2"], start_time_ns=100
    )
    assert span.attributes == {"batch.request_count": 2, "batch.scheduled_tokens": 6}
    assert span.end_calls == [(True, "", 200)]


def test_request_context_adapter_registers_w3c_headers_without_creating_span():
    runtime = MagicMock(enabled=True)
    request = SimpleNamespace(request_id="request-1", trace_headers={"traceparent": "valid"})

    def original(_, req):
        return req.request_id

    with patch("ms_service_profiler.patcher.core.trace_hook.get_hook_trace_runtime", return_value=runtime):
        result = _wrap(HookTraceSpec("add_request", "Request", adapter="request_context"), original)(object(), request)

    assert result == "request-1"
    runtime.register_request_context.assert_called_once_with("request-1", {"traceparent": "valid"})
    runtime.start_span.assert_not_called()


def test_output_adapter_finishes_only_completed_requests():
    runtime = MagicMock(enabled=True)
    span = FakeSpan()
    runtime.start_span.return_value = span
    outputs = [
        SimpleNamespace(request_id="running", finish_reason=None),
        SimpleNamespace(request_id="finished", finish_reason="stop"),
    ]

    def original(_, result):
        return result

    with patch("ms_service_profiler.patcher.core.trace_hook.get_hook_trace_runtime", return_value=runtime):
        assert _wrap(HookTraceSpec("output", "Request", adapter="output"), original)(object(), outputs) is outputs

    runtime.finish_request.assert_called_once_with("finished", True)
    assert span.end_calls == [(True, "", None)]


def test_async_around_hook_preserves_awaitable_result():
    runtime = MagicMock(enabled=True)
    span = FakeSpan()
    runtime.start_span.return_value = span

    async def original(value):
        return value + 1

    with patch("ms_service_profiler.patcher.core.trace_hook.get_hook_trace_runtime", return_value=runtime):
        result = asyncio.run(_wrap(HookTraceSpec("execute", "Execute"), original)(1))

    assert result == 2
    assert span.end_calls == [(True, "", None)]
