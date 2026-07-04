# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------

try:
    from sglang.srt.managers.io_struct import (
        BatchTokenizedGenerateReqInput,
        BatchTokenizedEmbeddingReqInput,
        TokenizedGenerateReqInput,
        TokenizedEmbeddingReqInput,
    )
    from sglang.srt.disaggregation.utils import DisaggregationMode
except ImportError:
    # 创建模拟类型供测试使用
    BatchTokenizedGenerateReqInput = type('BatchTokenizedGenerateReqInput', (), {})
    BatchTokenizedEmbeddingReqInput = type('BatchTokenizedEmbeddingReqInput', (), {})
    TokenizedGenerateReqInput = type('TokenizedGenerateReqInput', (), {})
    TokenizedEmbeddingReqInput = type('TokenizedEmbeddingReqInput', (), {})

    class DisaggregationMode:
        NULL = 'null'
        PREFILL = 'prefill'
        DECODE = 'decode'


from ms_service_profiler import Profiler, Level
from ms_service_profiler.patcher.core.module_hook import patcher


def prof_get_batch_rids(batch):
    return [str(req.rid) for req in batch.reqs]


def get_batch_type(batch):
    if batch.forward_mode.is_decode():
        return "decode"
    elif batch.forward_mode.is_extend():
        return "prefill"
    return "unknown"


def _get_batch_request_rids(req):
    for attr_name in ("rids", "rid"):
        rid_value = getattr(req, attr_name, None)
        if rid_value is None:
            continue
        if isinstance(rid_value, (list, tuple)):
            return [str(rid) for rid in rid_value]
        return [str(rid_value)]
    return []


def prof_kvcache_info(scheduler, name="allocate"):
    """Record SGLang KV cache state across scheduler layout changes."""
    pool_stats_observer = getattr(scheduler, "pool_stats_observer", None)
    if pool_stats_observer is not None:
        pool_stats = pool_stats_observer.get_pool_stats()
        full_available_size = pool_stats.full_available_size
        full_evictable_size = pool_stats.full_evictable_size
        prof = (
            Profiler(Level.INFO)
            .domain("KVCache")
            .metric("FreeBlocks", full_available_size)
            .metric("fullEvictableSize", full_evictable_size)
        )
        if getattr(pool_stats, "is_hybrid_swa", False):
            prof.metric("swaAvailableSize", pool_stats.swa_available_size).metric(
                "swaEvictableSize", pool_stats.swa_evictable_size
            )
        prof.event(name)
        return

    # 兼容 SGLang 0.5.4.post1 附近旧结构。
    is_hybrid = getattr(scheduler, "is_hybrid_swa", None) or getattr(scheduler, "is_hybrid", False)
    if is_hybrid and hasattr(scheduler, "_get_swa_token_info"):
        swa_info = scheduler._get_swa_token_info()
        if hasattr(swa_info, "full_available_size"):
            full_available_size = swa_info.full_available_size
            full_evictable_size = swa_info.full_evictable_size
            swa_available_size = swa_info.swa_available_size
            swa_evictable_size = swa_info.swa_evictable_size
        else:
            (
                _,
                _,
                _,
                _,
                full_available_size,
                full_evictable_size,
                swa_available_size,
                swa_evictable_size,
            ) = swa_info
        Profiler(Level.INFO).domain("KVCache").metric("FreeBlocks", full_available_size).metric(
            "fullEvictableSize", full_evictable_size
        ).metric("swaAvailableSize", swa_available_size).metric("swaEvictableSize", swa_evictable_size).event(name)
        return

    if hasattr(scheduler, "_get_token_info"):
        token_info = scheduler._get_token_info()
        if hasattr(token_info, "full_available_size"):
            available_size = token_info.full_available_size
            evictable_size = token_info.full_evictable_size
        else:
            _, _, available_size, evictable_size = token_info
        Profiler(Level.INFO).domain("KVCache").metric("FreeBlocks", available_size).metric(
            "fullEvictableSize", evictable_size
        ).event(name)
        return

    token_to_kv_pool_allocator = getattr(scheduler, "token_to_kv_pool_allocator", None)
    tree_cache = getattr(scheduler, "tree_cache", None)
    if token_to_kv_pool_allocator is None or tree_cache is None:
        return

    if hasattr(token_to_kv_pool_allocator, "full_available_size"):
        available_size = token_to_kv_pool_allocator.full_available_size()
        evictable_size = tree_cache.full_evictable_size() if hasattr(tree_cache, "full_evictable_size") else 0
    else:
        available_size = token_to_kv_pool_allocator.available_size()
        evictable_size = tree_cache.evictable_size()
    Profiler(Level.INFO).domain("KVCache").metric("FreeBlocks", available_size).metric(
        "fullEvictableSize", evictable_size
    ).event(name)


