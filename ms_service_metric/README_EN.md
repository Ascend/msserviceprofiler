# ms_service_metric

A lightweight Python service metric collection library that supports dynamic hooks and Prometheus metric output.

## Features

- 🔧 **Dynamic Hooks**: Hook target functions dynamically based on YAML configuration
- 📊 **Prometheus Integration**: Supports metric types such as Timer, Counter, Gauge, and Histogram
- 🔄 **Dynamic Switch**: Runtime switch control through shared memory and signals
- 🏗️ **Framework Adaptation**: Built-in vLLM framework adapter (SGLang provided as a sample reference)
- 🔍 **Locals Access**: Access function local variables through bytecode injection

## Installation

```bash
pip install ms_service_metric
```

### Dependencies

- Python >= 3.10
- pyyaml
- prometheus-client
- posix_ipc (Linux platform)

## Quick Start

### 1. vLLM Integration

vLLM is automatically adapted through the entry_points mechanism. No additional code is required:

1. Install `ms_service_metric`.
2. Set the environment variables for vLLM multi-process metric collection.

```bash
# Enable vLLM multi-process metric collection environment variables
export PROMETHEUS_MULTIPROC_DIR=/dev/shm/vllm_metrics && mkdir -p $PROMETHEUS_MULTIPROC_DIR

# Optional: clean up previous metric files
# rm -rf $PROMETHEUS_MULTIPROC_DIR/*

# Enable metric collection and confirm it is enabled
ms-service-metric on

ms-service-metric status

# If metrics were previously enabled and the content was modified afterward, restart is required
ms-service-metric restart

# Start vLLM
# vllm serve --model your_model
```

### 2. Controlling Metric Collection

```bash
# Enable metric collection
ms-service-metric on

# Disable metric collection
ms-service-metric off

# Restart (reload configuration)
ms-service-metric restart

# View status
ms-service-metric status
```

### 3. Prometheus + Grafana Visualization (Windows)

> [!NOTE]
>
> Grafana and Prometheus are third-party open source software. They are not part of the MindStudio Service Profiler or MindStudio product release package, nor are they the only visualization solution required by this tool. Users can choose Grafana, Prometheus, or other compatible monitoring and visualization systems based on their environment.
>
> If you choose to use Prometheus, use the officially maintained secure version. Complete security hardening such as access control, network isolation, and permission configuration based on your actual deployment environment.

#### Installing Prometheus

