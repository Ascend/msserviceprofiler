# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2026 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------

"""Convert Hook span packets into Perfetto-compatible Chrome Trace JSON."""

import json
import os
import stat
import threading
from collections import defaultdict
from typing import Dict, Iterable, List

from ms_service_profiler.utils.file_open_check import is_legal_args_path_string
from ms_service_profiler.utils.log import logger
from ms_service_profiler.tracer.perfetto_socket import PERFETTO_EVENT_MAGIC


MAX_TRACKED_SPANS = 100000


def validate_perfetto_output_path(path: str) -> str:
    """Return a normalized safe JSON path and create only its parent directory."""
    if not isinstance(path, str) or not path.lower().endswith(".json"):
        raise ValueError("--perfetto-output must point to a .json file")
    normalized = os.path.abspath(os.path.expanduser(path))
    if not is_legal_args_path_string(normalized):
        raise ValueError("--perfetto-output contains unsupported characters")
    parent = os.path.dirname(normalized) or os.getcwd()
    os.makedirs(parent, mode=0o750, exist_ok=True)
    if os.path.islink(normalized):
        raise ValueError("--perfetto-output cannot be a symbolic link")
    if os.path.exists(normalized):
        file_stat = os.stat(normalized)
        if not stat.S_ISREG(file_stat.st_mode):
            raise ValueError("--perfetto-output must be a regular file")
        if hasattr(os, "geteuid") and file_stat.st_uid != os.geteuid():
            raise PermissionError("--perfetto-output must be owned by the current user")
    return normalized


class PerfettoTraceExporter:
    """Append complete Chrome Trace events while keeping the JSON file valid."""

    def __init__(self, output_path: str):
        self.output_path = validate_perfetto_output_path(output_path)
        flags = os.O_CREAT | os.O_TRUNC | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.output_path, flags, 0o640)
        self._file = os.fdopen(descriptor, "w+", encoding="utf-8")
        self._file.write("[]")
        self._file.flush()
        self._has_events = False
        self._closed = False
        self._lock = threading.RLock()
        self._span_positions = {}
        self._pending_links = defaultdict(list)

    def export(self, binary_data: bytes) -> bool:
        try:
            if not binary_data.startswith(PERFETTO_EVENT_MAGIC):
                raise ValueError("unsupported Perfetto packet")
            payload = json.loads(binary_data[len(PERFETTO_EVENT_MAGIC) :].decode("utf-8"))
            events = self._convert_normalized_span(payload)
            self._append_events(events)
            return True
        except Exception as exc:
            logger.warning("Export Hook trace to Perfetto failed: %s", exc)
            return False

    def _convert_normalized_span(self, span: Dict) -> List[Dict]:
        attributes = dict(span.get("attributes") or {})
        pid = int(attributes.pop("process.pid", os.getpid()))
        tid = int(attributes.pop("thread.id", 0))
        start_us = int(span.get("start_time_ns", 0)) / 1000
        duration_us = max(int(span.get("end_time_ns", 0)) - int(span.get("start_time_ns", 0)), 0) / 1000
        trace_id = str(span.get("trace_id", ""))
        span_id = str(span.get("span_id", ""))
        resource_attributes = dict(span.get("resource_attributes") or {})
        service_name = span.get("service_name") or resource_attributes.get("service.name", "ms_service_profiler")
        args = dict(attributes)
        args.update(
            {
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": str(span.get("parent_span_id", "")),
                "span.kind": int(span.get("kind", 0)),
                "span.status": int(span.get("status", 0)),
                "service.name": service_name,
            }
        )
        for key, value in resource_attributes.items():
            args.setdefault("resource.{}".format(key), value)
        events = [
            {
                "name": span.get("name", ""),
                "cat": span.get("category", "Tracing"),
                "ph": "X",
                "ts": start_us,
                "dur": duration_us,
                "pid": pid,
                "tid": tid,
                "args": args,
            }
        ]
        key = (trace_id, span_id)
        position = (pid, tid, start_us)
        self._remember_position(key, position)
        for pending in self._pending_links.pop(key, []):
            events.extend(self._make_flow_events(key, position, *pending))
        for link in span.get("links") or []:
            source_key = (str(link.get("trace_id", "")), str(link.get("span_id", "")))
            flow_id = "{}:{}:{}".format(source_key[0], source_key[1], span_id)
            source_position = self._span_positions.get(source_key)
            destination = (pid, tid, start_us, flow_id)
            if source_position is None:
                if len(self._pending_links) < MAX_TRACKED_SPANS:
                    self._pending_links[source_key].append(destination)
            else:
                events.extend(self._make_flow_events(source_key, source_position, *destination))
        return events

    @staticmethod
    def _make_flow_events(source_key, source_position, dest_pid, dest_tid, dest_ts, flow_id):
        source_pid, source_tid, source_ts = source_position
        name = "request.link"
        return [
            {
                "name": name,
                "cat": "Tracing.Flow",
                "ph": "s",
                "ts": source_ts,
                "pid": source_pid,
                "tid": source_tid,
                "id": flow_id,
                "args": {"source.span_id": source_key[1]},
            },
            {
                "name": name,
                "cat": "Tracing.Flow",
                "ph": "f",
                "ts": dest_ts,
                "pid": dest_pid,
                "tid": dest_tid,
                "id": flow_id,
                "bp": "e",
            },
        ]

    def _remember_position(self, key, position) -> None:
        if len(self._span_positions) >= MAX_TRACKED_SPANS:
            oldest_key = next(iter(self._span_positions))
            self._span_positions.pop(oldest_key, None)
        self._span_positions[key] = position

    def _append_events(self, events: Iterable[Dict]) -> None:
        encoded = [json.dumps(event, ensure_ascii=False, separators=(",", ":")) for event in events]
        if not encoded:
            return
        with self._lock:
            if self._closed:
                return
            self._file.seek(0, os.SEEK_END)
            self._file.seek(self._file.tell() - 1)
            if self._has_events:
                self._file.write(",")
            self._file.write(",".join(encoded))
            self._file.write("]")
            self._file.truncate()
            self._file.flush()
            self._has_events = True

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._file.flush()
            self._file.close()
