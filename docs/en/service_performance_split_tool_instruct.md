# Service Performance Split Tool

## Overview

Based on performance data collected by msServiceProfiler, Service Performance Split Tool breaks down the time consumed in each phase of service batch execution—including batching, input transfer, model execution, and output retrieval. This breakdown helps identify performance bottlenecks, enabling developers to optimize the framework.

**Concepts**

- `prefill batch`: The prefill phase is the initial stage where the model processes the entire input prompt to compute and generate the first output token. The batch processed in this phase is called a prefill batch.
- `decode batch`: In the decode phase, the model generates subsequent output tokens one by one. Each iteration in this phase involves less computation compared to the prefill phase, but the decode phase may consist of many iterations due to the sequential token generation. The batch processed in this phase is called a decode batch.

## Product Support<a name="ZH-CN_TOPIC_0000002479925980"></a>

>[!NOTE]
>
>For details about Ascend product models, see [Ascend Product Models](https://www.hiascend.com/document/detail/en/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html).

|Product Type| Supported (Yes/No)|
|--|:----:|
|Atlas A3 training products and Atlas A3 inference products|  Yes  |
|Atlas A2 training products and Atlas A2 inference products|  Yes  |
|Atlas 200I/500 A2 inference products|  Yes  |
|Atlas inference products|  Yes  |
|Atlas training products|  x   |

>[!NOTE]
>
>For Atlas A2 training products/Atlas A2 inference products, only the Atlas 800I A2 inference server is supported.
>For Atlas inference products, only the Atlas 300I Duo inference card and Atlas 800 inference server (model 3000) are supported.

## Preparations

**Environment Setup**

Install [msServiceProfiler](msserviceprofiler_install_guide.md).

**Version Mapping**

| Service Performance Split Tool|     CANN     |     MindIE     |
|:-------------:|:------------:|:--------------:|
|     Dependency Version     | ≥ CANN 8.2.RC1 | ≥ MindIE 2.1.RC1 |

## Function Description

### Function

Performs fine-grained breakdown on service profile data.

**Precaution**

None

### Syntax

```bash
msserviceprofiler split 
--input-path /path/to/input 
[--output-path path/to/output] 
[--log-level level] 
[--prefill-number prefill_number] 
[--decode-number decode_number]
{
  --prefill-batch-size prefill_batch_size 
  --prefill-rid prefill_rid
  --decode-batch-size decode_batch_size 
  --decode-rid decode_rid
}
```

Optional fields are enclosed in square brackets ([]), and mandatory fields are enclosed in braces ({}).

### Parameter Description

| Parameter                | Description                                                           |Mandatory (Yes/No)|
| -------------------- | --------------------------------------------------------------- |-----|
| --input-path | Specifies the path to the profile data. |Yes|
| --output-path | Specifies the output directory where the breakdown result files will be saved. It defaults to the `output` folder in the current directory.|No|
| --log-level  | Sets the log level. The options are `debug`, `info`, `warning`, `error`, `fatal`, and `critical`. It defaults to `info`. |No|
| --prefill-batch-size  | Specifies the `batch_size` value for prefill batch breakdown. This value can be obtained from the `batch_size` field in `batch.csv`. It defaults to `0` (to disable prefill performance breakdown).|No|
| --prefill-number  | Specifies the number of prefill batches to break down. It defaults to `1` and is used to calculate the max, min, average, and standard deviation of execution time.|No|
| --prefill-rid  | Specifies the request ID for prefill batch breakdown. This value can be obtained from the `http_rid field` in `request.csv`. It defaults to `-1` (to disable prefill performance breakdown).|No|
| --decode-batch-size | Specifies the `batch_size` value for decode batch breakdown. This value can be obtained from the `batch_size` field in `batch.csv`. It defaults to `0` (to disable decode performance breakdown).|No|
| --decode-number  | Specifies the number of decode batches to break down. It defaults to `1` and is used to calculate the max, min, average, and standard deviation of execution time.|No|
| --decode-rid  | Specifies the request ID for decode batch breakdown. This value can be obtained from the `http_rid field` in `request.csv`. It defaults to `-1` (to disable decode performance breakdown).|No|

### Examples

- **Scenario 1: Specify the `batch size` value for breakdown.**
  - To break down 100 `prefill batch` data records with `batch_size` set to `1`:

    ```sh
    msserviceprofiler split --input-path=/path/to/input --output-path=/path/to/output/ --prefill-batch-size=1 --prefill-number=100
    ```

    After the execution is complete, the output file `prefill.csv` is generated in the result path.
  - To break down 50 `decode batch` data records with `batch_size` set to `10`:

    ```sh
    msserviceprofiler split --input-path=/path/to/input --output-path=/path/to/output/ --decode-batch-size=10 --decode-number=50
    ```

    After the execution is complete, the output file `decode.csv` is generated in the result path.
- **Scenario 2: Specify the `rid` value for breakdown.**
  - To break down data for the prefill phase:

    ```sh
    msserviceprofiler split --input-path=/path/to/input --output-path=/path/to/output/ --prefill-rid=efcas2d
    ```

    After the execution is complete, the output file `prefill.csv` is generated in the result path.
  - To break down data for the decode phase:

    ```sh
    msserviceprofiler split --input-path=/path/to/input --output-path=/path/to/output/ --decode-rid=efcas2d
    ```

    After the execution is complete, the output file `decode.csv` is generated in the result path.

### **Output Description**

- `prefill.csv`

   | Field                | Description                                           |
  | -------------------- | ----------------------------------------------- |
  | name | Labels a batch event. |
  | during_time(ms) | Execution time of the current batch event, in ms|
  | max  | Maximum event execution time, in ms |
  | min  | Minimum event execution time, in ms |
  | mean  | Average event execution time, in ms |
  | std  | Standard deviation of the event execution time, in ms |
  | pid  | Process ID of the event |
  | tid  | Thread ID of the event |
  | start_time(ms)  | Start time of the current batch event, displayed as a timestamp, in ms |
  | end_time(ms)  | End time of the current batch event, displayed as a timestamp, in ms |
  | rid  | Request ID. |

- `decode.csv`
The format is the same as that of `prefill.csv`. The `decode.csv` file does not contain the `rid` column.
- Mapping Between Domains and Parsed Results

  | Parsed Result                | Collection Domain                                |
  | -------------------- | ----------------------------------------------- |
  | prefill.csv | "Request; BatchSchedule; ModelExecute"  |
  | decode.csv | "BatchSchedule; ModelExecute"  |