@patcher(
    ("sglang.srt.managers.scheduler_components.request_receiver", "SchedulerRequestReceiver.recv_requests"),
    min_version="0.5.4",
)
def recv_requests(original_func, this, *args, **kwargs):
    recv_reqs = original_func(this, *args, **kwargs)

    for req in recv_reqs or []:
        if isinstance(
            req,
            (
                TokenizedGenerateReqInput,
                TokenizedEmbeddingReqInput,
                BatchTokenizedGenerateReqInput,
                BatchTokenizedEmbeddingReqInput,
            ),
        ):
            rids = _get_batch_request_rids(req)
            Profiler(Level.INFO).domain("Schedule").res(rids or str(req)).event("recvReq")

    return recv_reqs


@patcher(
    hook_points=[
        ("sglang.srt.managers.scheduler", "Scheduler.handle_generate_request"),
        ("sglang.srt.managers.scheduler", "Scheduler.handle_embedding_request"),
    ],
    min_version="0.5.4",
)
def request_dispatcher(original_func, this, recv_req, *args, **kwargs):
    prof = Profiler(Level.INFO).domain("Schedule").span_start("processReq").res(str(recv_req.rid))

    output = original_func(this, recv_req, *args, **kwargs)

    prof.span_end()

    return output


@patcher(("sglang.srt.managers.scheduler", "Scheduler.get_next_batch_to_run"), min_version="0.5.4")
def get_next_batch_to_run(original_func, this, *args, **kwargs):
    prof = Profiler(Level.INFO).domain("Schedule").span_start("batchFrameworkProcessing")

    batch = original_func(this, *args, **kwargs)

    if batch:
        prof_kvcache_info(this, "allocate")
        prof.attr("batch_type", get_batch_type(batch)).res(prof_get_batch_rids(batch))
        prof.span_end()

    return batch


@patcher(("sglang.srt.managers.scheduler", "Scheduler.run_batch"), min_version="0.5.4")
def run_batch(original_func, this, batch, *args, **kwargs):
    prof = (
        Profiler(Level.INFO)
        .domain("ModelExecute")
        .span_start("modelExec")
        .res(prof_get_batch_rids(batch))
        .attr("batch_type", get_batch_type(batch))
    )

    result = original_func(this, batch, *args, **kwargs)

    prof.span_end()

    return result


@patcher(("sglang.srt.managers.scheduler", "Scheduler.process_batch_result"), min_version="0.5.4")
def process_batch_result(original_func, this, batch, *args, **kwargs):
    prof = (
        Profiler(Level.INFO)
        .domain("ModelExecute")
        .span_start("postprocess")
        .res(prof_get_batch_rids(batch))
        .attr("batch_type", get_batch_type(batch))
    )

    result = original_func(this, batch, *args, **kwargs)

    prof.span_end()

    return result


