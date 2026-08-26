# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2026 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------

"""Tests for converting Hook span packets to Perfetto/Chrome Trace."""

import json
from unittest.mock import patch

import pytest

from ms_service_profiler.tracer.perfetto_exporter import (
    PerfettoTraceExporter,
    validate_perfetto_output_path,
)
from ms_service_profiler.tracer.perfetto_socket import PERFETTO_EVENT_MAGIC


def _make_packet(name, trace_id, span_id, start_ns, end_ns, link=None):
    payload = {
        "name": name,
        "category": "ms_service_profiler.hook.Tracing",
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": "",
        "start_time_ns": start_ns,
        "end_time_ns": end_ns,
        "kind": 1,
        "status": 1,
        "attributes": {"process.pid": 100, "thread.id": 200, "request.id": "request-1"},
        "resource_attributes": {"service.name": "vllm"},
        "links": [{"trace_id": link[0], "span_id": link[1]}] if link else [],
    }
    return PERFETTO_EVENT_MAGIC + json.dumps(payload).encode("utf-8")


def test_perfetto_exporter_writes_complete_events_and_cross_trace_flows(tmp_path):
    output = tmp_path / "hook_trace.json"
    with patch("ms_service_profiler.tracer.perfetto_exporter.is_legal_args_path_string", return_value=True):
        exporter = PerfettoTraceExporter(str(output))
    request_trace_id = "1" * 32
    request_span_id = "2" * 16
    schedule_trace_id = "3" * 32
    schedule_span_id = "4" * 16

    assert exporter.export(
        _make_packet(
            "vllm.scheduler.schedule",
            schedule_trace_id,
            schedule_span_id,
            2_000_000,
            3_000_000,
            link=(request_trace_id, request_span_id),
        )
    )
    # The linked request may arrive later; pending flow resolution must still
    # connect it to the already exported scheduler span.
    assert exporter.export(_make_packet("vllm.request", request_trace_id, request_span_id, 1_000_000, 4_000_000))
    exporter.close()

    events = json.loads(output.read_text(encoding="utf-8"))
    complete = [event for event in events if event["ph"] == "X"]
    flow = [event for event in events if event["ph"] in ("s", "f")]
    assert [event["name"] for event in complete] == ["vllm.scheduler.schedule", "vllm.request"]
    assert complete[0]["pid"] == 100
    assert complete[0]["tid"] == 200
    assert complete[0]["dur"] == 1000
    assert complete[0]["args"]["trace_id"] == schedule_trace_id
    assert len(flow) == 2
    assert flow[0]["id"] == flow[1]["id"]


def test_perfetto_exporter_accepts_normalized_hook_packet(tmp_path):
    output = tmp_path / "otel_hook_trace.json"
    with patch("ms_service_profiler.tracer.perfetto_exporter.is_legal_args_path_string", return_value=True):
        exporter = PerfettoTraceExporter(str(output))

    assert exporter.export(_make_packet("vllm.model.execute", "1" * 32, "2" * 16, 1_000_000, 2_000_000))
    exporter.close()

    events = json.loads(output.read_text(encoding="utf-8"))
    assert events[0]["name"] == "vllm.model.execute"
    assert events[0]["pid"] == 100
    assert events[0]["dur"] == 1000


def test_perfetto_exporter_rejects_legacy_binary_otlp_payload(tmp_path):
    output = tmp_path / "hook_trace.json"
    with patch("ms_service_profiler.tracer.perfetto_exporter.is_legal_args_path_string", return_value=True):
        exporter = PerfettoTraceExporter(str(output))

    assert exporter.export(b"binary-otlp") is False
    exporter.close()
    assert json.loads(output.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("path", ["trace.txt", "trace.json;"])
def test_perfetto_output_rejects_invalid_path(path):
    with pytest.raises(ValueError):
        validate_perfetto_output_path(path)
