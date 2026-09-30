# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2026 Huawei Technologies Co.,Ltd.
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

# ==================== Constants ====================
from typing import Dict, Optional
from ms_service_profiler.patcher.core.logger import logger
from ms_service_profiler.patcher.core.metric_hook import MetricConfig, MetricType, TIMER_BUCKETS, get_hook_metrics


class MetricConstants:
    """Metric name constants"""

    TOTAL_TOKENS = "total_tokens"
    SECOND_TOKEN_LATENCY = "second_token_latency"  # nosec B105: metric name, not a password
    BATCH_SIZE = "batch_size"
    WAITING_BATCH_SIZE = "waiting_batch_size"
    NUM_SPEC_TOKENS = "num_spec_tokens"
    INPUT_METRICS = "input"
    OUTPUT_METRICS = "output"
    FINE_GRAINED_TTFT = "fine_grained_ttft"
    FINE_GRAINED_TPOT = "fine_grained_tpot"

    TOTAL_KVCACHE_BLOCKS = "total_kvcache_blocks"
    FREE_KVCACHE_BLOCKS = "free_kvcache_blocks"
    ALLOCATED_KVCACHE_BLOCKS = "allocated_kvcache_blocks"


# ==================== Bucket Configurations ====================
class BucketConfig:
    """Bucket configurations for histograms"""

    # Custom buckets for various metrics
    CUSTOM_BUCKETS = [
        0,
        1,
        10,
        20,
        30,
        40,
        50,
        75,
        100,
        125,
        150,
        175,
        200,
        300,
        400,
        500,
        600,
        700,
        800,
        900,
        1000,
        1500,
        2000,
        2500,
        3000,
        4000,
        5000,
        6000,
        7000,
        8000,
        10000,
        262144,
        float('inf'),
    ]

    # Buckets for second token latency
    SECOND_TOKEN_BUCKETS = [
        0.01,
        0.025,
        0.05,
        0.075,
        0.1,
        0.15,
        0.2,
        0.3,
        0.4,
        0.5,
        0.75,
        1.0,
        2.5,
        5.0,
        7.5,
        10.0,
        20.0,
        40.0,
        80.0,
    ]

    # Buckets for total tokens
    TOTAL_TOKENS_BUCKETS = [1, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384]


# ==================== Metric Manager ====================
class MetricManager:
    """Manager for metric configurations and registration"""

    # Predefined metric configurations
    METRIC_CONFIGS = {
        MetricConstants.BATCH_SIZE: MetricConfig(
            name=MetricConstants.BATCH_SIZE, type=MetricType.HISTOGRAM, buckets=BucketConfig.CUSTOM_BUCKETS
        ),
        MetricConstants.WAITING_BATCH_SIZE: MetricConfig(
            name=MetricConstants.WAITING_BATCH_SIZE, type=MetricType.HISTOGRAM, buckets=BucketConfig.CUSTOM_BUCKETS
        ),
        MetricConstants.NUM_SPEC_TOKENS: MetricConfig(name=MetricConstants.NUM_SPEC_TOKENS, type=MetricType.GAUGE),
        MetricConstants.TOTAL_TOKENS: MetricConfig(
            name=MetricConstants.TOTAL_TOKENS, type=MetricType.HISTOGRAM, buckets=BucketConfig.TOTAL_TOKENS_BUCKETS
        ),
        MetricConstants.SECOND_TOKEN_LATENCY: MetricConfig(
            name=MetricConstants.SECOND_TOKEN_LATENCY,
            type=MetricType.HISTOGRAM,
            buckets=BucketConfig.SECOND_TOKEN_BUCKETS,
        ),
        MetricConstants.INPUT_METRICS: MetricConfig(name=MetricConstants.INPUT_METRICS, type=MetricType.COUNTER),
        MetricConstants.OUTPUT_METRICS: MetricConfig(name=MetricConstants.OUTPUT_METRICS, type=MetricType.COUNTER),
        MetricConstants.FINE_GRAINED_TTFT: MetricConfig(
            name=MetricConstants.FINE_GRAINED_TTFT, type=MetricType.HISTOGRAM, buckets=TIMER_BUCKETS
        ),
        MetricConstants.FINE_GRAINED_TPOT: MetricConfig(
            name=MetricConstants.FINE_GRAINED_TPOT, type=MetricType.HISTOGRAM, buckets=TIMER_BUCKETS
        ),
        MetricConstants.TOTAL_KVCACHE_BLOCKS: MetricConfig(
            name=MetricConstants.TOTAL_KVCACHE_BLOCKS, type=MetricType.GAUGE
        ),
        MetricConstants.FREE_KVCACHE_BLOCKS: MetricConfig(
            name=MetricConstants.FREE_KVCACHE_BLOCKS, type=MetricType.GAUGE
        ),
        MetricConstants.ALLOCATED_KVCACHE_BLOCKS: MetricConfig(
            name=MetricConstants.ALLOCATED_KVCACHE_BLOCKS, type=MetricType.GAUGE
        ),
    }

    metrics_client = get_hook_metrics()

    @classmethod
    def get_config(cls, metric_name: str) -> Optional[MetricConfig]:
        """Get metric configuration by name"""
        return cls.METRIC_CONFIGS.get(metric_name)

    @classmethod
    def record_metric(cls, metric_name: str, labels: Dict[str, str], value):
        """Register metric if it doesn't exist"""
        if metric_name not in cls.metrics_client.metrics:
            metric_config = cls.get_config(metric_name)
            if not metric_config:
                logger.warning(f"No configuration found for metric: {metric_name}")
                return

            cls.metrics_client.register_metric(metric_config, list(labels.keys()))

        cls.metrics_client.record_metric(metric_name, value, labels)
