# New Evaluation Dataset Triggers a KVCache Capacity Bottleneck

## Case Background

After the evaluation dataset was changed, the inference speed dropped noticeably. The first round of troubleshooting has to answer two questions: at which stage of the request lifecycle the performance drop occurs, and why the new dataset triggers a bottleneck at that stage.

## Symptoms

After the dataset was changed, the following changes appear in the same time window in Grafana:

- `fine_grained_ttft` and `fine_grained_tpot` deteriorate at the same time.
- The waiting queue keeps building up.
- `free_kvcache_blocks` drops to near 0, and the KVCache stays at the lower capacity limit for a long time.
- `scheduler:recompute_events` keeps increasing, indicating that the scheduler frequently triggers request recomputation.

These signals indicate that the problem is not in a single model computation but in the KVCache capacity pressure caused jointly by the request characteristics of the new dataset and the current concurrency.

## Troubleshooting Process

### Step 1: Confirming the Scope of Impact with TTFT and TPOT

First compare the baseline of the old dataset with the abnormal window of the new dataset:

- TTFT reflects the wait, scheduling, and prefill overhead between the arrival of a request and the return of the first token.
- TPOT reflects the average time per token after the request enters the generation stage.

When TTFT and TPOT deteriorate at the same time, do not check model execution alone. The waiting, KVCache, recomputation, and model execution metrics must be compared on the same timeline.

### Step 2: Confirming That the Waiting Queue and the KVCache Level Change Together

Use the following queries to pin down the capacity evidence. Keep the query window the same as the load test window, and split the results by labels such as `instance` and `dp` in the deployment.

KVCache usage:

```promql
100 * (
  1 -
  vllm_profiling_free_kvcache_blocks
  /
  vllm_profiling_total_kvcache_blocks
)
```

Use the `vllm_profiling_waiting_batch_size` panel to view the waiting queue size. If this metric is a histogram, use `_sum / _count` to calculate the average over the window, or use `_bucket` to calculate quantiles. Do not draw conclusions directly from the cumulative value.

When `free_kvcache_blocks` stays close to 0 and the waiting queue and TTFT rise together, the problem can be narrowed down to "requests are limited by KVCache capacity before they enter the execution stage".

### Step 3: Confirming with the Recomputation Counter That Capacity Pressure Has Affected Scheduling

`scheduler:recompute_events` is a counter. View it by window increment:

```promql
sum by (instance, dp) (
  increase(vllm_profiling_scheduler:recompute_events_total[5m])
)
```

Also check the two supporting signals:

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

When the following three conditions hold in the same time window, the first-level isolation of the KVCache capacity bottleneck is complete:

1. `free_kvcache_blocks` keeps touching the lower capacity limit.
2. The waiting queue and TTFT rise together.
3. `scheduler:recompute_events`, `running_to_waiting_count`, or `block_allocate_failures` shows an abnormal increment.

### Step 4: Tracing the Capacity Pressure Back to the New Dataset and Concurrency

When you reuse this case, first confirm that the model, the version, the serving parameters, and the deployment resources have not changed at the same time. Then collect statistics on the old and the new dataset by the following fields instead of comparing only the number of requests:

- P50, P90, P99, and the maximum of the input tokens.
- P50, P90, P99, and the maximum of the output tokens.
- Total tokens per request and the proportion of long-context requests.
- Request arrival pattern, per-instance concurrency, and steady-state batch size.

KV block consumption is determined jointly by the number of concurrently resident requests and the number of tokens per request. The data has confirmed that, under the current concurrency, the new dataset exhausts the KVCache for a long time, so the scheduler can only make requests wait or roll back running requests for recomputation. The root cause of this case is therefore not that "the dataset itself is slow" but that the current concurrency no longer matches the KVCache demand of the new dataset. Because the historical data does not retain the token distribution, it cannot be asserted whether the input length, the output length, or the proportion of long requests changed.

### Step 5: Ruling Out Slower Model Execution

Under the same prefill/decode stage, batch, and token scale, compare:

