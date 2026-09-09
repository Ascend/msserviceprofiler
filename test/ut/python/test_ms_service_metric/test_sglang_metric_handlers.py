# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------

from types import SimpleNamespace

import pytest

import ms_service_metric.adapters.sglang.handlers.metric_handlers as mh
from ms_service_metric.metrics.metrics_manager import MetricType


class FakeTensor:
    def __init__(self, shape):
        self.shape = shape

    def size(self, dim):
        return self.shape[dim]

    def numel(self):
        total = 1
        for dim in self.shape:
            total *= dim
        return total


class FakeMetricsClient:
    def __init__(self):
        self.created = []
        self.records = []

    def get_or_create_metric(self, metric_name, label_names=None, metric_type=MetricType.TIMER, buckets=None):
        self.created.append((metric_name, tuple(label_names or ()), metric_type, buckets))
        return self

    def record_metric(self, metric_name, value, labels=None):
        self.records.append((metric_name, value, labels or {}))


class FakeBatch:
    def __init__(self, batch_size):
        self._batch_size = batch_size

    def batch_size(self):
        return self._batch_size


def _metric(name, metric_type=MetricType.TIMER):
    return SimpleNamespace(
        name=name,
        type=metric_type,
        labels={},
        buckets=None,
        get=lambda key, default=None: {
            "name": name,
            "type": metric_type,
            "labels": {},
            "buckets": None,
        }.get(key, default),
    )


@pytest.fixture(name="fake_client")
def fake_metrics_client(monkeypatch):
    client = FakeMetricsClient()
    monkeypatch.setattr(mh, "metrics_client", client)
    monkeypatch.setattr(mh, "_REGISTERED", set())
    return client


def test_scheduler_handler_reads_forward_batch_size_and_tensor_tokens(fake_client):
    batch = SimpleNamespace(batch_size=4, input_ids=FakeTensor((12,)), output_ids=FakeTensor((4,)), is_decode=True)
    scheduler = SimpleNamespace(waiting=[], running=[], tree_cache=SimpleNamespace(free_size=8))
    handler = mh.scheduler_handler([_metric("scheduler:run_batch:duration")])

    ret = handler(lambda _self, _batch: _batch, scheduler, batch)

    assert ret is batch
    assert ("scheduler:batch_size", 4, {"batch_phase": "decode"}) in fake_client.records
    assert ("scheduler:input_tokens", 12, {"batch_phase": "decode"}) in fake_client.records
    assert ("scheduler:output_tokens", 4, {"batch_phase": "decode"}) in fake_client.records


def test_scheduler_handler_skips_queue_and_kvcache_for_non_scheduler_self(fake_client):
    req = SimpleNamespace(input_ids=[1, 2], is_prefill=True)
    non_scheduler = SimpleNamespace()
    handler = mh.scheduler_handler([_metric("scheduler:req_init_next_round_input:duration")])

    ret = handler(lambda _self, _req: _req, non_scheduler, req)

    assert ret is req
    assert not any(name == "scheduler:waiting_queue_size" for name, _, _ in fake_client.records)
    assert not any(name == "scheduler:running_queue_size" for name, _, _ in fake_client.records)
    assert not any(name == "scheduler:free_kvcache_blocks" for name, _, _ in fake_client.records)


def test_scheduler_handler_records_scheduler_queue_with_new_sglang_attrs(fake_client):
    scheduler = SimpleNamespace(
        waiting_queue=[object(), object()],
        running_batch=FakeBatch(5),
    )
    handler = mh.scheduler_handler([_metric("scheduler:process_batch_result:duration")])

    ret = handler(lambda _self: None, scheduler)

    assert ret is None
    assert ("scheduler:waiting_queue_size", 2, {}) in fake_client.records
    assert ("scheduler:running_queue_size", 5, {}) in fake_client.records


def test_model_handler_reads_model_worker_batch_from_classmethod_args(fake_client):
    worker_batch = SimpleNamespace(batch_size=3, input_ids=FakeTensor((9,)), is_prefill=True)
    handler = mh.model_handler([_metric("model:preprocess:duration")])

    ret = handler(lambda _cls, _batch: "ok", object(), worker_batch)

    assert ret == "ok"
    assert ("model:batch_size", 3, {"batch_phase": "prefill"}) in fake_client.records
    assert ("model:input_tokens", 9, {"batch_phase": "prefill"}) in fake_client.records


@pytest.mark.asyncio
async def test_model_handler_records_async_target_after_await(fake_client):
    batch = SimpleNamespace(batch_size=2, input_ids=FakeTensor((6,)), output_ids=FakeTensor((2,)), is_decode=True)
    handler = mh.model_handler([_metric("model:forward:duration")], is_async=True)

    async def forward(_self, _batch):
        return _batch

    ret = await handler(forward, object(), batch)

    assert ret is batch
    assert any(name == "model:forward:duration" for name, _, _ in fake_client.records)
    assert ("model:batch_size", 2, {"batch_phase": "decode"}) in fake_client.records
    assert ("model:input_tokens", 6, {"batch_phase": "decode"}) in fake_client.records
    assert ("model:output_tokens", 2, {"batch_phase": "decode"}) in fake_client.records


@pytest.mark.asyncio
async def test_model_handler_records_sync_target_returning_awaitable(fake_client):
    batch = SimpleNamespace(batch_size=2, input_ids=FakeTensor((5,)), is_prefill=True)
    handler = mh.model_handler([_metric("model:sample:duration")])

    async def result():
        return batch

    ret = await handler(lambda _self, _batch: result(), object(), batch)

    assert ret is batch
    assert any(name == "model:sample:duration" for name, _, _ in fake_client.records)
    assert ("model:batch_size", 2, {"batch_phase": "prefill"}) in fake_client.records
    assert ("model:input_tokens", 5, {"batch_phase": "prefill"}) in fake_client.records
