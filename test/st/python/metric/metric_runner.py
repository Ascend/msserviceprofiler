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
import json
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from executor.exec_vllm_server import ExecVLLMServer
from metric.metric_assertions import wait_for_metric_expectations
from metric.metric_log_health import assert_metric_log_health
from metric.metric_scenarios import ScenarioContext, get_scenario
from metric.metric_smoke_utils import (
    PreflightReport,
    check_model_path,
    check_npu,
    collect_runtime_info,
    choose_service_port,
    fetch_text,
    install_metric_source,
    prepare_prometheus_dir,
    require_command,
    restart_metric_collection,
    wait_http_ok,
)


@dataclass
class MetricRunnerConfig:
    scenario: str
    model_path: str
    devices: list[int]
    workspace: str
    debug: bool = False
    metric_source: str = "https://gitcode.com/Ascend/msserviceprofiler.git"
    metric_ref: str = "master"
    metric_install_mode: str = "editable"
    metric_service_port: int | None = None
    metric_skip_npu_busy_check: bool = False
    metric_npu_memory_threshold: int = 90
    vllm_extra_args: list[str] = field(default_factory=list)
    metric_request_count: int = 1
    metric_poll_timeout: float | None = None
    metric_poll_interval: float = 1.0
    scenario_options: dict[str, object] = field(default_factory=dict)


