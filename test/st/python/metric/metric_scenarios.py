# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from executor.exec_benchmark import ExecBenchmark
from metric.metric_assertions import MetricExpectation
from metric.metric_smoke_utils import MetricSmokeError, PreflightReport, run_command


class ScenarioUnavailable(MetricSmokeError):
    pass


@dataclass
class ScenarioContext:
    model_path: str
    devices: list[int]
    port: int
    artifact_dir: Path
    request_count: int = 1
    options: dict[str, object] = field(default_factory=dict)


@dataclass
class MetricScenario:
    name: str
    min_devices: int = 1
    startup_timeout: int = 900
    default_vllm_args: list[str] = field(default_factory=list)
    skip_if_unavailable: bool = False
    metric_poll_timeout: float = 30.0

    def preflight(self, context: ScenarioContext, report: PreflightReport) -> None:
        if len(context.devices) < self.min_devices:
            self.unavailable(
                report,
                f"requires at least {self.min_devices} NPU device(s), got {context.devices}",
            )
        report.pass_(f"scenario:{self.name}", f"selected devices={context.devices}")

    def unavailable(self, report: PreflightReport, detail: str) -> None:
        if not self.skip_if_unavailable:
            report.fail(f"scenario:{self.name}", detail)
        report.lines.append(f"[preflight:scenario:{self.name}] SKIP: {detail}")
        raise ScenarioUnavailable(str(report))

    def build_vllm_args(self, context: ScenarioContext, extra_args: Optional[list[str]] = None) -> list[str]:
        return [*self.default_vllm_args, *(extra_args or [])]

    def build_service_env(self, context: ScenarioContext) -> dict[str, str]:
        return {}

    def validate_startup(self, service_output: str) -> None:
        return

    def run_requests(self, context: ScenarioContext) -> ExecBenchmark:
        return _run_completion_requests(context, count=context.request_count)

    def expectations(self) -> list[MetricExpectation]:
        raise NotImplementedError


def _run_completion_requests(context: ScenarioContext, count: int) -> ExecBenchmark:
    benchmark = ExecBenchmark()
    for request_index in range(count):
        if benchmark.curl_vllm_test(
            server_ip="127.0.0.1",
            server_port=context.port,
            model_path=context.model_path,
        ):
            continue
        raise MetricSmokeError(
            f"vLLM completion request {request_index + 1}/{count} failed. Artifacts: {context.artifact_dir}"
        )
    return benchmark


class BasicScenario(MetricScenario):
    def __init__(self):
        super().__init__(
            name="basic",
            min_devices=1,
            startup_timeout=900,
            default_vllm_args=["--enforce-eager", "--max-model-len", "2048"],
        )

    def expectations(self) -> list[MetricExpectation]:
        return [
            MetricExpectation(
                names=[
                    "vllm_profiling_engine:generate:duration_count",
                    "vllm_profiling_engine_generate_duration_count",
                ],
                required=True,
                rules=["exists", "finite", "gt:0"],
                labels={"dp": "present", "phase": "present", "role": "present"},
                increase=True,
                description="basic generate path should be profiled after one completion request",
            ),
            MetricExpectation(
                names=[
                    "vllm_profiling_scheduler:duration_count",
                    "vllm_profiling_scheduler_duration_count",
                ],
                required=True,
                rules=["exists", "finite", "gt:0"],
                labels={"dp": "present", "phase": "present", "role": "present"},
                increase=True,
                description="scheduler should run during the basic completion request",
            ),
            MetricExpectation(
                names=[
                    "vllm_profiling_scheduler:add_request:duration_count",
                    "vllm_profiling_scheduler_add_request_duration_count",
                ],
                required=True,
                rules=["exists", "finite", "gt:0"],
                labels={"dp": "present", "phase": "present", "role": "present"},
                increase=True,
                description="scheduler add_request hook should record the incoming request",
            ),
            MetricExpectation(
                names=[
                    "vllm_profiling_executor:model_runner_execute_model:duration_count",
                    "vllm_profiling_executor_model_runner_execute_model_duration_count",
                ],
                required=True,
                rules=["exists", "finite", "gt:0"],
                labels={"dp": "present"},
                increase=True,
                description="NPU model runner execute_model should be profiled",
            ),
            MetricExpectation(
                names=[
                    "vllm_profiling_engine_core:engine_core_step:duration_count",
                    "vllm_profiling_engine_core_engine_core_step_duration_count",
                ],
                required=False,
                rules=["exists", "finite", "gt:0"],
                labels={"dp": "present"},
                increase=True,
                triggered=True,
                description="engine core step is validated when the installed vLLM exposes this hook",
            ),
            MetricExpectation(
                names=[
                    "vllm_profiling_engine:memory:total_gb",
                    "vllm_profiling_engine_memory_total_gb",
                ],
                required=False,
                rules=["exists", "finite", "gt:0"],
                labels={"dp": "present"},
                description="static device memory total should be exported when worker memory hook is available",
            ),
            MetricExpectation(
                names=[
                    "vllm_profiling_engine:memory:utilization_ratio",
                    "vllm_profiling_engine_memory_utilization_ratio",
                ],
                required=False,
                rules=["exists", "finite", "gte:0"],
                labels={"dp": "present"},
                description="vLLM memory utilization ratio should be exported when worker memory hook is available",
            ),
        ]


