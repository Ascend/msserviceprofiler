# msServiceProfiler Multi Analyze

## Overview

msServiceProfiler Multi Analyze parses the profile data collected by the msServiceProfiler from multiple dimensions, including request-level, batch-level, and overall service-level dimensions.

### Supported Products<a name="ZH-CN_TOPIC_0000002479925980"></a>
>
>[!NOTE]
>
>For details about Ascend product models, see [Ascend Product Models](https://www.hiascend.com/document/detail/en/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html).

|Product Type| Supported (Yes/No)|
|--|:----:|
|Atlas A3 Training Products and Atlas A3 Inference Products|  Yes  |
|Atlas A2 Training Products and Atlas A2 Inference Products|  Yes  |
|Atlas 200I/500 A2 inference products|  Yes  |
|Atlas Inference Products|  Yes  |
|Atlas training products|  No  |

>[!NOTE]
>
>For Atlas A2 training products/Atlas A2 inference products, only the Atlas 800I A2 inference server is supported.
>For Atlas inference products, only the Atlas 300I Duo inference card and Atlas 800 inference server (model 3000) are supported.

## Preparations

**Environment Setup**

Install [msServiceProfiler](msserviceprofiler_install_guide.md).

**Version Compatibility**

msServiceProfiler Multi Analyze depends on the `ms_service_profiler` tool provided in `Ascend-cann-toolkit`.

| msServiceProfiler Multi Analyze|     CANN     |     MindIE     |
|:-------------:|:------------:|:--------------:|
|     Dependency Version     | ≥ 8.1.RC1 | ≥ MindIE 2.0.RC1 |

## Function Description

### Function

This tool can analyze serving profile data across multiple dimensions.

**Precautions**

None

### Syntax

    ```bash
    msserviceprofiler analyze 
    --input-path=/path/to/input 
    [--output-path=/path/to/output/]
    [--log-level level]
    [--format format]
    ```

### Parameter Description

| Parameter            | Mandatory (Yes/No)| Description                                                                                                                                                        |
|------------------|-----------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| --input-path     | Yes     | Specifies the path to the profile data.                                                                                                                                       |
| --output-path    | No     | Specifies the output directory where the parsing result files will be saved. It defaults to the `output` folder in the current directory.                                                                                                     |
| --log-level      | No     | Sets the log level. The options are as follows:<br>- `debug`: debug level. Logs debugging information for issue diagnosis.<br>- `info`: informational level. Logs the normal tool operation information.<br>- `warning`: warning level. Indicates unexpected but non-critical states that do not interrupt execution.<br>- `error`: minor error level.<br>- `fatal`: major error level.<br>- `critical`: critical error level.|
| --format        | No     | Sets the export format for the profile data output files. The options are `json`, `csv`, and `db`.                                                                                                       |

### **Output File Description**

- `batch_summary.csv`

  | Field                | Description                                           |
  | -------------------- | ----------------------------------------------- |
  | Metric | Metric item, including the column header metrics and the row header metrics. |
  | Metrics (column header)|-|
  | prefill_batch_num  | Number of records with `batch_type` = `Prefill` in each batch.|
  | decode_batch_num  | Number of records with `batch_type` = `Decode` in each batch.|
  | prefill_exec_time(ms)  | `during_time` of all records with `batch_type` = `Prefill modelExec` in each batch. If `modelExec` is not present, this row is omitted. The unit is ms.|
  | decode_exec_time(ms)  | `during_time` of all records with `batch_type` = `Decode modelExec` in each batch. If `modelExec` is not present, this row is omitted. The unit is ms.|
  | Metrics (row header) |-|
  | Average  | Average value. |
  | Max | Maximum value. |
  | Min | Minimum value. |
  | P50  | 50th percentile.|
  | P90  | 90% quantile value.|
  | P99  | 99% quantile value.|

- `request_summary.csv`

  | Field                | Description                                           |
  | -------------------- | ----------------------------------------------- |
  | Metric| Metric item, including the column header metrics and the row header metrics. |
  | Metrics (column header)|-|
  | first_token_latency(ms)  | Time to first token (TTFT), in ms.|
  | subsequent_token_latency(ms)  | Inter-token latency, measuring the average time (in ms) taken to generate each subsequent token after the first one.|
  | total_time(ms)  | Total duration of an HTTP request, in ms.|
  | exec_time(ms)  | Execution time of `modelExec`. If `modelExec` is not present, this row is omitted. The unit is ms.|
  | waiting_time(ms)  | Request waiting time, in ms.|
  | input_token_num  | Number of input tokens per request.|
  | generated_token_num  | Number of output tokens per request.|
  | Metrics (row header) |-|
  | Average  | Average value. |
  | Max  | Maximum value. |
  | Min  | Minimum value. |
  | P50  | 50th percentile.|
  | P90  | 90% quantile value.|
  | P99  | 99% quantile value.|

- `service_summary.csv`

  | Field                | Description                                           |
  | -------------------- | ----------------------------------------------- |
  | Metric | Metric item, including the column header metrics and the row header metrics. |
  | Metrics (column header)|-|
  | total_input_token_num  | Total number of input tokens.|
  | total_generated_token_num  | Total number of output tokens.|
  | generate_token_speed(token/s)  | Tokens output per second (token/s).|
  | generate_all_token_speed(token/s) | Tokens processed per second (token/s) (total number of input and output tokens).|
  | Metrics (row header) |-|
  | Value | Value|

- Mapping between domains and parsed results

  | Parsed Result                | Collection Domain                                |
  | -------------------- | ----------------------------------------------- |
  | batch_summary.csv | "BatchSchedule" |
  | request_summary.csv | "Request" |
  | service_summary.csv | "Request; BatchSchedule; ModelExecute" |
