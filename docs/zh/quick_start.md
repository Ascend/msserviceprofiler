# 服务化性能调优工具快速入门<a name="ZH-CN_TOPIC_0000002475358702"></a>

服务化框架的性能调优往往如同置身 “黑盒”，问题根源难以精准定位 —— 比如请求量攀升后响应速度显著下降、硬件设备更换后性能表现迥异等场景，都难以快速排查。

msServiceProfiler（服务化调优工具）提供全链路性能剖析，清晰展示框架调度、模型推理等环节的表现，帮助用户快速找到性能瓶颈（帮助判断是框架问题还是模型问题），从而有效提升服务性能。

> [!NOTE]
> 
> 以下仅提供服务化调优工具的快速入门，工具更多操作及接口、参数、字段等详细内容介绍请参见“服务化调优工具”。

## 前提条件<a name="section1605203618349"></a>

- 在使用性能调优工具前请先完成msServiceProfiler工具安装，具体请参见《[msServiceProfiler工具安装指南](msserviceprofiler_install_guide.md)》。
- 已完成对应服务框架的安装，并通过可用性验证（服务能够正常启动，且可通过官方示例脚本或 API 成功发起一次推理请求）：
  - **MindIE Motor**：请参见《[MindIE 安装指南](https://gitcode.com/Ascend/MindIE-Motor/blob/dev/docs/zh/user_guide/install/environment_preparation.md)》完成 MindIE 的安装和配置，并确认 MindIE Motor 服务可以正常启动且能完成一次示例推理请求。
  - **vLLM-Ascend**：请参见《[vLLM 服务化性能采集工具使用指南](vLLM_service_oriented_performance_collection_tool.md)》以及 vLLM-Ascend 官方安装文档，完成环境准备并验证 vLLM 服务可正常对外提供推理接口。
  - **SGLang**：请参见《[SGLang 服务化性能采集工具使用指南](SGLang_service_oriented_performance_collection_tool.md)》以及 SGLang 官方安装文档，完成环境准备并验证 SGLang 服务可正常对外提供推理接口。

## 操作步骤<a name="section166491954201410"></a>

> 当前 msServiceProfiler 已支持多种服务化推理框架（如 MindIE Motor、vLLM-Ascend以及SGLang）。  

### 1. 配置环境变量<a name="li104932444507"></a>

msServiceProfiler 的采集能力需要在部署服务之前，通过设置环境变量 `SERVICE_PROF_CONFIG_PATH`方能生效。如果环境变量拼写错误，或者没有在部署服务之前设置环境变量，都无法使能采集能力。

- **通用说明**

  - `SERVICE_PROF_CONFIG_PATH`：指定性能采集配置文件（JSON），用于控制是否开启采集、数据输出目录等。

- **示例（以当前工作目录下的配置文件为例）**

  ```bash
  export SERVICE_PROF_CONFIG_PATH="./ms_service_profiler_config.json"
  ```

`SERVICE_PROF_CONFIG_PATH` 的值需要指定到 json 文件名，该 json 文件即为控制性能数据采集的配置文件，比如采集性能元数据存放位置、算子采集开关等，具体字段介绍参考[3. 数据采集](#li10670349115211)。若路径下无配置文件，工具将自动生成默认配置（采集开关默认为关闭状态）。

>[!NOTE]
>
>在多机部署时，通常不建议将配置文件或其指定的数据存储路径放置在共享目录（如网络共享位置）。由于数据写入方式可能涉及额外的网络或缓冲环节，而非直接落盘，此类配置在某些情况下可能导致预期外的系统行为或结果。

### 2. 运行服务

不同框架下的“运行服务”步骤不同，但对 msServiceProfiler 来说，关键是在服务进程启动之前完成环境变量配置，之后按照各框架原有方式启动服务。

#### 2.1 MindIE Motor

按照《[MindIE 安装指南](https://gitcode.com/Ascend/MindIE-Motor/blob/dev/docs/zh/user_guide/install/environment_preparation.md)》启动推理服务即可。若正确配置了 `SERVICE_PROF_CONFIG_PATH`，在服务部署完成之前会输出如下以 `[msservice_profiler]` 开头的日志，说明 msServiceProfiler 已启动，例如：

```ColdFusion
[msservice_profiler] [PID:225] [INFO] [ParseEnable:179] profile enable_: false
[msservice_profiler] [PID:225] [INFO] [ParseAclTaskTime:264] profile enableAclTaskTime_: false
[msservice_profiler] [PID:225] [INFO] [ParseAclTaskTime:265] profile msptiEnable_: false
[msservice_profiler] [PID:225] [INFO] [LogDomainInfo:357] profile enableDomainFilter_: false
```

如果 `SERVICE_PROF_CONFIG_PATH` 环境变量所指定的配置文件不存在，工具会自动创建，日志类似：

```ColdFusion
[msservice_profiler] [PID:225] [INFO] [SaveConfigToJsonFile:588] Successfully saved profiler configuration to: ./ms_service_profiler_config.json
```

#### 2.2 vLLM-Ascend

在完成 vLLM-Ascend 环境准备和变量配置后，按 vLLM 原生方式启动服务，例如：

```bash
cd ${path_to_store_profiling_files}
export SERVICE_PROF_CONFIG_PATH=ms_service_profiler_config.json
# 启动 vLLM 服务（示例）
vllm serve Qwen/Qwen2.5-0.5B-Instruct &
```

#### 2.3 SGLang 

### 1. 准备采集

a. 在启动服务前，需要在SGLang框架的**三个入口文件**中导入采集模块。

> [!NOTE]
>
> SGLang 使用 `spawn` 方式启动多进程，主进程（TokenizerManager）、调度进程（Scheduler/ModelRunner）、解码进程（DetokenizerManager）**各自运行在独立的 Python 解释器中**，彼此不共享 monkey-patch 状态。因此必须在每个子进程的入口函数里单独注册 profiler，否则 Scheduler、ModelRunner、DetokenizerManager 相关点位将无法采集。
>

**（1）主进程入口（TokenizerManager / HTTP 服务）**

```bash
# 编辑 SGLang 服务化启动入口文件
# /usr/local/pythonx.xx.xx/lib/pythonx.xx/site-packages 为 pip show sglang 回显的安装路径
vim /usr/local/pythonx.xx.xx/lib/pythonx.xx/site-packages/sglang/launch_server.py
# 在原本所有 import 语句后插入如下代码：
from ms_service_profiler.patcher.sglang import register_service_profiler
register_service_profiler()
```

**（2）调度子进程入口（Scheduler / ModelRunner）**

```bash
vim /usr/local/pythonx.xx.xx/lib/pythonx.xx/site-packages/sglang/srt/managers/scheduler.py
# 在 run_scheduler_process 函数体最开头（dp_rank = configure_scheduler_process(...) 之前）插入：
try:
    from ms_service_profiler.patcher.sglang import register_service_profiler
    register_service_profiler()
except ImportError:
    pass
```

**（3）解码子进程入口（DetokenizerManager）**

```bash
vim /usr/local/pythonx.xx.xx/lib/pythonx.xx/site-packages/sglang/srt/managers/detokenizer_manager.py
# 在 run_detokenizer_process 函数体最开头（kill_itself_when_parent_died() 之前）插入：
try:
    from ms_service_profiler.patcher.sglang import register_service_profiler
    register_service_profiler()
except ImportError:
    pass
```

### 2. 环境变量设置及启动服务

- `SERVICE_PROF_CONFIG_PATH`：指定性能分析配置文件路径
- `PROFILING_SYMBOLS_PATH`：指定符号配置文件路径（可选，如不设置默认读取本项目路径下ms_service_profiler/patcher/sglang/config/service_profiling_symbols.yaml文件）

```bash
cd ${path_to_store_profiling_files}
export SERVICE_PROF_CONFIG_PATH=ms_service_profiler_config.json
export PROFILING_SYMBOLS_PATH=service_profiling_symbols.yaml

# 启动 SGLang 服务
python3 -m sglang.launch_server --model-path=/Qwen2.5-0.5B-Instruct --device npu
```

### 3. 数据采集<a name="li10670349115211"></a>

服务部署成功之后，可以通过修改 `SERVICE_PROF_CONFIG_PATH` 对应配置文件中的字段来进行精准控制采集行为（此处仅以以下三个字段为例）：

```json
{
  "enable": 1,
  "prof_dir": "${PATH}/prof_dir/",
  "acl_task_time": 0
}
```

**表 1**  参数说明

| 参数          | 说明                                                         | 是否必选 |
| ------------- | ------------------------------------------------------------ | -------- |
| enable        | 性能数据采集总开关。取值为：<br>0：关闭。<br/>1：开启。<br/>即便其他开关开启，该开关不开启，仍然不会进行任何数据采集；如果只有该开关开启，只采集服务化性能数据。 | 是       |
| prof_dir      | 采集到的性能数据的存放路径，默认值为 ${HOME}/.ms_server_profiler。<br/>该路径下存放的是性能原始数据，需要继续执行后续解析步骤，才能获取可视化的性能数据文件进行分析。<br/>在 enable 为 0 时，对 prof_dir 进行自定义修改，随后修改 enable 为 1 时生效；在 enable 为 1 时，直接修改 prof_dir，则修改不生效。 | 否       |
| acl_task_time | 开启采集算子下发耗时、算子执行耗时数据的开关，取值为：<br/>0：关闭。默认值，配置为 0 或其他非法值均表示关闭。<br/>1：开启。<br/>该功能开启时会占用一定的设备性能，导致采集的性能数据不准确，建议在模型执行耗时异常时开启，用于更细致的分析。<br/>算子采集数据量较大，一般推荐集中采集 3 ~ 5s，时间过长会导致占用额外磁盘空间，消耗额外的解析时间，从而导致性能定位时间拉长。<br/>默认算子采集等级为 L0，如果需要开启其他算子采集等级，请参见“服务化调优工具”的完整参数介绍。 | 否       |

一般来说，如果 `enable` 一直为 1，当服务从收到请求的那一刻起，工具会一直采集，直到请求结束，`prof_dir` 下的目录大小也会不断增长，因此推荐用户仅采集关键时间段的信息。

每当 `enable` 字段发生变更时，工具都会输出对应的日志进行告知，例如：

```ColdFusion
[msservice_profiler] [PID:3259] [INFO] [DynamicControl:407] Profiler Enabled Successfully!
```

或：

```ColdFusion
[msservice_profiler] [PID:3057] [INFO] [DynamicControl:411] Profiler Disabled Successfully!
```

当 `enable` 由 0 改为 1 时，配置文件中的所有字段都会被工具重新加载，从而实现动态更新。

同样，工具会在 `prof_dir`（默认 `${HOME}/.ms_server_profiler/xxxx-xxxx`）下生成推理服务对应的原始性能数据。

### 4. 数据解析与调优分析

#### 4.1 数据解析

1. 安装环境依赖。

   ```bash
   python >= 3.10
   pandas >= 2.2
   numpy >= 1.24.3
   psutil >= 5.9.5
   ```

2. 执行解析命令示例（通用形式）：

   ```bash
   python3 -m ms_service_profiler.parse --input-path=${PATH}/prof_dir
   ```

   `--input-path` 指定为 [3. 数据采集](#li10670349115211) 中 **prof_dir** 参数指定的路径。解析完成后，默认在命令执行目录下生成解析后的性能数据文件。

> [!NOTE]
>
> 对于 vLLM-Ascend / SGLang on NPU，`prof_dir` 默认位于 `${HOME}/.ms_server_profiler/xxxx-xxxx`，可以在该目录下执行：
>
> ```bash
> msserviceprofiler parse --input-path=./ --output-path output
> ```
>
> 或等价的：
>
> ```bash
> python3 -m ms_service_profiler.parse --input-path=$PWD
> ```

#### 4.2 调优分析

解析后的性能数据包含db格式、csv格式和json格式，用户可以通过csv进行请求、调度等不同维度的快速分析，也可以通过MindStudio Insight工具导入db文件或者json文件进行可视化分析，详细操作和分析说明请参见《[MindStudio Insight工具用户指南](https://gitcode.com/Ascend/msinsight/blob/master/docs/zh/user_guide/overview.md)》中的“[服务化调优](https://gitcode.com/Ascend/msinsight/blob/master/docs/zh/user_guide/service_optimization.md)”章节。

根据MindStudio Insight工具的可视化呈现性能数据，如下图所示：

![](figures/zh-cn_image_0000002478067012.png)