1. Download the Prometheus Windows version:
   - Visit the [Prometheus download page](https://prometheus.io/download/)
   - Download `prometheus-<version>.windows-amd64.zip`

2. Extract and configure:

   ```powershell
   # Extract to the specified directory
   Expand-Archive -Path prometheus-*.zip -DestinationPath C:\Prometheus
   ```

3. Modify the `prometheus.yml` configuration file to add a vLLM metric collection job:

   ```yaml
   scrape_configs:
     - job_name: 'vllm'
       static_configs:
         - targets: ['localhost:8000']
       metrics_path: /metrics
   ```

4. Start Prometheus:

   ```powershell
   cd C:\Prometheus
   .\prometheus.exe --config.file=prometheus.yml
   ```

   Prometheus default access address: `http://localhost:9090`

#### Installing Grafana

1. Download the Grafana Windows version:

   - Visit the [Grafana download page](https://grafana.com/grafana/download?platform=windows)
   - Download and run the installer

2. Start the Grafana service:

   ```powershell
   # Start through the service manager
   net start grafana

   # Or start manually
   cd "C:\Program Files\GrafanaLabs\grafana\bin"
   .\grafana-server.exe
   ```

   Grafana default access address: `http://localhost:3000`
   - Default username: `admin`
   - Default password: `admin`

#### Importing a Dashboard

1. Log in to the Grafana web interface (`http://localhost:3000`).

2. Create a Prometheus data source:
   - Left menu: **Configuration** → **Data sources**
   - Click **Add data source**
   - Select **Prometheus**
   - Enter the URL: `http://localhost:9090`
   - Click **Save & Test**

3. Import the MsServiceMetric Dashboard:
   - Left menu: **Dashboards** → **Import**
   - Click **Upload dashboard JSON file**
   - Select the [Dashboard sample file (download to local, matching the default collection configuration)](https://gitcode.com/Ascend/msserviceprofiler/blob/26.1.0/ms_service_metric/example/MsServiceMetric-grafana-Dashboard.json) file
   - Click **Import**
   - Select the Prometheus data source you just created

### 4. More Information

For detailed usage, refer to the [Usage Guide](https://gitcode.com/Ascend/msserviceprofiler/blob/26.1.0/docs/zh/vLLM_metrics_tool_instruct.md).

## vLLM Built-in Metrics Overview

The default vLLM adapter adds a `vllm_profiling_` prefix to metric names and adds a `dp` label by default. Some metrics include additional labels, such as `engine`, `req_phase`, `phase`, `role`, `name`, `rank`, `layer`, `threshold`, and `exception_type`.

### Scheduling and Batching

| Metric Name | Type | Description |
|----------|------|------|
| batch_size | Histogram | Current number of requests being processed |
| waiting_batch_size | Histogram | Current number of requests waiting for scheduling |
| num_spec_tokens | Histogram | Number of draft tokens in speculative decoding |
| scheduler:duration | Histogram | Duration of a single scheduling operation |
| scheduler:batch_size | Histogram | Number of requests output by a single scheduling operation |
| scheduler:running_queue_size | Histogram | Number of requests in the running queue after scheduling |
| scheduler:seqlen:avg | Gauge | Average sequence length within a single scheduling batch |
| scheduler:seqlen:sum | Gauge | Sum of sequence lengths within a single scheduling batch |
| scheduler:phase_batch_size | Histogram | Number of scheduled requests per request phase |
| scheduler:phase_scheduled_tokens | Histogram | Number of tokens scheduled per request phase in a single scheduling operation |
| scheduler:phase_scheduled_token_counter | Counter | Cumulative number of tokens scheduled per request phase |
| running_phase_batch_size | Histogram | Number of requests per request phase in the running queue |
| waiting_phase_batch_size | Histogram | Number of requests per request phase in the waiting queue |
| scheduler:add_request:duration | Histogram | Duration of adding a request to the waiting queue |
| scheduler:update_from_output:duration | Histogram | Duration of the scheduler processing model output and updating state |
| scheduler:recompute_events | Counter | Number of recomputation triggers |

### Tokens and Slow Requests

| Metric Name | Type | Description |
|----------|------|------|
| total_tokens | Histogram | Sum of prompt tokens and generation tokens in a single iteration |
| input | Histogram | Number of tokens in the input prompt |
| output | Histogram | Number of tokens in the output generation result |
| second_token_latency | Histogram | Generation latency of the second token |
| fine_grained_ttft | Histogram | Fine-grained time to first token (TTFT) |
| fine_grained_tpot | Histogram | Fine-grained time per output token (TPOT) |
| decode_over_1s_count | Counter | Cumulative count of single-token intervals exceeding 1s during the decode phase |
| prefill_over_threshold_count | Counter | Cumulative count of first-token latency exceeding the 5s, 10s, and 20s thresholds during the prefill phase |

### KVCache and Memory

| Metric Name | Type | Description |
|----------|------|------|
| total_kvcache_blocks | Gauge | Total number of KVCache blocks in the current DP domain |
| free_kvcache_blocks | Gauge | Number of free KVCache blocks in the current DP domain |
| allocated_kvcache_blocks | Gauge | Number of allocated KVCache blocks in the current DP domain |
| block_allocate_failures | Counter | Number of KVCache block allocation failures |
| engine:memory:total_gb | Gauge | Total device memory at NPUWorker initialization, in GiB |
| engine:memory:utilization_ratio | Gauge | Configured memory utilization ratio in vLLM |
| engine:memory:reserved_gb | Gauge | Memory reserved by vLLM based on the utilization ratio, in GiB |
| engine:memory:weights_gb | Gauge | Memory occupied by model weights, in GiB |
| engine:memory:kvcache_gb | Gauge | Memory available for KVCache, in GiB |
| engine:memory:non_torch_gb | Gauge | Memory occupied by non-PyTorch components, in GiB |
| engine:memory:activation_gb | Gauge | Peak activation memory during profiling, in GiB |
| engine:memory:graph_gb | Gauge | Memory occupied by NPU Graph, in GiB |
| engine:memory:torch_reserved_gb | Gauge | PyTorch reserved memory at runtime in vllm-ascend, in GiB |
| engine:memory:torch_allocated_gb | Gauge | PyTorch allocated memory at runtime in vllm-ascend, in GiB |

### Engine, Executor, and NPU Duration

| Metric Name | Type | Description |
|----------|------|------|
| engine:async_add_request:duration | Histogram | Duration of AsyncLLM adding a request |
| engine:generate:duration | Histogram | End-to-end generation duration of AsyncLLM.generate |
| engine:tokenizer_encode | Histogram | Duration of input processing and tokenizer encoding |
| async_llm:record_stats:duration | Histogram | Duration of AsyncLLM recording stats |
| async_llm:abort_requests:duration | Histogram | Duration of AsyncLLM aborting requests |
| output_processor_duration | Histogram | Duration of OutputProcessor processing output |
| engine_core_outputs_len | Histogram | Number of engine core outputs processed by OutputProcessor in a single operation |
| engine_core:process_input_queue:duration | Histogram | Duration of EngineCore processing the input queue |
| engine_core:process_engine_step:duration | Histogram | Duration of EngineCore processing an engine step |
| engine_core:engine_core_step:duration | Histogram | Duration of a single EngineCore step execution |
| executor:execute_model:duration | Histogram | Duration of MultiprocExecutor executing the model |
| executor:model_runner_execute_model:duration | Histogram | Execution duration of NPUModelRunner.execute_model |
| executor:prepare_inputs:duration | Histogram | Duration of NPUModelRunner preparing inputs |
| executor:sample_tokens:duration | Histogram | Duration of MultiprocExecutor.sample_tokens sampling |
| worker:model_runner_get_output:duration | Histogram | Duration of ModelRunnerOutput.get_output |
| record_function_or_nullcontext | Histogram | Duration of internal record function segments in vLLM/vLLM-Ascend |
| npu:forward_duration | Histogram | Duration of the forward phase |
| npu:kernel_launch | Histogram | Kernel launch related duration between forward and post-processing |
| npu:non_forward_duration | Histogram | Non-forward duration between ModelRunner output and the end of the current round |

### Exception Status and EPLB

| Metric Name | Type | Description |
|----------|------|------|
| running_to_waiting_count | Counter | Number of times requests fall back from the running queue to the waiting queue |
| request_prefill_pending_nums | Counter | Cumulative count of pending requests when the running queue is full and requests remain in waiting/skipped_waiting |
| rpc_errors | Counter | Number of MultiprocExecutor.collective_rpc exceptions |
| health_check_failed | Counter | Number of `/health` check failures, 503 responses, or EngineDeadError occurrences |
| eplb:expert_hotness:current_mean | Gauge | Mean expert hotness before EPLB update |
| eplb:expert_hotness:current_max | Gauge | Maximum expert hotness before EPLB update |
| eplb:expert_hotness:update_mean | Gauge | Mean expert hotness after EPLB update |
| eplb:expert_hotness:update_max | Gauge | Maximum expert hotness after EPLB update |
| eplb:expert_hotness:imbalance | Gauge | Expert hotness imbalance across layers in EPLB |
| eplb:expert_weight_update:duration | Histogram | Total duration of EPLB expert mapping and weight update |
| eplb:expert_map_update:duration | Histogram | Duration of EPLB expert mapping update |
| eplb:log2phy_map_update:duration | Histogram | Duration of EPLB logical-to-physical mapping update |
| eplb:expert_weight_replace:duration | Histogram | Duration of EPLB expert weight replacement |

## Configuration

You can customize the content to collect by specifying a YAML file through the MS_SERVICE_METRIC_VLLM_CONFIG environment variable. If not specified, the internal collection configuration is used by default.

### Configuration File Format

Create a YAML configuration file:

```yaml
# Use the default timer handler
- symbol: my_module:MyClass.my_method
  metrics:
    - name: my_method_duration
      type: timer
      labels:
        - name: method
          expr: "ret.method"  # Attribute access

# Use counter to count the list length
- symbol: my_module:process_batch
  metrics:
    - name: batch_size
      type: counter
      expr: "len(items)"  # Function call

# Use gauge to record a value
- symbol: my_module:get_queue_length
  metrics:
    - name: queue_length
      type: gauge
      expr: "queue.size"  # Attribute access

# Use histogram to collect duration distribution
- symbol: my_module:process_data
  metrics:
    - name: processing_time
      type: histogram
      expr: "duration"  # Built-in variable: execution duration (seconds)
      buckets: [0.001, 0.01, 0.1, 1.0, 10.0]

# Use a custom handler (when a handler is specified, metrics configuration is generally not needed)
- symbol: my_module:complex_process
  handler: my_handlers:custom_handler
```

### Configuration Item Description

| Field | Type | Required | Description |
|------|------|------|------|
| symbol | string | Yes | Target symbol path. Format: `module.path:ClassName.method_name` |
| handler | string | No | Custom handler path. Format: `module.path:function_name`. When a handler is specified, metrics configuration is generally not needed |
| min_version | string | No | Minimum version requirement |
| max_version | string | No | Maximum version requirement |
| metrics | list | No | Metric configuration list (configured when using the default handler) |

### Metrics Configuration

| Field | Type | Required | Description |
|------|------|------|------|
| name | string | Yes | Metric name |
| type | string | Yes | Metric type: timer/counter/gauge/histogram |
| expr | string | No | Expression (required for non-timer types) |
| labels | list | No | Label configuration |
| buckets | list | No | Histogram buckets (for histogram type) |

### Environment Variables

| Variable Name | Description | Default Value |
|--------|------|--------|
| MS_SERVICE_METRIC_CONFIG_PATH | Configuration file path | None |
| MS_SERVICE_METRIC_SHM_PREFIX | Shared memory prefix | /ms_service_metric |
| MS_SERVICE_METRIC_MAX_PROCS | Maximum number of processes | 1000 |
| PROMETHEUS_MULTIPROC_DIR | Multi-process metric directory | None |

## Handler Types

### Wrap Handler

A wrapper function type that requires manual invocation of the original function:

```python
def my_wrap_handler(ori_func, *args, **kwargs):
    # Pre-processing
    start_time = time.time()

    # Call the original function
    result = ori_func(*args, **kwargs)

    # Post-processing
    duration = time.time() - start_time
    print(f"Duration: {duration}")

    return result
```

### Context Handler

A context manager type that uses yield to control the execution flow. When you use a context handler, local variables are automatically accessible:

```python
def context_handler(ctx):
    # ctx: FunctionContext object
    # ctx.return_value: return value (available after yield)
    # ctx.locals: locals dictionary of the function

    # Pre-processing
    start_time = time.time()
    print(f"Locals before: {ctx.locals}")

    yield  # The original function executes here

    # Post-processing
    duration = time.time() - start_time
    print(f"Duration: {duration}")
    print(f"Result: {ctx.return_value}")
    print(f"Locals after: {ctx.locals}")
```

**Default Handler:** The handler type is automatically determined based on whether the `expr` field exists in the configuration:

- With `expr`: Creates a context handler (can access locals)
- Without `expr`: Creates a wrap handler

**Configuration Sample:**

```yaml
# Use a custom context handler (handle metrics within the handler)
- symbol: my_module:complex_function
  handler: my_handlers:context_handler

# Use the default handler (with expr, automatically creates a context handler)
- symbol: my_module:another_function
  metrics:
    - name: item_count
      type: counter
      expr: "len(items)"  # items is a local variable within the function
```

## Multiple Handler Composition

The same symbol can be configured with multiple handlers, executed in an onion model:

```yaml
- symbol: my_module:process
  handler: handlers:auth_check
- symbol: my_module:process
  handler: handlers:timing
  metrics:
    - name: process_duration
      type: timer
```

Execution order: `auth_check -> timing -> original function -> timing -> auth_check`

## Framework Adaptation

### vLLM

Automatically adapted through entry_points. After installation, it can be used without additional code.

### SGLang (Sample Reference)

> **Note**: The SGLang adapter is provided only as a sample reference and is not a formally released feature.

```python
from ms_service_metric.adapters.sglang import initialize_sglang_metric

# Initialize
initialize_sglang_metric()
```

### Custom Adapter

```python
from ms_service_metric.core import SymbolHandlerManager

class MyAdapter:
    def __init__(self):
        self._manager = SymbolHandlerManager()

    def initialize(self, config_path: str):
        self._manager.initialize(config_path)

    def shutdown(self):
        self._manager.shutdown()
```

## Development

### Installing Development Dependencies

```bash
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest tests/
```

### Code Style

```bash
black ms_service_metric/
flake8 ms_service_metric/
```

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    SymbolHandlerManager                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ SymbolConfig│  │SymbolWatcher│  │ MetricConfigWatch   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                          │                                   │
│                          ▼                                   │
│                    ┌───────────┐                             │
│                    │  Symbol   │                             │
│                    └───────────┘                             │
│                          │                                   │
│              ┌───────────┼───────────┐                       │
│              ▼           ▼           ▼                       │
│         ┌────────┐ ┌────────┐ ┌────────┐                    │
│         │Handler │ │Handler │ │Handler │                    │
│         └────────┘ └────────┘ └────────┘                    │
│              │           │           │                       │
│              └───────────┼───────────┘                       │
│                          ▼                                   │
│                    ┌───────────┐                             │
│                  HookHelper   │                             │
│                    └───────────┘                             │
│                          │                                   │
│                          ▼                                   │
│                    ┌───────────┐                             │
│                 Target Func   │                             │
│                    └───────────┘                             │
└─────────────────────────────────────────────────────────────┘
```

## Security Risks

Metric data monitoring uses the metric functionality of vLLM to provide an external interface. For details, refer to the [vLLM observability documentation](https://github.com/vllm-project/vllm/tree/main/examples/observability/prometheus_grafana). If you integrate Prometheus or Grafana, note that both are third-party open source software. They are not part of the MindStudio product release package, nor are they the only visualization solution required by this tool. Users can choose compatible monitoring and visualization systems based on their environment. If you use Prometheus, use the officially maintained secure version and complete security hardening such as access control, network isolation, and permission configuration based on your actual deployment environment.

## License

Mulan Permissive Software License v2 (Mulan PSL v2)

## Contributing

You are welcome to submit Issues and Pull Requests.
