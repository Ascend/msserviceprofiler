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

import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from prometheus_client import Histogram, Counter, Gauge, REGISTRY, CollectorRegistry, Summary
from prometheus_client import multiprocess
from ms_service_profiler.utils.expr_eval import ExprEval

from .logger import logger


TIMER_BUCKETS = [
    0.001,
    0.002,
    0.005,
    0.01,
    0.015,
    0.02,
    0.025,
    0.03,
    0.04,
    0.05,
    0.06,
    0.07,
    0.08,
    0.09,
    0.1,
    0.15,
    0.2,
    0.25,
    0.3,
    0.35,
    0.4,
    0.45,
    0.5,
    0.6,
    0.7,
    0.8,
    0.9,
    1.0,
    # 细化1-10秒区间
    1.2,
    1.4,
    1.6,
    1.8,
    2.0,
    2.2,
    2.4,
    2.6,
    2.8,
    3.0,
    3.5,
    4.0,
    4.5,
    5.0,
    5.5,
    6.0,
    6.5,
    7.0,
    7.5,
    8.0,
    8.5,
    9.0,
    9.5,
    10.0,
    # 保持长尾分布
    15.0,
    20.0,
    30.0,
    40.0,
    60.0,
    90.0,
    120.0,
    180.0,
    300.0,
]


class MetricType(str, Enum):
    """指标类型枚举"""

    TIMER = "timer"  # 耗时指标
    HISTOGRAM = "histogram"  # 直方图
    COUNTER = "counter"  # 计数器
    GAUGE = "gauge"  # 仪表盘
    SUMMARY = "summary"  # 摘要


@dataclass
class MetricConfig:
    """指标配置数据结构"""

    name: str  # 指标名称
    type: MetricType  # 指标类型
    expr: str = ""  # 表达式（对于非timer类型）
    buckets: Optional[List[float]] = None  # 直方图分桶（可选）

    def __post_init__(self):
        """后初始化处理"""
        if self.type == MetricType.TIMER:
            # timer指标不需要expr
            self.expr = ""


