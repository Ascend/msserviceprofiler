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
import argparse
import importlib
import os
import sys

ST_PYTHON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ST_PYTHON_DIR not in sys.path:
    sys.path.insert(0, ST_PYTHON_DIR)


def main() -> int:
    metric_runner = importlib.import_module("metric.metric_runner")
    metric_scenarios = importlib.import_module("metric.metric_scenarios")
    metric_smoke_utils = importlib.import_module("metric.metric_smoke_utils")

    parser = argparse.ArgumentParser(description="Run ms-service-metric vLLM ST scenario")
    parser.add_argument("--scenario", choices=sorted(metric_scenarios.SCENARIOS), default="basic")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--device", action="append", type=int, default=[])
    parser.add_argument("--workspace", default="/workspace")
    parser.add_argument("--debug-mode", action="store_true", default=False)
    parser.add_argument("--metric-source", default=metric_smoke_utils.DEFAULT_METRIC_SOURCE)
    parser.add_argument("--metric-ref", default=metric_smoke_utils.DEFAULT_METRIC_REF)
    parser.add_argument("--metric-install-mode", choices=["editable", "installed"], default="editable")
    parser.add_argument("--metric-service-port", type=int, default=None)
    parser.add_argument("--metric-skip-npu-busy-check", action="store_true", default=False)
    parser.add_argument("--metric-npu-memory-threshold", type=int, default=90)
    parser.add_argument("--metric-request-count", type=int, default=1)
    parser.add_argument("--metric-poll-timeout", type=float, default=None)
    parser.add_argument("--metric-poll-interval", type=float, default=1.0)
    parser.add_argument("--eplb-heat-collection-interval", type=int, default=4)
    parser.add_argument("--eplb-algorithm-execution-interval", type=int, default=1)
    parser.add_argument("--eplb-policy-type", type=int, default=2)
    parser.add_argument("--eplb-num-redundant-experts", type=int, default=4)
    parser.add_argument("--eplb-max-model-len", type=int, default=4096)
    parser.add_argument("--vllm-extra-arg", action="append", default=[])
    args = parser.parse_args()

    try:
        metric_runner.run_metric_scenario(
            metric_runner.MetricRunnerConfig(
                scenario=args.scenario,
                model_path=args.model_path,
                devices=args.device,
                workspace=args.workspace,
                debug=args.debug_mode,
                metric_source=args.metric_source,
                metric_ref=args.metric_ref,
                metric_install_mode=args.metric_install_mode,
                metric_service_port=args.metric_service_port,
                metric_skip_npu_busy_check=args.metric_skip_npu_busy_check,
                metric_npu_memory_threshold=args.metric_npu_memory_threshold,
                vllm_extra_args=args.vllm_extra_arg,
                metric_request_count=args.metric_request_count,
                metric_poll_timeout=args.metric_poll_timeout,
                metric_poll_interval=args.metric_poll_interval,
                scenario_options={
                    "eplb_heat_collection_interval": args.eplb_heat_collection_interval,
                    "eplb_algorithm_execution_interval": args.eplb_algorithm_execution_interval,
                    "eplb_policy_type": args.eplb_policy_type,
                    "eplb_num_redundant_experts": args.eplb_num_redundant_experts,
                    "eplb_max_model_len": args.eplb_max_model_len,
                },
            )
        )
    except metric_scenarios.ScenarioUnavailable as exc:
        print(exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
