# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------

from unittest.mock import MagicMock

import pytest
import yaml

import ms_service_metric.adapters.vllm.adapter as adapter_module
from ms_service_metric.adapters.vllm.adapter import VLLMMetricAdapter
from ms_service_metric.utils.exceptions import SharedMemoryError


@pytest.mark.parametrize(
    ("process_name", "expected"),
    [
        ("EngineCore_DP0", 0),
        ("EngineCore_DP1", 1),
        ("(EngineCore_DP2 pid=1234)", 2),
        ("EngineCore-DP3", 3),
        ("ApiServer_1", -1),
        ("Worker", -1),
    ],
)
def test_parse_dp_rank_from_process_name(process_name, expected):
    assert VLLMMetricAdapter._parse_dp_rank_from_process_name(process_name) == expected


def test_setup_dp_rank_uses_env_first(monkeypatch):
    captured = []
    adapter = VLLMMetricAdapter()

    monkeypatch.setenv("VLLM_DP_RANK", "2")
    monkeypatch.setattr(adapter_module, "set_dp_rank", captured.append)
    monkeypatch.setattr(adapter, "_get_dp_rank_from_vllm", lambda: pytest.fail("vLLM fallback should not run"))
    monkeypatch.setattr(
        adapter, "_get_dp_rank_from_process_name", lambda: pytest.fail("process fallback should not run")
    )

    adapter._setup_dp_rank()

    assert captured == [2]


def test_setup_dp_rank_falls_back_to_process_name(monkeypatch):
    captured = []
    adapter = VLLMMetricAdapter()

    monkeypatch.delenv("VLLM_DP_RANK", raising=False)
    monkeypatch.setattr(adapter_module, "set_dp_rank", captured.append)
    monkeypatch.setattr(adapter, "_get_dp_rank_from_vllm", lambda: -1)
    monkeypatch.setattr(adapter, "_get_dp_rank_from_process_name", lambda: 1)

    adapter._setup_dp_rank()

    assert captured == [1]


def test_given_optional_metric_initialization_failure_when_plugin_loads_then_vllm_startup_continues(
    monkeypatch,
    caplog,
):
    adapter = MagicMock()
    adapter.initialize.side_effect = SharedMemoryError("posix_ipc unavailable")
    monkeypatch.setattr(adapter_module, "get_vllm_adapter", lambda: adapter)

    adapter_module.initialize_vllm_metric()

    adapter.shutdown.assert_called_once_with()
    assert "vLLM startup will continue" in caplog.text


def test_given_partial_metric_cleanup_failure_when_plugin_loads_then_exception_is_not_propagated(
    monkeypatch,
    caplog,
):
    adapter = MagicMock()
    adapter.initialize.side_effect = RuntimeError("initialization failed")
    adapter.shutdown.side_effect = RuntimeError("cleanup failed")
    monkeypatch.setattr(adapter_module, "get_vllm_adapter", lambda: adapter)

    adapter_module.initialize_vllm_metric()

    adapter.shutdown.assert_called_once_with()
    assert "Failed to clean up partially initialized" in caplog.text


def test_given_partial_manager_when_adapter_shutdown_then_manager_is_cleaned():
    adapter = VLLMMetricAdapter()
    manager = MagicMock()
    adapter._manager = manager

    adapter.shutdown()

    manager.shutdown.assert_called_once_with()
    assert adapter._manager is None


def test_v1_metrics_config_contains_exception_status_hooks():
    config_path = adapter_module.os.path.join(
        adapter_module.os.path.dirname(adapter_module.__file__),
        "config",
        "v1_metrics.yaml",
    )

    with open(config_path, encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    handlers_by_symbol = {}
    for item in config:
        handlers_by_symbol.setdefault(item["symbol"], []).append(item.get("handler"))

    scheduler_handler = "ms_service_metric.adapters.vllm.handlers.metric_handlers:scheduler_scheduler_hooker"
    for symbol in (
        "vllm.v1.core.sched.scheduler:Scheduler.schedule",
        "vllm_ascend.core.scheduler_dynamic_batch:SchedulerDynamicBatch.schedule",
        "vllm_ascend.core.scheduler_profiling_chunk:ProfilingChunkScheduler.schedule",
        "vllm_ascend.core.recompute_scheduler:RecomputeScheduler.schedule",
        "vllm_ascend.patch.platform.patch_balance_schedule:BalanceScheduler.schedule",
    ):
        assert scheduler_handler in handlers_by_symbol[symbol]

    assert (
        "ms_service_metric.adapters.vllm.handlers.metric_handlers:block_allocate_failure_hooker"
        in handlers_by_symbol["vllm.v1.core.kv_cache_manager:KVCacheManager.allocate_slots"]
    )
    assert (
        "ms_service_metric.adapters.vllm.handlers.metric_handlers:rpc_error_hooker"
        in handlers_by_symbol["vllm.v1.executor.multiproc_executor:MultiprocExecutor.collective_rpc"]
    )
    assert (
        "ms_service_metric.adapters.vllm.handlers.metric_handlers:health_engine_client_hooker"
        in handlers_by_symbol["vllm.entrypoints.serve.instrumentator.health:engine_client"]
    )
    assert (
        "ms_service_metric.adapters.vllm.handlers.metric_handlers:engine_core_pending_hooker"
        in handlers_by_symbol["vllm.v1.engine.core:EngineCore.step"]
    )
    assert (
        "ms_service_metric.adapters.vllm.handlers.metric_handlers:engine_core_pending_hooker"
        in handlers_by_symbol["vllm.v1.engine.core:EngineCore.step_with_batch_queue"]
    )