class HookMetrics:
    """
    Hook函数的Prometheus监测器
    """

    def __init__(self):
        """初始化Hook监测器"""
        self.metrics = {}  # 存储指标对象，key为指标名称
        self.label_definitions = {}  # 存储标签定义，key为 metric_name

        # 框架侧写入初始化变量
        self.registry = None  # 等指标开始注册时初始化，获取正确的registry
        self.metric_prefix = ""  # 给指标添加额外的前缀
        self.meta_state = None  # 框架线程独立储存信息，用于自定义的额外的标签信息，如dp域

    @staticmethod
    def _get_appropriate_registry():
        """
        创建Prometheus registry
        在多进程环境下使用vLLM的registry，否则使用默认registry
        """
        # 检查是否在多进程环境下
        if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
            # 多进程环境，创建新的registry并添加多进程收集器
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
            return registry

        # 单进程环境，使用默认registry
        return REGISTRY

    def _generate_custom_buckets(self):
        bucket_configs = [
            {'start': 0, 'end': 0.001, 'step': 0.0001, 'precision': 4},
            {'start': 0, 'end': 0.0001, 'step': 0.00001, 'precision': 5},
            {'start': 0, 'end': 0.00001, 'step': 0.000001, 'precision': 6},
            {'start': 0, 'end': 0.01, 'step': 0.001, 'precision': 3},
            {'start': 0, 'end': 0.1, 'step': 0.01, 'precision': 2},
            {'start': 0, 'end': 1.0, 'step': 0.25, 'precision': 2},
            {'start': 1, 'end': 5, 'step': 0.5, 'precision': 1},
            {'start': 5, 'end': 25, 'step': 1, 'precision': 0},
            {'start': 25, 'end': 100, 'step': 25, 'precision': 0},
            {'start': 100, 'end': 500, 'step': 100, 'precision': 0},
            {'start': 500, 'end': 1000, 'step': 250, 'precision': 0},
        ]
        buckets = [262144, float('inf')]

        for config in bucket_configs:
            start, end, step, precision = config['start'], config['end'], config['step'], config['precision']
            if step > 0:
                val = start
                while val <= end + 1e-9:
                    if precision == 0:
                        buckets.append(int(round(val)))
                    else:
                        buckets.append(round(val, precision))
                    val += step

        buckets = sorted(list(set(buckets)))
        return buckets

    def _add_prefix(self, metric_name: str) -> str:
        """为metric名称添加前缀"""
        if self.metric_prefix:
            return f"{self.metric_prefix}_{metric_name}"
        return metric_name

    def _add_dp_label_name(self, label_names: List[str] = None) -> List[str]:
        """为metric指标创建添加默认的dp域标签"""
        label_names = label_names or []

        if "dp" not in label_names:
            label_names.append("dp")
        return label_names

    def _add_dp_label_value(self, labels: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """为metric指标创建添加默认的dp域值（如果不存在则添加）"""
        labels = labels if labels is not None else {}

        if "dp" in labels:
            return labels

        # 只在dp键不存在时才添加
        dp_value = "-1"
        try:
            dp_value = str(self.meta_state.dp_rank_id)
        except Exception:
            dp_value = "-1"

        labels["dp"] = dp_value
        return labels

    def register_metric(self, metric_config: MetricConfig, label_names: List[str] = None) -> Any:
        """注册指标"""
        if self.registry is None:
            self.registry = HookMetrics._get_appropriate_registry()

        # 使用带前缀的metric名称
        full_name = self._add_prefix(self._sanitize_metric_name(metric_config.name))

        # 根据类型创建指标
        metric_obj = None
        labelnames = self._add_dp_label_name(label_names)

        try:
            if metric_config.type == MetricType.TIMER:
                # timer类型使用Histogram实现
                metric_obj = Histogram(
                    name=full_name,
                    documentation=f"Execution duration of {metric_config.name}",
                    labelnames=labelnames,
                    buckets=metric_config.buckets or TIMER_BUCKETS,
                    registry=self.registry,
                )
            elif metric_config.type == MetricType.HISTOGRAM:
                metric_obj = Histogram(
                    name=full_name,
                    documentation=f"Histogram for {metric_config.name}",
                    labelnames=labelnames,
                    buckets=metric_config.buckets or self._generate_custom_buckets(),
                    registry=self.registry,
                )
            elif metric_config.type == MetricType.COUNTER:
                metric_obj = Counter(
                    name=full_name,
                    documentation=f"Counter for {metric_config.name}",
                    labelnames=labelnames,
                    registry=self.registry,
                )
            elif metric_config.type == MetricType.GAUGE:
                metric_obj = Gauge(
                    name=full_name,
                    documentation=f"Gauge for {metric_config.name}",
                    labelnames=labelnames,
                    registry=self.registry,
                    multiprocess_mode="livemostrecent",
                )
            elif metric_config.type == MetricType.SUMMARY:
                metric_obj = Summary(
                    name=full_name,
                    documentation=f"Summary for {metric_config.name}",
                    labelnames=labelnames,
                    registry=self.registry,
                )

            if metric_obj:
                self.metrics[full_name] = metric_obj
                logger.debug(f"Registered metric: {full_name} ({metric_config.type})")

        except ValueError as e:
            # 如果指标已经存在，从缓存中获取
            if full_name in self.metrics:
                logger.debug(f"Metric {full_name} already exists, using cached instance")
                metric_obj = self.metrics[full_name]
            else:
                logger.warning(f"Failed to create metric {full_name}: {e}")

        return metric_obj

    def add_label_definition(self, metric_name: str, label_name: str, expr: str):
        """添加标签定义"""
        # 使用带前缀的metric名称
        full_metric_name = self._add_prefix(self._sanitize_metric_name(metric_name))

        if full_metric_name not in self.label_definitions:
            self.label_definitions[full_metric_name] = []

        self.label_definitions[full_metric_name].append({"name": label_name, "expr": expr})

    def get_labels_for_metric_ex(self, metric_name: str, context: Dict[str, Any]) -> Dict[str, str]:
        labels = {}
        # 使用带前缀的metric名称
        full_metric_name = self._add_prefix(self._sanitize_metric_name(metric_name))

        # 计算标签值
        if full_metric_name in self.label_definitions:
            for label_def in self.label_definitions[full_metric_name]:
                label_name = label_def["name"]
                expr = label_def["expr"]
                if not expr:
                    continue
                try:
                    label_value = ExprEval(expr)(context)
                    labels[label_name] = str(label_value)
                except Exception as e:
                    logger.warning(f"Failed to evaluate label expression '{expr}' for metric '{metric_name}': {e}")
                    continue

        return labels

    def record_metric(self, metric_name: str, value, labels: Optional[Dict[str, str]] = None) -> None:
        """记录指标"""
        # 使用带前缀的metric名称
        full_metric_name = self._add_prefix(self._sanitize_metric_name(metric_name))

        # 增加dp域标签
        labels = self._add_dp_label_value(labels)

        if full_metric_name not in self.metrics:
            logger.warning(f"Metric not found: {full_metric_name}")
            return

        metric_obj = self.metrics[full_metric_name]

        try:
            if isinstance(metric_obj, Histogram):
                if labels:
                    metric_obj.labels(**labels).observe(value)
                else:
                    metric_obj.observe(value)
            elif isinstance(metric_obj, Counter):
                if labels:
                    metric_obj.labels(**labels).inc(value if value > 0 else 1)
                else:
                    metric_obj.inc(value if value > 0 else 1)
            elif isinstance(metric_obj, Gauge):
                if labels:
                    metric_obj.labels(**labels).set(value)
                else:
                    metric_obj.set(value)
            elif isinstance(metric_obj, Summary):
                if labels:
                    metric_obj.labels(**labels).observe(value)
                else:
                    metric_obj.observe(value)
        except Exception as e:
            logger.warning(f"Metrics - Failed to record metric {metric_name}: {e}")

    def _sanitize_metric_name(self, name: str) -> str:
        """清理指标名称，确保符合Prometheus规范"""
        # 替换不合规的字符
        sanitized = name.replace("-", "_")
        # 确保以字母开头
        if sanitized[0].isdigit():
            sanitized = f"fn_{sanitized}"
        return sanitized

    def get_registry(self):
        """获取使用的registry"""
        return self.registry

    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有已创建的Hook指标"""
        return self.metrics


# 全局HookMetrics实例
_hook_metrics_instance = None


def get_hook_metrics() -> HookMetrics:
    """获取全局VLLMHookMetrics实例（单例模式）"""
    global _hook_metrics_instance
    if _hook_metrics_instance is None:
        _hook_metrics_instance = HookMetrics()
    return _hook_metrics_instance


def parse_metrics_config(metrics_config: Any) -> Tuple[List[MetricConfig], List[Dict]]:
    """解析 metrics 配置。

    Args:
        metrics_config: 来自 symbol 配置的 metrics 列表（或包含 'metrics' 键的 dict）

    Returns:
        Tuple[List[MetricConfig], List[Dict]]:
            - 第一个元素是指标配置列表
            - 第二个元素是标签配置列表
    """
    metrics = []
    labels = []

    if metrics_config is None:
        return metrics, labels
    if isinstance(metrics_config, dict):
        metrics_config = metrics_config.get("metrics", [])
    if not isinstance(metrics_config, list):
        return metrics, labels

    for item in metrics_config:
        if not isinstance(item, dict):
            continue
        name = item.get("name", "")
        if not name:
            logger.warning("Metric config missing name")
            continue
        type_str = item.get("type", "").lower()
        try:
            metric_type = MetricType(type_str)
        except ValueError:
            logger.warning("Invalid metric type: %s", type_str)
            continue
        expr = item.get("expr", "")
        metric_config = MetricConfig(
            name=name,
            type=metric_type,
            expr=expr if metric_type != MetricType.TIMER else "",
            buckets=item.get("buckets"),
        )
        metrics.append(metric_config)
        metric_labels = item.get("label", [])
        for label in metric_labels:
            if isinstance(label, dict):
                label_name = label.get("name")
                label_expr = label.get("expr")
                if label_name and label_expr:
                    labels.append(
                        {
                            "metric_name": name,
                            "label_name": label_name,
                            "expr": label_expr,
                        }
                    )
    return metrics, labels


class MetricsWrapper:
    """包装自定义 handler 函数以支持 metrics 记录。"""

    def __init__(self, handler_func_obj: Callable, symbol_info: dict):
        self.handler_func_obj = handler_func_obj
        self.symbol_info = symbol_info
        self.registered_metrics = {}
        self.metrics_client = get_hook_metrics()
        self._parse_metrics_config()

    def _parse_metrics_config(self):
        """解析 metrics 配置并预注册指标。"""
        metrics_configs, label_configs = parse_metrics_config(self.symbol_info)
        for label_info in label_configs:
            metric_name = label_info["metric_name"]
            label_name = label_info["label_name"]
            expr = label_info["expr"]
            self.metrics_client.add_label_definition(metric_name, label_name, expr)
        for metric_config in metrics_configs:
            label_names = [
                label_info["label_name"]
                for label_info in label_configs
                if label_info["metric_name"] == metric_config.name
            ]
            metric_obj = self.metrics_client.register_metric(metric_config, label_names)
            if metric_obj:
                self.registered_metrics[metric_config.name] = metric_config

    def wrap(self) -> Callable:
        """创建包装后的 handler 函数。"""

        def wrapped_handler(ctx):
            start_time = time.time()
            yield
            duration = time.time() - start_time
            self._record_metrics_in_handler_ex(ctx.local_values, ctx.return_value, duration)

        return wrapped_handler

    def _record_metrics_in_handler_ex(self, local_values: dict, return_value: Any, duration: float):
        expr_values = {**local_values, "ret": return_value}

        for metric_name, metric_config in self.registered_metrics.items():
            labels = self.metrics_client.get_labels_for_metric_ex(metric_name, expr_values)
            if metric_config.type == MetricType.TIMER:
                self.metrics_client.record_metric(metric_name, duration, labels)
            elif metric_config.expr:
                try:
                    value = ExprEval(metric_config.expr)(expr_values)
                    numeric_value = float(value)
                    self.metrics_client.record_metric(metric_name, numeric_value, labels)
                except Exception as e:
                    logger.warning("Failed to convert metric value to float: %s, error: %s", metric_config.expr, e)


def wrap_handler_with_metrics(handler_func_obj: Callable, symbol_info: dict) -> Callable:
    """包装自定义 handler 函数以支持 metrics 记录。"""
    wrapper = MetricsWrapper(handler_func_obj, symbol_info)
    return wrapper.wrap()
