# vLLM Serving Prometheus Metric Monitoring Tool User Guide

## Introduction

This metric monitoring tool enhances the native monitoring capability of the vLLM-Ascend inference framework. While vLLM-Ascend provides basic metrics out of the box, this tool adds the following capabilities:

- **KVCache monitoring**: tracks total blocks, idle block count, and the number of blocks allocated per DP domain.
- **Token and throughput**: monitors the number of input/output tokens and total tokens per DP domain.
- **Custom metric**: adds a timer metric for the execution duration of any function.

## Supported Products

> [!NOTE]
>
>For details about Ascend product models, see [Ascend Product Models](https://www.hiascend.com/document/detail/en/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html).

<!-- npu="950" id1 -->
- <term>Ascend 950PR&950DT products</term>: Supported
<!-- end id1 -->
<!-- npu="A3" id2 -->
- <term>Atlas A3 products</term>: Supported
<!-- end id2 -->
<!-- npu="910b" id3 -->
- <term>Atlas A2 products</term>: Supported
<!-- end id3 -->
<!-- npu="310b" id4 -->
- <term>Atlas 200I/500 A2 inference products</term>: Supported
<!-- end id4 -->
<!-- npu="310p" id5 -->
- <term>Atlas inference products</term>: Supported
<!-- end id5 -->
<!-- npu="910" id6 -->
- <term>Atlas training products</term>: Not supported
<!-- end id6 -->

## Preparations

### Environment Setup

1. In the Ascend environment, install the matching CANN Toolkit and ops operator packages, and configure CANN environment variables. For details, see [CANN Installation Guide](https://www.hiascend.com/en/cann/download).
2. Install vLLM and vLLM-Ascend. Verify that vLLM-Ascend can run properly and the metrics endpoint is accessible. For details, see [vLLM-Ascend Installation Guide](https://vllm-ascend.readthedocs.io/en/latest/installation.html).

### Restrictions

- **Version compatibility**: Ensure that vLLM-Ascend, CANN, and collection tool versions meet the requirements in the Appendix.
- **Resource usage**: Data monitoring requires enabling **Prometheus multi-process mode** (`PROMETHEUS_MULTIPROC_DIR`). This may impact inference performance.
- **Function restrictions**: Some advanced features may require specific vLLM-Ascend versions.

### Third-Party Visualization Tools

Grafana and Prometheus are third-party open-source software and are not included in the MindStudio Service Profiler or MindStudio release packages. They are also not the only visualization solutions required by this tool. Users may choose Grafana, Prometheus, or other compatible monitoring and visualization systems based on their environment.

If you choose to use Prometheus, ensure you deploy a security-maintained official version and implement appropriate security hardening measures—including access control, network isolation, and permission configuration—according to your deployment environment.

## Instructions

### Installation

```bash
pip install ms_service_metric
```

```bash
# Local installation (for development only; not recommended)
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler/ms_service_metric
pip install -e .
```

### Quick Start

Follow these steps to complete the metric monitoring process:

1. **Set environment variables and start the service** (with Prometheus multi-process mode enabled).
2. **Enable the collection function** by modifying the `metric_enable` field in the configuration file (independent of the `enable` field).
3. **Send an inference request**.
4. **View metrics** by accessing the metrics endpoint or Grafana.

### Step 1: Environment Variable Setup and Service Startup

Before starting the inference service, set the following environment variables.

| Environment Variable| Description|
|----------|------|
| `MS_SERVICE_METRIC_VLLM_CONFIG` | (Optional) Path to the symbol/event tracking configuration file. If the path is not specified, the default configuration is used.|
| `PROMETHEUS_MULTIPROC_DIR` | (**Mandatory**) Prometheus multi-process mode directory (an empty directory must be created in advance.)|

```bash
# Optional. If the path is not specified, the default configuration is used
cd ${path_to_store_config_files}
export MS_SERVICE_METRIC_VLLM_CONFIG=service_metrics_symbols.yaml

# (Mandatory) Enable the Prometheus multi-process mode.
export PROMETHEUS_MULTIPROC_DIR=/dev/shm/vllm_metrics  # /path/to/your/prometheus/dir
mkdir -p $PROMETHEUS_MULTIPROC_DIR

# Start the vLLM service.
vllm serve Qwen/Qwen2.5-0.5B-Instruct &
```

- `service_metrics_symbols.yaml` configures symbols. For details about how to customize symbols, see [Symbol Configuration User Guide](#symbol-configuration-user-guide).
- 8000 is the default port for vLLM serving inference startup. This document uses port 8000 as an example. To change the serving startup port, you can use the `--port` command line parameter to specify a port when starting the vLLM service. For details, see [vllm serve Command Parameter Description](https://docs.vllm.com.cn/en/latest/cli/serve/#arguments).

### Step 2 Profiler Collection Enabling

```bash
# Enable metric collection
ms-service-metric on

# Disable metric collection
ms-service-metric off

# Restart (reload configuration)
ms-service-metric restart

# Check status
ms-service-metric status
```

### Step 3: Request Sending

Send an inference request to generate monitoring data.

```bash
curl http://localhost:8000/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "Qwen/Qwen2.5-0.5B-Instruct",
        "prompt": "Beijing is a",
        "max_tokens": 5,
        "temperature": 0
}' | python3 -m json.tool
```

### Step 4: Metrics Viewing

Obtain data through the metrics endpoint of the vLLM service.

```bash
# Replace localhost:8000 with the serving IP address and port.
curl -s http://localhost:8000/metrics
```

You can also configure Prometheus to scrape metrics from this endpoint and visualize the metrics using Grafana or other tools.

## Symbol Configuration User Guide

### Function

The symbol configuration file defines the functions/methods to be monitored, and supports flexible configuration and custom attribute collection.

### Precautions

- When the collection points are updated, you can reload the configuration with `ms-service-metric restart`.
- All custom metric names are automatically prefixed with `vllm_profiling_` and must comply with [Prometheus Metric and label naming](https://prometheus.io/docs/practices/naming/).

### Configuration Fields

| Field| Description| Example|
|------|------|------|
| symbol| Python import path + attribute chain (format: `module:class.method`)| `vllm.v1.core.kv_cache_manager:KVCacheManager.free` |
| min_version | Earliest compatible version| `"0.9.1"` |
| max_version | Latest compatible version| `"0.11.0"` |
| metrics | List of custom metrics. Currently, the `timer` type is supported (which measures function execution duration).| See the following example.|

### Configuration Example

```yaml
# ===== Custom Metrics =====
- symbol: vllm.entrypoints.openai.serving_chat:OpenAIServingChat.create_chat_completion
  min_version: "0.9.1"
  metrics:
    - name: server:create_chat_completion:duration
      type: timer
```

## Result Description

### Output Example

You can access the metrics endpoint (for example, `http://localhost:8000/metrics`) of the vLLM service to view the current metrics. The following is an example output of the custom `server:create_chat_completion:duration` (`timer` type), which can be visualized using visualization tools like Grafana.

```bash
# Replace localhost:8000 with the serving IP address and port.
curl -s http://localhost:8000/metrics | grep -E "server:create_chat_completion:duration"
```

```ColdFusion
# HELP vllm_profiling_server:create_chat_completion:duration Execution duration of server:create_chat_completion:duration
# TYPE vllm_profiling_server:create_chat_completion:duration histogram
vllm_profiling_server:create_chat_completion:duration_sum{dp="-1"} 15.44140076637268
vllm_profiling_server:create_chat_completion:duration_bucket{dp="-1",le="0.001"} 0.0
...
vllm_profiling_server:create_chat_completion:duration_bucket{dp="-1",le="0.2"} 1.0
...
vllm_profiling_server:create_chat_completion:duration_bucket{dp="-1",le="+Inf"} 9.0
vllm_profiling_server:create_chat_completion:duration_count{dp="-1"} 9.0
```

### Built-in Metric Symbols

The following are default metric symbols built into the tool. All metric names are automatically prefixed with `vllm_profiling_` and contain the `dp` label. (The scheduling process is the actual DP domain ID, and the request process is `-1`.) Some metrics also include additional labels, such as `engine`, `req_phase`, `role`, `name`, `rank`, `phase`, `layer`, `threshold`, and `exception_type`.

#### Metrics for Scheduling and Batch Processing

| Metric Name | Type | Label | Description |
|-------------|------|--------|-------------|
| `batch_size` | Histogram | `engine` | Number of requests currently being executed |
| `waiting_batch_size` | Histogram | `engine` | Number of requests currently waiting to be scheduled |
| `num_spec_tokens` | Histogram | `engine` | Number of draft tokens in speculative decoding |
| `scheduler:duration` | Histogram | — | Duration of a single `Scheduler.schedule` call |
| `scheduler:batch_size` | Histogram | — | Number of requests output in a single scheduling iteration |
| `scheduler:running_queue_size` | Histogram | — | Number of requests in the running queue after scheduling |
| `scheduler:seqlen:avg` | Gauge | — | Average sequence length within a scheduled batch |
| `scheduler:seqlen:sum` | Gauge | — | Total sequence length within a scheduled batch |
| `scheduler:phase_batch_size` | Histogram | `req_phase` | Number of requests by phase (prefill, decode, mixed) in a single scheduling iteration |
| `scheduler:phase_scheduled_tokens` | Histogram | `req_phase` | Number of tokens scheduled per request phase |
| `scheduler:phase_scheduled_token_counter` | Counter | `req_phase` | Cumulative scheduled tokens per request phase |
| `running_phase_batch_size` | Histogram | `req_phase` | Number of requests in the running queue by phase |
| `waiting_phase_batch_size` | Histogram | `req_phase` | Number of requests in the waiting queue by phase |
| `scheduler:add_request:duration` | Histogram | — | Time taken to add a request to the scheduling waiting queue |
| `scheduler:update_from_output:duration` | Histogram | `phase` | Time taken by the scheduler to process model output and update state |
| `scheduler:recompute_events` | Counter | — | Number of recomputation triggers |

#### Token and Slow Request Metrics

| Metric Name | Type | Label | Description |
|-------------|------|--------|-------------|
| `total_tokens` | Histogram | `engine` | Total prompt + generation tokens per iteration |
| `input` | Histogram | `engine` | Number of prompt tokens |
| `output` | Histogram | `engine` | Number of generated tokens |
| `second_token_latency` | Histogram | — | Latency of the second token |
| `fine_grained_ttft` | Histogram | `engine` | Fine-grained time to first token (TTFT) |
| `fine_grained_tpot` | Histogram | `engine` | Fine-grained time per output token (TPOT) |
| `decode_over_1s_count` | Counter | — | Cumulative count of decode-phase token intervals exceeding 1s |
| `prefill_over_threshold_count` | Counter | `threshold` | Cumulative count of prefill TTFT exceeding 5s, 10s, and 20s thresholds |

#### KVCache & Memory Metrics

| Metric Name | Type | Label | Description |
|-------------|------|--------|-------------|
| `total_kvcache_blocks` | Gauge | — | Total number of KV Cache blocks in the current DP domain |
| `free_kvcache_blocks` | Gauge | — | Number of free KV Cache blocks in the current DP domain |
| `allocated_kvcache_blocks` | Gauge | — | Number of allocated KV Cache blocks in the current DP domain |
| `block_allocate_failures` | Counter | — | Number of failed KV Cache block allocations |
| `engine:memory:total_gb` | Gauge | — | Total device memory at NPUWorker initialization (GiB) |
| `engine:memory:utilization_ratio` | Gauge | — | vLLM-configured memory utilization ratio |
| `engine:memory:reserved_gb` | Gauge | — | Memory reserved by vLLM based on utilization ratio (GiB) |
| `engine:memory:weights_gb` | Gauge | — | Memory occupied by model weights (GiB) |
| `engine:memory:kvcache_gb` | Gauge | — | Memory available for KV Cache (GiB) |
| `engine:memory:non_torch_gb` | Gauge | — | Memory occupied by non-PyTorch components (GiB) |
| `engine:memory:activation_gb` | Gauge | — | Peak activation memory during profiling (GiB) |
| `engine:memory:graph_gb` | Gauge | — | Memory occupied by NPU Graph (GiB) |
| `engine:memory:torch_reserved_gb` | Gauge | — | PyTorch reserved memory at runtime in vLLM-Ascend (GiB) |
| `engine:memory:torch_allocated_gb` | Gauge | — | PyTorch allocated memory at runtime in vLLM-Ascend (GiB) |

>[!NOTE]
>
> KVCache utilization can be approximated as `(1 - free_kvcache_blocks / total_kvcache_blocks) * 100%`, which is useful for monitoring memory usage and load balancing. `engine:memory:torch_reserved_gb` and `engine:memory:torch_allocated_gb` are runtime memory metrics, while all other `engine:memory:*` metrics are static memory snapshots taken after worker initialization and are typically recorded only once per process.

#### Engine and End-to-End Latency Metrics

| Metric Name | Type | Label | Description |
|-------------|------|--------|-------------|
| `engine:async_add_request:duration` | Histogram | — | Time taken to add a request in AsyncLLM |
| `engine:generate:duration` | Histogram | — | End-to-end generation time in `AsyncLLM.generate` |
| `engine:tokenizer_encode` | Histogram | — | Input processing and tokenizer encoding time |
| `async_llm:record_stats:duration` | Histogram | `phase` | Time taken to record stats in AsyncLLM |
| `async_llm:abort_requests:duration` | Histogram | `phase` | Time taken to abort requests in AsyncLLM |
| `output_processor_duration` | Histogram | `phase` | Time taken by OutputProcessor to process outputs |
| `engine_core_outputs_len` | Histogram | `phase` | Number of engine core outputs per OutputProcessor cycle |
| `engine_core:process_input_queue:duration` | Histogram | `phase` | Time taken by EngineCore to process the input queue |
| `engine_core:process_engine_step:duration` | Histogram | `phase` | Time taken by EngineCore to process an engine step |
| `engine_core:engine_core_step:duration` | Histogram | `phase` | Time taken for a single EngineCore step |
| `server:create_chat_completion:duration` | Histogram | — | Time taken to process an OpenAI Chat Completion request |

#### Executor and NPU Stage Latency Metrics

| Metric Name | Type | Label | Description |
|-------------|------|--------|-------------|
| `executor:execute_model:duration` | Histogram | `phase` | Time taken by MultiprocExecutor to execute the model |
| `executor:model_runner_execute_model:duration` | Histogram | `phase` | Time taken by `NPUModelRunner.execute_model` |
| `executor:prepare_inputs:duration` | Histogram | `phase` | Time taken by NPUModelRunner to prepare inputs |
| `executor:sample_tokens:duration` | Histogram | `phase` | Time taken by `MultiprocExecutor.sample_tokens` |
| `worker:model_runner_get_output:duration` | Histogram | — | Time taken by `ModelRunnerOutput.get_output` |
| `record_function_or_nullcontext` | Histogram | `name`, `phase`, `role` | Time for internal record function fragments in vLLM/vLLM-Ascend; `name` indicates the fragment name |
| `npu:forward_duration` | Histogram | — | Time spent in the forward pass |
| `npu:kernel_launch` | Histogram | — | Kernel launch time between forward and post-processing |
| `npu:non_forward_duration` | Histogram | — | Non-forward time between ModelRunner output and the end of the current cycle |

#### Error and Anomaly Metrics

| Metric Name | Type | Label | Description |
|-------------|------|--------|-------------|
| `running_to_waiting_count` | Counter | — | Number of times requests moved from the running queue back to the waiting queue |
| `request_prefill_pending_nums` | Counter | — | Cumulative count of pending requests when the running queue is full and waiting/skipped_waiting queues are non-empty |
| `rpc_errors` | Counter | `exception_type` | Number of exceptions in `MultiprocExecutor.collective_rpc` |
| `health_check_failed` | Counter | — | Number of failed health checks (HTTP 503 or `EngineDeadError`) |

#### EPLB Metrics

| Metric Name | Type | Label | Description |
|-------------|------|--------|-------------|
| `eplb:expert_hotness:current_mean` | Gauge | `rank` | Mean expert hotness before EPLB update |
| `eplb:expert_hotness:current_max` | Gauge | `rank` | Maximum expert hotness before EPLB update |
| `eplb:expert_hotness:update_mean` | Gauge | `rank` | Mean expert hotness after EPLB update |
| `eplb:expert_hotness:update_max` | Gauge | `rank` | Maximum expert hotness after EPLB update |
| `eplb:expert_hotness:imbalance` | Gauge | `rank`, `phase`, `layer` | Expert hotness imbalance per layer in EPLB; `phase` is either `current` or `update` |
| `eplb:expert_weight_update:duration` | Histogram | — | Total time for EPLB expert mapping and weight update |
| `eplb:expert_map_update:duration` | Histogram | — | Time taken for EPLB expert mapping update |
| `eplb:log2phy_map_update:duration` | Histogram | — | Time taken for EPLB logical-to-physical mapping update |
| `eplb:expert_weight_replace:duration` | Histogram | — | Time taken for EPLB expert weight replacement |

## Relevant Documents

### Analysis Order

Performance analysis proceeds in the order of service SLO, scheduling and capacity, model execution, and abnormal states:

1. Use `fine_grained_ttft`, `fine_grained_tpot`, and `engine:generate:duration` to determine whether the anomaly affects the first token, subsequent tokens, or the engine generation process. Record the end-to-end latency of the load test client separately; do not mix it with the server-side engine duration.
2. Use `waiting_batch_size`, `batch_size`, and `scheduler:duration` to determine whether requests are blocked in the scheduling phase.
3. Use `free_kvcache_blocks`, `allocated_kvcache_blocks`, `block_allocate_failures`, and `running_to_waiting_count` to determine whether the KVCache is limiting requests from entering the execution phase.
4. Use `executor:execute_model:duration`, `executor:model_runner_execute_model:duration`, and `npu:forward_duration` to determine whether model execution has become slower.
5. Use `output_processor_duration`, `rpc_errors`, and `health_check_failed` to troubleshoot output processing and abnormal paths.
6. Break the results down by `instance`, `dp`, `phase`, and `rank` to distinguish global problems from local hotspots.

All comparisons must use the same model, version, input/output token distribution, concurrency, and service parameters. Judge anomalies against a normal window under the same load; only trends formed by consecutive collection points count as diagnostic evidence.

### Querying by Metric Type

| Type | Correct Usage | Description |
|---|---|---|
| Gauge | View the current value, range, and instance differences directly | Applies to state values such as KVCache blocks and device memory |
| Counter | Use `rate()` for the rate and `increase()` for the window increment | A process restart resets the counter to zero |
| Histogram | Use `_bucket` to calculate quantiles and `_sum/_count` to calculate the average | The `le` label must be kept when calculating quantiles |

The following PromQL uses the actual exported `vllm_profiling_` prefix. Adjust the query window according to the scrape interval and the load test duration.

Scheduling duration P99:

```promql
histogram_quantile(
  0.99,
  sum by (le, instance, dp) (
    rate(vllm_profiling_scheduler:duration_bucket[5m])
  )
)
```

Average model execution duration:

```promql
sum by (instance, dp, phase) (
  rate(vllm_profiling_executor:execute_model:duration_sum[5m])
)
/
sum by (instance, dp, phase) (
  rate(vllm_profiling_executor:execute_model:duration_count[5m])
)
```

KVCache utilization:

```promql
100 * (
  1 -
  vllm_profiling_free_kvcache_blocks
  /
  vllm_profiling_total_kvcache_blocks
)
```

KVCache allocation failure increment:

```promql
sum by (instance, dp) (
  increase(vllm_profiling_block_allocate_failures_total[5m])
)
```

Scheduling recomputation increment:

```promql
sum by (instance, dp) (
  increase(vllm_profiling_scheduler:recompute_events_total[5m])
)
```

Speculative inference acceptance rate:

```promql
sum by (instance, role) (
  rate(vllm:spec_decode_num_accepted_tokens_total[5m])
)
/
clamp_min(
  sum by (instance, role) (
    rate(vllm:spec_decode_num_draft_tokens_total[5m])
  ),
  1e-9
)
```

The speculative inference acceptance rate uses the native counters of vLLM and equals the number of accepted draft tokens in the window divided by the total number of draft tokens. Keep the instance dimension; windows in which the denominator has no increment do not take part in the comparison.

### Metric Combinations and Determination Conclusions

| Metric Combination | Determination Conclusion | Tracing Checks |
|---|---|---|
| TTFT rises; waiting rises; model execution duration is stable | The extra duration occurs before model execution | Scheduling spans, the gap between scheduling and model execution |
| waiting rises; scheduler P99 rises; NPU utilization is low; model duration is stable | The scheduling or host path is the bottleneck | The difference between `vllm.scheduler.schedule` and the model span |
| Free blocks stay low; allocation failures increase; waiting and TTFT rise together | KVCache capacity limits request scheduling | Request association, the wait interval after scheduling, and a control trace with the same token scale |
| Speculative inference acceptance rate drops; TPOT or output token throughput degrades; draft token scale is stable | The effective output of draft tokens decreases | Tracing is used only to rule out the scheduling, execution, and output phases; the acceptance rate is confirmed with counters or the Profiler |
| TPOT rises; execute model and forward rise together; scheduler is stable | The model execution phase has become slower | `vllm.model.execute`, `vllm_ascend.model_runner.execute` |
| execute model rises; model runner is stable | The overhead around the executor increases | IPC, synchronization, data preparation, and the gaps between spans |
| output processor rises; model is stable | The output processing phase has become slower | `vllm.output.process` |
| Only some dp/rank are abnormal | Local load or resource imbalance | Compare the request and token scale of abnormal and normal dp/rank |

A single metric is not a direct root cause. A conclusion must contain at least one SLO metric, one phase metric, and one capacity or execution metric, and these metrics must change consistently in the same time window.

### Optional: Drilling Down from Metrics to Tracing

If the metrics already support a phase or capacity conclusion, you can proceed directly to handling and re-testing. When you need to inspect a specific request path, associate Tracing as follows:

1. In Grafana, record the anomaly start time, end time, instance, DP domain, and request phase.
2. In Jaeger, select a lookback that covers this time window and limit it to the same service.
3. Select normal and abnormal observation groups with the same token scale and request phase.
4. Use `request.id`, `request.ids`, trace IDs, and span links to confirm the association between requests and batches.
5. Compare the scheduler, model, model runner, and output spans; calculate the gap between spans only for the same trace ID or a unified Perfetto timeline.

For the complete flow, see *[vLLM-Ascend Observability Performance Diagnostics Guide](../best_practices/vllm_ascend_observability_analysis_guide.md)*.

## Related Documents

- [vLLM Service Profiler](./vLLM_service_oriented_performance_collection_tool.md): Performance Profiling and Trace Analysis
- [vLLM Hook Tracing User Guide](./vLLM_hook_tracing_instruct.md): request link analysis
- [vLLM-Ascend Observability Performance Diagnostics Guide](../best_practices/vllm_ascend_observability_analysis_guide.md): joint Metrics and Tracing analysis
- [Data Collection Configuration Description](./msserviceprofiler_serving_tuning_instruct.md#data-collection): `ms_service_profiler_config.json` Configuration Description
