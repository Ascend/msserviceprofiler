# ms_service_metric

A lightweight Python service indicator collection library that supports dynamic Hook and Prometheus indicator output.

## Features

 * Dynamic Hook: Configure the dynamic hook objective function based on YAML.
 * Prometheus integration: supports timer, counter, Gauge, and Histogram indicators.
 * Dynamic switch: Runtime switch control through shared memory and signals
 * Framework adaptation: built-in vLLM framework adapter (SGLang is used as an example.)
 * Locals access: Access function local variables through bytecode injection.

## Installed

```bash
pip install ms_service_metric
```

### Depends on

 * Python >= 3.10
 * pyyaml
 * prometheus-client
 * posix_ipc (Linux)

## Quick start

### 1. vLLM integration

The vLLM automatically adapts to the entry_points mechanism without additional code.

1. Installed`ms_service_metric`
2. Starts the vLLM multi-process metric to collect environment variables.

```bash
#Enable the vLLM multi-process metric collection environment variable.
export PROMETHEUS_MULTIPROC_DIR=/dev/shm/vllm_metrics && mkdir -p $PROMETHEUS_MULTIPROC_DIR 

#(Optional) Delete the last counter file.
#rm -rf $PROMETHEUS_MULTIPROC_DIR/*

#Starting the vllm
#vllm serve --model your_model
```

### 2. Control indicator collection

```bash
#Enable indicator collection.
ms-service-metric on

#Disabling indicator collection
ms-service-metric off

#Restart (Configuration Reload)
ms-service-metric restart

#Viewing the status
ms-service-metric status
```

### 3. Prometheus + Grafana visualization (Windows)

#### Installing Prometheus