@patcher(("sglang.srt.managers.scheduler", "Scheduler._add_request_to_queue"), min_version="0.5.4")
def add_request_to_queue(original_func, this, req, *args, **kwargs):
    is_retracted = args[0] if args else kwargs.get("is_retracted", False)
    if this.disaggregation_mode == DisaggregationMode.NULL:
        if not this._abort_on_queued_limit(req):
            Profiler(Level.INFO).domain("Schedule").res(str(req.rid)).metric_scope("QueueName", "WAITING").event(
                "Enqueue"
            )
            Profiler(Level.INFO).domain("Schedule").metric("QueueSize", len(this.waiting_queue)).metric_scope(
                "QueueName", "WAITING"
            ).event("Queue")
    elif this.disaggregation_mode == DisaggregationMode.PREFILL:
        Profiler(Level.INFO).domain("Schedule").res(str(req.rid)).metric_scope("QueueName", "PrefillBootstrap").event(
            "Enqueue"
        )
        # disagg_prefill_bootstrap_queue 未实现 __len__，需取 .queue 列表
        Profiler(Level.INFO).domain("Schedule").metric(
            "QueueSize", len(this.disagg_prefill_bootstrap_queue.queue)
        ).metric_scope("QueueName", "PrefillBootstrap").event("Queue")
    elif this.disaggregation_mode == DisaggregationMode.DECODE:
        if not is_retracted:
            Profiler(Level.INFO).domain("Schedule").res(str(req.rid)).metric_scope("QueueName", "DecodePrealloc").event(
                "Enqueue"
            )
            # disagg_decode_prealloc_queue 未实现 __len__，需取 .queue 列表
            Profiler(Level.INFO).domain("Schedule").metric(
                "QueueSize", len(this.disagg_decode_prealloc_queue.queue)
            ).metric_scope("QueueName", "DecodePrealloc").event("Queue")

    result = original_func(this, req, *args, **kwargs)

    return result


@patcher(("sglang.srt.managers.scheduler", "Scheduler.get_new_batch_prefill"), min_version="0.5.4")
def get_new_batch_prefill(original_func, this, *args, **kwargs):
    new_batch = original_func(this, *args, **kwargs)
    if new_batch is None:
        return new_batch

    Profiler(Level.INFO).domain("Schedule").metric("QueueSize", len(this.waiting_queue)).metric_scope(
        "QueueName", "WAITING"
    ).event("Queue")

    for req in new_batch.reqs:
        Profiler(Level.INFO).domain("Schedule").res(str(req.rid)).metric_scope("QueueName", "WAITING").event("Dequeue")

    return new_batch


@patcher(("sglang.srt.managers.schedule_batch", "Req.init_next_round_input"), min_version="0.5.4")
def init_next_round_input(original_func, this, *args, **kwargs):
    ret = original_func(this, *args, **kwargs)

    # origin_input_ids 当前版本为 List[int]，用 bool() 兼容 list/int 两种类型
    if this.origin_input_ids:
        Profiler(Level.INFO).domain("HitCache").metric(
            "hitRate", str(len(this.prefix_indices) / len(this.origin_input_ids))
        ).res(str(this.rid)).event("HitCache")

    return ret


@patcher(
    (
        "sglang.srt.managers.scheduler_components.batch_result_processor",
        "SchedulerBatchResultProcessor.process_batch_result_prefill",
    ),
    min_version="0.5.4",
)
def process_batch_result_prefill(original_func, this, batch, *args, **kwargs):
    if this.is_generation:
        for req in batch.reqs:
            if this.enable_overlap and req.is_retracted and len(req.output_ids) > 0:
                continue

            not_finished = (
                getattr(this, "is_mixed_chunk", False) and this.enable_overlap and (req.finished() or req.is_retracted)
            )
            if not_finished:
                continue

            if req.is_retracted:
                continue

            if req.is_chunked <= 0 and req.finished():
                Profiler(Level.INFO).domain("Request").res(str(req.rid)).metric(
                    "recvTokenSize", len(req.origin_input_ids)
                ).metric("replyTokenSize", len(req.output_ids)).event("PrefillEnd")

    ret = original_func(this, batch, *args, **kwargs)

    prof_kvcache_info(this, "free")

    return ret


@patcher(
    (
        "sglang.srt.managers.scheduler_components.batch_result_processor",
        "SchedulerBatchResultProcessor.process_batch_result_decode",
    ),
    min_version="0.5.4",
)
def process_batch_result_decode(original_func, this, batch, *args, **kwargs):
    prof_list = []
    for req in batch.reqs:
        if this.enable_overlap and (req.finished() or req.is_retracted):
            prof_list.append(None)
        elif req.is_retracted:
            prof_list.append(None)
        else:
            prof_list.append(Profiler(Level.INFO).domain("Request").span_start("DecodeEnd"))

    ret = original_func(this, batch, *args, **kwargs)

    for i, req in enumerate(batch.reqs):
        if req.finished() and prof_list[i] is not None:
            prof_list[i].res(str(req.rid)).metric("recvTokenSize", len(req.origin_input_ids)).metric(
                "replyTokenSize", len(req.output_ids)
            ).span_end()

    prof_kvcache_info(this, "free")

    return ret
