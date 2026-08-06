# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------
"""Stable API surface for framework-owned metric providers and handlers."""

from __future__ import annotations

from typing import Protocol

from ms_service_metric.core.config.provider import MetricProvider
from ms_service_metric.metrics.meta_state import get_meta_state
from ms_service_metric.metrics.metrics_manager import MetricType
from ms_service_metric.metrics.metrics_manager import (
    get_metrics_manager as _get_metrics_manager,
)


class MetricRecorder(Protocol):
    """Narrow metric-writing contract exposed to framework handlers."""

    def get_or_create_metric(
        self,
        metric_name: str,
        label_names: list[str] | None = None,
        metric_type: MetricType = MetricType.TIMER,
        buckets: list[float] | None = None,
    ) -> MetricRecorder: ...

    def record_metric(
        self,
        metric_name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None: ...


def get_metric_recorder() -> MetricRecorder:
    """Return the stable write-only view used by Provider handlers."""
    return _get_metrics_manager()


__all__ = [
    "MetricProvider",
    "MetricRecorder",
    "MetricType",
    "get_meta_state",
    "get_metric_recorder",
]
