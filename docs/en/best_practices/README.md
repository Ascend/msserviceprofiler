# msServiceProfiler Case Studies

When you perform performance analysis for the first time, read the *[vLLM-Ascend Observability Performance Diagnostics Guide](./vllm_ascend_observability_analysis_guide.md)* first, and select independent Metrics analysis, independent Tracing analysis, or joint analysis according to the available data. [New Evaluation Dataset Triggers a KVCache Capacity Bottleneck](kv_block_shortage.md) provides the real Metrics handling chain for waiting, the KVCache level, and recomputation; [Speculative Inference Acceptance Rate Drops After Dynamic EPLB Is Enabled](speculative_acceptance_rate_with_dynamic_eplb.md) provides the A/B determination method for the speculative inference acceptance rate. Both cases clearly distinguish the available evidence, the optional enhancement steps, and the boundary of the conclusion. For other issues, see the following cases:

- [Asynchronous Dual Dispatch Not Taking Effect](async_dual_launch_failure.md)
- [Request Length Imbalance Within the Same Batch](batch_request_length_imbalance.md)
- [DP Load Imbalance](dp_load_imbalance.md)
- [EP Load Imbalance](ep_load_imbalance.md)
- [Framework Scheduling and Dispatch Not Synchronized](framework_dispatch_desync.md)
- [New Evaluation Dataset Triggers a KVCache Capacity Bottleneck](kv_block_shortage.md)
- [Impact of KVCache Transfer on Model Performance](kvcache_transfer_performance.md)
- [Model Performance Degradation Causing SLO Degradation](model_performance_slo_degradation.md)
- [Excessive Preprocessing and Postprocessing Time in Model Inference](model_pre_post_processing_latency.md)
- [Multi-Instance Load Imbalance](multi_instance_load_imbalance.md)
- [PrefixCache Misses](prefix_cache_miss.md)
- [Long Wait Time for Model Inference Requests](request_wait_latency.md)
- [Excessive Sampler Execution Time](sampler_high_latency.md)
- [Excessive Scheduler Execution Time](scheduler_high_latency.md)
- [Speculative Inference Acceptance Rate Drops After Dynamic EPLB Is Enabled](speculative_acceptance_rate_with_dynamic_eplb.md)
- [Large Performance Gaps Between Serving and Pure-Model Inference](service_vs_model_performance_gap.md)