def run_metric_scenario(config: MetricRunnerConfig) -> None:
    run_id = uuid.uuid4().hex
    artifact_dir = Path(config.workspace) / "metric-smoke" / config.scenario / run_id
    summary_dir = Path(config.workspace) / "metric-smoke" / "summaries"
    summary_path = summary_dir / f"{config.scenario}-{run_id}.json"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)
    scenario = get_scenario(config.scenario)
    server = None
    benchmark = None
    succeeded = False
    report = PreflightReport()
    install_info = {}
    runtime_info = {}
    assertion_report = None
    log_health_report = None
    metrics_url = ""
    service_env = {}
    vllm_args = []

    try:
        if config.metric_request_count < 1:
            report.fail("request", f"metric request count must be >= 1, got {config.metric_request_count}")
        if config.metric_poll_interval <= 0:
            report.fail("request", f"metric poll interval must be > 0, got {config.metric_poll_interval}")
        if config.metric_poll_timeout is not None and config.metric_poll_timeout <= 0:
            report.fail("request", f"metric poll timeout must be > 0, got {config.metric_poll_timeout}")
        require_command("vllm", report)
        require_command("curl", report)
        check_model_path(config.model_path, report)
        selected_devices = check_npu(
            config.devices,
            skip_busy_check=config.metric_skip_npu_busy_check,
            memory_threshold=config.metric_npu_memory_threshold,
            report=report,
        )
        port = choose_service_port(config.metric_service_port, report)
        prom_dir = prepare_prometheus_dir(str(artifact_dir), report)

        context = ScenarioContext(
            model_path=config.model_path,
            devices=selected_devices,
            port=port,
            artifact_dir=artifact_dir,
            request_count=config.metric_request_count,
            options=config.scenario_options,
        )
        scenario.preflight(context, report)
        (artifact_dir / "preflight.log").write_text(str(report), encoding="utf-8")
        print(report)

        install_info = install_metric_source(
            source=config.metric_source,
            ref=config.metric_ref,
            install_mode=config.metric_install_mode,
            workspace=str(artifact_dir),
        )
        runtime_info = collect_runtime_info()
        install_record = dict(install_info)
        install_record["runtime"] = runtime_info
        (artifact_dir / "metric_install.json").write_text(
            json.dumps(install_record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        service_env = {
            "PROMETHEUS_MULTIPROC_DIR": prom_dir,
            "ASCEND_RT_VISIBLE_DEVICES": ",".join(str(device) for device in selected_devices),
        }
        service_env.update(scenario.build_service_env(context))
        vllm_args = scenario.build_vllm_args(context, config.vllm_extra_args)
        print(f"[metric-scenario] name={scenario.name}")
        print(f"[metric-scenario] devices={selected_devices}")
        print(f"[metric-scenario] request_count={context.request_count}")
        print(f"[metric-scenario] vllm_args={vllm_args}")
        print(f"[metric-scenario] options={config.scenario_options}")
        for expectation in scenario.expectations():
            print(
                "[metric-expectation] "
                f"required={expectation.required}, forbidden={expectation.forbidden}, "
                f"increase={expectation.increase}, triggered={expectation.triggered}, "
                f"names={expectation.names}, rules={expectation.rules}, "
                f"labels={expectation.labels}, desc={expectation.description}"
            )
        restart_metric_collection()
        server = ExecVLLMServer(
            model_path=config.model_path,
            port=port,
            env=service_env,
            extra_args=vllm_args,
            startup_timeout=scenario.startup_timeout,
        )
        assert server.ready_go(), (
            f"vLLM service startup failed.\nArtifacts: {artifact_dir}\nService log tail:\n{server.get_output_tail()}"
        )
        scenario.validate_startup(server.get_output_tail(500))
        metrics_url = f"http://127.0.0.1:{port}/metrics"
        wait_http_ok(f"http://127.0.0.1:{port}/health")

        baseline_text = fetch_text(metrics_url)
        (artifact_dir / "metrics.before.raw").write_text(baseline_text, encoding="utf-8")
        benchmark = scenario.run_requests(context)

        poll_timeout = config.metric_poll_timeout or scenario.metric_poll_timeout
        metrics_text, assertion_report = wait_for_metric_expectations(
            fetcher=lambda: fetch_text(metrics_url),
            expectations=scenario.expectations(),
            baseline_text=baseline_text,
            timeout=poll_timeout,
            interval=config.metric_poll_interval,
            report_path=artifact_dir / "assertion_report.json",
        )
        (artifact_dir / "metrics.raw").write_text(metrics_text, encoding="utf-8")
        service_log_text = "".join(server.output_lines)
        log_health_report = assert_metric_log_health(
            service_log_text,
            report_path=artifact_dir / "log_health_report.json",
        )
        succeeded = True
    finally:
        (artifact_dir / "preflight.log").write_text(str(report), encoding="utf-8")
        if benchmark:
            (artifact_dir / "request.log").write_text(benchmark.get_output_tail(200), encoding="utf-8")
        if server:
            (artifact_dir / "service.log").write_text(server.get_output_tail(500), encoding="utf-8")
            server.kill()
        _write_run_summary(
            summary_path=summary_path,
            artifact_dir=artifact_dir,
            config=config,
            succeeded=succeeded,
            install_info=install_info,
            runtime_info=runtime_info,
            service_env=service_env,
            vllm_args=vllm_args,
            metrics_url=metrics_url,
            assertion_report=assertion_report,
            log_health_report=log_health_report,
        )
        if succeeded and not config.debug:
            shutil.rmtree(artifact_dir, ignore_errors=True)
        else:
            print(f"metric smoke artifacts: {artifact_dir}")
        print(f"metric smoke summary: {summary_path}")


def _write_run_summary(
    summary_path: Path,
    artifact_dir: Path,
    config: MetricRunnerConfig,
    succeeded: bool,
    install_info: dict,
    runtime_info: dict,
    service_env: dict,
    vllm_args: list[str],
    metrics_url: str,
    assertion_report,
    log_health_report,
) -> None:
    env_summary = {
        key: service_env.get(key)
        for key in ("ASCEND_RT_VISIBLE_DEVICES", "PROMETHEUS_MULTIPROC_DIR", "DYNAMIC_EPLB")
        if key in service_env
    }
    assertion_summary = {}
    if assertion_report is not None:
        assertion_summary = {
            "passed": len(assertion_report.passed),
            "failed": len(assertion_report.failed),
            "optional_skipped": len(assertion_report.skipped_optional),
        }
    log_health_summary = {}
    if log_health_report is not None:
        log_health_summary = {
            "fatal": len(log_health_report.fatal),
            "warnings": len(log_health_report.warnings),
            "scanned_metric_lines": log_health_report.scanned_metric_lines,
        }
    summary = {
        "scenario": config.scenario,
        "model_path": config.model_path,
        "devices": config.devices,
        "request_count": config.metric_request_count,
        "scenario_options": config.scenario_options,
        "vllm_args": vllm_args,
        "service_env": env_summary,
        "metric_source": {
            "source": config.metric_source,
            "ref": config.metric_ref,
            "install_mode": config.metric_install_mode,
        },
        "metric_install": install_info,
        "runtime": runtime_info,
        "metrics_url": metrics_url,
        "artifact_dir": str(artifact_dir),
        "artifact_retained": (not succeeded) or config.debug,
        "succeeded": succeeded,
        "assertions": assertion_summary,
        "log_health": log_health_summary,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
