# vLLM 服务化性能采集工具使用指南

## 简介

vLLM 服务化性能采集工具（vLLM Service Profiler）是用于监测和采集 vLLM-Ascend 推理服务框架内部执行流程性能数据的工具。该工具通过采集关键流程的起止时间、识别关键函数或迭代、记录关键事件并捕获多种类型的信息，帮助用户快速定位性能瓶颈。

vLLM Service Profiler 适用于在 vLLM-Ascend 推理服务过程中进行性能监测和优化分析，覆盖从准备、采集、解析到结果展示的完整流程。

### 基本概念

- **性能采集**：通过埋点技术记录服务运行时的关键时间点和事件，生成性能分析数据。
- **埋点/采集点位（Symbol）**：性能数据采集的具体目标，通过指定 vLLM 或者 vLLM-Ascend 源码中具体的可执行函数定义。
- **埋点域（Domain）**：性能数据采集的功能分类，如 Request、KVCache、ModelExecute 等。
- **点位配置**：定义需要采集的函数/方法及其属性的配置文件。

## 产品支持情况

> [!NOTE]
>
>昇腾产品的具体型号，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》

|产品类型| 是否支持 |
|--|:----:|
|Ascend 950 系列产品|√|
|Atlas A3 训练系列产品/Atlas A3 推理系列产品|√|
|Atlas A2 训练系列产品/Atlas A2 推理系列产品|√|
|Atlas 200I/500 A2 推理产品|√|
|Atlas 推理系列产品|√|
|Atlas 训练系列产品|x|

### 使用前准备

#### 环境准备

