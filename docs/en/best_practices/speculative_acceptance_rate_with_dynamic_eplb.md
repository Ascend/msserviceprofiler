# Speculative Inference Acceptance Rate Drops After Dynamic EPLB Is Enabled

## Case Background

Speculative inference first has the draft model generate candidate tokens, which are then verified by the target model. The more candidate tokens are accepted, the more generation steps one target model execution can advance. Once the acceptance rate keeps dropping, the computation already spent in the draft phase can no longer be converted into an equivalent number of valid tokens, so the benefit of speculative inference decreases and TPOT and throughput are directly affected.

## Symptoms

In the same evaluation run, the two acceptance rate curves show a clear difference:

- When dynamic EPLB is disabled, the average speculative inference acceptance rate curves of the instances are close together and stay in a narrow band near the upper limit during the steady state.
- After dynamic EPLB is enabled, the curves of the instances are clearly spread out, the steady-state acceptance rate fluctuates repeatedly and shifts down as a whole, and some curves drop rapidly to near 0 in the later part of the evaluation.

This change is not ordinary latency jitter. The acceptance rate directly reflects the proportion of draft tokens accepted by the target model, and a downward shift of the whole curve means that the effective advancement capability of speculative inference has decreased. The troubleshooting entry point therefore narrows from the scheduler, KVCache, and communication phases to the combination of dynamic EPLB and speculative inference.

## Troubleshooting Process

### Step 1: Fixing the A/B Comparison Conditions

When reusing this case, the two test groups must change only the dynamic EPLB switch, with all other conditions identical:

- Model, weights, tokenizer, and draft model.
- Versions of vLLM, vLLM-Ascend, CANN, and msServiceProfiler.
- Number of speculative tokens, sampling parameters, random seed, and precision configuration.
- Dataset, request order, input/output token distribution, concurrency, and warm-up process.
- NPU model, number of devices, EP/DP/TP configuration, number of instances, and routing policy.

If the preceding conditions are not fixed, the difference in the acceptance rate cannot be attributed to dynamic EPLB.

### Step 2: Calculating the Speculative Token Acceptance Rate

The Grafana dashboard shipped with the repository calculates the acceptance rate with the native counters of vLLM:

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

This value equals the number of accepted draft tokens in the window divided by the number of generated draft tokens in the window. Keep `instance` and `role` in the query; do not merge all instances into one curve first, otherwise a collapse of the acceptance rate on individual instances will be hidden by the average.

Also check `vllm_profiling_num_spec_tokens` to confirm that the speculative token configuration and the actual scheduling scale of the two test groups are the same. Time windows in which the denominator has no increment do not take part in the acceptance rate comparison.

### Step 3: Confirming That the Acceptance Rate Change and the Performance Change Are Synchronized

Align the following metrics on the same timeline:

- Acceptance rate: `vllm:spec_decode_num_accepted_tokens_total / vllm:spec_decode_num_draft_tokens_total`
- Per-token latency: `fine_grained_tpot`
- Time to first token: `fine_grained_ttft`
- Throughput: request throughput and output token throughput
- Draft scale: `num_spec_tokens`

When the acceptance rate drops, TPOT rises or output token throughput drops, and `num_spec_tokens` stays the same, you can confirm that the performance loss comes from a decrease in the effective output of speculative tokens rather than from a change in the draft length configuration.

### Step 4: Confirming the Switch and the Update Window with EPLB Metrics

Use the EPLB metrics of ms-service-metric to check whether dynamic load balancing is actually running:

- `eplb:expert_hotness:current_mean`, `eplb:expert_hotness:current_max`: expert hotness distribution before the update.
- `eplb:expert_hotness:update_mean`, `eplb:expert_hotness:update_max`: expert hotness distribution after the update.
- `eplb:expert_hotness:imbalance`: hotness imbalance before and after the update, by layer.
- `eplb:expert_map_update:duration`, `eplb:expert_weight_update:duration`: confirm the time windows in which the dynamic mapping and weight updates occur.

The EPLB update duration only shows that a dynamic update occurred and how much stall it produced; it cannot explain the drop in the acceptance rate by itself. The acceptance rate is the primary evidence of this case, and the EPLB metrics are responsible for confirming the trigger condition and the time alignment.

