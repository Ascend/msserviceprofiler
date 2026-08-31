# vLLM 服务化 Prometheus 数据监测工具使用指南

## 简介

vLLM 服务化 Prometheus 数据监测工具用于增强 vLLM-Ascend 推理服务框架的原生监测能力。在 vLLM-Ascend 原生 metrics 基础上，本工具新增以下监测能力：

- **KVCache 监测**：各 DP 域的 block 总数、空闲数、已分配数
- **Token 与吞吐**：各 DP 域的 请求输入/输出 token 数量、总 token 数
- **自定义指标**：支持对任意函数执行时长添加 timer 类型指标

## 产品支持情况

> [!NOTE]
>
>昇腾产品的具体型号，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》

|产品类型| 是否支持 |
|--|:----:|
|昇腾950PR&昇腾950DT系列产品|√|
|昇腾A3系列产品|√|
|昇腾A2系列产品|√|
|昇腾310B系列产品|√|
|昇腾310P系列产品|√|
|昇腾910系列产品|×|

## 使用前准备

### 环境准备

1. 在昇腾环境安装配套版本的CANN Toolkit开发套件包和ops算子包并配置CANN环境变量，具体请参见[CANN快速安装](https://www.hiascend.com/cann/download)。
2. 完成 vLLM 和 vLLM-Ascend 的安装和配置并确认 vLLM-Ascend 可以正常运行，metrics端口正常推送数据，具体请参见 [vLLM-Ascend installation](https://vllm-ascend.readthedocs.io/en/latest/installation.html)。

### 约束

- **版本配套**：请确保 vLLM-Ascend、CANN 和采集工具的版本配套关系符合附录中的要求。
- **资源占用**：数据监测必须开启 **Prometheus 多进程模式**（`PROMETHEUS_MULTIPROC_DIR`）。指标采集会增加运行开销，正式使用前应在固定负载下测量采集开启前后的性能差异。
- **功能限制**：部分高级功能需要特定版本的 vLLM-Ascend 框架支持。

### 第三方可视化工具说明

Grafana 与 Prometheus 为第三方开源软件，不属于 MindStudio Service Profiler 或 MindStudio 产品发布包的组成部分，也不是本工具强制要求用户使用的唯一可视化方案。用户可根据自身环境选择 Grafana、Prometheus 或其他兼容的监控、可视化系统。

如选择使用 Prometheus，请使用其官方维护的安全版本，并结合实际部署环境完成访问控制、网络隔离、权限配置等安全加固。

## 使用说明

### 安装

```bash
pip install ms_service_metric
```

```bash
# 本地安装（不推荐，仅建议开发时使用）
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler/ms_service_metric
pip install -e .
```

### 快速开始

按以下顺序操作即可完成指标监测的完整流程：

1. **设置环境变量并启动服务**（含 Prometheus 多进程模式）
2. **开启采集**
3. **发送推理请求**
4. **查看指标**（访问 metrics 端口或接入 Grafana）

### 步骤 1：设置环境变量并启动服务

在启动推理服务前，需设置以下环境变量：

| 环境变量 | 说明 |
|----------|------|
| `MS_SERVICE_METRIC_VLLM_CONFIG` | 符号/埋点配置文件路径（可选，不设置则使用默认配置） |
| `PROMETHEUS_MULTIPROC_DIR` | Prometheus 多进程模式目录（**必填**，需预先创建空目录） |

```bash
# 可选，不设置则使用默认配置
cd ${path_to_store_config_files}
export MS_SERVICE_METRIC_VLLM_CONFIG=service_metrics_symbols.yaml

# 开启 Prometheus 多进程模式（必填）
export PROMETHEUS_MULTIPROC_DIR=/dev/shm/vllm_metrics  # /path/to/your/prometheus/dir
mkdir -p $PROMETHEUS_MULTIPROC_DIR

# 启动 vLLM 服务
vllm serve Qwen/Qwen2.5-0.5B-Instruct &
```

- `service_metrics_symbols.yaml` 为埋点配置，自定义点位请参考[点位配置使用指南](#点位配置使用指南)。
- 8000为vLLM服务化推理启动的默认端口，本文档说明以默认8000端口为例。如需修改服务化启动端口，可在启动 vLLM 服务时通过--port命令行参数指定。更多详细说明可参考[vllm serve命令行参数说明](https://docs.vllm.com.cn/en/latest/cli/serve/#arguments)。

### 步骤 2：开启采集

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

### 步骤 3：发送请求

发送推理请求以产生监测数据：

```bash
curl http://localhost:8000/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "Qwen/Qwen2.5-0.5B-Instruct",
        "prompt": "Beijing is a",
        "max_tokens": 5,
        "temperature": 0
}' | python3 -m json.tool
```

### 步骤 4：查看指标

通过 vLLM 服务的 metrics 端口获取数据：

```bash
# localhost:8000请替换为服务化运行IP和端口
curl -s http://localhost:8000/metrics
```

也可将 Prometheus 配置为该端口进行抓取，并接入 Grafana 或其他兼容工具进行可视化。

## 点位配置使用指南

### 功能说明

点位配置文件用于定义需要采集的函数/方法，支持灵活配置与自定义属性采集。

### 注意事项

- 采集点位有更新时，可以通过 `ms-service-metric restart` 重新加载配置。
- 所有自定义指标名会自动添加 `vllm_profiling_` 前缀，且须符合 [Prometheus 指标命名规范](https://prometheus.io/docs/practices/naming/)。

### 配置字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| symbol | Python 导入路径 + 属性链（格式：`模块:类.方法`） | `vllm.v1.core.kv_cache_manager:KVCacheManager.free` |
| min_version | 最低版本约束 | `"0.9.1"` |
| max_version | 最高版本约束 | `"0.11.0"` |
| metrics | 自定义 metric 列表，当前支持 `timer` 类型（采集函数执行时长） | 见下方示例 |

### 配置示例

```yaml
# ===== Custom Metrics =====
- symbol: vllm.entrypoints.openai.serving_chat:OpenAIServingChat.create_chat_completion
  min_version: "0.9.1"
  metrics:
    - name: server:create_chat_completion:duration
      type: timer
```

## 结果说明

### 结果示例

访问 vLLM 服务的 metrics 端口（如 `http://localhost:8000/metrics`）可查看当前监测指标。以下为自定义 `server:create_chat_completion:duration`（timer 类型）的示例输出，可接入 Grafana 等可视化工具进行展示：

```bash
# localhost:8000请替换为服务化运行IP和端口
curl -s http://localhost:8000/metrics | grep -E "server:create_chat_completion:duration"
```

```ColdFusion
# HELP vllm_profiling_server:create_chat_completion:duration Execution duration of server:create_chat_completion:duration
# TYPE vllm_profiling_server:create_chat_completion:duration histogram
vllm_profiling_server:create_chat_completion:duration_sum{dp="-1"} 15.44140076637268
vllm_profiling_server:create_chat_completion:duration_bucket{dp="-1",le="0.001"} 0.0
...
vllm_profiling_server:create_chat_completion:duration_bucket{dp="-1",le="0.2"} 1.0
...
vllm_profiling_server:create_chat_completion:duration_bucket{dp="-1",le="+Inf"} 9.0
vllm_profiling_server:create_chat_completion:duration_count{dp="-1"} 9.0
```

### 内置指标点位说明

以下为工具默认配置中的内置 metrics 点位。所有指标名前会自动添加 `vllm_profiling_` 前缀，且默认包含 `dp` 标签（调度进程为实际 DP 域 ID，请求进程为 `-1`）。部分指标还包含额外标签，例如 `engine`、`req_phase`、`role`、`name`、`rank`、`phase`、`layer`、`threshold`、`exception_type`。

#### 调度与批处理类

| 指标名称 | 类型 | 标签 | 说明 |
|----------|------|------|------|
| batch_size | Histogram | engine | 当前正在执行的请求数量 |
| waiting_batch_size | Histogram | engine | 当前等待调度的请求数量 |
| num_spec_tokens | Histogram | engine | 投机解码中的草稿 token 数量 |
| scheduler:duration | Histogram | - | 单次 `Scheduler.schedule` 调度耗时 |
| scheduler:batch_size | Histogram | - | 单次调度输出的请求数量 |
| scheduler:running_queue_size | Histogram | - | 调度后 running 队列中的请求数量 |
| scheduler:seqlen:avg | Gauge | - | 单次调度批次内平均序列长度 |
| scheduler:seqlen:sum | Gauge | - | 单次调度批次内序列长度总和 |
| scheduler:phase_batch_size | Histogram | req_phase | 单次调度中 prefill、decode、mixed 等阶段的请求数量 |
| scheduler:phase_scheduled_tokens | Histogram | req_phase | 单次调度中各请求阶段的调度 token 数量 |
| scheduler:phase_scheduled_token_counter | Counter | req_phase | 各请求阶段累计调度 token 数量 |
| running_phase_batch_size | Histogram | req_phase | running 队列中各请求阶段的请求数量 |
| waiting_phase_batch_size | Histogram | req_phase | waiting 队列中各请求阶段的请求数量 |
| scheduler:add_request:duration | Histogram | - | 请求加入调度 waiting 队列的耗时 |
| scheduler:update_from_output:duration | Histogram | phase | Scheduler 处理模型输出并更新状态的耗时 |
| scheduler:recompute_events | Counter | - | 重计算触发次数 |

#### Token 与慢请求类

| 指标名称 | 类型 | 标签 | 说明 |
|----------|------|------|------|
| total_tokens | Histogram | engine | 单次迭代中 prompt token 与 generation token 之和 |
| input | Histogram | engine | 输入 prompt 的 token 数量 |
| output | Histogram | engine | 输出生成结果的 token 数量 |
| second_token_latency | Histogram | - | 第二个 token 的生成延迟 |
| fine_grained_ttft | Histogram | engine | 细粒度首 token 延迟（TTFT） |
| fine_grained_tpot | Histogram | engine | 细粒度每 token 平均耗时（TPOT） |
| decode_over_1s_count | Counter | - | Decode 阶段单 token 间隔超过 1s 的累计次数 |
| prefill_over_threshold_count | Counter | threshold | Prefill 首 token 延迟超过 5s、10s、20s 阈值的累计次数 |

#### KVCache 与显存类

| 指标名称 | 类型 | 标签 | 说明 |
|----------|------|------|------|
| total_kvcache_blocks | Gauge | - | 当前 DP 域 KVCache block 总数 |
| free_kvcache_blocks | Gauge | - | 当前 DP 域 KVCache 空闲 block 数 |
| allocated_kvcache_blocks | Gauge | - | 当前 DP 域 KVCache 已分配 block 数 |
| block_allocate_failures | Counter | - | KVCache block 分配失败次数 |
| engine:memory:total_gb | Gauge | - | NPUWorker 初始化时设备总显存，单位 GiB |
| engine:memory:utilization_ratio | Gauge | - | vLLM 配置的显存使用比例 |
| engine:memory:reserved_gb | Gauge | - | vLLM 按显存使用比例预留的显存，单位 GiB |
| engine:memory:weights_gb | Gauge | - | 模型权重占用显存，单位 GiB |
| engine:memory:kvcache_gb | Gauge | - | 可用于 KVCache 的显存，单位 GiB |
| engine:memory:non_torch_gb | Gauge | - | 非 PyTorch 组件占用显存，单位 GiB |
| engine:memory:activation_gb | Gauge | - | Profile 过程中峰值 activation 显存，单位 GiB |
| engine:memory:graph_gb | Gauge | - | NPU Graph 占用显存，单位 GiB |
| engine:memory:torch_reserved_gb | Gauge | - | vllm-ascend 运行态 PyTorch reserved 显存，单位 GiB |
| engine:memory:torch_allocated_gb | Gauge | - | vllm-ascend 运行态 PyTorch allocated 显存，单位 GiB |

>[!NOTE]
>
>KVCache 使用率可近似计算为 `(1 - free_kvcache_blocks / total_kvcache_blocks) * 100%`，用于监测显存占用与负载均衡。`engine:memory:torch_reserved_gb` 和 `engine:memory:torch_allocated_gb` 为运行态显存指标，其余 `engine:memory:*` 指标为 Worker 初始化后的静态显存快照，通常每个进程只记录一次。

#### 引擎与端到端耗时类

| 指标名称 | 类型 | 标签 | 说明 |
|----------|------|------|------|
| engine:async_add_request:duration | Histogram | - | AsyncLLM 添加请求的耗时 |
| engine:generate:duration | Histogram | - | AsyncLLM.generate 端到端生成耗时 |
| engine:tokenizer_encode | Histogram | - | 输入处理与 tokenizer encode 耗时 |
| async_llm:record_stats:duration | Histogram | phase | AsyncLLM 记录 stats 的耗时 |
| async_llm:abort_requests:duration | Histogram | phase | AsyncLLM 中止请求的耗时 |
| output_processor_duration | Histogram | phase | OutputProcessor 处理输出的耗时 |
| engine_core_outputs_len | Histogram | phase | OutputProcessor 单次处理的 engine core 输出数量 |
| engine_core:process_input_queue:duration | Histogram | phase | EngineCore 处理输入队列的耗时 |
| engine_core:process_engine_step:duration | Histogram | phase | EngineCore 处理 engine step 的耗时 |
| engine_core:engine_core_step:duration | Histogram | phase | EngineCore 单步执行耗时 |
| server:create_chat_completion:duration | Histogram | - | OpenAI Chat Completion 请求处理耗时 |

#### 执行器与 NPU 阶段耗时类

| 指标名称 | 类型 | 标签 | 说明 |
|----------|------|------|------|
| executor:execute_model:duration | Histogram | phase | MultiprocExecutor 执行模型的耗时 |
| executor:model_runner_execute_model:duration | Histogram | phase | NPUModelRunner.execute_model 执行耗时 |
| executor:prepare_inputs:duration | Histogram | phase | NPUModelRunner 准备输入的耗时 |
| executor:sample_tokens:duration | Histogram | phase | MultiprocExecutor.sample_tokens 采样耗时 |
| worker:model_runner_get_output:duration | Histogram | - | ModelRunnerOutput.get_output 耗时 |
| record_function_or_nullcontext | Histogram | name、phase、role | vLLM/vLLM-Ascend 内部 record function 片段耗时，`name` 表示片段名称 |
| npu:forward_duration | Histogram | - | Forward 阶段耗时 |
| npu:kernel_launch | Histogram | - | Forward 到 post process 之间的 kernel launch 相关耗时 |
| npu:non_forward_duration | Histogram | - | ModelRunner 输出后到本轮结束之间的非 forward 耗时 |

#### 异常状态类

| 指标名称 | 类型 | 标签 | 说明 |
|----------|------|------|------|
| running_to_waiting_count | Counter | - | 请求从 running 队列回退到 waiting 队列的次数 |
| request_prefill_pending_nums | Counter | - | running 队列满且 waiting/skipped_waiting 中仍有请求时的 pending 累计次数 |
| rpc_errors | Counter | exception_type | MultiprocExecutor.collective_rpc 异常次数 |
| health_check_failed | Counter | - | `/health` 检查失败、返回 503 或 EngineDeadError 的次数 |

#### EPLB 类

| 指标名称 | 类型 | 标签 | 说明 |
|----------|------|------|------|
| eplb:expert_hotness:current_mean | Gauge | rank | EPLB 更新前专家热点均值 |
| eplb:expert_hotness:current_max | Gauge | rank | EPLB 更新前专家热点最大值 |
| eplb:expert_hotness:update_mean | Gauge | rank | EPLB 更新后专家热点均值 |
| eplb:expert_hotness:update_max | Gauge | rank | EPLB 更新后专家热点最大值 |
| eplb:expert_hotness:imbalance | Gauge | rank、phase、layer | EPLB 各层专家热点失衡度，`phase` 为 current 或 update |
| eplb:expert_weight_update:duration | Histogram | - | EPLB 专家映射与权重更新总耗时 |
| eplb:expert_map_update:duration | Histogram | - | EPLB 专家映射更新耗时 |
| eplb:log2phy_map_update:duration | Histogram | - | EPLB 逻辑到物理映射更新耗时 |
| eplb:expert_weight_replace:duration | Histogram | - | EPLB 专家权重替换耗时 |

## 指标分析方法

### 分析顺序

性能分析按“业务 SLO、调度与容量、模型执行、异常状态”的顺序展开：

1. 使用 `fine_grained_ttft`、`fine_grained_tpot` 和 `engine:generate:duration` 确认异常影响首 Token、后续 Token 还是引擎生成过程；压测客户端端到端时延单独记录，不能与服务端引擎耗时混用。
2. 使用 `waiting_batch_size`、`batch_size` 和 `scheduler:duration` 判断请求是否堵塞在调度阶段。
3. 使用 `free_kvcache_blocks`、`allocated_kvcache_blocks`、`block_allocate_failures`、`running_to_waiting_count` 判断 KVCache 是否限制请求进入执行阶段。
4. 使用 `executor:execute_model:duration`、`executor:model_runner_execute_model:duration` 和 `npu:forward_duration` 判断模型执行是否变慢。
5. 使用 `output_processor_duration`、`rpc_errors` 和 `health_check_failed` 排查输出处理和异常路径。
6. 按 `instance`、`dp`、`phase`、`rank` 拆分结果，区分全局问题与局部热点。

所有对比必须使用相同模型、版本、输入/输出 Token 分布、并发和服务参数。异常判断以同负载正常窗口为基线，连续采集点形成的趋势才作为诊断证据。

### 按指标类型查询

| 类型 | 正确用法 | 说明 |
|---|---|---|
| Gauge | 直接查看当前值、范围和实例差异 | 适用于 KVCache Block、显存等状态量 |
| Counter | 使用 `rate()` 查看速率，使用 `increase()` 查看窗口增量 | 进程重启会使 Counter 归零 |
| Histogram | 使用 `_bucket` 计算分位数，使用 `_sum/_count` 计算平均值 | 计算分位数时必须保留 `le` 标签 |

以下 PromQL 使用实际导出的 `vllm_profiling_` 前缀。查询窗口可按抓取间隔和压测时长调整。

调度耗时 P99：

```promql
histogram_quantile(
  0.99,
  sum by (le, instance, dp) (
    rate(vllm_profiling_scheduler:duration_bucket[5m])
  )
)
```

模型执行平均耗时：

```promql
sum by (instance, dp, phase) (
  rate(vllm_profiling_executor:execute_model:duration_sum[5m])
)
/
sum by (instance, dp, phase) (
  rate(vllm_profiling_executor:execute_model:duration_count[5m])
)
```

KVCache 使用率：

```promql
100 * (
  1 -
  vllm_profiling_free_kvcache_blocks
  /
  vllm_profiling_total_kvcache_blocks
)
```

KVCache 分配失败增量：

```promql
sum by (instance, dp) (
  increase(vllm_profiling_block_allocate_failures_total[5m])
)
```

调度重计算增量：

```promql
sum by (instance, dp) (
  increase(vllm_profiling_scheduler:recompute_events_total[5m])
)
```

投机推理接受率：

```promql
sum by (instance, role) (
  rate(vllm:spec_decode_num_accepted_tokens_total[5m])
)
/
clamp_min(
  sum by (instance, role) (
    rate(vllm:spec_decode_num_draft_tokens_total[5m])
  ),
  1e-9
)
```

投机推理接受率使用 vLLM 原生 Counter，含义为窗口内被接受的草稿 Token 数除以草稿 Token 总数。保留实例维度，分母没有增量的窗口不参与比较。

### 指标组合与定界结论

| 指标组合 | 定界结论 | Tracing 检查项 |
|---|---|---|
| TTFT 升高；waiting 升高；模型执行耗时稳定 | 耗时增加在模型执行之前 | 调度 Span、调度到模型执行之间的空白 |
| waiting 升高；scheduler P99 升高；NPU 利用率低；model 耗时稳定 | 调度或 Host 路径形成瓶颈 | `vllm.scheduler.schedule` 与 model Span 的差值 |
| free blocks 持续低位；分配失败增加；waiting 与 TTFT 同步升高 | KVCache 容量限制请求调度 | 请求关联、调度后等待区间、相同 Token 规模的对照 Trace |
| 投机推理接受率下降；TPOT 或输出 Token 吞吐劣化；草稿 Token 规模稳定 | 草稿 Token 有效产出下降 | Tracing 仅用于排除调度、执行和输出阶段，接受率由 Counter 或 Profiler 确认 |
| TPOT 升高；execute model 与 forward 同步升高；scheduler 稳定 | 模型执行阶段变慢 | `vllm.model.execute`、`vllm_ascend.model_runner.execute` |
| execute model 升高；model runner 稳定 | Executor 外围开销增加 | IPC、同步、数据准备和 Span 间空白 |
| output processor 升高；model 稳定 | 输出处理阶段变慢 | `vllm.output.process` |
| 只有部分 dp/rank 异常 | 局部负载或资源不均 | 对比异常与正常 dp/rank 的请求和 Token 规模 |

单个指标不直接作为根因。结论至少包含一个 SLO 指标、一个阶段指标和一个容量或执行指标，并要求这些指标在同一时间窗口形成一致变化。

### 可选：从 Metrics 下钻到 Tracing

Metrics 已经能够形成阶段或容量结论时，可以直接进入处理和复测；需要查看具体请求路径时，再按以下步骤关联 Tracing：

1. 在 Grafana 中记录异常开始时间、结束时间、实例、DP 域和请求阶段。
2. 在 Jaeger 中选择覆盖该时间窗口的 Lookback，限定相同服务。
3. 选择相同 Token 规模和请求阶段的正常、异常观测组。
4. 使用 `request.id`、`request.ids`、Trace ID 和 Span Links 确认请求与 Batch 的关联。
5. 对比 scheduler、model、model runner 和 output Span；只有同一 Trace ID 或统一 Perfetto Timeline 才计算 Span 间空白。

完整流程参见[《vLLM-Ascend 可观测性性能诊断指南》](./vllm_ascend_observability_analysis_guide.md)。

## 相关文档

- [vLLM 服务化性能采集工具](./vLLM_service_oriented_performance_collection_tool.md)：性能剖析与 Trace 分析
- [vLLM Hook Tracing 使用指南](./vLLM_hook_tracing_instruct.md)：请求链路分析
- [vLLM-Ascend 可观测性性能诊断指南](./vllm_ascend_observability_analysis_guide.md)：Metrics 与 Tracing 联合分析
- [数据采集配置说明](./msserviceprofiler_serving_tuning_instruct.md#数据采集)：`ms_service_profiler_config.json` 配置详解
