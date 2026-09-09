# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------

import os

from ms_service_metric.core.config.symbol_config import SymbolConfig
from ms_service_metric.core.handler import MetricHandler


def test_sglang_default_config_loads_and_handlers_import():
    config_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "..",
            "ms_service_metric",
            "ms_service_metric",
            "adapters",
            "sglang",
            "config",
            "default.yaml",
        )
    )

    config = SymbolConfig(current_version=None).load(default_config_path=config_path)

    assert "sglang.srt.managers.scheduler:Scheduler.run_batch" in config
    assert "sglang.srt.model_executor.model_runner:ModelRunner.forward" in config

    for symbol_path, handlers in config.items():
        for handler_config in handlers:
            MetricHandler.from_config(handler_config, symbol_path)
