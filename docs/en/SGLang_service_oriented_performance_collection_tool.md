# SGLang Service Profiler User Guide

## Introduction

SGLang Service Profiler is a performance analysis tool designed for the SGLang inference service framework. It helps users quickly identify performance bottlenecks by tracing the execution flow. Specifically, it captures critical timing information (start/end timestamps), profiles key functions, and records significant events throughout the inference pipeline.

SGLang Service Profiler is used for performance monitoring and optimization analysis when deploying SGLang inference services on NPUs. It supports the end-to-end workflow, including preparation, data collection, data parsing, and result visualization.

## Supported Products

>[!NOTE]
>
>For details about Ascend product models, see [Ascend Product Models](https://www.hiascend.com/document/detail/en/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html).

|Product Type| Supported (Yes/No)|
|--|:----:|
|Atlas A3 training products and Atlas A3 inference products|  Yes  |
|Atlas A2 training products and Atlas A2 inference products|  Yes  |
|Atlas 200I/500 A2 inference products|  No  |
|Atlas inference products|  No  |
|Atlas training products|  No  |

The NPU models supported by this tool match those supported by the SGLang framework for inference serving. For details, see [SGLang installation with NPUs support](https://docs.sglang.io/docs/hardware-platforms/ascend-npus/ascend_npu).

## Preparations

### Environment Setup

1. In the Ascend environment, install the matching CANN Toolkit and ops operator packages, and configure CANN environment variables. For details, see [CANN Installation Guide](https://www.hiascend.com/cann/download).
2. Install and deploy SGLang on the NPU and ensure that the inference service can run properly. For details, see [SGLang installation with NPUs support](https://docs.sglang.io/docs/hardware-platforms/ascend-npus/ascend_npu).
3. Build the .run package from the source code and upgrade the tool. For details, see the section *Upgrade* in [msServiceProfiler Installation Guide](./msserviceprofiler_install_guide.md#upgrade).

### Restrictions

- **Version compatibility**: Currently, only SGLang 0.5.4.post1 is supported.
- **Resource usage**: The data collection process may consume significant memory. It is advised to adjust the collection frequency as required.

## Usage Instruction

**1. Preparing for Data Collection**

a. Before starting the service, import the profiling module into the SGLang framework.

```bash
# Open the SGLang server launch file to import the profiling module.
vim /usr/local/python3.11.13/lib/python3.11/site-packages/sglang/launch_server.py # Replace /usr/local/python3.11.13/lib/python3.11/site-packages with the sglang installation path from the pip show sglang command output.
# Insert the following code after all existing import statements:
from ms_service_profiler.patcher.sglang import register_service_profiler
register_service_profiler()
```

b. Before starting the service, set the following environment variables:

- `SERVICE_PROF_CONFIG_PATH`: specifies the path to the performance analysis configuration file.
- `PROFILING_SYMBOLS_PATH`: (optional) specifies the path to the symbol configuration file. If not set, the default file at ms_service_profiler/patcher/sglang/config/service_profiling_symbols.yaml is used.

```bash
cd ${path_to_store_profiling_files}
export SERVICE_PROF_CONFIG_PATH=ms_service_profiler_config.json
export PROFILING_SYMBOLS_PATH=service_profiling_symbols.yaml

# Start the SGLang service.
python -m sglang.launch_server --model-path=/Qwen2.5-0.5B-Instruct --device npu
```

`ms_service_profiler_config.json` indicates the collection configuration file. If the file does not exist, a default configuration is automatically generated. For custom configurations, see [Collection Configuration User Guide] (#Collection Configuration User Guide).
**Note:
This tool does not support the configuration of usage parameters `host_system_usage_freq` and `npu_memory_usage_freq`, or collection parameters `as acl_task_time=2`, `api_filter`, and `kernel_filter mspti`.**

`service_profiling_symbols.yaml` is the symbol configuration file to import. If you do not set the `PROFILING_SYMBOLS_PATH` environment variable, the default configuration file is used. For custom configurations, see [Symbol Configuration User Guide] (#Symbol-Configuration-User-Guide).

**2. Starting Data Collection**

Change the `enable` field in `ms_service_profiler_config.json` from `0` to `1` to enable performance data collection. You can run the following `sed` command:

```bash
sed -i 's/"enable":[[:space:]]*0/"enable":1/' ./ms_service_profiler_config.json
```

**3. Sending Requests**

Select a request sending method based on the actual profiling requirements.

```bash
curl http://localhost:30000/v1/completions \
    -H "Content-Type: application/json"  \
    -d '{
         "model": "/Qwen2.5-0.5B-Instruct",
        "prompt": "Beijing is a",
        "max_tokens": 5,
        "temperature": 0
}' | python3 -m json.tool
```

**4. Parsing Data**

```bash
# xxxx-xxxx is the directory automatically created by the profiler based on the SGLang launch time.
cd /root/.ms_server_profiler/xxxx-xxxx

# Parse data.
python -m ms_service_profiler.parse --input-path=$PWD
```

For details about the command parameters for parsing data, see [Data Parsing] (./msserviceprofiler_serving_tuning_instruct.md# Data Parsing).

**5. Viewing Data**

After parsing is complete, the `output` folder is generated in the current directory. The folder contains the following deliverables:

|          Deliverable         | Description                                                                                                        |
|:---------------------:|:-----------------------------------------------------------------------------------------------------------|
| `chrome_tracing.json` | Records trace data of inference service requests. You can use different visualization tools to view the data. For details, see [Data Visualization] (./msserviceprofiler_serving_tuning_instruct.md# Data Visualization).      |
|     `profiler.db`     | SQLite database file for generating visualized line charts. For details, see [profiler.db] (./msserviceprofiler_serving_tuning_instruct.md#profilerdb).|
|     `request.csv`     | Records detailed data of inference requests in a serving scenario. For details, see [request.csv] (./msserviceprofiler_serving_tuning_instruct.md#requestcsv).     |
|     `kvcache.csv`     | Records memory usage during inference. For details, see [kvcache.csv] (./msserviceprofiler_serving_tuning_instruct.md#kvcachecsv).         |
|      `batch.csv`      | Records detailed data of inference batches in a serving scenario. For details, see [batch.csv] (./msserviceprofiler_serving_tuning_instruct.md#batchcsv).      |

>[!NOTE]
>
> The output file is closely related to the collection of the domain field. For details, see [Mapping between domain fields and the parsing results] (./msserviceprofiler_serving_tuning_instruct.md# parsing result).

## Appendix

### Profiling Configuration Usage Guide

1. For details about the profiling configuration, see the instructions for creating configuration files and the clarifications [Data Collection] (./msserviceprofiler_serving_tuning_instruct.md# Data Collection).
2. When configuring the Torch Profiler, set `enable` to `0` (disabling profiling) first. After the SGLang inference framework starts, set `enable` to `1` (enabling profiling). To avoid collecting too much profile data, you can disable profiling after the corresponding data is collected. If the initial value of `enable` is `1`, a large amount of framework data is collected, which can easily generate trace files of several gigabytes.

### Symbol Configuration User Guide

This tool allows you to specify the functions/methods to be monitored for performance data collection, and supports flexible configuration and custom attribute collection.

To customize profiling symbols, you are advised to set the environment variable `PROFILING_SYMBOLS_PATH` and copy a symbol configuration file to the working directory for modification.

**If a profiling symbol is updated, restart the SGLang service to load the updated configuration file.**

For details about how to write the configuration file and configuration examples, see the secion *Symbol Configuration User Guide* in [vLLM Service Profiler User Guide](./vLLM_service_oriented_performance_collection_tool.md#symbol-configuration-user-guide).
