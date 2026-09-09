# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------
"""SGLang metrics initialization helpers."""

import os

from prometheus_client import REGISTRY

from ms_service_metric.metrics.metrics_manager import MetricsManager, get_metrics_manager
from ms_service_metric.utils.logger import get_logger

logger = get_logger(__name__)

SGLANG_METRICS_PREFIX = "sglang_profiling"


def set_sglang_multiprocess_prometheus():
    """Warn when multiprocess prometheus storage is not configured."""
    if "PROMETHEUS_MULTIPROC_DIR" not in os.environ:
        logger.warning(
            "Missing environment variable 'PROMETHEUS_MULTIPROC_DIR' may cause partial SGLang metrics loss in "
            "multi-process serving."
        )
    logger.info("Prometheus multiproc dir: %s", os.getenv("PROMETHEUS_MULTIPROC_DIR"))


def set_sglang_metric_prefix(metrics_client: MetricsManager):
    """Set SGLang-specific metric prefix."""
    metrics_client.metric_prefix = SGLANG_METRICS_PREFIX
    logger.debug("Set SGLang metric prefix: %s", SGLANG_METRICS_PREFIX)


def set_sglang_registry(metrics_client: MetricsManager):
    """Use the active Prometheus client registry for SGLang metric objects."""
    if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
        metrics_client.set_registry(metrics_client._get_appropriate_registry())
        logger.debug("Set SGLang multi-process prometheus registry")
        return
    metrics_client.set_registry(REGISTRY)
    logger.debug("Set SGLang default prometheus registry")


def setup_sglang_metrics():
    """Initialize SGLang metric collection environment."""
    logger.info("Setting up SGLang metrics...")
    set_sglang_multiprocess_prometheus()
    metrics_client = get_metrics_manager()
    set_sglang_registry(metrics_client)
    set_sglang_metric_prefix(metrics_client)
    logger.info("SGLang metrics setup completed")