class EplbScenario(MetricScenario):
    def __init__(self):
        super().__init__(
            name="eplb",
            min_devices=2,
            startup_timeout=1200,
            skip_if_unavailable=True,
            metric_poll_timeout=60.0,
        )

    def run_requests(self, context: ScenarioContext) -> ExecBenchmark:
        return _run_completion_requests(context, count=max(4, context.request_count))

    def preflight(self, context: ScenarioContext, report: PreflightReport) -> None:
        super().preflight(context, report)
        _require_moe_model(context.model_path, report, self)
        _require_import("vllm_ascend.eplb.core.eplb_worker", report, self)
        help_text = _get_vllm_help(report, self)
        for option in ("--tensor-parallel-size", "--enable-expert-parallel", "--additional-config"):
            _require_vllm_option(help_text, option, report, self)
        _require_positive_option(context, report, self, "eplb_heat_collection_interval")
        _require_positive_option(context, report, self, "eplb_algorithm_execution_interval")
        _require_positive_option(context, report, self, "eplb_max_model_len")
        _require_non_negative_option(context, report, self, "eplb_policy_type")
        _require_non_negative_option(context, report, self, "eplb_num_redundant_experts")

    def build_vllm_args(self, context: ScenarioContext, extra_args: Optional[list[str]] = None) -> list[str]:
        heat_collection_interval = _scenario_option(context, "eplb_heat_collection_interval", 4)
        algorithm_execution_interval = _scenario_option(context, "eplb_algorithm_execution_interval", 1)
        policy_type = _scenario_option(context, "eplb_policy_type", 2)
        redundant_experts = _scenario_option(context, "eplb_num_redundant_experts", 4)
        max_model_len = _scenario_option(context, "eplb_max_model_len", 4096)
        eplb_config = {
            "eplb_config": {
                "dynamic_eplb": True,
                "expert_heat_collection_interval": heat_collection_interval,
                "algorithm_execution_interval": algorithm_execution_interval,
                "eplb_policy_type": policy_type,
                "num_redundant_experts": redundant_experts,
            }
        }
        return [
            "--tensor-parallel-size",
            str(len(context.devices)),
            "--enable-expert-parallel",
            "--max-model-len",
            str(max_model_len),
            "--additional-config",
            json.dumps(eplb_config, separators=(",", ":")),
            *(extra_args or []),
        ]

    def build_service_env(self, context: ScenarioContext) -> dict[str, str]:
        return {"DYNAMIC_EPLB": "true"}

    def validate_startup(self, service_output: str) -> None:
        if "Dynamic EPLB is True" not in service_output:
            raise MetricSmokeError("EPLB service started but startup logs did not confirm 'Dynamic EPLB is True'")

    def expectations(self) -> list[MetricExpectation]:
        return [
            MetricExpectation(
                names=[
                    "vllm_profiling_eplb:expert_hotness:current_mean",
                ],
                required=True,
                rules=["exists", "finite", "gte:0"],
                description="EPLB should export expert hotness current_mean",
            ),
            MetricExpectation(
                names=["vllm_profiling_eplb:expert_hotness:current_max"],
                required=True,
                rules=["exists", "finite", "gte:0"],
                description="EPLB should export expert hotness current_max",
            ),
            MetricExpectation(
                names=["vllm_profiling_eplb:expert_hotness:imbalance"],
                required=False,
                rules=["exists", "finite", "gte:0"],
                labels={"layer": "present"},
                description="EPLB imbalance is emitted when per-layer hotness data is available",
            ),
            MetricExpectation(
                names=["vllm_profiling_eplb:expert_map_update:duration_count"],
                required=False,
                rules=["exists", "finite", "gt:0"],
                increase=True,
                triggered=True,
                description="EPLB expert map update duration should increase when update is triggered",
            ),
            MetricExpectation(
                names=["vllm_profiling_eplb:log2phy_map_update:duration_count"],
                required=False,
                rules=["exists", "finite", "gt:0"],
                increase=True,
                triggered=True,
                description="EPLB log2phy map update duration should increase when update is triggered",
            ),
            MetricExpectation(
                names=[
                    "vllm_profiling_eplb:expert_weight_update:duration_count",
                    "vllm_profiling_eplb:expert_weight_replace:duration_count",
                ],
                required=False,
                rules=["exists", "finite", "gt:0"],
                increase=True,
                triggered=True,
                description="EPLB expert weight update/replace duration should increase when update is triggered",
            ),
        ]


