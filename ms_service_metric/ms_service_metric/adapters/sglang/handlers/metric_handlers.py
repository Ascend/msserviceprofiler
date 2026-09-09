# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------
"""SGLang metric handlers."""

import inspect
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterable, List, Optional

from ms_service_metric.metrics.meta_state import get_meta_state
from ms_service_metric.metrics.metrics_manager import (
    MetricType,
    SIZE_BUCKETS,
    get_metrics_manager,
)
from ms_service_metric.utils.logger import get_logger

logger = get_logger(__name__)
metrics_client = get_metrics_manager()

_REGISTERED = set()


@contextmanager
def _phase_scope(phase: str):
    meta_state = get_meta_state()
    old_phase = meta_state.get("phase", "mixed")
    meta_state.set("phase", phase)
    try:
        yield
    finally:
        meta_state.set("phase", old_phase)


def _metric_type(value: Any) -> MetricType:
    if isinstance(value, MetricType):
        return value
    try:
        return MetricType(value)
    except Exception:
        return MetricType.TIMER


def _metric_get(metric: Any, key: str, default: Any = None) -> Any:
    if hasattr(metric, "get"):
        return metric.get(key, default)
    return getattr(metric, key, default)


def _label_names(metric: Any) -> List[str]:
    labels = _metric_get(metric, "labels", {}) or {}
    if isinstance(labels, dict):
        return list(labels)
    if isinstance(labels, list):
        return [item.get("name") for item in labels if isinstance(item, dict) and item.get("name")]
    return []


def _register(
    metric_name: str,
    metric_type: MetricType = MetricType.TIMER,
    labels: Optional[List[str]] = None,
    buckets: Optional[List[float]] = None,
) -> None:
    if not metric_name:
        return
    key = (metric_name, metric_type.value, tuple(labels or ()))
    if key in _REGISTERED:
        return
    try:
        metrics_client.get_or_create_metric(metric_name, label_names=labels, metric_type=metric_type, buckets=buckets)
        _REGISTERED.add(key)
    except Exception:
        logger.warning("Failed to register SGLang metric %s", metric_name, exc_info=True)


def _record(metric_name: str, value: float = 1, labels: Optional[Dict[str, str]] = None) -> None:
    try:
        metrics_client.record_metric(metric_name, value, labels or {})
    except Exception:
        logger.warning("Failed to record SGLang metric %s", metric_name, exc_info=True)


def _safe_len(obj: Any, default: int = 0) -> int:
    if obj is None:
        return default
    try:
        return len(obj)
    except Exception:
        return default


def _size_at(value: Any, dim: int) -> int:
    size = getattr(value, "size", None)
    if callable(size):
        try:
            return int(size(dim))
        except Exception:
            return 0
    return 0


def _shape_at(value: Any, dim: int) -> int:
    shape = getattr(value, "shape", None)
    if shape is None:
        return 0
    try:
        return int(shape[dim])
    except Exception:
        return 0


def _len_dim0(value: Any) -> int:
    if value is None or isinstance(value, str):
        return 0
    size = _size_at(value, 0)
    if size:
        return size
    shape = _shape_at(value, 0)
    if shape:
        return shape
    return _safe_len(value)


def _first_present(obj: Any, names: Iterable[str]) -> Any:
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return None


def _as_number(value: Any, default: float = 0) -> float:
    try:
        if callable(value):
            value = value()
        return float(value)
    except Exception:
        return default


def _as_rank(value: Any) -> int:
    try:
        if callable(value):
            value = value()
        rank = int(value)
    except Exception:
        return -1
    return rank if rank >= 0 else -1


def _iter_rank_sources(*objects: Any) -> List[Any]:
    sources = []
    nested_attrs = ("parallel_config", "server_args", "model_runner", "worker", "tp_worker")
    for obj in objects:
        if obj is None:
            continue
        sources.append(obj)
        for attr in nested_attrs:
            nested = getattr(obj, attr, None)
            if nested is not None:
                sources.append(nested)
    return sources


def _get_rank_from_sources(sources: Iterable[Any], attr_names: Iterable[str]) -> int:
    for source in sources:
        for attr_name in attr_names:
            rank = _as_rank(getattr(source, attr_name, None))
            if rank >= 0:
                return rank
    return -1


