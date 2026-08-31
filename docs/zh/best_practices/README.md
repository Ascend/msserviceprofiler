# msServiceProfiler 典型案例

首次进行性能分析时，先阅读《[vLLM-Ascend 可观测性性能诊断指南](../vllm_ascend_observability_analysis_guide.md)》，根据现有数据选择 Metrics 独立分析、Tracing 独立分析或联合分析。其中，《[新测评数据集触发 KVCache 容量瓶颈](kv_block_shortage.md)》给出 waiting、KVCache 水位和重计算的真实 Metrics 处置链路；《[动态 EPLB 开启后投机推理接受率下降](speculative_acceptance_rate_with_dynamic_eplb.md)》给出投机推理接受率的 A/B 定界方法。两个案例均明确区分已有证据、可选增强步骤和结论边界。

- [异步双发未生效](async_dual_launch_failure.md)
- [同一Batch内请求长度不均](batch_request_length_imbalance.md)
- [DP负载不均](dp_load_imbalance.md)
- [EP负载不均](ep_load_imbalance.md)
- [框架调度下发不同步](framework_dispatch_desync.md)
- [新测评数据集触发 KVCache 容量瓶颈](kv_block_shortage.md)
- [KVCache传输影响模型性能](kvcache_transfer_performance.md)
- [模型性能劣化导致SLO劣化](model_performance_slo_degradation.md)
- [模型前后处理耗时过长](model_pre_post_processing_latency.md)
- [多实例负载不均](multi_instance_load_imbalance.md)
- [PrefixCache未命中](prefix_cache_miss.md)
- [模型推理请求等待时间过长](request_wait_latency.md)
- [sampler执行耗时过长](sampler_high_latency.md)
- [scheduler耗时过长](scheduler_high_latency.md)
- [动态 EPLB 开启后投机推理接受率下降](speculative_acceptance_rate_with_dynamic_eplb.md)
- [服务化与纯模型性能差异过大](service_vs_model_performance_gap.md)
