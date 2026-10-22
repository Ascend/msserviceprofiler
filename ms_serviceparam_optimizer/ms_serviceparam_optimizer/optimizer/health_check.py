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

from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Optional, Dict, Any, Tuple, List

# The subprocess module is used only for its SubprocessError exception base.
import subprocess  # nosec B404

from ..config.config import get_settings, ErrorSeverity, ErrorType

LOG_ERROR_MESSAGE = "Detected {error_type} in logs"
BENCHMARK_LOG_ERROR_MESSAGE = "Detected {error_type} in benchmark logs"


class FatalError(subprocess.SubprocessError):
    """致命错误，不重试（OOM、设备故障等）"""

    pass


class RetryableError(subprocess.SubprocessError):
    """可重试错误（网络抖动、IO错误等）"""

    pass


class ServiceHookPoint(Enum):
    """服务化框架钩子点"""

    STARTUP_POLLING = "startup_polling"
    RUNTIME_MONITOR = "runtime_monitor"


class BenchmarkHookPoint(Enum):
    """测评框架钩子点"""

    RUNTIME_MONITOR = "runtime_monitor"


@dataclass
class ErrorContext:
    """错误上下文信息"""

    error_type: Any
    severity: Any
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthCheckContext:
    """健康检查上下文"""

    simulator: Any
    benchmark: Any
    scheduler: Any
    current_time: float
    elapsed_time: float
    startup: bool = False


@dataclass
class HealthCheckResult:
    """健康检查结果"""

    is_healthy: bool
    error_context: Optional[ErrorContext] = None


def _check_log_patterns(
    log_content: str,
    patterns_dict: Dict[ErrorType, List[str]],
    severity: ErrorSeverity,
    error_message_format: str,
    log_snippet_length: int,
) -> Optional[HealthCheckResult]:
    """检查日志中的错误模式（公共函数）

    Args:
        log_content: 日志内容
        patterns_dict: 错误模式字典 {ErrorType: [pattern1, pattern2, ...]}
        severity: 错误严重程度
        error_message_format: 错误消息格式字符串
        log_snippet_length: 日志片段长度

    Returns:
        如果检测到错误返回 HealthCheckResult(is_healthy=False)，否则返回 None
    """
    log_lower = log_content.lower()
    for error_type, patterns in patterns_dict.items():
        for pattern in patterns:
            if pattern.lower() in log_lower:
                return HealthCheckResult(
                    is_healthy=False,
                    error_context=ErrorContext(
                        error_type=error_type,
                        severity=severity,
                        message=error_message_format.format(error_type=error_type.value),
                        details={"log_snippet": log_content[-log_snippet_length:]},
                    ),
                )
    return None


class HealthCheckHook:
    """健康检查钩子基类"""

    def __init__(self):
        self._hooks: Dict[Enum, List[Tuple[int, Callable, str]]] = {}

    def register(
        self, hook_point: Enum, func: Optional[Callable] = None, *, priority: int = 0, name: Optional[str] = None
    ):
        """注册钩子函数（在基类实现，子类直接继承）"""

        def decorator(f):
            hook_name = name or f.__name__
            if hook_point not in self._hooks:
                self._hooks[hook_point] = []
            self._hooks[hook_point].append((priority, f, hook_name))
            return f

        return decorator(func) if func else decorator

    def run(self, hook_point: Enum, context: HealthCheckContext) -> HealthCheckResult:
        """执行指定钩子点的所有检查"""
        if hook_point not in self._hooks:
            return HealthCheckResult(is_healthy=True)
        hooks = sorted(self._hooks[hook_point], key=lambda x: x[0])
        for priority, hook_func, hook_name in hooks:
            try:
                result = hook_func(context)
                if isinstance(result, HealthCheckResult):
                    if not result.is_healthy:
                        return result
            except Exception as e:
                return HealthCheckResult(
                    is_healthy=False,
                    error_context=ErrorContext(
                        error_type=ErrorType.UNKNOWN,
                        severity=ErrorSeverity.FATAL,
                        message=f"Hook {hook_name} raised unexpected exception: {type(e).__name__}: {str(e)}",
                    ),
                )

        return HealthCheckResult(is_healthy=True)


class ServiceHealthCheckHook(HealthCheckHook):
    """服务化框架健康检查钩子（只继承，无需重复实现register）"""

    pass


class BenchmarkHealthCheckHook(HealthCheckHook):
    """测评框架健康检查钩子（只继承，无需重复实现register）"""

    pass


class ServiceHealthChecks:
    """服务化框架预定义健康检查"""

    @staticmethod
    def check_log_errors(context: HealthCheckContext) -> HealthCheckResult:
        """检查日志中的错误信息"""
        if not hasattr(context.simulator, 'get_last_log'):
            return HealthCheckResult(is_healthy=True)
        settings = get_settings()
        config = settings.health_check.service_errors
        log_content = context.simulator.get_last_log(number=settings.health_check.log_snippet_length)
        # 检查致命错误
        result = _check_log_patterns(
            log_content=log_content,
            patterns_dict=config.fatal_patterns,
            severity=ErrorSeverity.FATAL,
            error_message_format=LOG_ERROR_MESSAGE,
            log_snippet_length=settings.health_check.log_snippet_length,
        )
        if result:
            return result
        # 检查可重试错误
        result = _check_log_patterns(
            log_content=log_content,
            patterns_dict=config.retryable_patterns,
            severity=ErrorSeverity.RETRYABLE,
            error_message_format=LOG_ERROR_MESSAGE,
            log_snippet_length=settings.health_check.log_snippet_length,
        )
        if result:
            return result
        return HealthCheckResult(is_healthy=True)


class BenchmarkHealthChecks:
    """测评框架预定义健康检查"""

    @staticmethod
    def check_log_errors(context: HealthCheckContext) -> HealthCheckResult:
        """检查 benchmark 日志中的错误信息"""
        if not hasattr(context.benchmark, 'get_last_log'):
            return HealthCheckResult(is_healthy=True)
        settings = get_settings()
        config = settings.health_check.benchmark_errors
        log_content = context.benchmark.get_last_log(number=settings.health_check.log_snippet_length)
        # 检查致命错误
        result = _check_log_patterns(
            log_content=log_content,
            patterns_dict=config.fatal_patterns,
            severity=ErrorSeverity.FATAL,
            error_message_format=BENCHMARK_LOG_ERROR_MESSAGE,
            log_snippet_length=settings.health_check.log_snippet_length,
        )
        if result:
            return result
        # 检查可重试错误
        result = _check_log_patterns(
            log_content=log_content,
            patterns_dict=config.retryable_patterns,
            severity=ErrorSeverity.RETRYABLE,
            error_message_format=BENCHMARK_LOG_ERROR_MESSAGE,
            log_snippet_length=settings.health_check.log_snippet_length,
        )
        if result:
            return result
        return HealthCheckResult(is_healthy=True)


service_health_checks_hooks = [
    (ServiceHookPoint.STARTUP_POLLING, ServiceHealthChecks.check_log_errors, 10),
    (ServiceHookPoint.RUNTIME_MONITOR, ServiceHealthChecks.check_log_errors, 10),
]

benchmark_health_checks_hooks = [(BenchmarkHookPoint.RUNTIME_MONITOR, BenchmarkHealthChecks.check_log_errors, 10)]
