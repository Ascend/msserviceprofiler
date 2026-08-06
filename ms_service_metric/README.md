# ms_service_metric

一个轻量级的 Python 服务指标采集库，支持动态 Hook 和 Prometheus 指标输出。

## 特性

- 🔧 **动态 Hook**: 基于 YAML 配置动态 Hook 目标函数
- 📊 **Prometheus 集成**: 支持 Timer、Counter、Gauge、Histogram 等指标类型
- 🔄 **动态开关**: 通过共享内存和信号实现运行时开关控制
- 🏗️ **框架适配**: 内置 vLLM 框架适配器（SGLang 作为示例参考）
- 🔍 **Locals 访问**: 通过字节码注入访问函数局部变量

## 安装

```bash
pip install ms_service_metric
```

### 依赖

- Python >= 3.10
- pyyaml
- prometheus-client
- posix_ipc (Linux 平台)

## 快速开始

### 1. vLLM 集成

vLLM 通过 entry_points 机制自动适配，无需额外代码：

1. 安装 `ms_service_metric`
2. 启动 vLLM 的多进程 metric 采集环境变量

```bash
# 开启 vLLM 多进程 metric 采集环境变量
export PROMETHEUS_MULTIPROC_DIR=/dev/shm/vllm_metrics && mkdir -p $PROMETHEUS_MULTIPROC_DIR

# 可选，清理上次的指标文件
# rm -rf $PROMETHEUS_MULTIPROC_DIR/*

# 开启指标采集并确认已经开启
ms-service-metric on

ms-service-metric status

# 如之前已开启过指标，之后修改了内容，需要重启
ms-service-metric restart

# 启动vllm
# vllm serve --model your_model
```

### 2. 控制指标采集

```bash
# 开启指标采集
ms-service-metric on

# 关闭指标采集
ms-service-metric off

# 重启（重新加载配置）
ms-service-metric restart

# 查看状态
ms-service-metric status
```

### 3. Prometheus + Grafana 可视化 (Windows)

> [!NOTE]
>
> Grafana 与 Prometheus 为第三方开源软件，不属于 MindStudio Service Profiler 或 MindStudio 产品发布包的组成部分，也不是本工具强制要求用户使用的唯一可视化方案。用户可根据自身环境选择 Grafana、Prometheus 或其他兼容的监控、可视化系统。
>
> 如选择使用 Prometheus，请使用其官方维护的安全版本，并结合实际部署环境完成访问控制、网络隔离、权限配置等安全加固。

#### 安装 Prometheus

