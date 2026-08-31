# 动态 EPLB 开启后投机推理接受率下降

## 案例背景

投机推理先由草稿模型生成候选 Token，再由目标模型校验。接受的候选 Token 越多，一次目标模型执行能够推进的生成步数越多；接受率持续下降后，草稿阶段已经付出的计算无法转化为等量的有效 Token，投机推理收益随之下降，TPOT 和吞吐会直接受到影响。

## 问题现象

相同测评过程中，两组接受率曲线呈现出清晰差异：

- 未开启动态 EPLB 时，各实例的投机推理平均接受率曲线集中，稳态阶段保持在接近上限的窄幅区间。
- 开启动态 EPLB 后，各实例曲线明显分散，稳态接受率反复波动并整体下移，部分曲线在测评后段快速降至接近 0。

这种变化不是普通的时延抖动。接受率直接反映草稿 Token 被目标模型接受的比例，曲线整体下移说明投机推理的有效推进能力下降。因而排查入口从 Scheduler、KVCache 和通信阶段收敛到“动态 EPLB 与投机推理组合”。

## 定位过程

### 步骤 1：固定 A/B 对比条件

复用本案例时，两组测试必须只改变动态 EPLB 开关，其余条件全部一致：

- 模型、权重、Tokenizer 和草稿模型。
- vLLM、vLLM-Ascend、CANN 和 msServiceProfiler 版本。
- 投机 Token 数、采样参数、随机种子和精度配置。
- 数据集、请求顺序、输入/输出 Token 分布、并发和预热过程。
- NPU 型号、卡数、EP/DP/TP 配置、实例数和路由策略。

上述条件没有固定时，接受率差异不能归因到动态 EPLB。

### 步骤 2：计算投机 Token 接受率

仓库自带 Grafana 面板使用 vLLM 原生 Counter 计算接受率：

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

该值等于“窗口内被接受的草稿 Token 数 / 窗口内生成的草稿 Token 数”。查询时保留 `instance` 和 `role`，不能先把所有实例合并成一条曲线，否则局部实例的接受率塌陷会被平均值掩盖。

同时检查 `vllm_profiling_num_spec_tokens`，确认两组测试的投机 Token 配置和实际调度规模一致。分母没有增量的时间窗口不参与接受率比较。

### 步骤 3：确认接受率变化与性能变化同步

在同一时间轴上对齐以下指标：

- 接受率：`vllm:spec_decode_num_accepted_tokens_total / vllm:spec_decode_num_draft_tokens_total`
- 单 Token 时延：`fine_grained_tpot`
- 首 Token 时延：`fine_grained_ttft`
- 吞吐：请求吞吐和输出 Token 吞吐
- 草稿规模：`num_spec_tokens`

接受率下降、TPOT 上升或输出 Token 吞吐下降，并且 `num_spec_tokens` 保持一致时，可以确认性能损失来自投机 Token 的有效产出下降，而不是草稿长度配置发生变化。

### 步骤 4：用 EPLB 指标确认开关和更新时段

使用 ms-service-metric 的 EPLB 指标核对动态负载均衡是否实际运行：

- `eplb:expert_hotness:current_mean`、`eplb:expert_hotness:current_max`：更新前的专家热点分布。
- `eplb:expert_hotness:update_mean`、`eplb:expert_hotness:update_max`：更新后的专家热点分布。
- `eplb:expert_hotness:imbalance`：按 Layer 查看更新前后的热点失衡度。
- `eplb:expert_map_update:duration`、`eplb:expert_weight_update:duration`：确认动态映射和权重更新发生的时间窗口。

EPLB 更新耗时只能说明动态更新发生以及产生了多少停顿，不能单独解释接受率下降。接受率是本案例的主证据，EPLB 指标负责确认触发条件和时间对齐。

### 步骤 5：排除相邻性能瓶颈

按同一异常窗口检查：

- waiting、`scheduler:duration` 和 KVCache 水位没有同步异常时，排除排队和 KVCache 容量瓶颈。
- `executor:model_runner_execute_model:duration` 没有出现与接受率跌落一致的阶跃变化时，排除单纯的模型执行变慢。
- 错误率、健康检查和 RPC 错误没有增加时，排除服务异常导致的吞吐损失。

Tracing 在本案例中用于排除 scheduler、model runner 和 output 阶段的额外等待，不用于计算接受率。接受率必须从 Token Counter 或 Profiler 的投机推理字段计算。

### 步骤 6：完成配置级归因

本案例的开关对比中，关闭动态 EPLB 时接受率稳定，开启动态 EPLB 后接受率曲线整体下移并出现实例级塌陷。复现时按步骤 1 固定其余变量后，开关变量与异常指标形成一一对应关系，配置级结论成立：动态 EPLB 是该投机推理组合的回退触发条件。

这一结论不等同于“动态 EPLB 在所有场景都有问题”，也不等同于“已经定位到 EPLB 内部某段代码”。要继续给出代码级根因，必须补充相同请求的逐步 accepted Token 数据、专家映射更新记录、Rank 间权重一致性检查和更新前后模型输出对比。

## 根因结论

当前模型、版本、精度和投机推理配置与动态 EPLB 组合后，投机 Token 接受率发生稳定回退，导致草稿计算不能转化为有效生成步数，最终削弱投机推理性能。

现有证据已经完成性能问题的配置级根因定位；内部实现层根因不在本案例证据范围内。

## 处理方法

该工作负载关闭动态 EPLB，保留已经通过接受率和精度验证的 EPLB 配置。需要重新开启动态 EPLB 时，必须先在相同模型、版本和精度配置下完成独立 A/B 验证，不能只依据专家负载均衡改善就上线。

验证过程中一次只修改动态 EPLB 开关。不得同时修改投机 Token 数、采样参数、并行策略或精度配置。

## 复测标准

关闭动态 EPLB 后，使用原问题数据集和完全相同的压测条件复测。以下条件全部满足才通过：

- 各实例接受率回到关闭动态 EPLB 的基线分布，不再出现持续下移或接近 0 的曲线。
- TPOT 和输出 Token 吞吐回到基线范围。
- TTFT、端到端时延和错误率没有回退。
- 相同输入和采样条件下，输出正确性检查通过。
- `num_spec_tokens`、请求 Token 分布和并发与问题窗口一致。

如果接受率恢复但性能没有恢复，继续检查模型执行耗时和 EPLB 更新停顿；如果性能恢复但输出正确性没有通过，该配置仍然不能上线。

## 可复用判断链

```text
投机推理性能下降
  → 按实例查看 accepted_tokens / draft_tokens
  → 确认接受率整体下移或局部塌陷
  → 与 TPOT、吞吐和 num_spec_tokens 对齐
  → 固定全部条件，只切换动态 EPLB
  → 排除 waiting、KVCache、模型执行和服务错误
  → 关闭动态 EPLB 复测接受率、性能和正确性
```

这条链路同时满足现象定界、触发条件归因和处理后验证，可以直接用于其他投机推理与动态 EPLB 组合的性能排查。

## 参考资料

- [vLLM-Ascend 投机推理说明](https://docs.vllm.ai/projects/ascend/en/main/user_guide/feature_guide/speculative_decoding.html)
- [vLLM 投机推理接受率定义](https://docs.vllm.ai/en/latest/features/speculative_decoding/acceptance_metrics/)
- [vLLM-Ascend EPLB 使用说明](https://docs.vllm.ai/projects/ascend/en/latest/user_guide/feature_guide/expert_parallelism_load_balancer.html)