### Step 5: Ruling Out Adjacent Performance Bottlenecks

Check the same anomaly window:

- If waiting, `scheduler:duration`, and the KVCache level show no synchronized anomaly, queueing and KVCache capacity bottlenecks are ruled out.
- If `executor:model_runner_execute_model:duration` shows no step change consistent with the acceptance rate drop, slower model execution alone is ruled out.
- If the error rate, health checks, and RPC errors do not increase, throughput loss caused by service errors is ruled out.

In this case, Tracing is used to rule out extra waiting in the scheduler, model runner, and output phases, not to calculate the acceptance rate. The acceptance rate must be calculated from token counters or from the speculative inference fields of the Profiler.

### Step 6: Completing the Configuration-Level Attribution

In the switch comparison of this case, the acceptance rate is stable when dynamic EPLB is disabled, and after dynamic EPLB is enabled the acceptance rate curve shifts down as a whole and an instance-level collapse occurs. When the other variables are fixed as described in step 1 and the case is reproduced, the switch variable and the abnormal metric form a one-to-one correspondence, so the configuration-level conclusion holds: dynamic EPLB is the regression trigger for this speculative inference combination.

This conclusion is not equivalent to "dynamic EPLB has problems in all scenarios", nor to "a specific piece of code inside EPLB has been located". To go on to a code-level root cause, you must add step-by-step accepted token data for the same request, expert mapping update records, cross-rank weight consistency checks, and a comparison of the model output before and after the update.

## Root Cause

When the current model, version, precision, and speculative inference configuration are combined with dynamic EPLB, the speculative token acceptance rate regresses consistently, so the draft computation cannot be converted into effective generation steps and the speculative inference performance is weakened.

The available evidence completes the configuration-level root cause analysis of the performance problem; the root cause at the internal implementation level is beyond the evidence scope of this case.

## Solutions

Disable dynamic EPLB for this workload and keep the EPLB configuration that has already passed acceptance rate and precision verification. If dynamic EPLB must be enabled again, complete an independent A/B verification under the same model, version, and precision configuration first; do not roll it out based only on an improvement in expert load balancing.

During verification, change only the dynamic EPLB switch at a time. Do not change the number of speculative tokens, sampling parameters, parallelism strategy, or precision configuration at the same time.

## Re-Test Criteria

After dynamic EPLB is disabled, re-test with the original problem dataset and exactly the same load test conditions. The result passes only if all of the following conditions are met:

- The acceptance rate of each instance returns to the baseline distribution of the case with dynamic EPLB disabled, with no curve that keeps shifting down or approaches 0.
- TPOT and output token throughput return to the baseline range.
- TTFT, end-to-end latency, and the error rate do not regress.
- The output correctness check passes under the same input and sampling conditions.
- `num_spec_tokens`, the request token distribution, and the concurrency are the same as in the problem window.

If the acceptance rate recovers but the performance does not, continue checking the model execution duration and the EPLB update stall; if the performance recovers but the output correctness check does not pass, the configuration still cannot be rolled out.

## Reusable Decision Chain

```text
Speculative inference performance degrades
  → check accepted_tokens / draft_tokens by instance
  → confirm that the acceptance rate shifts down as a whole or collapses locally
  → align with TPOT, throughput, and num_spec_tokens
  → fix all conditions and toggle only dynamic EPLB
  → rule out waiting, KVCache, model execution, and service errors
  → disable dynamic EPLB and re-test the acceptance rate, performance, and correctness
```

This chain covers symptom determination, trigger attribution, and post-processing verification at the same time, and can be used directly for performance troubleshooting of other combinations of speculative inference and dynamic EPLB.

## References

- [vLLM-Ascend Speculative Decoding](https://docs.vllm.ai/projects/ascend/en/main/user_guide/feature_guide/speculative_decoding.html)
- [vLLM Speculative Decoding Acceptance Metrics](https://docs.vllm.ai/en/latest/features/speculative_decoding/acceptance_metrics/)
- [vLLM-Ascend EPLB User Guide](https://docs.vllm.ai/projects/ascend/en/latest/user_guide/feature_guide/expert_parallelism_load_balancer.html)