1. 下载 Prometheus Windows 版本:
   - 访问 [Prometheus 下载页面](https://prometheus.io/download/)
   - 下载 `prometheus-<version>.windows-amd64.zip`

2. 解压并配置:

   ```powershell
   # 解压到指定目录
   Expand-Archive -Path prometheus-*.zip -DestinationPath C:\Prometheus
   ```

3. 修改 `prometheus.yml` 配置文件，添加 vLLM 指标采集任务:

   ```yaml
   scrape_configs:
     - job_name: 'vllm'
       static_configs:
         - targets: ['localhost:8000']
       metrics_path: /metrics
   ```

4. 启动 Prometheus:

   ```powershell
   cd C:\Prometheus
   .\prometheus.exe --config.file=prometheus.yml
   ```

   Prometheus 默认访问地址: `http://localhost:9090`

#### 安装 Grafana

1. 下载 Grafana Windows 版本:

   - 访问 [Grafana 下载页面](https://grafana.com/grafana/download?platform=windows)
   - 下载并运行安装程序

2. 启动 Grafana 服务:

   ```powershell
   # 通过服务管理器启动
   net start grafana

   # 或者手动启动
   cd "C:\Program Files\GrafanaLabs\grafana\bin"
   .\grafana-server.exe
   ```

   Grafana 默认访问地址: `http://localhost:3000`
   - 默认用户名: `admin`
   - 默认密码: `admin`

#### 导入 Dashboard

1. 登录 Grafana Web 界面 (`http://localhost:3000`)

2. 创建 Prometheus 数据源:
   - 左侧菜单: **Configuration** → **Data sources**
   - 点击 **Add data source**
   - 选择 **Prometheus**
   - URL 填写: `http://localhost:9090`
   - 点击 **Save & Test**

3. 导入 MsServiceMetric Dashboard:
   - 左侧菜单: **Dashboards** → **Import**
   - 点击 **Upload dashboard JSON file**
   - 选择 [Dashboard 样例文件(下载到本地，匹配默认的采集配置)](https://gitcode.com/Ascend/msserviceprofiler/blob/master/ms_service_metric/example/MsServiceMetric-grafana-Dashboard.json) 文件
   - 点击 **Import**
   - 选择刚才创建的 Prometheus 数据源

### 4. 更多介绍

详细使用方法，请参考：[使用指南](https://gitcode.com/Ascend/msserviceprofiler/blob/master/docs/zh/vLLM_metrics_tool_instruct.md)

## vLLM 内置指标概览

默认 vLLM 适配器会为指标名添加 `vllm_profiling_` 前缀，并默认补充 `dp` 标签。部分指标包含额外标签，例如 `engine`、`req_phase`、`phase`、`role`、`name`、`rank`、`layer`、`threshold`、`exception_type`。

### 调度与批处理

| 指标名称 | 类型 | 说明 |
|----------|------|------|
| batch_size | Histogram | 当前正在执行的请求数量 |
| waiting_batch_size | Histogram | 当前等待调度的请求数量 |
| num_spec_tokens | Histogram | 投机解码中的草稿 token 数量 |
| scheduler:duration | Histogram | 单次调度耗时 |
| scheduler:batch_size | Histogram | 单次调度输出的请求数量 |
| scheduler:running_queue_size | Histogram | 调度后 running 队列中的请求数量 |
| scheduler:seqlen:avg | Gauge | 单次调度批次内平均序列长度 |
| scheduler:seqlen:sum | Gauge | 单次调度批次内序列长度总和 |
| scheduler:phase_batch_size | Histogram | 各请求阶段的调度请求数量 |
| scheduler:phase_scheduled_tokens | Histogram | 各请求阶段的单次调度 token 数量 |
| scheduler:phase_scheduled_token_counter | Counter | 各请求阶段累计调度 token 数量 |
| running_phase_batch_size | Histogram | running 队列中各请求阶段的请求数量 |
| waiting_phase_batch_size | Histogram | waiting 队列中各请求阶段的请求数量 |
| scheduler:add_request:duration | Histogram | 请求加入 waiting 队列的耗时 |
| scheduler:update_from_output:duration | Histogram | Scheduler 处理模型输出并更新状态的耗时 |
| scheduler:recompute_events | Counter | 重计算触发次数 |

### Token 与慢请求

| 指标名称 | 类型 | 说明 |
|----------|------|------|
| total_tokens | Histogram | 单次迭代中 prompt token 与 generation token 之和 |
| input | Histogram | 输入 prompt 的 token 数量 |
| output | Histogram | 输出生成结果的 token 数量 |
| second_token_latency | Histogram | 第二个 token 的生成延迟 |
| fine_grained_ttft | Histogram | 细粒度首 token 延迟（TTFT） |
| fine_grained_tpot | Histogram | 细粒度每 token 平均耗时（TPOT） |
| decode_over_1s_count | Counter | Decode 阶段单 token 间隔超过 1s 的累计次数 |
| prefill_over_threshold_count | Counter | Prefill 首 token 延迟超过 5s、10s、20s 阈值的累计次数 |

### KVCache 与显存

| 指标名称 | 类型 | 说明 |
|----------|------|------|
| total_kvcache_blocks | Gauge | 当前 DP 域 KVCache block 总数 |
| free_kvcache_blocks | Gauge | 当前 DP 域 KVCache 空闲 block 数 |
| allocated_kvcache_blocks | Gauge | 当前 DP 域 KVCache 已分配 block 数 |
| block_allocate_failures | Counter | KVCache block 分配失败次数 |
| engine:memory:total_gb | Gauge | NPUWorker 初始化时设备总显存，单位 GiB |
| engine:memory:utilization_ratio | Gauge | vLLM 配置的显存使用比例 |
| engine:memory:reserved_gb | Gauge | vLLM 按显存使用比例预留的显存，单位 GiB |
| engine:memory:weights_gb | Gauge | 模型权重占用显存，单位 GiB |
| engine:memory:kvcache_gb | Gauge | 可用于 KVCache 的显存，单位 GiB |
| engine:memory:non_torch_gb | Gauge | 非 PyTorch 组件占用显存，单位 GiB |
| engine:memory:activation_gb | Gauge | Profile 过程中峰值 activation 显存，单位 GiB |
| engine:memory:graph_gb | Gauge | NPU Graph 占用显存，单位 GiB |
| engine:memory:torch_reserved_gb | Gauge | vllm-ascend 运行态 PyTorch reserved 显存，单位 GiB |
| engine:memory:torch_allocated_gb | Gauge | vllm-ascend 运行态 PyTorch allocated 显存，单位 GiB |

### 引擎、执行器与 NPU 耗时

| 指标名称 | 类型 | 说明 |
|----------|------|------|
| engine:async_add_request:duration | Histogram | AsyncLLM 添加请求的耗时 |
| engine:generate:duration | Histogram | AsyncLLM.generate 端到端生成耗时 |
| engine:tokenizer_encode | Histogram | 输入处理与 tokenizer encode 耗时 |
| async_llm:record_stats:duration | Histogram | AsyncLLM 记录 stats 的耗时 |
| async_llm:abort_requests:duration | Histogram | AsyncLLM 中止请求的耗时 |
| output_processor_duration | Histogram | OutputProcessor 处理输出的耗时 |
| engine_core_outputs_len | Histogram | OutputProcessor 单次处理的 engine core 输出数量 |
| engine_core:process_input_queue:duration | Histogram | EngineCore 处理输入队列的耗时 |
| engine_core:process_engine_step:duration | Histogram | EngineCore 处理 engine step 的耗时 |
| engine_core:engine_core_step:duration | Histogram | EngineCore 单步执行耗时 |
| executor:execute_model:duration | Histogram | MultiprocExecutor 执行模型的耗时 |
| executor:model_runner_execute_model:duration | Histogram | NPUModelRunner.execute_model 执行耗时 |
| executor:prepare_inputs:duration | Histogram | NPUModelRunner 准备输入的耗时 |
| executor:sample_tokens:duration | Histogram | MultiprocExecutor.sample_tokens 采样耗时 |
| worker:model_runner_get_output:duration | Histogram | ModelRunnerOutput.get_output 耗时 |
| record_function_or_nullcontext | Histogram | vLLM/vLLM-Ascend 内部 record function 片段耗时 |
| npu:forward_duration | Histogram | Forward 阶段耗时 |
| npu:kernel_launch | Histogram | Forward 到 post process 之间的 kernel launch 相关耗时 |
| npu:non_forward_duration | Histogram | ModelRunner 输出后到本轮结束之间的非 forward 耗时 |

### 异常状态与 EPLB

| 指标名称 | 类型 | 说明 |
|----------|------|------|
| running_to_waiting_count | Counter | 请求从 running 队列回退到 waiting 队列的次数 |
| request_prefill_pending_nums | Counter | running 队列满且 waiting/skipped_waiting 中仍有请求时的 pending 累计次数 |
| rpc_errors | Counter | MultiprocExecutor.collective_rpc 异常次数 |
| health_check_failed | Counter | `/health` 检查失败、返回 503 或 EngineDeadError 的次数 |
| eplb:expert_hotness:current_mean | Gauge | EPLB 更新前专家热点均值 |
| eplb:expert_hotness:current_max | Gauge | EPLB 更新前专家热点最大值 |
| eplb:expert_hotness:update_mean | Gauge | EPLB 更新后专家热点均值 |
| eplb:expert_hotness:update_max | Gauge | EPLB 更新后专家热点最大值 |
| eplb:expert_hotness:imbalance | Gauge | EPLB 各层专家热点失衡度 |
| eplb:expert_weight_update:duration | Histogram | EPLB 专家映射与权重更新总耗时 |
| eplb:expert_map_update:duration | Histogram | EPLB 专家映射更新耗时 |
| eplb:log2phy_map_update:duration | Histogram | EPLB 逻辑到物理映射更新耗时 |
| eplb:expert_weight_replace:duration | Histogram | EPLB 专家权重替换耗时 |

## 配置

用户可以自定义需要采集的内容，可以通过：MS_SERVICE_METRIC_VLLM_CONFIG 环境变量指定yaml 文件。如果不指定，默认使用内部的采集配置

### 配置文件格式

创建 YAML 配置文件：

```yaml
# 使用默认 timer handler
- symbol: my_module:MyClass.my_method
  metrics:
    - name: my_method_duration
      type: timer
      labels:
        - name: method
          expr: "ret.method"  # 属性访问

# 使用 counter 统计列表长度
- symbol: my_module:process_batch
  metrics:
    - name: batch_size
      type: counter
      expr: "len(items)"  # 函数调用

# 使用 gauge 记录数值
- symbol: my_module:get_queue_length
  metrics:
    - name: queue_length
      type: gauge
      expr: "queue.size"  # 属性访问

# 使用 histogram 统计耗时分布
- symbol: my_module:process_data
  metrics:
    - name: processing_time
      type: histogram
      expr: "duration"  # 内置变量：执行耗时（秒）
      buckets: [0.001, 0.01, 0.1, 1.0, 10.0]

# 使用自定义 handler（指定 handler 时一般不需要配置 metrics）
- symbol: my_module:complex_process
  handler: my_handlers:custom_handler
```

### 配置项说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| symbol | string | 是 | 目标符号路径，格式：`module.path:ClassName.method_name` |
| handler | string | 否 | 自定义 handler 路径，格式：`module.path:function_name`。指定 handler 时一般不需要配置 metrics |
| min_version | string | 否 | 最小版本要求 |
| max_version | string | 否 | 最大版本要求 |
| metrics | list | 否 | 指标配置列表（使用默认 handler 时配置）|

### Metrics 配置

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 指标名称 |
| type | string | 是 | 指标类型：timer/counter/gauge/histogram |
| expr | string | 否 | 表达式（非 timer 类型必填） |
| labels | list | 否 | 标签配置 |
| buckets | list | 否 | 直方图分桶（histogram 类型） |

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| MS_SERVICE_METRIC_CONFIG_PATH | 配置文件路径 | 无 |
| MS_SERVICE_METRIC_SHM_PREFIX | 共享内存前缀 | /ms_service_metric |
| MS_SERVICE_METRIC_MAX_PROCS | 最大进程数 | 1000 |
| PROMETHEUS_MULTIPROC_DIR | 多进程指标目录 | 无 |

### Framework Metric Provider

与框架实现强相关的 YAML 和 Handler 可以由框架仓通过 Python Entry Point
提供。Core 只负责发现、校验、合并、Hook 和指标上报，不反向依赖框架实现。

```mermaid
flowchart LR
    A["ms_service_metric Core"] --> B["发现 Entry Point"]
    B --> C["校验 YAML、symbol 归属、Handler"]
    C --> D{"Provider 可激活?"}
    D -- "否" --> E["保留 Core/Adapter 兜底配置"]
    D -- "是，Overlay" --> F["仅覆盖 Provider 已声明的 symbol"]
    D -- "是，Exclusive" --> I["过滤所属前缀后加载 Provider symbol"]
    F --> G["合并用户覆盖配置"]
    I --> G
    E --> G
    G --> H["构造 Handler 后应用 Hook"]
```

#### Provider 声明

框架仓只从稳定接口 `ms_service_metric.provider_api` 导入类型：

```python
from pathlib import Path

from ms_service_metric.provider_api import MetricProvider


def get_metric_provider():
    config_dir = Path(__file__).with_name("config")
    return MetricProvider(
        name="vllm-ascend",
        config_paths=tuple(
            str(path) for path in sorted(config_dir.glob("*.yaml"))
        ),
        priority=200,
        framework_package="vllm_ascend",
        owned_symbol_prefixes=("vllm_ascend.",),
        handler_module_prefixes=(
            "vllm_ascend.observability.ms_metrics.",
        ),
    )
```

`config_paths` 支持多个文件。目录扫描由 Provider 自己完成，Core 接收确定、有序的
文件列表，因此框架仓可以按 `scheduler.yaml`、`worker.yaml`、`eplb.yaml` 拆分配置，
也不会把临时文件或非 YAML 文件误加载。

`framework_package` 仅在 YAML 使用 `min_version`/`max_version` 时提供当前框架版本，
不是 Core 与 Provider 的接口版本握手，也不会限制两个仓的发布顺序。

在框架仓注册 Python Entry Point。`setup.py` 示例：

```python
entry_points={
    "ms_service_metric.providers": [
        "vllm-ascend = "
        "vllm_ascend.observability.ms_metrics:get_metric_provider",
    ],
}
```

`pyproject.toml` 的等价写法：

```toml
[project.entry-points."ms_service_metric.providers"]
"vllm-ascend" = "vllm_ascend.observability.ms_metrics:get_metric_provider"
```

#### 激活与合并规则

Provider 不是“被发现就接管”，而是在以下检查全部通过后才成为 Active Provider：

1. Entry Point 可加载，Provider 声明结构合法，`ownership_mode` 为 `overlay` 或
   `exclusive`；未声明时默认为 `overlay`。
2. 所有 `config_paths` 都是可读取的非空 YAML 文件；Provider 配置采用严格解析，
   任一坏条目都会使整个 Provider 回退。
3. Provider 必须显式声明非空的 `owned_symbol_prefixes`，且 YAML 中的 symbol 均属于
   所声明的前缀。
4. Handler 只能来自 `ms_service_metric.provider_handlers`、
   `ms_service_metric.handlers` 或 Provider 声明的 `handler_module_prefixes`；
   稳定 Handler 名称必须存在，Provider 自有 Handler 必须可成功导入。
5. 多个 Overlay Provider 可以按优先级贡献配置；只要重叠范围内存在 Exclusive
   Provider，就视为所有权冲突，冲突双方都不接管。

Overlay 是迁移期默认模式：Provider 只覆盖自己已经提供的 symbol，未迁移的 symbol
继续使用 Core/Adapter 兜底配置。同一个 symbol 是原子迁移单元，Provider YAML 必须写出
该 symbol 最终需要保留的全部 Handler，避免新旧自定义 Handler 同时执行导致重复上报。

Exclusive 用于迁移完成后的完整接管：只有 Active Exclusive Provider 的
`owned_symbol_prefixes` 才会过滤 Core/Adapter 中的兜底点位。Provider 任一检查失败时，
该 Provider 整体跳过，兜底配置继续生效，不影响推理主流程。

最终优先级为：

1. Core 默认配置。
2. Adapter 内置兼容配置。
3. Active Provider 配置。
4. `MS_SERVICE_METRIC_VLLM_CONFIG` 指向的框架用户配置。
5. `MS_SERVICE_METRIC_CONFIG_PATH` 指向的全局用户配置。

Core 默认配置和 Adapter 内置配置按 symbol 合并；Provider 和用户配置按 symbol
执行整体覆盖。Provider 的多个 YAML 文件内部仍按 symbol 合并，运行语义相同的 Handler
配置（包括“省略默认值”和“显式写出默认值”）按内部指纹自动去重，不需要也不建议在
YAML 增加 `id`。同一 symbol、同一 Handler 但 metrics 或 labels 不同的配置会生成
不同的内部指纹，可以同时生效；多个 Handler 的应用顺序保持配置文件中的声明顺序。

#### Core 与 Provider 边界

- Core 保留 Hook、配置模型、Prometheus 上报、通用 DP/PD/role 元数据逻辑和通用 Handler。
- Provider 保留框架 symbol、版本范围、框架私有计算和业务 Handler。
- Provider YAML 引用 Core 通用 Handler 时使用稳定门面
  `ms_service_metric.provider_handlers`，不要引用 `adapters.*` 等内部路径。
- Provider 自定义 Handler 只从 `ms_service_metric.provider_api` 获取稳定的指标写入接口。
- Provider 声明函数和 Handler 模块导入应无副作用，不得在导入阶段修改推理状态。
- 公共 Handler 门面采用惰性导入，`metric off` 时发现 Provider 不会提前注册指标。

#### 重载与兼容

执行 `metric on` 或 `metric restart` 时会重新发现 Provider 并重新读取 YAML。重载先
完整构造候选 Handler，再停止现有 Hook；配置或 Handler 构造失败时保留原有 Hook 状态。
已导入的 Python 模块不会热重载，因此修改 YAML 后可通过 `metric restart` 生效，修改
Handler Python 代码仍需重启服务进程。

兼容策略如下：

| 组合 | 行为 |
|------|------|
| 新 Core + 无框架 Provider | 无 Provider，全部使用 Core/Adapter 兜底配置 |
| 新 Core + 部分框架 Provider | Overlay 覆盖已迁移 symbol，未迁移 symbol 继续兜底 |
| 新 Core + 完整框架 Provider | 先以 Overlay 验证，之后可切换 Exclusive 完整接管 |
| 新 Core + 旧框架 | 无 Provider，继续使用 Adapter 兜底配置 |
| 旧 Core + 新框架 | 旧 Core 不发现该 Entry Point，框架原有逻辑不受影响 |
| Provider 激活失败 | 跳过 Provider，继续使用 Core/Adapter 兜底 |

当前阶段只完成 Provider 架构和 vLLM-Ascend 穿刺，不包含 SGLang Provider 适配。

## Handler 类型

### Wrap Handler

包装函数类型，需要手动调用原函数：

```python
def my_wrap_handler(ori_func, *args, **kwargs):
    # 前置处理
    start_time = time.time()

    # 调用原函数
    result = ori_func(*args, **kwargs)

    # 后置处理
    duration = time.time() - start_time
    print(f"Duration: {duration}")

    return result
```

### Context Handler

上下文管理器类型，使用 yield 控制执行流程。只要使用 context handler，就会自动访问局部变量：

```python
def context_handler(ctx):
    # ctx: FunctionContext 对象
    # ctx.return_value: 返回值（yield 后可用）
    # ctx.locals: 函数的 locals 字典

    # 前置处理
    start_time = time.time()
    print(f"Locals before: {ctx.locals}")

    yield  # 原函数在这里执行

    # 后置处理
    duration = time.time() - start_time
    print(f"Duration: {duration}")
    print(f"Result: {ctx.return_value}")
    print(f"Locals after: {ctx.locals}")
```

**默认 Handler：** 根据配置中是否存在 `expr` 字段自动决定 handler 类型：

- 有 `expr`：创建 context handler（可访问 locals）
- 无 `expr`：创建 wrap handler

**配置示例：**

```yaml
# 使用自定义 context handler（在 handler 中自行处理指标）
- symbol: my_module:complex_function
  handler: my_handlers:context_handler

# 使用默认 handler（有 expr，自动创建 context handler）
- symbol: my_module:another_function
  metrics:
    - name: item_count
      type: counter
      expr: "len(items)"  # items 是函数内的局部变量
```

## 多 Handler 组合

同一个 symbol 可以配置多个 handler，按洋葱模型执行：

```yaml
- symbol: my_module:process
  handler: handlers:auth_check
- symbol: my_module:process
  handler: handlers:timing
  metrics:
    - name: process_duration
      type: timer
```

执行顺序：`auth_check -> timing -> 原函数 -> timing -> auth_check`

## 框架适配

### vLLM

通过 entry_points 自动适配，安装后即可使用，无需额外代码。

### SGLang（示例参考）

> **注意**: SGLang 适配器仅作为示例参考，不作为正式发布功能。

```python
from ms_service_metric.adapters.sglang import initialize_sglang_metric

# 初始化
initialize_sglang_metric()
```

### 自定义适配器

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

## 开发

### 安装开发依赖

```bash
pip install -e ".[dev]"
```

### 运行测试

```bash
pytest tests/
```

### 代码风格

```bash
black ms_service_metric/
flake8 ms_service_metric/
```

## 架构

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

## 安全风险

Metric 数据监测利用了 vllm 的 metric 功能对外提供接口，[详细参考](https://github.com/vllm-project/vllm/tree/main/examples/observability/prometheus_grafana)。如接入 Prometheus 或 Grafana，请注意其均为第三方开源软件，不属于 MindStudio 产品发布包的组成部分，也不是本工具强制要求用户使用的唯一可视化方案。用户可根据自身环境选择兼容的监控、可视化系统；如使用 Prometheus，请使用其官方维护的安全版本，并结合实际部署环境完成访问控制、网络隔离、权限配置等安全加固。

## 许可证

木兰宽松许可证第2版 (Mulan PSL v2)

## 贡献

欢迎提交 Issue 和 Pull Request。