1. Download Prometheus Windows version:
    
     * Access to[Prometheus download page](https://prometheus.io/download/)    
     * Download`prometheus-<version>.windows-amd64.zip`
2. Decompress and configure:
    
    ```powershell
    #Decompress the package to a specified directory.
    Expand-Archive -Path prometheus-*.zip -DestinationPath C:\Prometheus
    ```

3. Modifying`prometheus.yml`Add a vLLM indicator collection task in the configuration file.
    
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
    
    Default access address of Prometheus:`http://localhost:9090`

#### Installing Grafana

1. Download the Grafana Windows version:
    
     * Access to[Grafana download page](https://grafana.com/grafana/download?platform=windows)    
     * Download and run the installer
2. Run the following command to start the Grafana service:
    
    ```powershell
    #Started through Service Manager
    net start grafana
    
    #Or start it manually.
    cd "C:\Program Files\GrafanaLabs\grafana\bin"
    .\grafana-server.exe
    ```
    
    Default address for accessing Grafana:`http://localhost:3000`
    
     * Default User Name:`admin`
     * Default password:`admin`

#### Import Dashboard

1. Log in to the Grafana web page (`http://localhost:3000`)
2. To create a Prometheus data source:
    
     * Menu on the left: Configuration → Data sources
     * Click Add data source.
     * Select Prometheus.
     * URL:`http://localhost:9090`
     * Click Save & Test.
3. Import the MsServiceMetric Dashboard:
    
     * Menu on the left: Dashboards → Import
     * Click Upload dashboard JSON file.
     * Selecting[Dashboard sample file (downloaded to the local computer to match the default collection configuration)](https://gitcode.com/Ascend/msserviceprofiler/blob/26.0.0/ms_service_metric/example/MsServiceMetric-grafana-Dashboard.json)    File
     * Click Import.
     * Select the created Prometheus data source.

### 4. More introduction

For details, see:[Usage Guide](https://gitcode.com/Ascend/msserviceprofiler/blob/26.0.0/docs/zh/vLLM_metrics_tool_instruct.md)    

## Configuration

Users can customize the content to be collected. You can specify the YAML file by setting the MS_SERVICE_LUM_VLLM_CONFIG environment variable. If this parameter is not specified, the internal collection configuration is used by default.

### Configuration File Format

Create a YAML configuration file.

```yaml
#Use the default timer handler.
- symbol: my_module:MyClass.my_method
  metrics:
    - name: my_method_duration
      type: timer
      labels:
        - name: method
          expr: "ret.method"  #Attribute Access

#Use the counter to measure the list length.
- symbol: my_module:process_batch
  metrics:
    - name: batch_size
      type: counter
      expr: "len(items)"  #Function call

#Use the gauge to record values.
- symbol: my_module:get_queue_length
  metrics:
    - name: queue_length
      type: gauge
      expr: "queue.size"  #Attribute Access

#Use the histogram to collect statistics on the time consumption distribution.
- symbol: my_module:process_data
  metrics:
    - name: processing_time
      type: histogram
      expr: "duration"  #Built-in variable: Execution duration (seconds)
      buckets: [0.001, 0.01, 0.1, 1.0, 10.0]

#User-defined handlers are used. Generally, metrics do not need to be configured when handlers are specified.
- symbol: my_module:complex_process
  handler: my_handlers:custom_handler
```

### Configuration Item Description

| Field       | Type   | Mandatory | Description                                                                                                                                               |
| ----------- | ------ | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| symbol      | string | Yes       | Indicates the target symbol path. Format:`module.path:ClassName.method_name`                                                                              |
| handler     | string | No.       | User-defined handler path, in the following format:`module.path:function_name`. Generally, you do not need to configure metrics when specifying handlers. |
| min_version | string | No.       | Minimum version requirements                                                                                                                              |
| max_version | string | No.       | Maximum version requirements                                                                                                                              |
| metrics     | list   | No.       | Indicator configuration list (configured when the default handler is used)                                                                                |

### Metrics Configuration

| Field   | Type   | Required | Description                                        |
| ------- | ------ | -------- | -------------------------------------------------- |
| name    | string | Yes      | Indicator Name                                     |
| type    | string | Yes      | Counter type: timer, counter, gauge, or histogram. |
| expr    | string | No.      | Expression (mandatory for non-timer types)         |
| labels  | list   | No.      | Label Configuration                                |
| buckets | list   | No.      | Histogram bucket (histogram type)                  |

### Environment variables

| Variable name                 | Description                       | Default value      |
| ----------------------------- | --------------------------------- | ------------------ |
| MS_SERVICE_METRIC_CONFIG_PATH | Configuration File Path           | None               |
| MS_SERVICE_METRIC_SHM_PREFIX  | Shared Memory Prefix              | /ms_service_metric |
| MS_SERVICE_METRIC_MAX_PROCS   | Maximum number of processes       | 1000               |
| PROMETHEUS_MULTIPROC_DIR      | Multi-Process Indicator Directory | None               |

## Handler type

### Wrap Handler

Type of the wrapping function. The original function needs to be invoked manually.

```python
def my_wrap_handler(ori_func, *args, **kwargs):
    #Preprocessing
    start_time = time.time()
    
    #Invoke the original function.
    result = ori_func(*args, **kwargs)
    
    #Post-processing
    duration = time.time() - start_time
    print(f"Duration: {duration}")
    
    return result
```

### Context Handler

Context manager type, which uses yield to control the execution process. Local variables are automatically accessed as long as the context handler is used:

```python
def context_handler(ctx):
    #ctx: FunctionContext object
    #ctx.return_value: return value (available after yield)
    #ctx.locals: locals dictionary of functions
    
    #Preprocessing
    start_time = time.time()
    print(f"Locals before: {ctx.locals}")
    
    yield  #The original function is executed here.
    
    #Post-processing
    duration = time.time() - start_time
    print(f"Duration: {duration}")
    print(f"Result: {ctx.return_value}")
    print(f"Locals after: {ctx.locals}")
```

**Default Handler: Check whether the handler exists in the configuration.**`expr`The field automatically determines the handler type.

 * And there are`expr`\: Create a context handler (accessible to locals).
 * None`expr`\: Create a wrap handler.

**Configuration example:**

```yaml
#Use the customized context handler (handle metrics in the handler).
- symbol: my_module:complex_function
  handler: my_handlers:context_handler

#Use the default handler. (If expr is available, the context handler is automatically created.)
- symbol: my_module:another_function
  metrics:
    - name: item_count
      type: counter
      expr: "len(items)"  #items are local variables within a function.
```

## Multi-handler combination

Multiple handlers can be configured for a symbol, which is executed based on the onion model.

```yaml
- symbol: my_module:process
  handler: handlers:auth_check
- symbol: my_module:process
  handler: handlers:timing
  metrics:
    - name: process_duration
      type: timer
```

Execution sequence:`auth_check -> timing -> 原函数 -> timing -> auth_check`

## Framework adaptation

### vLLM

Automatically adapts with entry_points and is ready to use after installation without additional code.

### SGLang (example reference)

> **Note: The SGLang adapter is for reference only and is not an official release feature.**

```python
from ms_service_metric.adapters.sglang import initialize_sglang_metric

#Initializing
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

## development

### Installation and Development Dependency

```bash
pip install -e ".[dev]"
```

### Run the test

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

## Security risk

Metric data monitoring uses the metric function of vllm and provides interfaces for external systems.[For details, see.](https://github.com/vllm-project/vllm/tree/main/examples/observability/prometheus_grafana)    Pay attention to possible security risks.

## License

Mulan PSL v2

## Contributed

Welcome to submit the Issue and Pull Request.
