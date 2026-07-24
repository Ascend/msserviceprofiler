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
"""
vLLM Metric Handlers (v1)

从重构前的 ms_service_profiler/patcher/vllm/handlers/v1/metric_handlers.py 迁移
提供vLLM v1特定的metric处理函数。
"""

import inspect
import time
from typing import Any, NamedTuple

from ms_service_metric.utils.logger import get_logger
from ms_service_metric.metrics.metrics_manager import get_metrics_manager, MetricType, SIZE_BUCKETS
from ms_service_metric.adapters.vllm.handlers.utils import (
    clear_request_phase_state as _clear_request_phase_state,
    collect_phase_metrics as _collect_phase_metrics,
    get_scheduler_phase_state as _get_scheduler_phase_state,
    get_batch_phase_details as _get_batch_phase_details,
    phase_scope as _phase_scope,
    meta_state_scope as _meta_state_scope,
    _iter_cached_req_id_and_num_comp,
)
from ms_service_metric.metrics.meta_state import get_meta_state
from ms_service_metric.handlers.builtin import default_handler
from ms_service_metric.utils.expr_eval import ExprEval

logger = get_logger(__name__)
metrics_client = get_metrics_manager()

GIB_BYTES = 1024**3

_PHASE_SENSITIVE_OPERATION_NAMES = frozenset(
    {
        "prepare input",
        "forward",
        "post process",
        "sample_token",
        "draft_token",
    }
)


def _with_phase_all(labels: dict[str, str] | None = None) -> dict[str, str]:
    fixed_labels = labels.copy() if labels is not None else {}
    fixed_labels.setdefault("phase", "all")
    return fixed_labels


class TimeRecord(NamedTuple):
    start: float
    end: float


class Timeline:
    """时间线记录器

    用于记录和计算特定时间段内的耗时。
    """

    duration_config = {
        "npu:forward_duration": ("forward", "model_runner_get_output"),
        "npu:kernel_launch": ("forward", "post process"),
        "npu:non_forward_duration": ("model_runner_get_output", "post process", "end"),
    }

    def __init__(self):
        self.time_record_set = {value[0] for value in self.duration_config.values()}
        self.time_record_set.add("model_runner_get_output")
        self.duration_activate_dict = {}
        for metric, config in self.duration_config.items():
            start, trigger = config[:2]
            start_point = config[2] if len(config) > 2 else "start"
            self.duration_activate_dict.setdefault(trigger, []).append((start, metric, start_point))
        self.time_recorded = {}
        for metric_name in self.duration_config:
            metrics_client.get_or_create_metric(metric_name)

    def record(self, name, start_time, duration):
        if name in self.time_record_set:
            self.time_recorded[name] = TimeRecord(start_time, start_time + duration)

        end_time = start_time + duration
        for start_name, metric_name, start_point in self.duration_activate_dict.get(name, ()):
            start_record = self.time_recorded.get(start_name)
            if start_record is None:
                continue
            start_value = getattr(start_record, start_point)
            duration_value = end_time - start_value
            if duration_value < 0:
                logger.debug(
                    "Negative duration detected for %s: %.6f, start=%s.%s=%.6f, end=%s.%s=%.6f",
                    metric_name,
                    duration_value,
                    start_name,
                    start_point,
                    start_value,
                    name,
                    "end",
                    end_time,
                )
                continue
            metrics_client.record_metric(metric_name, duration_value, _with_phase_all())


timeline_recorder: Timeline = Timeline()


def _extract_scheduler_output_from_model_runner(self) -> Any:
    execute_model_state = getattr(self, "execute_model_state", None)
    if execute_model_state is not None:
        try:
            candidate = execute_model_state[0]
            if hasattr(candidate, "scheduled_new_reqs") or hasattr(candidate, "num_scheduled_tokens"):
                return candidate
        except Exception:
            return None
    return None


def _infer_model_runner_phase(self) -> tuple[str, dict[str, int] | None]:
    scheduler_output = _extract_scheduler_output_from_model_runner(self)
    if scheduler_output is None:
        return "mixed", None
    return _get_batch_phase_details(_get_scheduler_phase_state(), scheduler_output)


