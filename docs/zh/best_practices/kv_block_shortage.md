# 新测评数据集触发 KVCache 容量瓶颈

## 案例背景

更换测评数据集后，推理速度明显下降。首轮排查需要回答两个问题：性能下降发生在请求生命周期的哪个阶段，以及新数据集为什么会触发该阶段的瓶颈。

## 问题现象

更换数据集后，Grafana 中出现以下同窗口变化：

- `fine_grained_ttft` 和 `fine_grained_tpot` 同时劣化。
- waiting 队列持续积压。
- `free_kvcache_blocks` 降至接近 0，KVCache 长时间处于容量下限。
- `scheduler:recompute_events` 持续增加，说明调度器频繁触发请求重计算。

这组信号表明问题不在单次模型计算本身，而在新数据集的请求特征与当前并发共同造成的 KVCache 容量压力。

## 定位过程

### 步骤 1：用 TTFT 和 TPOT 确认影响范围

先对比旧数据集基线和新数据集异常窗口：

- TTFT 反映请求进入后到首个 Token 返回前的等待、调度和 Prefill 开销。
- TPOT 反映进入生成阶段后的单 Token 平均耗时。

TTFT 与 TPOT 同时劣化时，不能只检查模型执行。waiting、KVCache、重计算和模型执行指标必须放在同一时间轴上比较。

### 步骤 2：确认 waiting 与 KVCache 水位同步变化

使用以下查询固定容量证据。查询窗口与压测窗口保持一致，并按部署中的 `instance`、`dp` 等标签拆分。

KVCache 使用率：

```promql
100 * (
  1 -
  vllm_profiling_free_kvcache_blocks
  /
  vllm_profiling_total_kvcache_blocks
)
```

waiting 队列规模使用 `vllm_profiling_waiting_batch_size` 面板查看。若该指标为 Histogram，使用 `_sum / _count` 计算窗口平均值，或使用 `_bucket` 计算分位数，不能直接对累计值下结论。

当 `free_kvcache_blocks` 持续接近 0，并且 waiting 与 TTFT 同步升高时，可以把问题定界到“请求进入执行阶段前受到 KVCache 容量限制”。

### 步骤 3：用重计算计数确认容量压力已经影响调度

`scheduler:recompute_events` 是 Counter，使用窗口增量查看：

```promql
sum by (instance, dp) (
  increase(vllm_profiling_scheduler:recompute_events_total[5m])
)
```

同时查看两个旁证：

```promql
sum by (instance, dp) (
  increase(vllm_profiling_running_to_waiting_count_total[5m])
)
```

```promql
sum by (instance, dp) (
  increase(vllm_profiling_block_allocate_failures_total[5m])
)
```

以下三项在同一时间窗口成立时，KVCache 容量瓶颈的一级定界完成：

1. `free_kvcache_blocks` 持续触及容量下限。
2. waiting 与 TTFT 同步升高。
3. `scheduler:recompute_events`、`running_to_waiting_count` 或 `block_allocate_failures` 出现异常增量。

### 步骤 4：把容量压力追溯到新数据集和并发

复用本案例时，先确认模型、版本、服务参数和部署资源没有同时变化，再按以下字段统计新旧数据集，而不是只比较请求条数：

- 输入 Token 的 P50、P90、P99 和最大值。
- 输出 Token 的 P50、P90、P99 和最大值。
- 单请求总 Token 数以及长上下文请求占比。
- 请求到达方式、单实例并发和稳态 Batch 大小。

KV Block 的消耗由同时驻留的请求数量和请求 Token 数共同决定。数据已经确认新数据集在当前并发下使 KVCache 长时间耗尽，调度器只能让请求等待或将已运行请求回退并重算。因而本案例的根因不是“数据集本身慢”，而是当前并发不再匹配新数据集的 KVCache 需求。历史数据没有保留 Token 分布，不能继续断言是输入长度、输出长度还是长请求占比发生了变化。

### 步骤 5：排除模型执行本身变慢