1. 在昇腾环境安装配套版本的CANN Toolkit开发套件包和ops算子包并配置CANN环境变量，具体请参见[CANN快速安装](https://www.hiascend.com/cann/download)。
2. 完成 vLLM 和 vLLM-Ascend 的安装和配置并确认 vLLM-Ascend 可以正常运行，具体请参见《 [vLLM-Ascend安装指南](https://docs.vllm.ai/projects/ascend/zh-cn/v0.13.0/installation.html)》。
3. 升级 msServiceProfiler 工具，请参见《msServiceProfiler工具安装指南》文档中“[4. 升级](./msserviceprofiler_install_guide.md#5-升级)”章节。

#### 约束

- **版本配套**：请确保 vLLM-Ascend、CANN 和采集工具的版本配套关系符合附录中的要求。
- **资源占用**：采集过程中可能占用较大内存，建议根据实际需求调整采集频率参数。
- **功能限制**：部分高级功能需要特定版本的 vLLM-Ascend 框架支持。

## 快速入门

**1. 准备采集**

在启动服务前，需要设置以下环境变量：

- `SERVICE_PROF_CONFIG_PATH`：指定性能分析配置文件路径
- `PROFILING_SYMBOLS_PATH`：指定符号配置文件路径

```bash
cd ${path_to_store_profiling_files}
export SERVICE_PROF_CONFIG_PATH=ms_service_profiler_config.json
export PROFILING_SYMBOLS_PATH=service_profiling_symbols.yaml

# 启动 vLLM 服务
vllm serve Qwen/Qwen2.5-0.5B-Instruct &
```

其中 `ms_service_profiler_config.json` 为采集配置文件，若不存在会自动生成默认配置。若有需要，可参照[采集配置使用指南](#采集配置使用指南)章节提前进行自定义配置。

`service_profiling_symbols.yaml` 为需要导入的埋点配置文件。你也可以选择不设置环境变量 `PROFILING_SYMBOLS_PATH` ，此时将使用默认的配置文件；若你指定的路径下不存在该文件，系统同样会在你指定的路径生成一份配置文件以便后续修改。可参考[点位配置使用指南](#点位配置使用指南)一节进行自定义。

**2. 开启采集**

将配置文件`ms_service_profiler_config.json`中的 `enable` 字段由 `0` 修改为 `1`，即可开启性能数据采集的开关，可以通过执行下面sed指令完成采集服务的开启：

```bash
sed -i 's/"enable":\s*0/"enable": 1/' ./ms_service_profiler_config.json
```

**3. 发送请求**

根据实际采集需求选择请求发送方式：

```bash
curl http://localhost:8000/v1/completions \
    -H "Content-Type: application/json"  \
    -d '{
         "model": "Qwen/Qwen2.5-0.5B-Instruct",
        "prompt": "Beijing is a",
        "max_tokens": 5,
        "temperature": 0
}' | python3 -m json.tool
```

**4. 解析数据**

```bash
# xxxx-xxxx 为采集工具根据 vLLM 启动时间自动创建的存放目录
cd /root/.ms_server_profiler/xxxx-xxxx

# 解析数据
msserviceprofiler parse --input-path=./ --output-path output
```

**5. 查看数据**

解析完成后在`--output-path`指定的目录下会生成性能数据文件，详细介绍请参见[输出结果文件说明](#输出结果文件说明)。

## 点位配置使用指南

### 功能说明

点位配置文件用于定义需要采集的函数/方法，支持灵活配置与自定义属性采集。

### 注意事项

#### 内置/自定义点位配置文件

点位配置文件已在 vLLM-Ascend 以及工具中内置：

- 默认加载路径：`~/.config/vllm_ascend/service_profiling_symbols.MAJOR.MINOR.PATCH.yaml`（适用于 vLLM-Ascend 框架且文件名随已安装的 vllm 版本变化）
- 备用加载路径：`工具安装路径/ms_service_profiler/patcher/vllm/config/service_profiling_symbols.yaml`

如需自定义采集点，推荐通过设置环境变量`PROFILING_SYMBOLS_PATH`，将一份点位配置文件复制到工作目录进行修改使用。

#### 点位配置文件更新

采集点位有更新，需要重启 vLLM 服务加载更新后的配置文件。

### 配置字段说明

|     字段      | 说明                | 示例                                                    |
|:-----------:|:------------------|:------------------------------------------------------|
|   symbol    | Python 导入路径 + 属性链 | `"vllm.v1.core.kv_cache_manager:KVCacheManager.free"` |
|   handler   | 处理函数类型            | `"timer"`（计时器）或 `"pkg.mod:func"`（自定义）                 |
|   domain    | 埋点域标识             | `"KVCache"`, `"ModelExecute"`                         |
|    name     | 埋点名称              | `"EngineCoreExecute"`                                 |
| min_version | 最低版本约束            | `"0.9.1"`                                             |
| max_version | 最高版本约束            | `"0.11.0"`                                            |
| attributes  | 自定义属性采集           | 只支持 `"timer"` handler。详见下方自定义属性采集机制                   |

#### 配置示例

- **示例 1：自定义处理函数**

```yaml
- symbol: vllm.v1.core.kv_cache_manager:KVCacheManager.free
  handler: ms_service_profiler.patcher.config.custom_handler_example.kvcache_manager_free_example_handler
  domain: Example
  name: example_custom
```

- **示例 2：默认计时器**

```yaml
- symbol: vllm.v1.engine.core:EngineCore.execute_model
  domain: ModelExecute
  name: EngineCoreExecute
```

- **示例 3：版本约束**

```yaml
- symbol: vllm.v1.executor.abstract:Executor.execute_model
  min_version: "0.9.1"
  # 未指定 handler -> 默认 timer
```

### 自定义属性采集机制

`attributes` 字段支持灵活的自定义属性采集，可对函数参数与返回值进行多种操作与转换。

#### 基本语法

- **参数访问**：直接使用参数名称，如 `request_id`
- **返回值访问**：使用 `return` 关键字
- **属性访问**：使用 `attr` 操作符，如 `obj | attr name`
- **方法调用**：支持内置函数如 `len()`, `str()`, `int()`, `float()`
- **管道操作**：使用 `|` 连接多个操作步骤，表达式从左到右依次执行，每个操作符的输出作为下一个操作符的输入

#### 配置示例

```yaml
- symbol: vllm_ascend.worker.model_runner_v1:NPUModelRunner.execute_model
  name: ModelRunnerExecuteModel
  domain: ModelExecute
  attributes:
  - name: device
    expr: args[0] | attr device | str
  - name: dp
    expr: args[0] | attr dp_rank | str
  - name: batch_size
    expr: args[0] | attr input_batch | attr _req_ids | len
```

#### 表达式说明

1. `len(input_ids)`：获取 `input_ids` 参数的长度。
2. `len(return) | str`：获取返回值长度并转换为字符串（等价于 `str(len(return))`）。
3. `return[0] | attr input_ids | len`：获取返回值第一个元素的 `input_ids` 属性长度。

#### 高级示例

```yaml
attributes:
  # 获取张量形状
  - name: tensor_shape
    expr: input_tensor | attr shape | str

  # 获取字典中的特定值
  - name: batch_size
    expr: kwargs['batch_size']

  # 条件表达式（需要自定义处理函数支持）
  - name: is_training_mode
    expr: training | bool

  # 复杂的数据处理
  - name: processed_data_len
    expr: data | attr items | len | str
```

### 自定义处理函数

当 `handler` 字段指定自定义处理函数时，该函数需满足以下签名：

```python
def custom_handler(original_func, this, *args, **kwargs):
    """
    自定义处理函数

    Args:
        original_func: 原始函数对象
        this: 调用对象（对于方法调用）
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        处理结果
    """
    # 自定义处理逻辑
    pass
```

> [!NOTE]
>
> 若自定义处理函数导入失败，系统会自动回退至默认计时器模式。

### 输出说明

自定义配置采集的函数或方法可以展示在解析输出的`chrome_tracing.json`时间轴上，下面给出一个示例：

点位配置文件配置：

```yaml
- symbol: vllm.entrypoints.openai.serving_chat:OpenAIServingChat.create_chat_completion
  name: OpenAIServingChat.create_chat_completion
  domain: Server

- symbol: vllm.entrypoints.openai.serving_chat:EngineCoreProc._process_engine_step
  name: EngineCoreProc._process_engine_step
  domain: Engine

- symbol: vllm.entrypoints.openai.serving_chat:EngineCoreProc.step
  name: EngineCoreProc.step
  domain: Engine
```

`chrome_tracing.json`时间轴效果图：

![](figures/vllm_profiler_custom_symbol_timeline_display.PNG)

## 输出结果文件说明

解析完成后，`output` 目录下会生成下面表格中列出的交付件：

|          输出件          | 说明                                                                                                                                         |
|:---------------------:|:-------------------------------------------------------------------------------------------------------------------------------------------|
| `chrome_tracing.json` | 记录推理服务化请求trace数据，可使用不同可视化工具进行查看，详细介绍请参考[数据可视化](./msserviceprofiler_serving_tuning_instruct.md#数据可视化)                                       |
|     `profiler.db`     | 用于生成可视化折线图的SQLite数据库文件，详细介绍请参考[profiler.db 说明](./msserviceprofiler_serving_tuning_instruct.md#profilerdb)                                 |
|     `request.csv`     | 记录服务化推理请求为粒度的详细数据，详细介绍请参考[request.csv 说明](./msserviceprofiler_serving_tuning_instruct.md#requestcsv)                                      |
| `request_summary.csv` | 请求总体统计指标                                                                                                                                   |
| `forward.csv` | 记录服务化推理模型前向执行过程的详细数据，详情介绍请参考[forward.csv 说明](./msserviceprofiler_serving_tuning_instruct.md#forwardcsv)                                    |
|     `kvcache.csv`     | 记录推理过程的显存使用情况，详细介绍请参考[kvcache.csv 说明](./msserviceprofiler_serving_tuning_instruct.md#kvcachecsv)                                          |
|      `batch.csv`      | 记录服务化推理batch为粒度的详细数据，详细介绍请参考[batch.csv 说明](./msserviceprofiler_serving_tuning_instruct.md#batchcsv)                                       |
|   `spec_decode.csv`   | 投机推理场景下以每条请求为粒度的详细数据，详细介绍请参考[spec_decode.csv 说明](./msserviceprofiler_serving_tuning_instruct.md#spec_decodecsv) |
|  `batch_summary.csv`  | 批次调度总体统计指标                                                                                                                                 |
| `service_summary.csv` | 服务化维度总体统计指标                                                                                                                                |
|     `span_info/`      | 包含forward.csv, batchFrameworkProcessing.csv等关键span信息，详细介绍请参考[span_info 目录说明](./msserviceprofiler_serving_tuning_instruct.md#span_info目录) |

>[!NOTE]
>
>输出结果文件与domain域的采集有强关联关系，具体对照可以参照[domain域与解析结果对照表](./msserviceprofiler_serving_tuning_instruct.md#解析结果)。

## 附录

### vLLM各版本及框架支持情况

| 配套CANN版本 | vLLM-Ascend V0 | vLLM-Ascend V1 |
|:--------:|:--------------:|:--------------:|
| 8.3.RC1  |       /        |  v0.11.0.RC3   |
| 8.3.RC1  |       /        |  v0.11.0.RC2   |
| 8.3.RC1  |       /        |  v0.11.0.RC1   |
| 8.2.RC1  |       /        |  v0.11.0.RC0   |
| 8.2.RC1  |       /        |  v0.10.2.RC1   |
| 8.2.RC1  |       /        |  v0.10.1.RC1   |
| 8.2.RC1  |       /        |  v0.10.0.RC1   |
| 8.2.RC1  |       /        |   v0.9.2.RC1   |
| 8.2.RC1  |     v0.9.1     |     v0.9.1     |
| 8.1.RC1  |   v0.8.5.RC1   |       /        |
| 8.1.RC1  |     v0.8.4     |       /        |
| 8.0.RC3  |     v0.6.3     |       /        |

### 采集配置使用指南

采集配置可以参考[数据采集](./msserviceprofiler_serving_tuning_instruct.md#数据采集)中的配置文件创建的说明以及注意事项的澄清。

>[!NOTE]
>
> - vLLM Service Profiler 在 `acl_task_time` 参数配置为1时，不支持同时配置vLLM原生 Torch Profiler 的 `VLLM_TORCH_PROFILER_DIR` 环境变量进行性能数据采集。
> - 配置 Torch Profiler 采集时，`enable`参数取值初始须为0（表示关闭性能数据采集），之后在启动 vLLM-Ascend 推理服务框架服务后再将配置`enable`参数配置为1（开启采集），为了避免采集过多的性能数据，可在完成相应数据采集过后关闭采集。如果`enable`参数取值初始为1，会采集大量框架层数据，很容易生成几个 GB 的跟踪文件。
