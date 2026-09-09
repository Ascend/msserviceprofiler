# Serviceparam Optimizer

## Overview

**Serviceparam Optimizer** is an automatic optimization tool for serving parameters based on Particle Swarm Optimization (PSO). It supports `MindIE` and `vLLM`, automatically tuning parameters to find the optimal throughput configuration that meets latency requirements.

The tool supports simulation and lightweight modes and consists of three core functional modules:

- **Parameter optimization module**: uses PSO to automatically generate serving parameter combinations and iteratively approach the optimal solution. In addition, the Early Rejection algorithm performs early-stage benchmarks on serving parameters based on theoretical modeling, tuning experience, and partial test data.

- **Simulation module**: accurately predicts the inference duration of LLMs based on the XGBoost model. It accelerates the verification of serving parameters using the virtual timeline technology.

- **Parameter verification module**: automatically starts the serving process and benchmark tool to test parameters and obtain performance results. Currently, the supported benchmark tools include `AISBench` and `vllm_benchmark`.

>[!NOTE]
> 
> The benchmark tool is about to be replaced by AISBench and is no longer supported by Serviceparam Optimizer.

Based on the modules above, Serviceparam Optimizer can automatically recommend serving parameter combinations that deliver high throughput. It can be used in the following modes:

- [Lightweight mode](#lightweight-mode)
- [Simulation mode](#simulation-mode)

The tool has been validated on LLaMA3-8B and Qwen3-8B. In principle, it does not limit the supported model types, and broader validation coverage is planned for future releases.

**Concepts**

- `MindIE` and `vLLM`: serving frameworks, which support model deployment in serving scenarios.
- `AISBench` and `vLLM_Benchmark`: inference performance benchmark tools for serving frameworks.

## Supported Products<a name="ZH-CN_TOPIC_0000002479925980"></a>

>[!NOTE]
>
>For details about Ascend product models, see [Ascend Product Models](https://www.hiascend.com/document/detail/en/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html).

|Product Type| Supported (Yes/No)|
|--|:----:|
|Ascend 950 products|No|
|Atlas A3 Training Products and Atlas A3 Inference Products|  Yes  |
|Atlas A2 training products and Atlas A2 inference products|  Yes  |
|Atlas 200I/500 A2 inference products|  Yes  |
|Atlas inference products|  Yes  |
|Atlas training products|  No  |

>[!NOTE]
>
>For Atlas A2 training products/Atlas A2 inference products, only the Atlas 800I A2 inference server is supported.
>For Atlas inference products, only the Atlas 300I Duo inference card and Atlas 800 inference server (model 3000) are supported.

## Preparations

**Environment Setup**
Set up an environment where serving tools (such as [MindIE Service](https://gitcode.com/Ascend/MindIE-Motor/blob/v3.1.0/docs/en/user_guide/quick_start.md)/[vLLM Server](https://docs.vllm.ai/projects/ascend/en/latest/quick_start.html)) and benchmark tools (such as `vllm_benchmark`/`ais_bench`, see [Benchmark Tool Deployment](https://github.com/AISBench/benchmark/blob/master/docs/source_en/get_started/install.md)) can run properly.

## Tool Installation

Serviceparam Optimizer requires msServiceProfiler as its entry point. If msServiceProfiler is not installed, install it first. For details, see [msServiceProfiler](msserviceprofiler_install_guide.md). The command is as follows:

 ```bash
 git clone https://gitcode.com/Ascend/msserviceprofiler.git # Skip this if the repository is already cloned.
 cd msserviceprofiler/ms_serviceparam_optimizer
 pip install -e .[real] # Install the lightweight version.
 ```

 To perform lightweight optimization, only minimal dependencies are required. The simulation mode needs additional dependencies.

 ```bash
 # Same as before.
 pip install -e .[speed] # Install the tool with the speed option.
 ```

 If the installation fails, try installing a third-party package with fewer dependencies. Note that this may result in lower performance when handling large datasets during simulation.

 ```bash
 pip install -e .[train] # Install the tool with the train option.
 ```

## Tool Uninstallation

```bash
pip uninstall ms_serviceparam_optimizer
```

## Version Compatibility for Simulation Mode

| Version Compatibility|     CANN    |     Framework    |
|:-------------:|:------------:|:--------------:|
|     Current MindIE Version     | CANN 8.3.RC2 | MindIE 2.2.RC1 |
|     vLLM Current Version     | CANN 8.2.RC1 | VLLM 0.8.4 |

**Constraints**

The tool uses MindIE images and must follow their startup instructions. In Prefill-Decode (PD) disaggregation scenarios where MindIE uses Kubernetes, users should be aware of the associated risks.

## Quick Start

1. Complete the operations described in [Preparations](#preparations).

2. Modify the configuration file. Before starting optimization, configure [`config.toml`](../../ms_serviceparam_optimizer/ms_serviceparam_optimizer/config.toml) according to your environment, including optimization parameters, benchmark tool parameters, and serving parameters. See [Configuration File Description](#configuration-file-description) for details. You can also specify a custom path for the configuration file using  `-c`. For more details, see [Command-line Arguments](#lightweight-mode).

3. Start optimization. After the preceding steps are complete, start lightweight automatic optimization with a single command:

    ```bash
    msserviceprofiler optimizer
    ```

    By default, the tool optimizes `MindIE` serving parameters with `Ais_Bench` as the benchmark tool.

4. View the results. The optimization time depends on the model size and dataset size, typically taking 4 to 8 hours. Upon completion, the `data_storage_*.csv` file is generated and saved in the `result/store` subdirectory under the current directory. The file records the performance of each parameter set. For details, see [Output File Description](#output-file-description).

## Lightweight Mode

**Function**

This mode prioritizes accuracy and reliability. By combining real-device testing with the parameter verification and optimization modules, it delivers reliable recommended values for serving parameters.

**Precautions**

None

**Syntax**

```bash
msserviceprofiler optimizer [options]
```

**Parameters**

|Parameter|Mandatory (Yes/No)|Description|
|---|---|---|
|-lb or --load_breakpoint|No|Specifies whether to resume optimization from a breakpoint. Including this parameter enables breakpoint resumption; omitting it disables this feature.|
|-d or --deploy_policy|No|Specifies a deployment policy. The options are as follows:<br>&#8226;`single`: single-node deployment<br>&#8226;`multiple`: multi-node deployment<br>The default value is `single`.|
|--backup|No|Specifies whether to back up data during optimization. The options are as follows:<br>&#8226; `True`: enables backup.<br>&#8226; `False`: disables backup.<br>The default value is `False`.|
|-b or --benchmark_policy|No|Specifies a benchmark tool. The options are as follows:<br>&#8226;`vllm_benchmark`: vllm_benchmark is used as the benchmark tool.<br>&#8226;`ais_bench`: ais_bench is used as the benchmark tool.<br>The default value is `ais_bench`.<br>You need to select a benchmark tool compatible with your inference framework.|
|-e or --engine|No|Specifies an inference framework. The options are as follows:<br>&#8226;`mindie`: MindIE is used as the inference framework.<br>&#8226;`vllm`: vLLM is used as the inference framework.<br>The default value is `mindie`.|
|--pd|No|Specifies an inference framework mode. The options are as follows:<br>&#8226;`competition`: PD competition mode<br>&#8226;`disaggregation`: PD disaggregation mode<br>The default value is `competition`.|
| `-c` or `--config` | Optional | Path to a custom configuration file (TOML format). Supports: <br> • Absolute path – used as given. <br> • Relative path (with directory separator) – resolved relative to the current working directory. <br> • Filename only – searched for in the current working directory. <br> If not specified, the tool automatically searches for a configuration file in a predefined order. If provided, the file must be valid TOML and takes the highest precedence. |

**Example (MindIE Serving Parameter Optimization)**

1. Modify the configuration file. Before starting optimization, configure [<idp:inline displayname="code" id="code151415418558">config.toml</idp:inline>](../../ms_serviceparam_optimizer/ms_serviceparam_optimizer/config.toml) according to your environment, including optimization parameters, benchmark tool parameters, and serving parameters. See [Configuration File Description](#configuration-file-description) for details.

2. To set environment variables for the MindIE/vLLM services, configure them before running the tool. For example:

    ```bash
    export ASCEND_RT_VISIBLE_DEVICES=0
    ```

    The tool automatically applies these environment variables during optimization (applicable to both simulation and lightweight modes).

3. Once the prerequisites are ready, run the following command to start lightweight automatic optimization with a single command:

    ```bash
    msserviceprofiler optimizer
    ```

**Example (vLLM Service Parameter Optimization)**

1. Modify the configuration file. Before starting optimization, configure [<idp:inline displayname="code" id="code121419465514">config.toml</idp:inline>](../../ms_serviceparam_optimizer/ms_serviceparam_optimizer/config.toml) according to your environment, including optimization parameters, benchmark tool parameters, and serving parameters. See [Configuration File Description](#configuration-file-description) for details.
2. To set environment variables for the MindIE/vLLM services, configure them before running the tool. For example:

    ```bash
    export ASCEND_RT_VISIBLE_DEVICES=0
    ```

    The tool automatically applies these environment variables during optimization (applicable to both simulation and lightweight modes).

3. Once the prerequisites are ready, run the following command to start lightweight automatic optimization with a single command:

    ```bash
    msserviceprofiler optimizer -e vllm
    ```

    To use `vllm_benchmark` in the vLLM scenario:

    ```bash
    msserviceprofiler optimizer -e vllm -b vllm_benchmark
    ```

### Usage Example (Custom Config File)

If your config file is not in the default search paths, specify it explicitly with `-c`:

```bash
# Absolute path
msserviceprofiler optimizer -c /data/configs/my_config.toml

# Filename in current directory
msserviceprofiler optimizer -c my_config.toml

# Relative path
msserviceprofiler optimizer -e vllm -b vllm_benchmark -c ../configs/vllm_config.toml
```

The specified config file takes the highest precedence, overriding any matching settings from default paths.

**Output Description**

After automatic optimization is complete, a result file in CSV format is generated and stored in the `result/store` folder in the current directory. For details, see [Output File Description](#output-file-description).

## Simulation Mode

**Function**

The simulation mode prioritizes speed and resource efficiency. It invokes all modules to quickly and accurately predict throughput for each parameter set, delivering recommended serving parameters with minimal NPU resource usage.

**Precautions**

The simulation mode requires training on collected serving data. Run the MindIE inference service test script with the profiling feature enabled. See [Service Profiler Quick Start](https://gitcode.com/Ascend/msserviceprofiler/blob/master/docs/en/quick_start.md) for details. Then, parse the collected profile data for model training. The profile data to be collected must include `batch_type`, `batch_size`, `forward_time`, `batch_end_time(ms)`, `request_recv_token_size`, `request_reply_token_size`, `need_blocks`, `request_execution_time(ms)` and `first_token_latency(ms)`.

**Syntax**

- train

    ```bash
    msserviceprofiler train [options]
    ```

- optimizer

    ```bash
    msserviceprofiler optimizer [options]
    ```

**Parameters for model training**

|Parameter|Mandatory (Yes/No)|Description|
|---|---|---|
|-i or --input|Yes|Input data directory, which is the profiling output path.|
|-o or --output|No|Output directory. You are advised to create a `/result/latency_model` directory under `ms_serviceparam_optimizer` to store the output. If not specified, output is generated in the current directory.|
|-t or --type|No|Framework type. The options are as follows:<br>&#8226;`mindie`: MindIE is used as the inference framework.<br>&#8226;`vllm`: vLLM is used as the inference framework.<br>The default value is `mindie`.|

**Optimizer parameters**

|Parameter|Mandatory (Yes/No)|Description|
|---|---|---|
|-lb or --load_breakpoint|No|Specifies whether to resume optimization from a breakpoint. Including this parameter enables breakpoint resumption; omitting it disables this feature.|
|-d or --deploy_policy|No|Specifies a deployment policy. The options are as follows:<br>&#8226;`single`: single-node deployment<br>&#8226;`multiple`: multi-node deployment<br>The default value is `single`.|
|--backup|No|Specifies whether to back up data during optimization. The options are as follows:<br>&#8226; `True`: enables backup.<br>&#8226; `False`: disables backup.<br>The default value is `False`.|
|-b or --benchmark_policy|No|Specifies a benchmark tool. The options are as follows:<br>&#8226;`vllm_benchmark`: vllm_benchmark is used as the benchmark tool.<br>&#8226;`ais_bench`: ais_bench is used as the benchmark tool.<br>The default value is `ais_bench`.<br>You need to select a benchmark tool compatible with your inference framework.|
|-e or --engine|No|Specifies an inference framework. The options are as follows:<br>&#8226;`mindie`: MindIE is used as the inference framework.<br>&#8226;`vllm`: vLLM is used as the inference framework.<br>The default value is `mindie`.|
|--pd|No|Specifies an inference framework mode. The options are as follows:<br>&#8226;`competition`: PD competition mode<br>&#8226;`disaggregation`: PD disaggregation mode<br>The default value is `competition`.|

**Example**

1. Modify the configuration file. Before starting optimization, configure [<idp:inline displayname="code" id="code915343552">config.toml</idp:inline>](../../ms_serviceparam_optimizer/ms_serviceparam_optimizer/config.toml) according to your environment, including optimization parameters, benchmark tool parameters, and serving parameters. See [Configuration File Description](#configuration-file-description) for details.

2. Train a model:

    ```bash
    msserviceprofiler train -i=/path/to/input -o=/path/to/output
    ```

3. Set environment variables before optimization:

    ```bash
    export MODEL_EVAL_STATE_ALL=True
    export MODEL_EVAL_STATE_IS_SLEEP_FLAG=True
    export PYTHONPATH=msserviceprofiler/:$PYTHONPATH # Change it to the actual path.
    ```

4. Start simulation mode optimization:

    ```bash
    msserviceprofiler optimizer -e vllm -b vllm_benchmark
    ```

**Output Description**

After automatic optimization is complete, a result file in CSV format is generated and stored in the `result/store` folder in the current directory. For details, see [Output File Description](#output-file-description).

## Output File Description

Each row in the output CSV corresponds to a parameter set, with the first four columns representing performance metrics. You can filter rows that meet your requirements and update MindIE and ais_bench/vllm_benchmark parameters with the corresponding values from the CSV.

| Field| Description|
| --- | --- |
| generate_speed | Throughput|
| time_to_first_token | Time to first token (TTFT), in seconds.|
| time_per_output_token | Time per output token (TPOT), in seconds.|
| success_rate | Request success rate|
| throughput | Test throughput, in requests per second.|
| CONCURRENCY | Concurrency|
| REQUESTRATE | Send rate|
| error | Records error reasons if parameters failed to execute.|
| backup | Data backup path (recorded when `--backup` is enabled)|
| real_evaluation | Specifies whether data is obtained from the actual test result. `false` indicates that the data is obtained from the GP model prediction.|
| fitness | Optimization score. Lower values indicate better parameter sets.|
| num_prompts | Number of requests sent by the benchmark tool.|

Other columns are the `config.toml` parameters from MindIE or vLLM.

## Appendixes

### Configuration File Description

**Optimization parameters**: `n_particles` (number of optimization particles), `iters` (number of iterations), and `tpot_slo` (latency constraint for `time_per_output_token`).
You can configure the number of particles and iterations based on the estimated time. Each particle requires time for service startup and testing. For example, if service startup and testing takes 9 to 10 minutes per run, and you allocate 8 hours for optimization, you can run approximately 50 particles in total. The recommended configuration is 5 × 10. That is, 10 particles and 5 iterations. As a rule of thumb, set the number of particles to about twice the number of iterations.

> **Note**: The following optimization parameters are mandatory. Do not delete or omit them, as doing so will cause runtime errors.

|Parameter|Mandatory (Yes/No)|Description|
|---|---|---|
|n_particles|Yes|Number of particles (parameter combinations). The value is an integer ranging from 1 to 1000. The recommended value ranges from 15 to 30.|
|iters|Yes|Number of iterations. The value is an integer ranging from 1 to 1000. The recommended value ranges from 5 to 10.|
|ttft_penalty|Yes|Penalty coefficient for `time_to_first_token` (TTFT) violations. Set it to `0` if there is no TTFT constraint. Value range: [0, 100]. The recommended value is `1`.|
|tpot_penalty|Yes|Penalty coefficient for `time_per_output_token` (TPOT) violations. Set it to `0` if there is no TPOT constraint. Value range: [0, 100]. The recommended value is `1`.|
|success_rate_penalty|Yes|Penalty coefficient for the request success rate. The value is an integer ranging from 1 to 1000. The recommended value is `5`.|
|ttft_slo|Yes|TTFT latency constraint (in seconds) For example, if TTFT is limited to 2s, set the value to `2`. Value range: (0, 100].|
|tpot_slo|Yes|TPOT latency constraint (in seconds) For example, if TPOT is limited to 50 ms, set the value to `0.05`. Value range: (0, 100].|
|service|Yes|Node role in multi-node deployment. The options are as follows:<br>&#8226;`master`: primary node<br>&#8226;`slave`: secondary node<br>The default value is `master`.|
|sample_size|No|Dataset sampling size for improved efficiency. The value is an integer ranging from 1000 to 10000. The recommended value is 1/3 of original dataset size.|

**Benchmark tool parameters**:
If `AISBench` is used for the test, modify the following parameters. For details, see [AISBench Usage Description](https://github.com/AISBench/benchmark/blob/master/README.md).

|Parameter|Description|
|---|---|
|models| Specifies a model task. You can configure it as described in [Model Configuration Description](https://github.com/AISBench/benchmark/blob/master/docs/source_en/base_tutorials/all_params/models.md).|
|datasets| Specifies a dataset task. For details, see [Dataset Preparation Guide](https://github.com/AISBench/benchmark/blob/master/docs/source_en/get_started/datasets.md).|
|mode| Specifies the operation mode. For details, see [Operation Mode Description](https://github.com/AISBench/benchmark/blob/master/docs/source_en/base_tutorials/all_params/mode.md).|
|num_prompts| Specifies the number of prompts to run from the dataset. This parameter is valid only when `mode` is set to `perf`.|

If `vllm_benchmark` is used for the test, modify the following parameters:

|Parameter|Mandatory (Yes/No)|Description|
|---|---|---|
|host|Yes| Host IP address, which must match `host` in `[vllm.command]`. The value can be `127.0.0.1`.|
|port|Yes| Port number, which must match `port` in `[vllm.command]`.|
|model|Yes| Model path, which must match `model` in `[vllm.command]`.|
|served_model_name|Yes| Model name, which must match `served_model_name` in `[vllm.command]`.|
|dataset_name|Yes| Dataset name|
|dataset_path|Yes| Dataset path|
|num_prompts|Yes| Specifies the number of prompts to run from the dataset.<br>The value is an integer ranging from 1 to 10000.|
|others|No| Additional parameters. Use spaces to separate them, and no space is allowed within the parameters, for example, `--ignore-eos --custom-output-len 1500`. This parameter is left empty by default.|

**Serving parameters**: Modify these parameters as described in [MindIE Server Configuration Parameter Description](https://gitcode.com/Ascend/MindIE-LLM/blob/v3.1.0/docs/en/user_guide/user_manual/service_parameter_configuration.md).
You can define search ranges directly using these parameters. For example, to set the optimization search space for `max_batch_size` to 10 to 400:

```shell
[[mindie.target_field]]
name = "max_batch_size"     # Serving parameter name
config_position = "BackendConfig.ScheduleConfig.maxBatchSize"   # Path to the serving parameters in MindIE Server config
min = 10     # Minimum value
max = 400    # Maximum value
dtype = "int"    # Data type
```

You can also define parameters relative to others. For example, to set `max_prefill_batch_size` as a ratio of `max_batch_size`, that is, `max_prefill_batch_size = ratio * max_batch_size (0 < ratio < 1)`:

```shell
[[mindie.target_field]]
name = "max_prefill_batch_size"
config_position = "BackendConfig.ScheduleConfig.maxPrefillBatchSize"
min = 0
max = 1
dtype = "ratio"
dtype_param = "max_batch_size" # Indicates that max_prefill_batch_size is proportional to max_batch_size.
```

In addition, all `dtype` types supported by `target_field` are as follows:

| Category | dtype | Meaning | dtype_param Format |
|---|---|---|---|
| Base Type | `int` | An integer within [min, max] | — |
| Base Type | `float` | A floating-point number within [min, max] | — |
| Base Type | `bool` | Boolean switch (true when the parameter value > 0.5) | — |
| Base Type | `enum` | A value from the candidate list (numeric or string values supported) | Candidate value list, such as `[1, 2, 4, 8]` |
| Base Type | `range` | Enumerates within [min, max] by step | Step integer, such as `10` |
| Binary Derivation | `ratio` | `int(ratio × target)` | Dependent field name (string), such as `"max_batch_size"` |
| Binary Derivation | `share` | `target.min + target.max - target.value` (complementary) | Dependent field name (string) |
| Binary Derivation | `factories` | `product ÷ target` | `{"target_name": "field name", "product": value, "dtype": "int"}` |
| Binary Derivation | `times` | `product × target` | `{"target_name": "field name", "product": value, "dtype": "int"}` |
| **Ternary Derivation** | **`ternary_factories`** | **`product ÷ (field_a × field_b)`** | **`{"target_names": ["A", "B"], "product": value, "dtype": "int"}`** |
| **Ternary Derivation** | **`ternary_times`** | **`product × field_a × field_b`** | **`{"target_names": ["A", "B"], "product": value, "dtype": "int"}`** |

>[!NOTE]
>
> The values of derived type fields (`factories` / `times` / `ternary_factories` / `ternary_times`) are automatically derived from dependency relationships and **do not participate in particle swarm search**. Both `min` and `max` must be set to `0`. If any dependent field value is `0` (division scenario) or `None`/`NaN` (multiplication scenario), the current derivation is skipped, the field retains its original value, and a warning log is output.

**Usage Example of Ternary Derivation Type**

Scenario 1: `tp` and `pp` are tunable parameters, and `dp` is automatically derived from the total number of ranks (16) (`dp = 16 ÷ (tp × pp)`):

>[!NOTE]Constraints
>
> `ternary_factories` requires that the product of the dependent fields can legally derive the derived field. For `dtype = "int"`, `product` must be divisible by the product of the dependent fields; otherwise, priority-based repair is triggered.
>
> - **Built-in protection for the int type**: When the result is less than 1 or not divisible, the source fields are repaired first; if the repair fails, the value is degraded according to min/max, and a WARNING is output.
> - **Explicit range setting**: Configure `min_value` / `max_value` in `dtype_param` to override the upper and lower bounds.
> - **Best practice**: Restrict the enumeration candidates of `tp` and `pp` so that the product is divisible by `product`, avoiding reliance on degraded handling.

```shell
# Method 1 (best practice): Restrict the enumeration candidates of tp and pp to ensure tp × pp ≤ 16
[[mindie.target_field]]
name = "tp"
config_position = "BackendConfig.ModelDeployConfig.ModelConfig.0.tp"
min = 0
max = 1
dtype = "enum"
dtype_param = [1, 2, 4, 8]   # Set the maximum value of tp to 8

[[mindie.target_field]]
name = "pp"
config_position = "BackendConfig.ModelDeployConfig.ModelConfig.0.pp"
min = 0
max = 1
dtype = "enum"
dtype_param = [1, 2]          # Restrict pp to 1 or 2 to ensure the maximum tp × pp of 8 × 2 = 16 is not exceeded

[[mindie.target_field]]
name = "dp"
config_position = "BackendConfig.ModelDeployConfig.ModelConfig.0.dp"
min = 0
max = 0
dtype = "ternary_factories"
dtype_param = {target_names = ["tp", "pp"], product = 16, dtype = "int"}
# Example: tp=4, pp=2 → dp = 16 ÷ (4 × 2) = 2
#        tp=8, pp=2 → dp = 16 ÷ (8 × 2) = 1
```

```shell
# Method 2: Configure min_value as the lower-bound protection after repair fails, and output a warning
[[mindie.target_field]]
name = "dp"
config_position = "BackendConfig.ModelDeployConfig.ModelConfig.0.dp"
min = 0
max = 0
dtype = "ternary_factories"
dtype_param = {target_names = ["tp", "pp"], product = 16, dtype = "int", min_value = 1}
# If no repairable legal combination exists and the result is lower than min_value, it degrades to min_value=1 and outputs WARNING
```

**Priority Repair Policy (`priority_policy`)**

When the `tp` and `pp` combination generated by PSO cannot derive `dp` (for example, it is not divisible or exceeds the bound), the system attempts a repair. The repair policy is controlled by `priority_policy`:

| Policy Name | Semantics | Applicable Scenario |
|--------|------|----------|
| `balanced` (default) | Divides particles evenly into two groups: the first half is repaired in the order of `target_names`, and the second half is repaired in reverse order, reducing the structural bias introduced by a single decoding order. | The user has no explicit field priority preference; used by default |
| `fixed` | The user explicitly specifies the repair order: high-priority fields are kept unchanged as much as possible, and low-priority fields are adjusted first | The user clearly knows which field should be more stable |

```shell
# Example of the balanced (default) policy
# Applicable when the user does not specify which field is more important; the system automatically balances the repair direction
[[mindie.target_field]]
name = "dp"
config_position = "BackendConfig.ModelDeployConfig.ModelConfig.0.dp"
min = 0
max = 0
dtype = "ternary_factories"
dtype_param = {
  target_names = ["tp", "pp"],
  product = 32,
  dtype = "int",
  priority_policy = "balanced"   # The default is balanced, so this can be omitted
}
```

```shell
# Example of the fixed policy
# Applicable when the user explicitly knows that tp should remain stable and pp should be adjusted first
[[mindie.target_field]]
name = "dp"
config_position = "BackendConfig.ModelDeployConfig.ModelConfig.0.dp"
min = 0
max = 0
dtype = "ternary_factories"
dtype_param = {
  target_names = ["tp", "pp"],
  product = 32,
  dtype = "int",
  priority_policy = "fixed",
  priority = ["tp", "pp"]        # tp has high priority: keep tp as much as possible and adjust pp first
}
# Example: tp=8, pp=3 (invalid)
#   stage1: fix tp=8, find the nearest legal value among pp candidates -> pp=4, dp=1
#   If stage1 fails, proceed to stage2: both fields can be adjusted, searching in ascending order of distance
```

>[!NOTE]priority_policy
>
> - `balanced` is the default policy and takes effect automatically when not configured.
> - `balanced` reduces the structural bias caused by the order of a single field by stratifying particles according to the decoding order, but it cannot guarantee a global optimum.
> - `fixed` is suitable for scenarios where the user explicitly knows which field should remain more stable, for example, when tp is determined by hardware resources.
> - The repair is performed in two stages: stage1 fixes the high-priority field and adjusts the low-priority field; if stage1 fails, stage2 allows both fields to be adjusted.
> - When all candidates are invalid, the repair fails and falls back to min/max truncation with a warning output.

Scenario 2: `seq_len` and `prefill_batch_size` are adjustable parameters, and `max_prefill_tokens` is automatically set to twice the product of the two (`max_prefill_tokens = 2 × seq_len × prefill_batch_size`):

```shell
[[mindie.target_field]]
name = "seq_len"
config_position = "BackendConfig.ModelConfig.seqLen"
min = 0
max = 1
dtype = "enum"
dtype_param = [512, 1024, 2048, 4096]

[[mindie.target_field]]
name = "prefill_batch_size"
config_position = "BackendConfig.ScheduleConfig.maxPrefillBatchSize"
min = 1
max = 16
dtype = "int"

[[mindie.target_field]]
name = "max_prefill_tokens"
config_position = "BackendConfig.ScheduleConfig.maxPrefillTokens"
min = 0         # Set to 0 to make it a constant that does not participate in the search
max = 0
dtype = "ternary_times"
dtype_param = {target_names = ["seq_len", "prefill_batch_size"], product = 2, dtype = "int"}
# When seq_len=1024 and prefill_batch_size=4, max_prefill_tokens = 2 × 1024 × 4 = 8192.
```

When the vLLM framework is used, you need to modify the `[vllm.command]` parameter in the `config.toml` file. For example:

```shell
[vllm.command]
host = "127.0.0.1"
port = "8000"
model = "/workspace/vllm/models/llama-2-7b-chat-hf"
served_model_name = "llama-2-7b-chat-hf"
others = ""
```

|Parameter|Mandatory (Yes/No)|Description|
|---|---|---|
|host|Yes| Host IP address, which must match `host` in `[vllm_benchmark.command]`. The value can be `127.0.0.1`.|
|port|Yes| Port number, which must match `port` in `[vllm_benchmark.command]`.|
|model|Yes| Model path, which must match `model` in `[vllm_benchmark.command]`.|
|served_model_name|Yes| Model name, which must match `served_model_name` in `[vllm_benchmark.command]`.|
|others|No| Additional parameters. Use spaces to separate them, and no space is allowed within the parameters, for example, `--tensor-parallel-size 2 --no-enable-prefix-caching`. This parameter is left empty by default.|

### Custom Parameter Optimization

The optimization tool supports adding any vllm startup parameter for optimization through `[[vllm.target_field]]`. The configuration consists of two steps: **declare the optimization field** + **reference the variable in `others`**.

> **Variable reference rule**: In `others`, reference the optimization field using the `$UPPERCASE_FIELD_NAME` format. At runtime, the tool automatically replaces it with the actual value of the current iteration.

#### Example 1: Enumerated Numeric Parameter (Using `gpu_memory_utilization` as an Example)

**Step 1**: Declare the optimization field.

```toml
[[vllm.target_field]]
name = "GPU_MEMORY_UTILIZATION"
config_position = "env"
dtype = "enum"
dtype_param = [0.9, 0.91, 0.92]
value = 0.9
```

**Step 2**: Reference the variable in `others` under `[vllm.command]`.

```toml
[vllm.command]
# ... Other required parameters ...
others = "--gpu-memory-utilization $GPU_MEMORY_UTILIZATION"
```

#### Example 2: Switch-type/Composite String Parameter (Using the Compilation Configuration `--compilation-config` as an Example)

When the parameter itself is a complete CLI string, the two forms of "disabled" (empty string `""`) and "enabled" can be used as enumeration candidate values. When the tool encounters an empty string, it automatically skips it and does not append any content to the startup command.

**Step 1**: Declare the optimization field.

> **Note**: TOML strings use double quotes `"` as delimiters. If the string content contains double quotes, they must be escaped with `\"`; otherwise, a parsing error will occur.

```toml
[[vllm.target_field]]
name = "COMPILATION_CONFIG"
config_position = "env"
dtype = "enum"
dtype_param = ["", "--compilation-config '{\"cudagraph_mode\": \"FULL_DECODE_ONLY\"}'"]
value = "--compilation-config '{\"cudagraph_mode\": \"FULL_DECODE_ONLY\"}'"
```

**Step 2**: Reference the variable in `others` under `[vllm.command]`.

```toml
[vllm.command]
# ... other mandatory parameters ...
others = "$COMPILATION_CONFIG"
```

**Log detection**: checks abnormal information in logs, distinguishes fatal errors from retryable errors, and implements intelligent error handling and retry mechanisms. Detectable error types include out-of-memory (OOM), device faults (NPU), network errors, and I/O errors. Fatal errors (such as OOM and NPU faults) immediately stop the scheduler, while retryable errors (such as network jitter and I/O failures) trigger automatic retries (up to 3 times).

|Parameter|Mandatory (Yes/No)|Description|
|---|---|---|
|log_snippet_length|No|Length of the log snippet used to display error details. Value range: 50-1000, default 200.|
|service_errors.fatal_patterns|No|List of fatal error patterns of the serving framework, empty by default. Common fatal errors include out-of-memory and device faults.|
|service_errors.retryable_patterns|No|List of retryable error patterns of the serving framework, empty by default. Common retryable errors include network errors and I/O errors.|
|benchmark_errors.fatal_patterns|No|List of fatal error patterns of the evaluation tool, empty by default.|
|benchmark_errors.retryable_patterns|No|List of retryable error patterns of the evaluation tool, empty by default.|

Configuration example:

```toml
[health_check]
log_snippet_length = 200

[health_check.service_errors.fatal_patterns]
out_of_memory = ["out of memory", "OOM killed", "MemoryError"]
device_error = ["NPU error", "device fault", "Ascend error"]

[health_check.service_errors.retryable_patterns]
network_error = ["connection reset", "connection refused", "timeout"]
io_error = ["file not found", "permission denied", "IO error"]
```

### PD Disaggregation Optimization

Serviceparam Optimizer supports parameter optimization for MindIE in A2 single-node PD disaggregation scenarios (lightweight mode only). This requires a Kubernetes deployment. Ensure that Kubernetes can successfully start the MindIE service.
>[!NOTE]
> Currently, only MindIE 2.2.RC1 is supported.

Set the `kubectl_default_path` field in `config.toml` to the single-node execution directory extracted from the Kubernetes installation script. The directory structure must be as follows:

```text
K8s_v1.23_MindCluster.7.1.RC1.B098.aarch/
├── all_label_a2.sh
├── all_label_a3.sh
├── Ascend-docker-runtime_7.1.RC1_linux-aarch64.run
├── Ascend-mindxdl-ascend-operator_7.1.RC1_linux-aarch64/
├── Ascend-mindxdl-clusterd_7.1.RC1_linux-aarch64/
├── Ascend-mindxdl-device-plugin_7.1.RC1_linux-aarch64/
├── Ascend-mindxdl-noded_7.1.RC1_linux-aarch64/
├── Ascend-mindxdl-volcano_7.1.RC1_linux-aarch64/
├── k8s
│   ├── alpine.tar
│   ├── calico3_23.yaml
│   ├── k8s1_23_0+calico3_23.tar.gz
│   └── ubuntu-18.04.tar
└── kubernetes
│   ├── Packages.gz
│   ├── kubeadm_1.23.0-00_arm64.deb
│   ├── kubectl_1.23.0-00_arm64.deb
│   ├── kubelet_1.23.0-00_arm64.deb
│   ├── ...
│   └── zlib1g_1%3a1.2.11.dfsg-2ubuntu9.2_arm64.deb
└── kubernetes_deploy_scripts_latest
    ├──boot_helper
    ├──chat.sh
    ├──conf
    ├──delete.sh
    ├──deploy_ac_job.py
    ├──deployment
    ├──deploy.sh
    ├──envcheck.sh
    ├──gen_ranktable_helper
    ├──log.sh
    ├──pd_scripts_single
    ├──show_logs.sh
    ├──user_config.json
    ├──user_config_base_A3.json
```

Configuration example:

```shell
kubectl_default_path = "K8s_v1.23_MindCluster.7.1.RC1.B098.aarch/kubernetes_deploy_scripts_latest" # Use an absolute path.
```

To optimize PD ratio parameters, add the following to the `mindie` section in `config.toml`:

```shell
[[mindie.target_field]]
name = "default_p_rate"
config_position = "default_p_rate"
min = 1
max = 3
dtype = "int"
value = 1
[[mindie.target_field]]
name = "default_d_rate"
config_position = "default_d_rate"
min = 1
max = 3
dtype = "share" #Indicates that this parameter is related to default_p_rate. The sum of the two values is fixed.
dtype_param = "default_p_rate"
```

### Plugin Mode

Serviceparam Optimizer supports user-defined inference frameworks and benchmark tools. You can configure them as needed by adapting to the plugin interface and registering the corresponding plugin. For details, see [Plugin Development Guide](serviceparam_optimizer_plugin_instruct.md).

### Log Description

The default log level during optimization is `INFO`. To view detailed per-iteration logs, set the following environment variable before running the tool:

```bash
export MODELEVALSTATE_LEVEL=DEBUG
```

The status of each iteration is printed to the console. Detailed `MindIE/vLLM` logs are redirected to `/tmp`. The exact file path is shown in the console output for debugging.
