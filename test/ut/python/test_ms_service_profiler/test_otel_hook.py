# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2026 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------

"""Unit tests for the public-API-only OpenTelemetry Hook backend."""

from unittest.mock import MagicMock, patch

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanContext, TraceFlags, TraceState

from ms_service_profiler.tracer.otel_hook import HookSpanContext, OpenTelemetryHookBackend
from ms_service_profiler.tracer.perfetto_socket import (
    PERFETTO_EVENT_MAGIC,
    PerfettoSpanProcessor,
    serialize_readable_span,
)


def _remote_context():
    return HookSpanContext(
        SpanContext(
            trace_id=int("1" * 32, 16),
            span_id=int("2" * 16, 16),
            is_remote=True,
            trace_flags=TraceFlags.SAMPLED,
            trace_state=TraceState(),
        )
    )


def test_backend_reuses_active_global_provider_and_exports_custom_span():
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    backend = OpenTelemetryHookBackend()

    with (
        patch.dict("os.environ", {"MS_TRACE_ENABLE": "1"}, clear=True),
        patch.object(backend, "_active_global_provider", return_value=provider),
        patch("ms_service_profiler.tracer.otel_hook.PerfettoSocketSender.is_available", return_value=False),
    ):
        span = backend.start_span(
            "vllm.scheduler.schedule",
            "Schedule",
            links=[(_remote_context(), "request-1")],
        )
        span.set_attribute("batch.request_count", 1)
        span.end(True)

    finished = exporter.get_finished_spans()
    assert len(finished) == 1
    assert finished[0].name == "vllm.scheduler.schedule"
    assert finished[0].attributes["batch.request_count"] == 1
    assert len(finished[0].links) == 1
    assert finished[0].links[0].attributes["request.id"] == "request-1"


def test_backend_requires_vllm_global_provider_and_never_creates_private_provider():
    backend = OpenTelemetryHookBackend()

    with (
        patch.dict("os.environ", {"MS_TRACE_ENABLE": "1"}, clear=True),
        patch.object(backend, "_active_global_provider", return_value=None),
        patch("ms_service_profiler.tracer.otel_hook.logger.warning") as warning,
    ):
        span = backend.start_span("schedule", "Schedule")

    assert not span.is_recording
    warning.assert_called_once()
    assert "--otlp-traces-endpoint" in warning.call_args.args[0]


def test_backend_disabled_is_noop_without_touching_provider():
    backend = OpenTelemetryHookBackend()
    with patch.dict("os.environ", {}, clear=True), patch.object(backend, "_active_global_provider") as active_provider:
        span = backend.start_span("schedule", "Schedule")

    assert not span.is_recording
    active_provider.assert_not_called()


def test_perfetto_processor_registration_failure_does_not_disable_jaeger_provider():
    backend = OpenTelemetryHookBackend()
    provider = MagicMock()
    provider.add_span_processor.side_effect = RuntimeError("registration failed")
    processor = MagicMock()

    with (
        patch.dict("os.environ", {"MS_TRACE_ENABLE": "1"}, clear=True),
        patch.object(backend, "_active_global_provider", return_value=provider),
        patch("ms_service_profiler.tracer.otel_hook.PerfettoSocketSender.is_available", return_value=True),
        patch("ms_service_profiler.tracer.otel_hook.PerfettoSpanProcessor", return_value=processor),
    ):
        assert backend._get_provider() is provider

    processor.shutdown.assert_called_once()


def test_backend_missing_otel_dependency_is_fail_open():
    backend = OpenTelemetryHookBackend()
    with (
        patch.dict("os.environ", {"MS_TRACE_ENABLE": "1"}, clear=True),
        patch("ms_service_profiler.tracer.otel_hook._OTEL_AVAILABLE", False),
    ):
        span = backend.start_span("schedule", "Schedule")

    assert not span.is_recording


def test_readable_span_serialization_uses_version_neutral_perfetto_packet():
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    span = provider.get_tracer("Execute").start_span("vllm.model.execute")
    span.set_attribute("request.ids", ["request-1"])
    span.end()

    packet = serialize_readable_span(exporter.get_finished_spans()[0])

    assert packet.startswith(PERFETTO_EVENT_MAGIC)
    assert b'"name":"vllm.model.execute"' in packet


def test_perfetto_processor_exports_only_msserviceprofiler_hook_spans():
    provider = TracerProvider()
    sender = MagicMock()
    provider.add_span_processor(PerfettoSpanProcessor(sender))

    with patch.dict("os.environ", {"MS_TRACE_ENABLE": "1"}, clear=True):
        native_span = provider.get_tracer("vllm.engine").start_span("native-vllm")
        native_span.end()
        hook_span = provider.get_tracer("ms_service_profiler.hook.Schedule").start_span("hook-schedule")
        hook_span.end()

    sender.submit.assert_called_once()
    assert b'"name":"hook-schedule"' in sender.submit.call_args.args[0]