def _ensure_sglang_rank_meta_collected(*objects: Any) -> None:
    meta_state = get_meta_state()
    sources = _iter_rank_sources(*objects)
    if meta_state.dp_rank < 0:
        dp_rank = _get_rank_from_sources(sources, ("dp_rank", "data_parallel_rank", "data_parallel_rank_id"))
        if dp_rank >= 0:
            meta_state.dp_rank = dp_rank
    if meta_state.get("tp_rank", -1) < 0:
        tp_rank = _get_rank_from_sources(sources, ("tp_rank", "tensor_parallel_rank", "tensor_parallel_rank_id"))
        if tp_rank >= 0:
            meta_state.set("tp_rank", tp_rank)


def _iter_requests(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, dict):
        return list(value.values())
    for attr in ("reqs", "requests", "batch", "new_reqs"):
        nested = getattr(value, attr, None)
        if nested is not None and nested is not value:
            return _iter_requests(nested)
    if _looks_like_sglang_batch(value):
        return []
    return [value]


def _looks_like_sglang_batch(value: Any) -> bool:
    class_name = type(value).__name__.lower()
    if "batch" in class_name:
        return True
    return any(hasattr(value, attr) for attr in ("batch_size", "bs", "num_reqs"))


def _count_batch_requests(batch: Any) -> int:
    if batch is None:
        return 0
    for attr in ("batch_size", "bs", "num_reqs"):
        count = _as_rank(getattr(batch, attr, None))
        if count >= 0:
            return count
    for attr in ("input_ids", "input_token_ids", "output_ids", "output_token_ids"):
        count = _len_dim0(getattr(batch, attr, None))
        if count:
            return count
    return 0