在相同的 Prefill/Decode 阶段、Batch 和 Token 规模下，对比：

- `executor:execute_model:duration`
- `executor:model_runner_execute_model:duration`
- `npu:forward_duration`

这些指标保持旧数据集基线，而 waiting、KVCache 水位和重计算计数发生异常时，模型执行阶段被排除。若模型执行耗时也升高，需要先按 Token 和 Batch 规模归一化，再判断是否同时存在计算瓶颈。

### 步骤 6：使用 Tracing 与 Profiler 增强请求级证据

Metrics 已经满足步骤 2～5 的组合判断时，可以直接形成 KVCache 容量结论；需要继续定位具体请求、Batch 或模型执行前等待位置时，再执行以下增强分析。

Tracing 验证：

1. 使用 `request.id`、`request.ids` 或 Span Links 确认 scheduler、model 与目标请求的关联。
2. 对比 Token 和 Batch 规模一致的正常、异常观测组。
3. 检查 `vllm.scheduler.schedule`、`vllm.model.execute` 和 `vllm_ascend.model_runner.execute`。
4. 只有 Span 属于同一 Trace ID，或已经进入统一 Perfetto Timeline 时，才计算模型执行前的空白区间。

Profiler 验证：

- `request.csv`：确认 `queue_wait_time(ms)` 和 `first_token_latency(ms)` 的增长集中在哪些请求。
- `batch.csv`：确认 `free_blocks`、`kvcache_usage_rate` 和 `decode_batch_size` 的变化。
- `kvcache.csv`：确认 Block 申请、释放和耗尽发生的 Batch。

Tracing 用于排除模型执行自身变慢，Profiler 用于下钻具体请求和 Batch；KVCache 根因仍由同窗口的水位、waiting 和重计算/回退证据确认。

## 根因结论

新测评数据集在原有并发下产生的 KVCache 需求超过单实例稳定容量。可用 KV Block 长时间接近 0，调度器频繁回退并重计算请求，最终同时推高 waiting、TTFT 和 TPOT。

## 处理方法

本次处理动作是降低单实例并发，使同时驻留请求的 KVCache 总需求回到实例容量以内。

该处理只改变并发，不同时修改模型版本、数据集、KVCache 配置或调度策略。这样才能通过单变量复测验证并发是否为直接触发条件。

其他场景只有在证据对应时才采用以下处理：

- 长上下文请求占比过高：限制最大输入/输出长度，或将长请求路由到 KVCache 容量更大的实例。
- 单实例 Block 总量不足：调整可用于 KVCache 的显存比例，或增加实例和设备资源。
- 实例负载不均：按实例队列和 KVCache 水位分配请求，避免少数实例先耗尽 Block。

## 复测标准

使用同一份新数据集、相同请求顺序、模型版本、服务参数和设备资源，只降低并发。以下条件全部满足，处理结果才通过：

- `free_kvcache_blocks` 在稳态窗口保留稳定余量，不再持续接近 0。
- `scheduler:recompute_events` 不再持续出现异常增量。
- waiting 队列不再持续增长。
- TTFT 和 TPOT 相比问题窗口回落，吞吐没有出现不可接受的损失。
- 模型输出正确性、错误率和显存占用没有回退。

如果降低并发后 KVCache 水位恢复，但 TTFT 或 TPOT 没有恢复，说明系统还存在第二个瓶颈，需要继续检查模型执行、通信和输出处理阶段，不能把全部性能问题归到 KVCache。

## 可复用判断链

本案例的判断链可以直接复用：

```text
新负载变慢
  → TTFT/TPOT 确认受影响 SLO
  → waiting 增长且 free_kvcache_blocks 接近 0
  → recompute/回退/分配失败计数增加
  → 按 Token 分布和并发解释容量需求变化
  → 单变量降低并发
  → 同负载复测水位、重计算、时延和吞吐
```

缺少 KVCache 水位、waiting 和重计算/回退三类证据中的任意一类，只能输出排查方向，不能输出本案例的根因结论。
