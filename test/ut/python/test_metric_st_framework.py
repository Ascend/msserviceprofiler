# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ST_PYTHON_DIR = Path(__file__).resolve().parents[2] / "st" / "python"
sys.path.insert(0, str(ST_PYTHON_DIR))

metric_assertions = importlib.import_module("metric.metric_assertions")
metric_log_health = importlib.import_module("metric.metric_log_health")
metric_runner = importlib.import_module("metric.metric_runner")
metric_scenarios = importlib.import_module("metric.metric_scenarios")
metric_smoke_utils = importlib.import_module("metric.metric_smoke_utils")

MetricExpectation = metric_assertions.MetricExpectation
assert_metric_expectations = metric_assertions.assert_metric_expectations
parse_prometheus_text = metric_assertions.parse_prometheus_text
wait_for_metric_expectations = metric_assertions.wait_for_metric_expectations
assert_metric_log_health = metric_log_health.assert_metric_log_health
scan_metric_log_health = metric_log_health.scan_metric_log_health
ScenarioContext = metric_scenarios.ScenarioContext
get_scenario = metric_scenarios.get_scenario
MetricSmokeError = metric_smoke_utils.MetricSmokeError
_parse_visible_devices = metric_smoke_utils._parse_visible_devices


PROMETHEUS_TEXT = """
# TYPE vllm_profiling_engine:generate:duration histogram
vllm_profiling_engine:generate:duration_sum{dp="0",phase="mixed",role="mixed"} 0.25
vllm_profiling_engine:generate:duration_count{dp="0",phase="mixed",role="mixed"} 1
# TYPE vllm_profiling_scheduler:duration histogram
vllm_profiling_scheduler:duration_sum{dp="0",phase="prefill",role="mixed"} 0.5
vllm_profiling_scheduler:duration_count{dp="0",phase="prefill",role="mixed"} 2
optional_nan NaN
optional_inf +Inf
"""


def test_parse_prometheus_text_preserves_names_labels_and_special_values():
    samples = parse_prometheus_text(PROMETHEUS_TEXT)
    generate = next(sample for sample in samples if sample.name.endswith("generate:duration_count"))

    assert generate.value == 1
    assert generate.labels == {"dp": "0", "phase": "mixed", "role": "mixed"}
    assert any(sample.value != sample.value for sample in samples if sample.name == "optional_nan")


def test_expectation_supports_fallback_names_labels_and_rules(tmp_path):
    report = assert_metric_expectations(
        PROMETHEUS_TEXT,
        [
            MetricExpectation(
                names=["old_name", "vllm_profiling_engine:generate:duration_count"],
                rules=["exists", "finite", "gt:0"],
                labels={"dp": "present", "phase": ["mixed", "decode"]},
            )
        ],
        report_path=tmp_path / "assertion_report.json",
    )

    assert len(report.passed) == 1
    assert (tmp_path / "assertion_report.json").exists()


def test_histogram_requires_count_and_sum():
    assert_metric_expectations(
        PROMETHEUS_TEXT,
        [
            MetricExpectation(
                names=["vllm_profiling_engine:generate:duration"],
                histogram=True,
                rules=["exists", "finite", "gte:0"],
                labels={"dp": "0"},
            )
        ],
    )

    with pytest.raises(MetricSmokeError):
        assert_metric_expectations(
            "metric_count 1\n",
            [MetricExpectation(names=["metric"], histogram=True)],
        )


def test_optional_and_forbidden_expectations():
    report = assert_metric_expectations(
        PROMETHEUS_TEXT,
        [
            MetricExpectation(names=["missing_optional"], required=False),
            MetricExpectation(names=["must_not_exist"], forbidden=True),
        ],
    )

    assert len(report.skipped_optional) == 1
    assert len(report.passed) == 1


def test_expectation_checks_distinct_label_values():
    text = """
metric_total{dp="0"} 1
metric_total{dp="1"} 2
"""
    assert_metric_expectations(
        text,
        [
            MetricExpectation(
                names=["metric_total"],
                labels={"dp": "present"},
                min_distinct_labels={"dp": 2},
            )
        ],
    )


def test_expectation_requires_metric_increase_from_baseline():
    expectation = MetricExpectation(names=["request_count"], increase=True)

    report = assert_metric_expectations(
        "request_count 3\n",
        [expectation],
        baseline_text="request_count 2\n",
    )
    assert len(report.passed) == 1

    with pytest.raises(MetricSmokeError):
        assert_metric_expectations(
            "request_count 2\n",
            [expectation],
            baseline_text="request_count 2\n",
        )