def _count_tokens_from_value(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    numel = getattr(value, "numel", None)
    if callable(numel):
        try:
            return int(numel())
        except Exception:
            return 0
    shape = getattr(value, "shape", None)
    if shape is not None:
        try:
            total = 1
            for dim in shape:
                total *= int(dim)
            return total
        except Exception:
            return 0
    return _len_dim0(value)


def _count_tokens_from_reqs(reqs: Iterable[Any], attr_names: Iterable[str]) -> int:
    total = 0
    for req in reqs:
        value = _first_present(req, attr_names)
        total += _count_tokens_from_value(value)
    return total


def _count_tokens_from_batch(batch: Any, attr_names: Iterable[str]) -> int:
    return _count_tokens_from_value(_first_present(batch, attr_names))


def _looks_like_scheduler(value: Any) -> bool:
    if value is None:
        return False
    if "scheduler" in type(value).__name__.lower():
        return True
    return any(
        hasattr(value, attr)
        for attr in (
            "waiting_queue",
            "running_batch",
            "tree_cache",
            "req_to_token_pool",
            "token_to_kv_pool_allocator",
            "cache_controller",
        )
    )


def _queue_len(value: Any) -> int:
    count = _count_batch_requests(value)
    if count:
        return count
    batch_size = getattr(value, "batch_size", None)
    if callable(batch_size):
        try:
            return int(batch_size())
        except Exception:
            return 0
    return _safe_len(value)


def _infer_phase(batch: Any = None, ret: Any = None) -> str:
    for candidate in (batch, ret):
        if candidate is None:
            continue
        if getattr(candidate, "is_prefill", False):
            return "prefill"
        if getattr(candidate, "is_decode", False):
            return "decode"
        mode = str(_first_present(candidate, ("forward_mode", "batch_type", "phase", "mode")) or "").lower()
        if "prefill" in mode or "extend" in mode:
            return "prefill"
        if "decode" in mode:
            return "decode"
    return get_meta_state().get("phase", "mixed")


def _extract_batch(args: tuple, kwargs: dict, ret: Any = None) -> Any:
    for name in ("batch", "forward_batch", "model_worker_batch", "scheduler_batch"):
        if name in kwargs:
            return kwargs[name]
    for candidate in (ret, *args):
        if candidate is None:
            continue
        if _looks_like_sglang_batch(candidate) or any(
            hasattr(candidate, attr) for attr in ("batch", "reqs", "requests")
        ):
            return candidate
    return args[0] if args else ret


def _record_configured(
    metrics_config: List[Any],
    duration: float,
    ret: Any = None,
    labels: Optional[Dict[str, str]] = None,
) -> None:
    del ret
    for metric in metrics_config:
        name = _metric_get(metric, "name", "")
        if not name:
            continue
        metric_type = _metric_type(_metric_get(metric, "type", MetricType.TIMER))
        label_names = _label_names(metric)
        for label_name in labels or {}:
            if label_name not in label_names:
                label_names.append(label_name)
        _register(name, metric_type, label_names, _metric_get(metric, "buckets"))
        value = duration if metric_type == MetricType.TIMER else 1
        _record(name, value, labels)


def _operation_from_metrics(metrics_config: List[Any], prefix: str, default: str) -> str:
    for metric in metrics_config:
        name = _metric_get(metric, "name", "")
        if name.startswith(prefix) and name.endswith(":duration"):
            return name[len(prefix) : -len(":duration")]
    return default


def phase_timer_handler(metrics_config, is_async: bool = False, phase: str = "mixed", **_kwargs) -> Callable:
    """Record configured timer metrics with a fixed phase."""
    for metric in metrics_config:
        _register(
            _metric_get(metric, "name", ""),
            _metric_type(_metric_get(metric, "type", MetricType.TIMER)),
            _label_names(metric),
            _metric_get(metric, "buckets"),
        )

    if is_async:

        async def async_handler(ori, *args, **kwargs):
            start = time.time()
            with _phase_scope(phase):
                ret = await ori(*args, **kwargs)
            _record_configured(metrics_config, time.time() - start, ret)
            return ret

        return async_handler

    def sync_handler(ori, *args, **kwargs):
        start = time.time()
        with _phase_scope(phase):
            ret = ori(*args, **kwargs)
        _record_configured(metrics_config, time.time() - start, ret)
        return ret

    return sync_handler


for _metric_name, _metric_kind, _labels in (
    ("request:http_total", MetricType.COUNTER, ["operation"]),
    ("request:tokens", MetricType.HISTOGRAM, ["direction"]),
    ("request:response_events_total", MetricType.COUNTER, ["event"]),
):
    _register(
        _metric_name,
        _metric_kind,
        _labels,
        SIZE_BUCKETS if _metric_kind == MetricType.HISTOGRAM else None,
    )


def request_io_handler(metrics_config, is_async: bool = False, operation: str = "request", **_kwargs) -> Callable:
    """Record frontend request/tokenizer/detokenizer costs and token counts."""
    del is_async
    operation = _operation_from_metrics(metrics_config, "request:", operation)

    async def _await_result(awaitable, start, args, kwargs):
        ret = await awaitable
        _ensure_sglang_rank_meta_collected(*args, ret)
        _record_request_metrics(
            metrics_config,
            time.time() - start,
            ret,
            operation,
            args=args,
            kwargs=kwargs,
        )
        return ret

    def handler(ori, *args, **kwargs):
        _ensure_sglang_rank_meta_collected(*args)
        start = time.time()
        try:
            ret = ori(*args, **kwargs)
        except Exception:
            _record("request:http_total", 1, {"operation": f"{operation}_error"})
            raise
        if inspect.isawaitable(ret):
            return _await_result(ret, start, args, kwargs)
        _ensure_sglang_rank_meta_collected(*args, ret)
        _record_request_metrics(
            metrics_config,
            time.time() - start,
            ret,
            operation,
            args=args,
            kwargs=kwargs,
        )
        return ret

    return handler


def _record_request_metrics(metrics_config, duration, ret, operation, args=None, kwargs=None):
    del kwargs
    with _phase_scope("all"):
        _record("request:http_total", 1, {"operation": operation})
        _record_configured(metrics_config, duration, ret, {"operation": operation})
        reqs = _iter_requests(ret)
        if not reqs and args:
            reqs = _iter_requests(args[-1])
        batch = _extract_batch(args or (), {}, ret)
        input_tokens = _count_tokens_from_reqs(reqs, ("input_ids", "input_token_ids", "origin_input_ids"))
        if not input_tokens:
            input_tokens = _count_tokens_from_batch(batch, ("input_ids", "input_token_ids", "origin_input_ids"))
        output_tokens = _count_tokens_from_reqs(reqs, ("output_ids", "output_token_ids", "output_token_logprobs"))
        if not output_tokens:
            output_tokens = _count_tokens_from_batch(batch, ("output_ids", "output_token_ids", "output_token_logprobs"))
        if input_tokens > 0:
            _record("request:tokens", input_tokens, {"direction": "input"})
        if output_tokens > 0:
            _record("request:tokens", output_tokens, {"direction": "output"})
        if operation in {"wait_response", "detokenize"}:
            _record("request:response_events_total", 1, {"event": operation})


for _metric_name, _metric_kind, _labels in (
    ("scheduler:recv_requests_total", MetricType.COUNTER, None),
    ("scheduler:enqueue_requests_total", MetricType.COUNTER, None),
    ("scheduler:dequeue_requests_total", MetricType.COUNTER, None),
    ("scheduler:waiting_queue_size", MetricType.GAUGE, None),
    ("scheduler:running_queue_size", MetricType.GAUGE, None),
    ("scheduler:batch_size", MetricType.HISTOGRAM, ["batch_phase"]),
    ("scheduler:input_tokens", MetricType.HISTOGRAM, ["batch_phase"]),
    ("scheduler:output_tokens", MetricType.HISTOGRAM, ["batch_phase"]),
    ("scheduler:free_kvcache_blocks", MetricType.GAUGE, None),
    ("scheduler:evictable_kvcache_blocks", MetricType.GAUGE, None),
    ("scheduler:swa_available_blocks", MetricType.GAUGE, None),
    ("scheduler:swa_evictable_blocks", MetricType.GAUGE, None),
    ("scheduler:prefix_cache_hit_rate", MetricType.GAUGE, None),
    ("scheduler:prefill_end_total", MetricType.COUNTER, None),
    ("scheduler:decode_end_total", MetricType.COUNTER, None),
    ("scheduler:exceptions_total", MetricType.COUNTER, ["operation", "exception_type"]),
):
    _register(
        _metric_name,
        _metric_kind,
        _labels,
        SIZE_BUCKETS if _metric_kind == MetricType.HISTOGRAM else None,
    )


def scheduler_handler(metrics_config, is_async: bool = False, operation: str = "scheduler", **_kwargs) -> Callable:
    """Record scheduler loop, queue, batch and KV cache metrics."""
    del is_async
    operation = _operation_from_metrics(metrics_config, "scheduler:", operation)

    async def _await_result(awaitable, self_obj, start, args, kwargs):
        ret = await awaitable
        _record_scheduler_metrics(metrics_config, time.time() - start, self_obj, ret, args, kwargs, operation)
        return ret

    def handler(ori, self_obj, *args, **kwargs):
        batch = _extract_batch(args, kwargs)
        _ensure_sglang_rank_meta_collected(self_obj, batch)
        phase = _infer_phase(batch)
        with _phase_scope(phase):
            start = time.time()
            try:
                ret = ori(self_obj, *args, **kwargs)
            except Exception as exc:
                _record(
                    "scheduler:exceptions_total",
                    1,
                    {
                        "operation": operation,
                        "exception_type": type(exc).__name__,
                    },
                )
                raise
        if inspect.isawaitable(ret):
            return _await_result(ret, self_obj, start, args, kwargs)
        _record_scheduler_metrics(metrics_config, time.time() - start, self_obj, ret, args, kwargs, operation)
        return ret

    return handler


def _record_scheduler_metrics(metrics_config, duration, self_obj, ret, args, kwargs, operation):
    batch = _extract_batch(args, kwargs, ret)
    _ensure_sglang_rank_meta_collected(self_obj, batch, ret)
    phase = _infer_phase(batch, ret)
    with _phase_scope(phase):
        _record_configured(metrics_config, duration, ret, {"operation": operation})
        if _looks_like_scheduler(self_obj):
            _record_queue_metrics(self_obj)
            _record_kvcache_metrics(self_obj)
        reqs = _iter_requests(batch) or _iter_requests(ret)
        req_count = _safe_len(reqs) or _count_batch_requests(batch) or _count_batch_requests(ret)
        if operation in {"recv_requests", "handle_generate_request", "handle_embedding_request"} and req_count:
            _record("scheduler:recv_requests_total", req_count)
        if (
            operation
            in {
                "add_request_to_queue",
                "handle_generate_request",
                "handle_embedding_request",
            }
            and req_count
        ):
            _record("scheduler:enqueue_requests_total", req_count)
        if operation in {"get_new_batch_prefill", "get_next_batch_to_run", "run_batch"} and req_count:
            _record("scheduler:dequeue_requests_total", req_count)
        if req_count:
            _record("scheduler:batch_size", req_count, {"batch_phase": phase})
        input_tokens = _count_tokens_from_reqs(reqs, ("input_ids", "input_token_ids", "origin_input_ids", "fill_ids"))
        if not input_tokens:
            input_tokens = _count_tokens_from_batch(
                batch, ("input_ids", "input_token_ids", "origin_input_ids", "fill_ids")
            )
        output_tokens = _count_tokens_from_reqs(reqs, ("output_ids", "output_token_ids", "decoded_text"))
        if not output_tokens:
            output_tokens = _count_tokens_from_batch(batch, ("output_ids", "output_token_ids", "decoded_text"))
        if input_tokens:
            _record("scheduler:input_tokens", input_tokens, {"batch_phase": phase})
        if output_tokens:
            _record("scheduler:output_tokens", output_tokens, {"batch_phase": phase})
        if operation in {"process_batch_result_prefill", "get_new_batch_prefill"} and req_count:
            _record("scheduler:prefill_end_total", req_count)
        if (
            operation in {"process_batch_result_decode", "process_batch_result"}
            and phase in {"decode", "mixed"}
            and req_count
        ):
            _record("scheduler:decode_end_total", req_count)


def _record_queue_metrics(scheduler: Any) -> None:
    waiting = _first_present(scheduler, ("waiting_queue", "waiting"))
    running = _first_present(scheduler, ("running_batch", "running_queue", "running"))
    _record("scheduler:waiting_queue_size", _queue_len(waiting))
    _record("scheduler:running_queue_size", _queue_len(running))


def _record_kvcache_metrics(scheduler: Any) -> None:
    cache = _first_present(
        scheduler,
        (
            "tree_cache",
            "req_to_token_pool",
            "token_to_kv_pool_allocator",
            "cache_controller",
        ),
    )
    if cache is None:
        return
    accessors = {
        "scheduler:free_kvcache_blocks": (
            "free_size",
            "available_size",
            "num_free_blocks",
            "available_blocks",
        ),
        "scheduler:evictable_kvcache_blocks": (
            "evictable_size",
            "evictable_blocks",
            "num_evictable_blocks",
        ),
        "scheduler:swa_available_blocks": (
            "swa_available_blocks",
            "swa_available_size",
        ),
        "scheduler:swa_evictable_blocks": (
            "swa_evictable_blocks",
            "swa_evictable_size",
        ),
        "scheduler:prefix_cache_hit_rate": ("hit_rate", "prefix_cache_hit_rate"),
    }
    for metric_name, attrs in accessors.items():
        value = _first_present(cache, attrs)
        if value is not None:
            _record(metric_name, _as_number(value))


for _metric_name in ("model:batch_size", "model:input_tokens", "model:output_tokens"):
    _register(_metric_name, MetricType.HISTOGRAM, ["batch_phase"], SIZE_BUCKETS)


def model_handler(metrics_config, is_async: bool = False, operation: str = "model", **_kwargs) -> Callable:
    """Record model preprocessing, forward, sampling and postprocess metrics."""
    operation = _operation_from_metrics(metrics_config, "model:", operation)

    async def _await_result(awaitable, batch, start):
        ret = await awaitable
        _record_model_metrics(metrics_config, time.time() - start, batch, ret, operation)
        return ret

    if is_async:

        async def async_handler(ori, self_obj, *args, **kwargs):
            batch = _extract_batch(args, kwargs)
            _ensure_sglang_rank_meta_collected(self_obj, batch)
            phase = _infer_phase(batch)
            with _phase_scope(phase):
                start = time.time()
                ret = ori(self_obj, *args, **kwargs)
                if inspect.isawaitable(ret):
                    ret = await ret
            _record_model_metrics(metrics_config, time.time() - start, batch, ret, operation)
            return ret

        return async_handler

    def handler(ori, self_obj, *args, **kwargs):
        batch = _extract_batch(args, kwargs)
        _ensure_sglang_rank_meta_collected(self_obj, batch)
        phase = _infer_phase(batch)
        with _phase_scope(phase):
            start = time.time()
            ret = ori(self_obj, *args, **kwargs)
        if inspect.isawaitable(ret):
            return _await_result(ret, batch, start)
        _record_model_metrics(metrics_config, time.time() - start, batch, ret, operation)
        return ret

    return handler


def _record_model_metrics(metrics_config, duration, batch, ret, operation):
    _ensure_sglang_rank_meta_collected(batch, ret)
    phase = _infer_phase(batch, ret)
    with _phase_scope(phase):
        _record_configured(metrics_config, duration, ret, {"operation": operation})
        reqs = _iter_requests(batch)
        req_count = _safe_len(reqs) or _count_batch_requests(batch) or _count_batch_requests(ret)
        if req_count:
            _record("model:batch_size", req_count, {"batch_phase": phase})
        input_tokens = _count_tokens_from_reqs(reqs, ("input_ids", "input_token_ids", "extend_input_ids"))
        if not input_tokens:
            input_tokens = _count_tokens_from_batch(batch, ("input_ids", "input_token_ids", "extend_input_ids"))
        output_tokens = _count_tokens_from_reqs(reqs, ("output_ids", "output_token_ids"))
        if not output_tokens:
            output_tokens = _count_tokens_from_batch(batch, ("output_ids", "output_token_ids"))
        if input_tokens:
            _record("model:input_tokens", input_tokens, {"batch_phase": phase})
        if output_tokens:
            _record("model:output_tokens", output_tokens, {"batch_phase": phase})
