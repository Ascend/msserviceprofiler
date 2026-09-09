# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------

from unittest.mock import MagicMock

import pytest
import yaml

import ms_service_metric.adapters.sglang.adapter as adapter_module
from ms_service_metric.adapters.sglang.adapter import SGLangMetricAdapter
from ms_service_metric.metrics.meta_state import get_meta_state
from ms_service_metric.utils.exceptions import SharedMemoryError


@pytest.mark.parametrize(
    ("process_name", "prefix", "expected"),
    [
        ("Scheduler_DP0", "DP", 0),
        ("Scheduler-DP3", "DP", 3),
        ("TpWorker_TP2", "TP", 2),
        ("sglang::scheduler_dp2_tp5", "DP", 2),
        ("ApiServer_1", "DP", -1),
    ],
)
def test_parse_rank_from_process_name(process_name, prefix, expected):
    assert SGLangMetricAdapter._parse_rank_from_process_name(process_name, prefix) == expected


def test_setup_ranks_uses_env(monkeypatch):
    adapter = SGLangMetricAdapter()
    monkeypatch.setenv("SGLANG_DP_RANK", "2")
    monkeypatch.setenv("SGLANG_TP_RANK", "7")

    adapter._setup_ranks()

    assert get_meta_state().dp_rank == 2
    assert get_meta_state().get("tp_rank") == 7


def test_setup_ranks_uses_sglang_process_title(monkeypatch):
    adapter = SGLangMetricAdapter()
    monkeypatch.delenv("SGLANG_DP_RANK", raising=False)
    monkeypatch.delenv("SGLANG_TP_RANK", raising=False)
    monkeypatch.setattr(
        adapter,
        "_get_rank_source_names",
        lambda: ("Process-3", "sglang::scheduler_DP2_TP5"),
    )

    adapter._setup_ranks()

    assert get_meta_state().dp_rank == 2
    assert get_meta_state().get("tp_rank") == 5


def test_get_config_path_uses_env_as_user_config(monkeypatch, tmp_path):
    config = tmp_path / "sglang.yaml"
    config.write_text("[]", encoding="utf-8")
    adapter = SGLangMetricAdapter()
    monkeypatch.setenv("MS_SERVICE_METRIC_SGLANG_CONFIG", str(config))

    config_path, default_path, is_user = adapter._get_config_path()

    assert config_path == str(config)
    assert default_path.endswith("default.yaml")
    assert is_user is True


def test_given_optional_metric_initialization_failure_when_plugin_loads_then_sglang_startup_continues(
    monkeypatch,
):
    adapter = MagicMock()
    adapter.initialize.side_effect = SharedMemoryError("posix_ipc unavailable")
    monkeypatch.setattr(adapter_module, "get_sglang_adapter", lambda: adapter)

    adapter_module.initialize_sglang_metric()

    adapter.shutdown.assert_called_once_with()


def test_default_config_contains_core_sglang_symbols():
    config_path = adapter_module.os.path.join(
        adapter_module.os.path.dirname(adapter_module.__file__),
        "config",
        "default.yaml",
    )

    with open(config_path, encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    handlers_by_symbol = {item["symbol"]: item.get("handler") for item in config}
    handler = "ms_service_metric.adapters.sglang.handlers.metric_handlers:scheduler_handler"
    assert handlers_by_symbol["sglang.srt.managers.scheduler:Scheduler.run_batch"] == handler
    assert "sglang.srt.model_executor.model_runner:ModelRunner.forward" in handlers_by_symbol
    assert "sglang.srt.managers.tokenizer_manager:TokenizerManager._wait_one_response" in handlers_by_symbol