def test_triggered_optional_metric_skips_when_not_increased():
    report = assert_metric_expectations(
        "eplb_update_count 2\n",
        [
            MetricExpectation(
                names=["eplb_update_count"],
                required=False,
                increase=True,
                triggered=True,
            )
        ],
        baseline_text="eplb_update_count 2\n",
    )

    assert len(report.skipped_optional) == 1
    assert "should increase" in report.skipped_optional[0]["reason"]


def test_metric_polling_retries_until_expectation_passes():
    samples = iter(["request_count 1\n", "request_count 2\n"])
    calls = []

    def fetcher():
        calls.append(1)
        return next(samples)

    metrics_text, report = wait_for_metric_expectations(
        fetcher=fetcher,
        expectations=[MetricExpectation(names=["request_count"], increase=True)],
        baseline_text="request_count 1\n",
        timeout=1,
        interval=0,
    )

    assert metrics_text == "request_count 2\n"
    assert len(calls) == 2
    assert len(report.passed) == 1


def test_metric_log_health_flags_only_metric_failures(tmp_path):
    service_log = """
WARNING 06-11 NIXL is not available
[ms_service_metric.symbol] ERROR Failed to apply hook for module: boom
[ms_service_metric.metrics_manager] WARNING Failed to record metric scheduler:duration: bad labels
[ms_service_metric.symbol] WARNING No target available for symbol optional.module:func
"""

    report = scan_metric_log_health(service_log)

    assert len(report.fatal) == 2
    assert len(report.warnings) == 1
    with pytest.raises(MetricSmokeError):
        assert_metric_log_health(service_log, report_path=tmp_path / "log_health_report.json")
    assert (tmp_path / "log_health_report.json").exists()


def test_scenario_registry_and_vllm_args(tmp_path):
    context = ScenarioContext(
        model_path="/model",
        devices=[0, 1],
        port=8000,
        artifact_dir=tmp_path,
    )

    basic = get_scenario("basic")
    assert basic.build_vllm_args(context) == ["--enforce-eager", "--max-model-len", "2048"]

    eplb = get_scenario("eplb")
    eplb_args = eplb.build_vllm_args(context)
    assert eplb_args[:5] == [
        "--tensor-parallel-size",
        "2",
        "--enable-expert-parallel",
        "--max-model-len",
        "4096",
    ]
    assert eplb.build_service_env(context) == {"DYNAMIC_EPLB": "true"}
    eplb_config = json.loads(eplb_args[eplb_args.index("--additional-config") + 1])
    assert eplb_config["eplb_config"]["expert_heat_collection_interval"] == 4

    custom_eplb_context = ScenarioContext(
        model_path="/model",
        devices=[0, 1],
        port=8000,
        artifact_dir=tmp_path,
        options={
            "eplb_heat_collection_interval": 8,
            "eplb_algorithm_execution_interval": 2,
            "eplb_policy_type": 1,
            "eplb_num_redundant_experts": 0,
            "eplb_max_model_len": 8192,
        },
    )
    custom_eplb_args = eplb.build_vllm_args(custom_eplb_context)
    custom_eplb_config = json.loads(custom_eplb_args[custom_eplb_args.index("--additional-config") + 1])
    assert custom_eplb_args[custom_eplb_args.index("--max-model-len") + 1] == "8192"
    assert custom_eplb_config["eplb_config"] == {
        "dynamic_eplb": True,
        "expert_heat_collection_interval": 8,
        "algorithm_execution_interval": 2,
        "eplb_policy_type": 1,
        "num_redundant_experts": 0,
    }

    dplb = get_scenario("dplb")
    assert dplb.build_vllm_args(context, ["--trust-remote-code"]) == [
        "--enforce-eager",
        "--max-model-len",
        "2048",
        "--data-parallel-size",
        "2",
        "--data-parallel-hybrid-lb",
        "--trust-remote-code",
    ]

    with pytest.raises(MetricSmokeError):
        get_scenario("unknown")


@pytest.mark.parametrize("key", ["num_experts", "n_routed_experts", "moe_intermediate_size", "num_local_experts"])
@pytest.mark.parametrize("nested", [False, True])
def test_moe_model_markers_at_top_level_or_in_text_config(tmp_path, key, nested):
    config = {"text_config": {key: 8}} if nested else {key: 8}
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    report = metric_smoke_utils.PreflightReport()

    metric_scenarios._require_moe_model(str(tmp_path), report, get_scenario("eplb"))

    assert "MoE model markers found" in str(report)


