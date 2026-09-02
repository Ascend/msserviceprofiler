# Metric ST

The default command runs only the stable basic scenario:

```bash
python run_metric_st.py \
  --model-path /data/models/Qwen3-8B \
  --metric-source /home/user/msserviceprofiler \
  --workspace /tmp/metric-st
```

Special scenarios are selected explicitly:

```bash
python run_metric_st.py --scenario eplb --model-path /data/models/MoE --device 0 --device 1
python run_metric_st.py --scenario dplb --model-path /data/models/model --device 0 --device 1
```

The EPLB scenario sets `DYNAMIC_EPLB=true`, enables expert parallelism, uses
tensor parallel size equal to the selected device count, and injects the
vllm-ascend `eplb_config` through `--additional-config`.

The runner owns vLLM scenario arguments and capability checks. Advanced arguments
can be appended with `--vllm-extra-arg=--option`.
The default smoke request driver uses short OpenAI-compatible `curl` requests to
avoid depending on version-specific `vllm bench` CLI flags. Increase request
coverage with `--metric-request-count`; EPLB and DPLB also send multiple requests
by default to make runtime metrics easier to trigger.

Each scenario starts an isolated vLLM service. Failed or debug runs keep artifacts
under `<workspace>/metric-smoke/<scenario>/<uuid>/`, including preflight, install,
service, request, raw metrics, and assertion reports.

## Scenario assertions

- `basic`: requires request-time increases for generate, scheduler,
  scheduler add_request, and model runner execute_model duration counters.
  Engine core step and static memory metrics are validated when the installed
  vLLM/vllm-ascend version exposes the corresponding hooks.
- `eplb`: requires current expert hotness mean/max. Per-layer imbalance is
  validated when available. Map, log2phy, and expert weight update durations
  are treated as triggered metrics: they are validated only when the current
  request batch triggers an update.
- `dplb`: requires the scheduler duration counter to increase and verifies
  samples from at least two distinct `dp` ranks.
- `exception`: remains skipped until a deterministic health/RPC failure
  trigger is implemented.

The runner captures `/metrics` before requests and compares it with the final
snapshot. Required counters must increase during the current scenario rather
than merely having a historical value greater than zero.

The runner also scans vLLM service logs for `ms_service_metric` hook and metric
health issues. Any `ms_service_metric` error or critical log fails the smoke.
Targeted metric warnings such as failed metric creation, registration, or
recording also fail the smoke. Optional symbol-not-found messages are recorded
as warnings but do not block multi-version compatibility.

Metric publication is asynchronous, so the runner polls `/metrics` until the
scenario contract passes. `basic` and `dplb` default to 30 seconds; `eplb`
defaults to 60 seconds. Use `--metric-poll-timeout` and
`--metric-poll-interval` to override them.

## EPLB overrides

Defaults match the recommended dynamic EPLB configuration:

```text
--eplb-heat-collection-interval 4
--eplb-algorithm-execution-interval 1
--eplb-policy-type 2
--eplb-num-redundant-experts 4
--eplb-max-model-len 4096
```

Ordinary runs do not need to specify these options.

## Artifacts

Failure or debug-mode artifacts include:

- `preflight.log`: environment, model, NPU, port, and scenario capability checks.
- `metric_install.json`: installed metric source, commit, module, and entry point.
- `service.log`: vLLM startup and runtime logs.
- `request.log`: request or benchmark output.
- `metrics.before.raw`: `/metrics` snapshot before scenario requests.
- `metrics.raw`: final `/metrics` snapshot used for assertions.
- `assertion_report.json`: matched values, baseline values, candidates, and failures.
- `log_health_report.json`: matched `ms_service_metric` fatal logs and non-fatal
  compatibility warnings.

Every run also keeps a lightweight summary under `metric-smoke/summaries`.
It records the scenario, generated vLLM arguments, package versions, metric
source, assertion counts, and log-health counts even when full success artifacts
are cleaned.