class DplbScenario(MetricScenario):
    def __init__(self):
        super().__init__(name="dplb", min_devices=2, startup_timeout=1200, skip_if_unavailable=True)

    def run_requests(self, context: ScenarioContext) -> ExecBenchmark:
        return _run_completion_requests(context, count=max(4, len(context.devices) * 2, context.request_count))

    def preflight(self, context: ScenarioContext, report: PreflightReport) -> None:
        super().preflight(context, report)
        help_text = _get_vllm_help(report, self)
        _require_vllm_option(help_text, "--data-parallel-size", report, self)
        _require_vllm_option(help_text, "--data-parallel-hybrid-lb", report, self)

    def build_vllm_args(self, context: ScenarioContext, extra_args: Optional[list[str]] = None) -> list[str]:
        return [
            "--enforce-eager",
            "--max-model-len",
            "2048",
            "--data-parallel-size",
            str(len(context.devices)),
            "--data-parallel-hybrid-lb",
            *(extra_args or []),
        ]

    def expectations(self) -> list[MetricExpectation]:
        return [
            MetricExpectation(
                names=[
                    "vllm_profiling_scheduler:duration_count",
                    "vllm_profiling_scheduler_duration_count",
                ],
                required=True,
                rules=["exists", "finite", "gt:0"],
                labels={"dp": "present"},
                min_distinct_labels={"dp": 2},
                increase=True,
                description="DPLB scenario should expose scheduler metrics from multiple dp ranks",
            ),
        ]


class ExceptionScenario(MetricScenario):
    def __init__(self):
        super().__init__(name="exception", min_devices=1, startup_timeout=900, skip_if_unavailable=True)

    def preflight(self, context: ScenarioContext, report: PreflightReport) -> None:
        super().preflight(context, report)
        self.unavailable(
            report,
            "no deterministic health/RPC failure trigger is implemented yet; refusing a false-positive ST pass",
        )

    def expectations(self) -> list[MetricExpectation]:
        return [
            MetricExpectation(
                names=["vllm_profiling_health_check_failed_total"],
                required=False,
                rules=["exists", "finite", "gt:0"],
                description="health failure metric is optional until a stable failure trigger is added",
            )
        ]


SCENARIOS = {
    "basic": BasicScenario,
    "eplb": EplbScenario,
    "dplb": DplbScenario,
    "exception": ExceptionScenario,
}


def get_scenario(name: str) -> MetricScenario:
    try:
        return SCENARIOS[name]()
    except KeyError as exc:
        raise MetricSmokeError(f"Unknown metric scenario '{name}', choices: {sorted(SCENARIOS)}") from exc


def _require_import(module_name: str, report: PreflightReport, scenario: MetricScenario) -> None:
    try:
        __import__(module_name)
    except Exception as exc:
        scenario.unavailable(report, f"required module is unavailable: {module_name}, error={exc}")
    report.pass_(f"scenario:{scenario.name}", f"required module available: {module_name}")


def _require_moe_model(model_path: str, report: PreflightReport, scenario: MetricScenario) -> None:
    config_path = Path(model_path) / "config.json"
    if not config_path.exists():
        scenario.unavailable(report, f"MoE model check requires config.json under {model_path}")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        scenario.unavailable(report, f"failed to read model config.json: {exc}")

    moe_keys = ("num_experts", "n_routed_experts", "moe_intermediate_size", "num_local_experts")
    text_config = config.get("text_config")
    candidates = [config]
    if isinstance(text_config, dict):
        candidates.append(text_config)
    if not any(key in candidate for candidate in candidates for key in moe_keys):
        scenario.unavailable(report, f"EPLB requires a MoE model config, missing keys {moe_keys}")
    report.pass_(f"scenario:{scenario.name}", "MoE model markers found")


def _get_vllm_help(report: PreflightReport, scenario: MetricScenario) -> str:
    result = run_command(["vllm", "serve", "--help=all"], timeout=60)
    if result.returncode != 0:
        result = run_command(["vllm", "serve", "--help"], timeout=60)
    if result.returncode != 0:
        scenario.unavailable(report, f"failed to inspect vLLM serve options:\n{result.stdout}")
    return result.stdout


def _require_vllm_option(
    help_text: str,
    option: str,
    report: PreflightReport,
    scenario: MetricScenario,
) -> None:
    if option not in help_text:
        scenario.unavailable(
            report,
            f"installed vLLM/vllm-ascend does not expose required option {option}",
        )
    report.pass_(f"scenario:{scenario.name}", f"vLLM option available: {option}")


def _scenario_option(context: ScenarioContext, key: str, default: int) -> int:
    return int(context.options.get(key, default))


def _require_positive_option(
    context: ScenarioContext,
    report: PreflightReport,
    scenario: MetricScenario,
    key: str,
) -> None:
    value = _scenario_option(context, key, 1)
    if value <= 0:
        scenario.unavailable(report, f"{key} must be > 0, got {value}")
    report.pass_(f"scenario:{scenario.name}", f"{key}={value}")


def _require_non_negative_option(
    context: ScenarioContext,
    report: PreflightReport,
    scenario: MetricScenario,
    key: str,
) -> None:
    value = _scenario_option(context, key, 0)
    if value < 0:
        scenario.unavailable(report, f"{key} must be >= 0, got {value}")
    report.pass_(f"scenario:{scenario.name}", f"{key}={value}")