def _infer_phase_from_iteration_stats(iteration_stats: Any) -> str:
    if iteration_stats is None:
        return "mixed"
    num_prompt_tokens = getattr(iteration_stats, "num_prompt_tokens", 0) or 0
    num_generation_tokens = getattr(iteration_stats, "num_generation_tokens", 0) or 0
    if num_prompt_tokens > 0 >= num_generation_tokens:
        return "prefill"
    if num_prompt_tokens <= 0 < num_generation_tokens:
        return "decode"
    if num_prompt_tokens > 0 and num_generation_tokens > 0:
        return "mixed"
    return "mixed"


def _infer_iteration_stats_from_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    iteration_stats = kwargs.get("iteration_stats")
    if iteration_stats is not None:
        return iteration_stats
    for arg in args:
        if hasattr(arg, "num_prompt_tokens") and hasattr(arg, "num_generation_tokens"):
            return arg
    return None


def _resolve_phase_from_iteration_stats_or_last(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    iteration_stats = _infer_iteration_stats_from_args(args, kwargs)
    phase = _infer_phase_from_iteration_stats(iteration_stats)
    if phase != "mixed":
        return phase
    return get_meta_state().get("last_async_llm_phase", "mixed")


def _build_metrics_recorder(metrics_config, default_labels: dict[str, str] | None = None):
    manager = get_metrics_manager()
    default_labels = default_labels or {}
    expr_evaluators = {}
    label_evaluators = {}
    for metric in metrics_config:
        metric_name = metric.get('name', '')
        metric_type = metric.get('type', 'timer')
        expr = metric.get('expr', '')
        if expr:
            try:
                expr_evaluators[metric_name] = ExprEval(expr)
            except Exception as e:
                logger.debug("Failed to compile expr for metric %s: %s", metric_name, e)
        label_exprs = {}
        for label_name, label_expr in metric.get('labels', {}).items():
            if label_name and label_expr:
                try:
                    label_exprs[label_name] = ExprEval(label_expr)
                except Exception as e:
                    logger.debug("Failed to compile label expr for %s: %s", label_name, e)
        if label_exprs:
            label_evaluators[metric_name] = label_exprs
        manager.get_or_create_metric(
            metric_name=metric_name,
            metric_type=metric_type,
            buckets=metric.get('buckets'),
            label_names=list(label_exprs.keys()),
        )

    def _record(duration, ret, local_values=None):
        eval_context = {'duration': duration, 'ret': ret}
        if local_values:
            eval_context.update(local_values)
        for metric in metrics_config:
            name = metric.get('name', '')
            metric_type_str = metric.get('type', 'timer')
            if metric_type_str == 'timer':
                value = duration
            else:
                evaluator = expr_evaluators.get(name)
                if evaluator:
                    try:
                        value = evaluator(eval_context)
                    except Exception:
                        value = 1
                else:
                    value = 1
            labels = {}
            labels.update(default_labels)
            for label_name, evaluator in label_evaluators.get(name, {}).items():
                try:
                    labels[label_name] = evaluator(eval_context)
                except Exception:  # nosec B110
                    pass
            manager.record_metric(name, value, labels)

    return _record


def phase_all_handler(metrics_config, is_async: bool = False, **_kwargs):
    """Record metrics that are not semantically split by prefill/decode phase."""
    record = _build_metrics_recorder(metrics_config, default_labels=_with_phase_all())
    if is_async:

        async def async_handler(ori, *args, **kwargs):
            start_time = time.time()
            ret = await ori(*args, **kwargs)
            record(time.time() - start_time, ret)
            return ret

        return async_handler

    def sync_handler(ori, *args, **kwargs):
        start_time = time.time()
        ret = ori(*args, **kwargs)
        record(time.time() - start_time, ret)
        return ret

    return sync_handler


def _format_gib_value(b: int) -> float:
    return round(b / GIB_BYTES, 2)


def _get_metric_config_value(metric_config, key: str, default=None):
    if hasattr(metric_config, "get"):
        return metric_config.get(key, default)
    return getattr(metric_config, key, default)


_ENGINE_MEMORY_METRIC_ACCESSORS = {
    "engine:memory:total_gb": lambda self: _format_gib_value(self.init_snapshot.total_memory),
    "engine:memory:utilization_ratio": lambda self: self.cache_config.gpu_memory_utilization,
    "engine:memory:reserved_gb": lambda self: _format_gib_value(self.requested_memory),
    "engine:memory:weights_gb": lambda self: _format_gib_value(self.model_runner.model_memory_usage),
    "engine:memory:kvcache_gb": lambda self: _format_gib_value(self.available_kv_cache_memory_bytes),
    "engine:memory:non_torch_gb": lambda self: _format_gib_value(self.non_torch_memory),
    "engine:memory:activation_gb": lambda self: _format_gib_value(self.peak_activation_memory),
    "engine:memory:graph_gb": lambda self: _format_gib_value(self.npugraph_memory_bytes),
}


_RUNTIME_MEMORY_METRIC_ACCESSORS = {
    "engine:memory:torch_reserved_gb": lambda self: _format_gib_value(self.torch_reserved),
    "engine:memory:torch_allocated_gb": lambda self: _format_gib_value(self.torch_allocated),
}


def engine_memory_phase_handler(metrics_config, **_kwargs):
    """Record one-shot engine memory metrics after worker initialization."""
    configured_metrics = []
    for m in metrics_config:
        metric_name = _get_metric_config_value(m, "name", "")
        if not metric_name:
            continue
        configured_metrics.append(metric_name)
        metrics_client.get_or_create_metric(metric_name, metric_type=MetricType.GAUGE)

    def handler(ori, self, *args, **kwargs):
        ret = ori(self, *args, **kwargs)
        try:
            for name in configured_metrics:
                accessor = _ENGINE_MEMORY_METRIC_ACCESSORS.get(name)
                if accessor is None:
                    logger.debug("Skip unknown engine memory metric: %s", name)
                    continue
                metrics_client.record_metric(name, accessor(self), _with_phase_all())
        except Exception:
            logger.warning("Failed to record engine memory metrics", exc_info=True)
        return ret

    return handler


def runtime_memory_phase_handler(metrics_config, **_kwargs):
    """Record runtime torch memory metrics after vllm-ascend refreshes them."""
    configured_metrics = []
    for m in metrics_config:
        metric_name = _get_metric_config_value(m, "name", "")
        if not metric_name:
            continue
        configured_metrics.append(metric_name)
        metrics_client.get_or_create_metric(metric_name, metric_type=MetricType.GAUGE)

    def handler(ori, self, *args, **kwargs):
        ret = ori(self, *args, **kwargs)
        try:
            for name in configured_metrics:
                accessor = _RUNTIME_MEMORY_METRIC_ACCESSORS.get(name)
                if accessor is None:
                    logger.debug("Skip unknown runtime memory metric: %s", name)
                    continue
                metrics_client.record_metric(name, accessor(self), _with_phase_all())
        except Exception:
            logger.warning("Failed to record runtime memory metrics", exc_info=True)
        return ret

    return handler


def process_outputs_phase_handler(metrics_config, is_async: bool = False, **kwargs):
    record = _build_metrics_recorder(metrics_config)
    if is_async:

        async def async_handler(ori, *args, **kwargs):
            phase = _resolve_phase_from_iteration_stats_or_last(args, kwargs)
            logger.debug("process_outputs phase=%s", phase)
            with _meta_state_scope(get_meta_state(), {"phase": phase, "last_async_llm_phase": phase}):
                start_time = time.time()
                ret = await ori(*args, **kwargs)
                duration = time.time() - start_time
                engine_core_outputs = args[1] if len(args) > 1 else kwargs.get("engine_core_outputs")
                record(
                    duration,
                    ret,
                    {"engine_core_outputs": engine_core_outputs} if engine_core_outputs is not None else {},
                )
                return ret

        return async_handler

    def sync_handler(ori, *args, **kwargs):
        phase = _resolve_phase_from_iteration_stats_or_last(args, kwargs)
        logger.debug("process_outputs phase=%s", phase)
        with _meta_state_scope(get_meta_state(), {"phase": phase, "last_async_llm_phase": phase}):
            start_time = time.time()
            ret = ori(*args, **kwargs)
            duration = time.time() - start_time
            engine_core_outputs = args[1] if len(args) > 1 else kwargs.get("engine_core_outputs")
            record(
                duration, ret, {"engine_core_outputs": engine_core_outputs} if engine_core_outputs is not None else {}
            )
            return ret

    return sync_handler


def record_stats_phase_handler(metrics_config, is_async: bool = False, **kwargs):
    base_handler = default_handler(metrics_config, is_async=is_async, **kwargs)
    if is_async:

        async def async_handler(ori, *args, **kwargs):
            phase = _resolve_phase_from_iteration_stats_or_last(args, kwargs)
            logger.debug("record_stats phase=%s", phase)
            with _meta_state_scope(get_meta_state(), {"phase": phase, "last_async_llm_phase": phase}):
                return await base_handler(ori, *args, **kwargs)

        return async_handler

    def sync_handler(ori, *args, **kwargs):
        phase = _resolve_phase_from_iteration_stats_or_last(args, kwargs)
        logger.debug("record_stats phase=%s", phase)
        with _meta_state_scope(get_meta_state(), {"phase": phase, "last_async_llm_phase": phase}):
            return base_handler(ori, *args, **kwargs)

    return sync_handler


def abort_requests_phase_handler(metrics_config, is_async: bool = False, **kwargs):
    base_handler = default_handler(metrics_config, is_async=is_async, **kwargs)
    if is_async:

        async def async_handler(ori, *args, **kwargs):
            meta_state = get_meta_state()
            phase = meta_state.get("last_async_llm_phase", meta_state.get("phase", "mixed"))
            logger.debug("abort_requests phase=%s", phase)
            with _phase_scope(meta_state, phase):
                return await base_handler(ori, *args, **kwargs)

        return async_handler

    def sync_handler(ori, *args, **kwargs):
        meta_state = get_meta_state()
        phase = meta_state.get("last_async_llm_phase", meta_state.get("phase", "mixed"))
        logger.debug("abort_requests phase=%s", phase)
        with _phase_scope(meta_state, phase):
            return base_handler(ori, *args, **kwargs)

    return sync_handler


class TimingContextManager:
    """用于计时的上下文管理器包装类。

    包装原始的上下文管理器，在进入和退出时记录执行时间，
    并将耗时作为 timer 指标记录到 Prometheus。
    """

    def __init__(self, label_name: str, original_context: Any):
        self.label_name = label_name
        self.original_context = original_context
        self.start_time: float = 0.0
        self._captured_phase: str = "mixed"
        self._captured_role: str = "mixed"

    def __enter__(self):
        self.start_time = time.time()
        meta_state = get_meta_state()
        self._captured_phase = meta_state.get("phase", "mixed")
        if self.label_name in ("sample_token", "draft_token"):
            self._captured_phase = meta_state.get("last_model_runner_phase", self._captured_phase)
        self._captured_role = meta_state.get("pd_role", meta_state.get("role", "mixed"))
        logger.debug("TimingContextManager.enter: name=%s phase=%s", self.label_name, self._captured_phase)
        return self.original_context.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            duration = time.time() - self.start_time
            logger.debug(
                "TimingContextManager.exit: name=%s phase=%s duration=%.4f",
                self.label_name,
                self._captured_phase,
                duration,
            )
            metrics_client.record_metric(
                "record_function_or_nullcontext",
                duration,
                {
                    "name": self.label_name,
                    "phase": self._captured_phase,
                    "role": self._captured_role,
                },
            )
            timeline_recorder.record(self.label_name, self.start_time, duration)
        return self.original_context.__exit__(exc_type, exc_val, exc_tb)


metrics_client.get_or_create_metric("record_function_or_nullcontext", ["name"])


def record_function_timer_hook(original_func, name, *args, **kwargs):
    """record_function_or_nullcontext 的 hook 处理函数。"""
    original_context = original_func(name, *args, **kwargs)
    return TimingContextManager(name, original_context)


def record_function_timer_hook_vllm_ascend(original_func, self, name, *args, **kwargs):
    """vllm_ascend 的 record_function_or_nullcontext hook 处理函数。"""
    phase = "mixed"
    phase_detail = None
    if name in _PHASE_SENSITIVE_OPERATION_NAMES:
        phase, phase_detail = _infer_model_runner_phase(self)
        logger.debug("batch phase detail: name=%s phase=%s detail=%s", name, phase, phase_detail)
    original_context = original_func(self, name, *args, **kwargs)
    if phase == "mixed":
        return TimingContextManager(name, original_context)

    meta_state = get_meta_state()

    class PhaseTimingContextManager(TimingContextManager):
        def __init__(self, label_name: str, wrapped_context: Any):
            super().__init__(label_name, wrapped_context)
            self._phase_cm = None

        def __enter__(self):
            self._phase_cm = _phase_scope(meta_state, phase)
            self._phase_cm.__enter__()
            return super().__enter__()

        def __exit__(self, exc_type, exc_val, exc_tb):
            try:
                return super().__exit__(exc_type, exc_val, exc_tb)
            finally:
                if self._phase_cm is not None:
                    self._phase_cm.__exit__(exc_type, exc_val, exc_tb)

    return PhaseTimingContextManager(name, original_context)


metrics_client.get_or_create_metric("worker:model_runner_get_output:duration")


def runner_get_output_hooker(original_func, *args, **kwargs):
    """ModelRunner.get_output 的 hook 处理函数。"""
    start_time = time.time()
    ret = original_func(*args, **kwargs)
    duration = time.time() - start_time

    metrics_client.record_metric("worker:model_runner_get_output:duration", duration, _with_phase_all())
    timeline_recorder.record("model_runner_get_output", start_time, duration)
    return ret


metrics_client.get_or_create_metric("scheduler:duration")
metrics_client.get_or_create_metric("scheduler:batch_size", buckets=SIZE_BUCKETS)
metrics_client.get_or_create_metric("scheduler:running_queue_size", buckets=SIZE_BUCKETS)
metrics_client.get_or_create_metric("scheduler:seqlen:avg", metric_type=MetricType.GAUGE, buckets=SIZE_BUCKETS)
metrics_client.get_or_create_metric("scheduler:seqlen:sum", metric_type=MetricType.GAUGE, buckets=SIZE_BUCKETS)
metrics_client.get_or_create_metric("scheduler:phase_batch_size", ["req_phase"], buckets=SIZE_BUCKETS)
metrics_client.get_or_create_metric("scheduler:recompute_events", metric_type=MetricType.COUNTER)
metrics_client.get_or_create_metric(
    "scheduler:phase_scheduled_token_counter", ["req_phase"], metric_type=MetricType.COUNTER
)
metrics_client.get_or_create_metric(
    "scheduler:phase_scheduled_tokens",
    ["req_phase"],
    metric_type=MetricType.HISTOGRAM,
    buckets=SIZE_BUCKETS,
)

RUNNING_TO_WAITING_COUNT = "running_to_waiting_count"
BLOCK_ALLOCATE_FAILURES = "block_allocate_failures"
RPC_ERRORS = "rpc_errors"
REQUEST_PREFILL_PENDING_NUMS = "request_prefill_pending_nums"
HEALTH_CHECK_FAILED = "health_check_failed"
_PENDING_RECORDED_ATTR = "_ms_service_metric_pending_recorded"
_HEALTH_WRAPPED_ATTR = "_ms_service_metric_health_wrapped"

metrics_client.get_or_create_metric(RUNNING_TO_WAITING_COUNT, metric_type=MetricType.COUNTER)
metrics_client.get_or_create_metric(BLOCK_ALLOCATE_FAILURES, metric_type=MetricType.COUNTER)
metrics_client.get_or_create_metric(RPC_ERRORS, ["exception_type"], metric_type=MetricType.COUNTER)
metrics_client.get_or_create_metric(REQUEST_PREFILL_PENDING_NUMS, metric_type=MetricType.COUNTER)
metrics_client.get_or_create_metric(HEALTH_CHECK_FAILED, metric_type=MetricType.COUNTER)


def _record_metric_safely(metric_name: str, value: int = 1, labels: dict[str, str] | None = None) -> None:
    try:
        metrics_client.record_metric(metric_name, value, _with_phase_all(labels))
    except Exception as exc:
        logger.warning("Failed to record metric %s safely: %s", metric_name, exc)


def _queue_has_items(queue: Any) -> bool:
    if queue is None:
        return False
    try:
        return len(queue) > 0
    except Exception:
        try:
            return bool(queue)
        except Exception as exc:
            logger.debug("Skip queue size check: %s", exc)
            return False


def _is_running_capacity_blocked(scheduler: Any) -> bool:
    running = getattr(scheduler, "running", None)
    max_num_running_reqs = getattr(scheduler, "max_num_running_reqs", None)
    if running is None or max_num_running_reqs is None:
        return False

    try:
        running_is_full = len(running) == max_num_running_reqs
    except Exception as exc:
        logger.debug("Skip running capacity check: %s", exc)
        return False

    if not running_is_full:
        return False

    return _queue_has_items(getattr(scheduler, "waiting", None)) or _queue_has_items(
        getattr(scheduler, "skipped_waiting", None)
    )


def _is_failed_allocation_result(ret: Any) -> bool:
    if ret is None or ret is False:
        return True
    for attr_name in ("failed", "is_failed", "allocation_failed"):
        attr = getattr(ret, attr_name, None)
        try:
            if attr() if callable(attr) else bool(attr):
                return True
        except Exception as exc:
            logger.debug("Skip failed allocation attribute '%s': %s", attr_name, exc)
    return False


def _get_exception_type(exc: BaseException) -> str:
    return type(exc).__name__


def scheduler_scheduler_hooker(original_func, self, *args, **kwargs):
    """Scheduler.schedule 的 hook 处理函数。"""
    if _is_running_capacity_blocked(self):
        if not getattr(self, _PENDING_RECORDED_ATTR, False):
            _record_metric_safely(REQUEST_PREFILL_PENDING_NUMS)
            setattr(self, _PENDING_RECORDED_ATTR, True)
    else:
        setattr(self, _PENDING_RECORDED_ATTR, False)

    start_time = time.time()
    ret = original_func(self, *args, **kwargs)
    duration = time.time() - start_time
    phase_metrics = _collect_phase_metrics(_get_scheduler_phase_state(), ret)

    scheduler_phase, batch_detail = _get_batch_phase_details(_get_scheduler_phase_state(), ret)
    logger.debug("scheduler phase=%s detail=%s", scheduler_phase, batch_detail)
    meta_state = get_meta_state()
    meta_state.set("last_scheduler_phase", scheduler_phase)
    meta_state.set("phase", scheduler_phase)

    phase_all_labels = _with_phase_all()
    metrics_client.record_metric("scheduler:duration", duration, phase_all_labels)
    metrics_client.record_metric("scheduler:batch_size", len(ret.num_scheduled_tokens), phase_all_labels)
    metrics_client.record_metric("scheduler:running_queue_size", len(self.running), phase_all_labels)

    seqlen_sum = 0
    seqlen_cnt = len(ret.scheduled_new_reqs) + len(ret.scheduled_cached_reqs.num_computed_tokens)

    for req in ret.scheduled_new_reqs:
        seqlen_sum += req.num_computed_tokens

    for num_computed_token in ret.scheduled_cached_reqs.num_computed_tokens:
        seqlen_sum += num_computed_token
    seqlen_sum += ret.total_num_scheduled_tokens

    if seqlen_cnt > 0 and seqlen_sum > 0:
        metrics_client.record_metric("scheduler:seqlen:avg", seqlen_sum / seqlen_cnt, phase_all_labels)
    if seqlen_sum > 0:
        metrics_client.record_metric("scheduler:seqlen:sum", seqlen_sum, phase_all_labels)

    for req_phase, phase_values in phase_metrics.items():
        labels = _with_phase_all({"req_phase": req_phase})
        batch_size = phase_values["batch_size"]
        scheduled_tokens_sum = phase_values["scheduled_tokens_sum"]
        if batch_size <= 0:
            continue
        metrics_client.record_metric("scheduler:phase_batch_size", batch_size, labels)
        metrics_client.record_metric("scheduler:phase_scheduled_tokens", scheduled_tokens_sum, labels)
        if scheduled_tokens_sum > 0:
            metrics_client.record_metric("scheduler:phase_scheduled_token_counter", scheduled_tokens_sum, labels)

    return ret


def engine_core_pending_hooker(original_func, self, *args, **kwargs):
    scheduler = getattr(self, "scheduler", None)
    if _is_running_capacity_blocked(scheduler):
        if not getattr(scheduler, _PENDING_RECORDED_ATTR, False):
            _record_metric_safely(REQUEST_PREFILL_PENDING_NUMS)
            setattr(scheduler, _PENDING_RECORDED_ATTR, True)
    elif scheduler is not None:
        setattr(scheduler, _PENDING_RECORDED_ATTR, False)
    return original_func(self, *args, **kwargs)


def scheduler_preempt_request_hooker(original_func, self, *args, **kwargs):
    ret = original_func(self, *args, **kwargs)
    _clear_request_phase_state(_get_scheduler_phase_state(), *args, *kwargs.values(), ret)
    metrics_client.record_metric(RUNNING_TO_WAITING_COUNT, 1, _with_phase_all())
    metrics_client.record_metric("scheduler:recompute_events", 1, _with_phase_all())
    return ret


def block_allocate_failure_hooker(original_func, self, *args, **kwargs):
    try:
        ret = original_func(self, *args, **kwargs)
    except Exception:
        metrics_client.record_metric(BLOCK_ALLOCATE_FAILURES, 1, _with_phase_all())
        raise

    if _is_failed_allocation_result(ret):
        metrics_client.record_metric(BLOCK_ALLOCATE_FAILURES, 1, _with_phase_all())

    return ret


def rpc_error_hooker(original_func, *args, **kwargs):
    try:
        return original_func(*args, **kwargs)
    except Exception as exc:
        metrics_client.record_metric(RPC_ERRORS, 1, _with_phase_all({"exception_type": _get_exception_type(exc)}))
        raise


def _is_engine_dead_error(exc: BaseException) -> bool:
    return _get_exception_type(exc) == "EngineDeadError"


def _record_health_check_failed_if_needed(ret: Any) -> Any:
    if getattr(ret, "status_code", None) == 503:
        _record_metric_safely(HEALTH_CHECK_FAILED)
    return ret


async def _await_health_result(awaitable):
    try:
        ret = await awaitable
    except Exception as exc:
        if _is_engine_dead_error(exc):
            _record_metric_safely(HEALTH_CHECK_FAILED)
        raise
    return _record_health_check_failed_if_needed(ret)


def health_check_failed_hooker(original_func, *args, **kwargs):
    try:
        ret = original_func(*args, **kwargs)
    except Exception as exc:
        if _is_engine_dead_error(exc):
            _record_metric_safely(HEALTH_CHECK_FAILED)
        raise

    if inspect.isawaitable(ret):
        return _await_health_result(ret)
    return _record_health_check_failed_if_needed(ret)


def _is_health_request(request: Any) -> bool:
    return getattr(getattr(request, "url", None), "path", None) == "/health"


def _wrap_health_check_once(client: Any) -> None:
    if client is None or getattr(client, _HEALTH_WRAPPED_ATTR, False):
        return

    check_health = getattr(client, "check_health", None)
    if not callable(check_health):
        logger.debug("Skip wrapping health client because check_health is not callable: %r", client)
        return

    async def wrapped_check_health(*args, **kwargs):
        try:
            ret = check_health(*args, **kwargs)
            if inspect.isawaitable(ret):
                ret = await ret
            return ret
        except Exception as exc:
            if _is_engine_dead_error(exc):
                _record_metric_safely(HEALTH_CHECK_FAILED)
            raise

    try:
        setattr(client, "check_health", wrapped_check_health)
        setattr(client, _HEALTH_WRAPPED_ATTR, True)
    except Exception as exc:
        logger.debug("Failed to wrap health client: %s", exc)


def health_engine_client_hooker(original_func, request, *args, **kwargs):
    client = original_func(request, *args, **kwargs)
    if _is_health_request(request):
        _wrap_health_check_once(client)
    return client


_EPLB_HOTNESS_SUMMARY_METRICS = (
    "eplb:expert_hotness:current_mean",
    "eplb:expert_hotness:current_max",
    "eplb:expert_hotness:update_mean",
    "eplb:expert_hotness:update_max",
)

for summary_metric_name in _EPLB_HOTNESS_SUMMARY_METRICS:
    metrics_client.get_or_create_metric(
        summary_metric_name,
        metric_type=MetricType.GAUGE,
        label_names=["rank"],
    )

metrics_client.get_or_create_metric(
    "eplb:expert_hotness:imbalance",
    metric_type=MetricType.GAUGE,
    label_names=["rank", "phase", "layer"],
)


def eplb_do_update_hotness_handler(original_func, self, *args, **kwargs):
    """Record EPLB hotness metrics exposed by vllm-ascend EplbWorker.

    Only rank 0 records hotness metrics because vllm-ascend computes and
    exposes the aggregated EPLB imbalance summary on rank 0.
    """
    result = original_func(self, *args, **kwargs)

    rank_id = getattr(self, "rank_id", -1)
    if rank_id != 0:
        return result

    hotness = getattr(self, "latest_expert_hotness", None)
    if not hotness:
        logger.debug("Skip EPLB hotness metrics because latest_expert_hotness is missing")
        return result

    labels = {"rank": str(rank_id)}
    for suffix in ("current_mean", "current_max", "update_mean", "update_max"):
        value = hotness.get(suffix)
        if value is None:
            logger.debug(
                "Skip EPLB hotness metric for rank %s because value '%s' is missing",
                rank_id,
                suffix,
            )
            continue
        metrics_client.record_metric(
            f"eplb:expert_hotness:{suffix}",
            value=float(value),
            labels=_with_phase_all(labels),
        )

    for phase, key in (
        ("current", "current_imbalance_list"),
        ("update", "update_imbalance_list"),
    ):
        imbalance_list = hotness.get(key)
        if imbalance_list is None:
            logger.debug("Skip EPLB %s imbalance metrics because %s is missing", phase, key)
            continue
        base_labels = {"rank": str(rank_id), "phase": phase}
        for layer_idx, value in enumerate(imbalance_list):
            base_labels["layer"] = str(layer_idx)
            metrics_client.record_metric(
                "eplb:expert_hotness:imbalance",
                value=float(value),
                labels=base_labels,
            )

    return result


def _infer_phase_from_scheduler_output(scheduler_output) -> str:
    if scheduler_output is None:
        return "mixed"
    has_new = bool(getattr(scheduler_output, "scheduled_new_reqs", None))
    has_cached = bool(list(_iter_cached_req_id_and_num_comp(getattr(scheduler_output, "scheduled_cached_reqs", None))))
    if has_new and not has_cached:
        return "prefill"
    if has_cached and not has_new:
        return "decode"
    if has_new and has_cached:
        return "mixed"
    return "mixed"


def _resolve_worker_phase(self, args=None) -> str:
    try:
        inferred_phase, _ = _infer_model_runner_phase(self)
        if inferred_phase != "mixed":
            return inferred_phase
    except Exception:
        logger.debug("Failed to infer model runner phase", exc_info=True)

    scheduler_output = None
    if args and len(args) > 0:
        scheduler_output = args[0]

    if scheduler_output is not None:
        phase = _infer_phase_from_scheduler_output(scheduler_output)
        if phase != "mixed":
            return phase

    return get_meta_state().get("pd_role", get_meta_state().get("role", "mixed"))


def model_runner_phase_handler(metrics_config, is_async: bool = False, **kwargs):
    base_handler = default_handler(metrics_config, is_async=is_async, **kwargs)

    def handler(ori, self, *args, **kwargs):
        phase = _resolve_worker_phase(self, args)
        meta_state = get_meta_state()
        meta_state.set("last_model_runner_phase", phase)
        logger.debug("model_runner_phase: phase=%s", phase)
        with _phase_scope(meta_state, phase):
            return base_handler(ori, self, *args, **kwargs)

    return handler


def engine_core_phase_handler(metrics_config, is_async: bool = False, **kwargs):
    base_handler = default_handler(metrics_config, is_async=is_async, **kwargs)

    def handler(ori, *args, **kwargs):
        meta_state = get_meta_state()
        phase = meta_state.get("last_scheduler_phase", meta_state.get("pd_role", "mixed"))
        logger.debug("engine_core_phase: phase=%s", phase)
        with _phase_scope(meta_state, phase):
            return base_handler(ori, *args, **kwargs)

    return handler


def executor_execute_model_phase_handler(metrics_config, is_async: bool = False, **kwargs):
    base_handler = default_handler(metrics_config, is_async=is_async, **kwargs)

    def _extract_scheduler_output(args, kwargs):
        for i, arg in enumerate(args):
            if i == 0:
                continue
            if hasattr(arg, "num_scheduled_tokens") or hasattr(arg, "scheduled_new_reqs"):
                return arg
        return kwargs.get("scheduler_output")

    def handler(ori, *args, **kwargs):
        phase = "mixed"
        scheduler_output = _extract_scheduler_output(args, kwargs)
        if scheduler_output is not None:
            try:
                sched_phase, _ = _get_batch_phase_details(_get_scheduler_phase_state(), scheduler_output)
                if sched_phase != "mixed":
                    phase = sched_phase
            except Exception:
                logger.debug("Failed to get batch phase details", exc_info=True)

        meta_state = get_meta_state()
        if phase == "mixed":
            phase = meta_state.get("last_scheduler_phase", meta_state.get("pd_role", "mixed"))
        logger.debug("executor_execute_model_phase: phase=%s", phase)
        with _phase_scope(meta_state, phase):
            return base_handler(ori, *args, **kwargs)

    return handler
