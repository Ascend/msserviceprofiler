# vLLM Serving Prometheus Metric Monitoring Tool User Guide

## Introduction

This metric monitoring tool enhances the native monitoring capability of the vLLM-Ascend inference framework. While vLLM-Ascend provides basic metrics out of the box, this tool adds the following capabilities:

- **KVCache monitoring**: tracks total blocks, idle block count, and the number of blocks allocated per DP domain.
- **Token and throughput**: monitors the number of input/output tokens and total tokens per DP domain.
- **Custom metric**: adds a timer metric for the execution duration of any function.

## Supported Products

>[!NOTE]
>
>For details about Ascend product models, see [Ascend Product Models](https://www.hiascend.com/document/detail/en/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html).

|Product Type| Supported (Yes/No)|
|--|:----:|
|Atlas A3 training products and Atlas A3 inference products|  Yes  |
|Atlas A2 training products and Atlas A2 inference products|  Yes  |
|Atlas 200I/500 A2 inference products|  Yes  |
|Atlas inference products|  Yes  |
|Atlas training products|  No   |

## Preparations

### Environment Setup

1. In the Ascend environment, install the matching CANN Toolkit and ops operator packages, and configure CANN environment variables. For details, see [CANN Installation Guide](https://www.hiascend.com/cann/download).
2. Install vLLM and vLLM-Ascend. Verify that vLLM-ascend can run properly and the metrics endpoint is accessible. For details, see [vLLM-Ascend Installation Guide](https://vllm-ascend.readthedocs.io/en/latest/installation.html).
3. Build the .run package from the source code and upgrade the tool. For details, see the section *Upgrade* in [msServiceProfiler Installation Guide](./msserviceprofiler_install_guide.md#upgrade).

### Restrictions

- **Version compatibility**: Ensure that vLLM-Ascend, CANN, and collection tool versions meet the requirements in the Appendix.
- **Resource usage**: Data monitoring requires enabling **Prometheus multi-process mode** (`PROMETHEUS_MULTIPROC_DIR`). This may impact inference performance.
- **Function restrictions**: Some advanced features may require specific vLLM-Ascend versions.

## Instructions

### Quick Start

Follow these steps to complete the metric monitoring process:

1. **Set environment variables and start the service** (with Prometheus multi-process mode enabled).
2. **Enable the collection function** by modifying the `metric_enable` field in the configuration file (independent of the `enable` field).
3. **Send an inference request**.
4. **View metrics** by accessing the metrics endpoint or Grafana.

### Step 1: Environment Variable Setup and Service Startup

Before starting the inference service, set the following environment variables:

| Environment Variable| Description|
|----------|------|
| `SERVICE_PROF_CONFIG_PATH` | Path to the performance profiling configuration file.|
| `METRIC_SYMBOLS_PATH` | (Optional) Path to the symbol/event tracking configuration file. If the path is not specified, the default configuration is used.|
| `PROMETHEUS_MULTIPROC_DIR` | (**Mandatory**) Prometheus multi-process mode directory (an empty directory must be created in advance.)|

```bash
cd ${path_to_store_config_files}
export SERVICE_PROF_CONFIG_PATH=ms_service_profiler_config.json
export METRIC_SYMBOLS_PATH=service_metrics_symbols.yaml

# (Mandatory) Enable the Prometheus multi-process mode.
mkdir -p /path/to/your/prometheus/dir
export PROMETHEUS_MULTIPROC_DIR=/path/to/your/prometheus/dir

# Start the vLLM service.
vllm serve Qwen/Qwen2.5-0.5B-Instruct &
```

- `ms_service_profiler_config.json` is the collection configuration file (shared with performance profiling). **`metric_enable`** controls Prometheus metric collection, and **`enable`** controls performance profiling. If the file does not exist, the default configuration is automatically generated. For details, see [Data Collection](./msserviceprofiler_serving_tuning_instruct.md#data-collection).
- `service_metrics_symbols.yaml` configures symbols. For details about how to customize symbols, see [Symbol Configuration User Guide](#Symbol Configuration User Guide).
- 8000 is the default port for vLLM serving inference startup. This document uses port 8000 as an example. To change the serving startup port, you can use the `--port` command line parameter to specify a port when starting the vLLM service. For details, see [vllm serve Command Parameter Description](https://docs.vllm.com.cn/en/latest/cli/serve/#arguments).

### Step 2 Profiler Collection Enabling

In this tool, **`metric_enable`** in the `ms_service_profiler_config.json` configuration file controls **metric collection**. **`metric_enable`** is independent of the **`enable`** field (which controls performance profiling), so you can enable them separately or together.

**Enable metric collection** by setting `metric_enable` in `ms_service_profiler_config.json` to `1`. If the field is not set (default) or does not exist, it is set to `0`, metric collection is disabled. If the JSON file does not contain the `metric_enable` field, manually add it and change the value to `1`.

```bash
sed -i 's/"metric_enable":\s*0/"metric_enable": 1/' ./ms_service_profiler_config.json
```

The modification takes effect without restarting the service. When the function is enabled or disabled, the corresponding information (for example, "Metric collection enabled" or "Metric collection disabled") is recorded in the log.

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

You can also configure Prometheus to scrape metrics from this endpoint and visualize the metrics using Grafana.

## Symbol Configuration User Guide

### Function

The symbol configuration file defines the functions/methods to be monitored, and supports flexible configuration and custom attribute collection.

### Precautions

- When the collection symbols are updated, you need to **restart the vLLM service** to load the new configuration.
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

The following are metric symbols built into the tool. All metric names are automatically prefixed with `vllm_profiling_` and contain the `dp` label. (The scheduling process is the actual DP domain ID, and the request process is `-1`.)

#### Metrics for scheduling and batch processing

| Metric Name| Type| Description|
|----------|------|------|
| batch_size | Histogram | Number of requests that are being executed|
| waiting_batch_size | Histogram | Number of requests to be scheduled|
| num_spec_tokens | Gauge | Number of draft tokens in speculative decoding|

#### Token metrics

| Metric Name| Type| Description|
|----------|------|------|
| total_tokens | Histogram | Sum of prompt and generation tokens in a single iteration|
| input | Counter | Number of tokens in the input prompt|
| output | Counter | Number of tokens in the generated output|
| second_token_latency | Histogram | Latency for generating the second token|
| fine_grained_ttft | Histogram | Fine-grained time to first token (TTFT)|
| fine_grained_tpot | Histogram | Fine-grained time per output token (TPOT)|

#### KVCache metrics

| Metric Name| Type| Description|
|----------|------|------|
| total_kvcache_blocks | Gauge | Total number of KVCache blocks in the current DP domain.|
| free_kvcache_blocks | Gauge | Number of idle KVCache blocks in the current DP domain.|
| allocated_kvcache_blocks | Gauge | Number of blocks allocated to the KVCache in the current DP domain.|

>![](public_sys-resources/icon-tip.gif)**Note**: The KVCache usage can be approximately calculated as `(1 - free_kvcache_blocks / total_kvcache_blocks) * 100%`. This helps monitor memory usage and load balancing.

## Relevant Documents

- [vLLM Service Profiler] (./vLLM_service_oriented_performance_collection_tool.md): Performance Profiling and Trace Analysis
- [Data Collection Configuration Description](./msserviceprofiler_serving_tuning_instruct.md#Data Collection): `ms_service_profiler_config.json` Configuration Description
