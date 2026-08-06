# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------
# ruff: noqa: F822
# pylint: disable=undefined-all-variable
"""Stable, lazy Core handlers that framework Provider YAML may reference."""

from importlib import import_module

_HANDLER_TARGETS = {
    "init_data_parallel_worker": (
        "ms_service_metric.adapters.vllm.handlers.meta_handlers",
        "init_data_parallel_worker",
    ),
    "engine_memory_phase_handler": (
        "ms_service_metric.adapters.vllm.handlers.metric_handlers",
        "engine_memory_phase_handler",
    ),
    "model_runner_phase_handler": (
        "ms_service_metric.adapters.vllm.handlers.metric_handlers",
        "model_runner_phase_handler",
    ),
    "phase_all_handler": (
        "ms_service_metric.adapters.vllm.handlers.metric_handlers",
        "phase_all_handler",
    ),
    "scheduler_scheduler_hooker": (
        "ms_service_metric.adapters.vllm.handlers.metric_handlers",
        "scheduler_scheduler_hooker",
    ),
}


def __getattr__(name: str):
    """Resolve a stable export only when metrics are being enabled."""
    target = _HANDLER_TARGETS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, handler_name = target
    return getattr(import_module(module_path), handler_name)


__all__ = list(_HANDLER_TARGETS)
