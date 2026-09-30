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

import pytest

from metric.metric_runner import MetricRunnerConfig, run_metric_scenario
from metric.metric_scenarios import ScenarioUnavailable


def test_vllm_metric_basic(
    devices,
    model_path,
    workspace,
    debug,
    metric_scenario,
    metric_source,
    metric_ref,
    metric_install_mode,
    metric_service_port,
    metric_skip_npu_busy_check,
    metric_npu_memory_threshold,
    vllm_extra_args,
    metric_request_count,
    metric_poll_timeout,
    metric_poll_interval,
    metric_scenario_options,
):
    try:
        run_metric_scenario(
            MetricRunnerConfig(
                scenario=metric_scenario,
                model_path=model_path,
                devices=devices,
                workspace=workspace,
                debug=debug,
                metric_source=metric_source,
                metric_ref=metric_ref,
                metric_install_mode=metric_install_mode,
                metric_service_port=metric_service_port,
                metric_skip_npu_busy_check=metric_skip_npu_busy_check,
                metric_npu_memory_threshold=metric_npu_memory_threshold,
                vllm_extra_args=vllm_extra_args,
                metric_request_count=metric_request_count,
                metric_poll_timeout=metric_poll_timeout,
                metric_poll_interval=metric_poll_interval,
                scenario_options=metric_scenario_options,
            )
        )
    except ScenarioUnavailable as exc:
        pytest.skip(str(exc))