- `executor:execute_model:duration`
- `executor:model_runner_execute_model:duration`
- `npu:forward_duration`

If these metrics stay at the baseline of the old dataset while the waiting queue, the KVCache level, and the recomputation counter behave abnormally, the model execution stage is ruled out. If the model execution time also increases, normalize by token and batch scale before deciding whether a compute bottleneck exists at the same time.

### Step 6: Strengthening Request-Level Evidence with Tracing and Profiler

When the metrics already satisfy the combined criteria in steps 2 to 5, the KVCache capacity conclusion can be drawn directly. If you need to further locate specific requests, batches, or the place where requests wait before model execution, run the following enhanced analysis.

Tracing verification:

1. Use `request.id`, `request.ids`, or span links to confirm the association of the scheduler and the model with the target request.
2. Compare a normal observation group with an abnormal one that has the same token and batch scale.
3. Check `vllm.scheduler.schedule`, `vllm.model.execute`, and `vllm_ascend.model_runner.execute`.
4. Calculate the blank interval before model execution only when the spans belong to the same trace ID or have been imported into a unified Perfetto timeline.

Profiler verification:

- `request.csv`: identify which requests account for most of the growth of `queue_wait_time(ms)` and `first_token_latency(ms)`.
- `batch.csv`: check the changes in `free_blocks`, `kvcache_usage_rate`, and `decode_batch_size`.
- `kvcache.csv`: identify the batches in which blocks are requested, released, and exhausted.

Tracing is used to rule out slower model execution itself, and Profiler is used to drill down into specific requests and batches. The KVCache root cause is still confirmed by the level, waiting, and recomputation/rollback evidence in the same window.

## Root Cause

Under the original concurrency, the new evaluation dataset generates a KVCache demand that exceeds the stable capacity of a single instance. The available KV blocks stay close to 0 for a long time, and the scheduler frequently rolls back and recomputes requests, which finally pushes up the waiting queue, TTFT, and TPOT at the same time.

## Handling Method

In this case, the action taken was to reduce the per-instance concurrency so that the total KVCache demand of concurrently resident requests returns within the instance capacity.

This action changes only the concurrency; the model version, the dataset, the KVCache configuration, and the scheduling policy stay unchanged. Only in this way can a single-variable re-test verify whether concurrency is the direct trigger.

Use the following handling methods in other scenarios only when the evidence matches:

- The proportion of long-context requests is too high: limit the maximum input/output length, or route long requests to instances with a larger KVCache capacity.
- The total number of blocks per instance is insufficient: adjust the proportion of device memory available for the KVCache, or add instance and device resources.
- Instance load is unbalanced: distribute requests by instance queue and KVCache level so that a few instances do not exhaust their blocks first.

## Re-Test Criteria

Use the same new dataset, the same request order, the same model version, the same serving parameters, and the same device resources, and reduce only the concurrency. The handling passes only when all of the following conditions are met:

- `free_kvcache_blocks` keeps a stable margin in the steady-state window and no longer stays close to 0.
- `scheduler:recompute_events` no longer shows abnormal increments.
- The waiting queue no longer keeps growing.
- TTFT and TPOT fall back compared with the problem window, and throughput does not show an unacceptable loss.
- Model output correctness, the error rate, and the device memory usage do not regress.

If the KVCache level recovers after the concurrency is reduced but TTFT or TPOT does not recover, a second bottleneck still exists. Continue to check the model execution, communication, and output processing stages instead of attributing all performance problems to the KVCache.

## Reusable Decision Chain

The decision chain of this case can be reused directly:

```text
The new load becomes slower
  -> TTFT/TPOT confirms the affected SLOs
  -> the waiting queue grows and free_kvcache_blocks approaches 0
  -> the recompute/rollback/allocation failure counters increase
  -> explain the change in capacity demand by token distribution and concurrency
  -> reduce the concurrency as a single variable
  -> re-test the level, recomputation, latency, and throughput with the same load
```

If any one of the three kinds of evidence (KVCache level, waiting queue, and recomputation/rollback) is missing, you can give only a troubleshooting direction, not the root-cause conclusion of this case.
