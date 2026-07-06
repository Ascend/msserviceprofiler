# Service Profiling Advisor

## Overview

- Service Profiling Advisor, built upon the MindIE Service framework, provides one-click parameter tuning recommendations based on the output of benchmark tests to assist users in performance optimization. By analyzing the instance output results from benchmarks, the `config.json` configuration of MindIE Service, NPU memory utilization, and model deployment, the tool performs a comprehensive analysis to offer tuning recommendations for parameters such as `maxBatchSize` and `maxPrefillBatchSize` within `config.json`. These recommendations aim to improve performance metrics like Time to First Token (TTFT) and throughput.
- **Note: Due to variations in hardware such as CPU and memory, differences in network environments, and specific model parameter configurations, the recommended values may not guarantee performance improvement. Validation through actual modifications is required.**

## Supported Products
>
> **Note:**
>For details about Ascend product models, see [Ascend Product Models](https://www.hiascend.com/document/detail/en/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html).

|Product Type| Supported (Yes/No)|
|--|:----:|
|Atlas A3 Training Products and Atlas A3 Inference Products|  Yes  |
|Atlas A2 Training Series Product|  Yes  |
|Atlas 200I/500 A2 inference products|  Yes  |
|Atlas Inference Products|  Yes  |
|Atlas training products|  No  |

## Before You Start

### Environment Setup

- Prepare an Ascend Atlas 800I A2 training server with NPUs.
- Prepare the **Python environment**: Python 3.10 or later is required.
- **Install dependencies**.

    ```bash
    pip install scipy loguru pandas psutil # Install necessary dependencies.
    ```

### Data Preparation

- Ensure that the MindIE benchmark produces the expected output. The generated `instance` folder should be placed under `/your/path/instance/`.
- Ensure that the MindIE Service `config.json` file is correctly configured. This file is typically located under `/usr/local/Ascend/mindie/latest/mindie-service/conf/`.

## Tool Installation

- **Installation from Source**
  Service Profiling Advisor requires msServiceProfiler as its entry point. If msServiceProfiler is not installed, install it first. For details, see [msServiceProfiler](msserviceprofiler_install_guide.md).

  ```sh
  git clone https://gitcode.com/Ascend/msserviceprofiler.git # Skip this if the repository is already cloned.
  cd msserviceprofiler/msservice_advisor
  pip install .
  msserviceprofiler advisor -h
  ```

## Tool Uninstallation

```shell
pip uninstall msservice_advisor
```

## Function Description

### Functions

- **Scenario 1: Recommend `maxBatchSize` for the decode phase based on the NPU memory, input/output lengths, and model size.**
  - You need to provide the `instance` folder, or manually specify the input/output token lengths using `-in, --input_token_num` and `-out, --output_token_num``.
  - To obtain the model path, you need to provide the MindIE Service `config.json` file.
  - The NPU memory usage corresponding to `npuDeviceIds` specified in the MindIE Service `config.json` file should reflect the actual memory usage before MindIE Service startup. Alternatively, `npuMemSize` in the MindIE Service `config.json` file must be explicitly specified.
- **Scenario 2: Fit a model to the `instance` output data from benchmark tests and recommend `maxBatchSize` and `maxPrefillBatchSize` values.**
  - The `instance` folder must be provided, containing at least 1,000 samples.
  - If the data required for Scenario 1 is also provided, the `maxBatchSize` recommendation from Scenario 1 will be taken into account.

### Precautions

Security warning: Do not run this tool as user `root`. Executing operations with elevated privileges may compromise system security. It is advised to use a regular user account.

### Syntax

  ```sh
  # Specifies the input and output token lengths (`-in, --input_token_num` and `-out, --output_token_num`).
  msserviceprofiler advisor -in 4096 -out 256

  # Provide the 'instance' folder.
  msserviceprofiler advisor -i /your/path/instance/
  ```

### Parameter Description

  | Parameters                | Mandatory (Yes/No)| Description                                                           |
  | -------------------- | --------- | --------------------------------------------------------------- |
  | -i or --instance_path | No       | Path to the benchmark instance output. If this parameter is not specified, related information will not be used in the analysis by default. |
  | -s or --service_config_path | No       | Path to the MindIE Service path or `config. json` file. The default value is the environment variable `MIES_INSTALL_PATH` of MindIE Service. If neither of them is configured, `/usr/local/Ascend/mindie/latest/mindie-service` is used.|
  | -t or --target        | No       | Metrics to optimize. The options are as follows:<br> · `ttft`: Time to First Token (TTFT).<br> · `firsttokentime`: TTFT.<br> · `throughput`: throughput.<br> The default value is `ttft`.      |
  | -m or --target_metrics| No       | Specific metric to optimize. The options are as follows:<br> · `average`: average value.<br> · `max`: maximum value.<br> · `min`: minimum value.<br> · `P75`: 75th percentile.<br> · `P90`: 90th percentile.<br> · `SLO_P90`: 90 percentile under the specific Service Level Objective (SLO) constraints.<br> · `P99`: 99th percentile.<br> · `N`: Nth percentile.<br>The default value is `average`.|
  | -l or --log_level | No       | Log level. The options are as follows:<br> · `debug`: debug level.<br> · `info`: information level.<br> · `warning`: warning level.<br> · `error`: error level.<br> · `fatal`: fatal level.<br> · `critical`: critical level.<br>The default value is `info`. |
  | -in or --input_token_num | No       | Request input length. The value must be a positive integer. If this parameter is not specified, the value is obtained from the benchmark `instance` results by default.|
  | -out or --output_token_num | No       | Request output length. The value must be a positive integer. If this parameter is not specified, the value defaults to the `maxIterTimes` value in the MindIE Service `config.json`.|
  | -tp or --tp | No       | Tensor Parallelism (TP) domain size. The value must be a positive integer. If this parameter is not specified, the value is obtained from the MindIE Service `config.json` file. If not found, `1` is used by default.|

### Usage Example

- **Scenario 1**
  - Enter the `-i` or `-in` parameter. The related parameters in the MindIE Service `config.json` file are correctly configured, and the available NPU memory for the serving configuration is not 0 (as described in the third point in Scenario 1 from [Function Description](#function-description)).

  ```sh
  msserviceprofiler advisor -in 4096 -out 256
  ```

- **Scenario 2**
  - Fit a model to the benchmark `instance` output data from the path specified by `-i, --instance_path` and recommend `maxBatchSize` and `maxPrefillBatchSize` values. The `maxBatchSize` recommendation from `Scenario 1` will be taken into account.

  ```sh
  msserviceprofiler advisor -i /your/path/instance/
  ```

### Output Description

After the advisor command completes, tuning recommendations are displayed as follows:

- **Scenario 1**
  - The output indicates the recommended range for the `maxBatchSize` value in the MindIE Service `config.json` file. The range is calculated based on available NPU memory, model architecture, MindIE Service `config.json` configuration, and input/output token lengths.
  - You are advised to set `maxBatchSize` in the MindIE Service `config.json` file to the average value and set `maxPrefillBatchSize` to half of `maxBatchSize`. Then, restart the service, and check whether performance improves.
  - If performance improves, try to gradually approach the maximum value within the range and monitor the performance metrics.
  - If `maxBatchSize` is set too high, the model may fail to start. In this case, decrease the value toward the lower end of the range until the model starts successfully.
  - Generally, `maxPrefillBatchSize` is typically set to half of `maxBatchSize`.

  ```sh
  # msservice_advisor_logger - INFO - </think>
  # msservice_advisor_logger - INFO -
  # msservice_advisor_logger - INFO - <advice>
  # msservice_advisor_logger - INFO - [config] maxBatchSize
  # The value range of `msservice_advisor_logger - INFO - [advice]` is [xx, xx], and the average value is `xx`.
  # Based on current NPU memory usage, it is advised to set maxBatchSize to the average value and gradually adjust toward the upper end of the range to fully utilize NPU memory.
  # msservice_advisor_logger - INFO - </advice>
  ```

- **Scenario 2**
  - The output provides recommendations for `maxBatchSize` and `maxPrefillBatchSize`. The `maxBatchSize` recommendation takes into account the value recommended in `Scenario 1`.
  - You can apply the recommended values to the `config.json` file and check whether the performance improves. If the result is not satisfactory, you can apply only one of these values and verify the inference performance.
  - In this mode, a fitted data plot is also generated to help you assess whether the data fitting is reasonable.

  ```sh
  # Path of the msservice_advisor_logger - INFO - fitted plot path: func_curv_031734.png
  # msservice_advisor_logger - INFO - <think>
  # ...
  # msservice_advisor_logger - INFO - </think>
  # msservice_advisor_logger - INFO -
  # msservice_advisor_logger - INFO - <advice>
  # msservice_advisor_logger - INFO - [config] maxBatchSize
  # Try to set msservice_advisor_logger - INFO - [advice] Try setting to 25 (original value: 50).
  # Based on latency data for different batch sizes and function fitting analysis, this is the recommended optimal batch size.
  # msservice_advisor_logger - INFO -
  # msservice_advisor_logger - INFO - [config] maxPrefillBatchSize
  # Try to set msservice_advisor_logger - INFO - [advice] Try setting to 50 (original value: 100).
  # Based on latency data for different batch sizes and function fitting analysis, this is the recommended optimal batch size.
  # msservice_advisor_logger - INFO -
  # msservice_advisor_logger - INFO - </advice>
  ```