@pytest.mark.parametrize("text_config", [None, {}, [], ["num_experts"], "num_experts", 8])
@pytest.mark.parametrize("top_level_moe", [False, True])
def test_moe_model_ignores_text_config_without_markers(tmp_path, text_config, top_level_moe):
    config = {"text_config": text_config, "vision_config": {"num_experts": 8}}
    if top_level_moe:
        config["num_experts"] = 8
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    report = metric_smoke_utils.PreflightReport()

    if top_level_moe:
        metric_scenarios._require_moe_model(str(tmp_path), report, get_scenario("eplb"))
    else:
        with pytest.raises(metric_scenarios.ScenarioUnavailable, match="EPLB requires a MoE model config"):
            metric_scenarios._require_moe_model(str(tmp_path), report, get_scenario("eplb"))


def test_scenario_expectations_cover_stable_and_triggered_metrics():
    basic_expectations = get_scenario("basic").expectations()
    eplb_expectations = get_scenario("eplb").expectations()

    assert len([item for item in basic_expectations if item.required]) == 4
    assert all(item.increase for item in basic_expectations if item.required)
    assert len([item for item in basic_expectations if item.triggered]) == 1
    assert len([item for item in eplb_expectations if item.required]) == 2
    assert len([item for item in eplb_expectations if item.triggered]) == 3


def test_metric_runner_restarts_collection_before_service_start(monkeypatch, tmp_path):
    events = []

    class FakeScenario:
        name = "basic"
        startup_timeout = 1
        metric_poll_timeout = 1

        def preflight(self, _context, report):
            report.pass_("scenario:basic", "ok")

        def build_service_env(self, _context):
            return {}

        def build_vllm_args(self, _context, _extra_args):
            return []

        def expectations(self):
            return []

        def validate_startup(self, _service_output):
            events.append("validate_startup")

        def run_requests(self, _context):
            events.append("run_requests")
            return SimpleNamespace(get_output_tail=lambda _limit: "request log")

    class FakeServer:
        output_lines = ["service log"]

        def __init__(self, **_kwargs):
            events.append("server_init")

        def ready_go(self):
            events.append("ready_go")
            return True

        def get_output_tail(self, _limit=None):
            return "service log"

        def kill(self):
            events.append("kill")

    monkeypatch.setattr(metric_runner, "get_scenario", lambda _name: FakeScenario())
    monkeypatch.setattr(metric_runner, "require_command", lambda name, _report: events.append(f"require:{name}"))
    monkeypatch.setattr(metric_runner, "check_model_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(metric_runner, "check_npu", lambda devices, **_kwargs: devices)
    monkeypatch.setattr(metric_runner, "choose_service_port", lambda *_args, **_kwargs: 8000)
    monkeypatch.setattr(metric_runner, "prepare_prometheus_dir", lambda *_args, **_kwargs: str(tmp_path / "prom"))
    monkeypatch.setattr(metric_runner, "install_metric_source", lambda **_kwargs: {})
    monkeypatch.setattr(metric_runner, "collect_runtime_info", lambda: {})
    monkeypatch.setattr(metric_runner, "restart_metric_collection", lambda: events.append("restart"))
    monkeypatch.setattr(metric_runner, "ExecVLLMServer", FakeServer)
    monkeypatch.setattr(metric_runner, "wait_http_ok", lambda _url: events.append("wait_http_ok"))
    monkeypatch.setattr(metric_runner, "fetch_text", lambda _url: "metrics")
    monkeypatch.setattr(
        metric_runner,
        "wait_for_metric_expectations",
        lambda **_kwargs: ("metrics", SimpleNamespace(passed=[], failed=[], skipped_optional=[])),
    )
    monkeypatch.setattr(
        metric_runner,
        "assert_metric_log_health",
        lambda *_args, **_kwargs: SimpleNamespace(fatal=[], warnings=[], scanned_metric_lines=0),
    )

    metric_runner.run_metric_scenario(
        metric_runner.MetricRunnerConfig(
            scenario="basic",
            model_path="/model",
            devices=[0],
            workspace=str(tmp_path),
            debug=True,
        )
    )

    assert events.index("restart") < events.index("server_init")
    assert events.index("restart") < events.index("ready_go")
    assert events.index("wait_http_ok") < events.index("run_requests")


def test_explicit_devices_override_visible_devices(monkeypatch):
    monkeypatch.setenv("ASCEND_RT_VISIBLE_DEVICES", "0")

    assert _parse_visible_devices([0, 1]) == [0, 1]
    assert _parse_visible_devices([]) == [0]
