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
Handler: Hook处理函数基础类和MetricHandler实现

模块结构：
1. HandlerType: Handler类型枚举
2. MetricType: Metric类型枚举
3. MetricConfig: Metric配置数据类
4. Handler: 基础抽象类，定义Symbol需要的接口
5. MetricHandler: 具体的Handler实现，支持metrics配置

Handler分类：
    1. wrap_func: 包装函数，内部需要手动调用ori_func
    2. context_funcs: 上下文管理器函数，使用yield或ContextManager实现
       由框架自动调用原函数

Context Handler 参数签名：
    - 1个参数 (ctx): 不需要locals，转换为wrap handler处理
    - 2个参数 (ctx, local_values): 需要locals，走字节码注入方式

使用示例：
    # 从配置创建MetricHandler（无需配置need_locals，自动检测）
    handler = MetricHandler.from_config({
        'name': 'timer',
        'handler': 'my_module:my_handler'
    }, 'module.path:Class.method')

    # 直接创建MetricHandler
    handler = MetricHandler(
        name='timer',
        symbol_path='module.path:Class.method',
        hook_func=my_handler_func
    )

    # 自定义Handler（继承基础Handler类）
    class MyHandler(Handler):
        @property
        def id(self) -> str:
            return "my_handler"

        def get_hook_func(self, target: Callable) -> tuple[HandlerType, Callable]:
            return (HandlerType.WRAP, my_hook_func)
"""

import asyncio
import hashlib
import importlib
import inspect
import json
from abc import ABC, abstractmethod
from contextlib import contextmanager
from enum import Enum
from typing import Callable, ContextManager, Dict, List, Optional, Sequence, Tuple

from ms_service_metric.metrics.metrics_manager import MetricConfig, MetricType
from ms_service_metric.utils.exceptions import HandlerError
from ms_service_metric.utils.import_security import is_allowed_handler_module
from ms_service_metric.utils.logger import get_logger

logger = get_logger("handler")


class HandlerType(Enum):
    """Handler类型枚举"""

    WRAP = "wrap"  # 包装函数类型
    CONTEXT = "context"  # 上下文管理器类型


class Handler(ABC):
    """
    Handler抽象基类：定义Symbol需要的基础接口

    所有自定义Handler都应该继承此类，实现以下抽象方法：
    - id: 唯一标识符属性
    - get_hook_func: 获取hook函数

    可选实现：
    - name: handler名称（默认空字符串）
    - symbol_path: 所属symbol路径（默认空字符串）

    使用示例：
        class MyCustomHandler(Handler):
            def __init__(self, hook_func):
                self._hook_func = hook_func

            @property
            def id(self) -> str:
                return f"custom:{self._hook_func.__name__}"

            def get_hook_func(self, target: Callable) -> tuple[HandlerType, Callable]:
                return (HandlerType.WRAP, self._hook_func)
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """获取handler唯一标识符

        Returns:
            唯一ID字符串，用于在Symbol中标识和管理handler
        """
        pass

    @abstractmethod
    def get_hook_func(self, target: Callable) -> tuple[HandlerType, Callable]:
        """获取hook函数

        根据handler类型返回对应的hook函数。

        Args:
            target: 目标函数（原函数），用于构建wrap handler的调用

        Returns:
            tuple[HandlerType, Callable]: (handler类型, hook函数)
            - WRAP类型: 返回 (HandlerType.WRAP, wrap_func)
            - CONTEXT类型: 返回 (HandlerType.CONTEXT, context_func)
        """
        pass

    @property
    def name(self) -> str:
        """获取handler名称

        Returns:
            默认返回id字符串，子类可覆盖
        """
        return self.id

    def __hash__(self) -> int:
        """支持hash，用于set和dict"""
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        """支持相等比较"""
        if not isinstance(other, Handler):
            return False
        return self.id == other.id

    def __repr__(self) -> str:
        """字符串表示"""
        return f"Handler(id={self.id})"


class MetricHandler(Handler):
    """
    MetricHandler类：支持metrics配置的Handler实现

    职责：
    1. 加载并包装handler函数
    2. 分类handler类型（wrap/context）
    3. 自动检测是否需要locals（通过参数签名）
    4. 生成唯一ID
    5. 支持metrics配置

    Attributes:
        _id: 唯一标识符（从hook_func的完整路径生成）
        _name: handler名称
        _symbol_path: 所属symbol路径
        _hook_func: 原始hook函数，上下文管理器函数（如果是context类型）
        _handler_type: handler类型（从函数类型自动判断）
        _min_version: 最小版本要求
        _max_version: 最大版本要求
        _metrics_config: metrics配置列表
    """

    def __init__(
        self,
        name: str,
        symbol_info: dict,
        hook_func: Callable,
        min_version: Optional[str] = None,
        max_version: Optional[str] = None,
        metrics_config: Optional[List[MetricConfig]] = None,
        lock_patch: bool = False,
        config_fingerprint: Optional[str] = None,
    ):
        """
        初始化MetricHandler

        Args:
            name: handler名称
            symbol_path: 所属symbol路径
            hook_func: hook处理函数
            min_version: 最小版本要求
            max_version: 最大版本要求
            metrics_config: metrics配置列表
            lock_patch: 是否锁定patch，为True时关闭不删除此handler

        Note:
            - context handler 只有1个参数(ctx): 不需要locals
        """
        super().__init__()
        self._name = name
        self._symbol_info = symbol_info
        self._symbol_path = symbol_info.get("symbol_path")
        self._hook_func = hook_func
        self._min_version = min_version
        self._max_version = max_version
        self._metrics_config = metrics_config or []
        self._lock_patch = lock_patch
        self._config_fingerprint = config_fingerprint

        # 分类hook_func，同时确定handler_type
        handler_type, hook_func = self._classify_hook_func(hook_func)
        if handler_type is not None:
            self._handler_type = handler_type
            self._hook_func = hook_func
        else:
            self._handler_type = None

        # 生成唯一ID
        self._id = self._generate_id()

        logger.debug("Created MetricHandler: %s for %s, type=%s", self._id, self._symbol_path, self._handler_type)

    def _generate_id(self) -> str:
        """
        生成唯一ID

        基于hook_func的完整路径（模块路径+函数名）生成唯一标识符。

        Returns:
            唯一ID字符串
        """
        func = self._hook_func

        # 获取函数的模块路径和名称
        module = getattr(func, '__module__', 'unknown')
        name = getattr(func, '__name__', 'unknown')
        symbol_path = self._symbol_path or 'unknown'

        if self._config_fingerprint:
            return f"{symbol_path}:config:{self._config_fingerprint}"
        return f"{symbol_path}:{module}:{name}-{self.name}"

    @property
    def id(self) -> str:
        """获取handler ID"""
        return self._id

    @property
    def name(self) -> str:
        """获取handler名称"""
        return self._name

    @property
    def symbol_path(self) -> str:
        """获取所属symbol路径"""
        return self._symbol_path

    @property
    def min_version(self) -> Optional[str]:
        """获取最小版本要求"""
        return self._min_version

    @property
    def max_version(self) -> Optional[str]:
        """获取最大版本要求"""
        return self._max_version

    @property
    def lock_patch(self) -> bool:
        """是否锁定patch（关闭时不删除）"""
        return self._lock_patch

    def get_hook_func(self, target: Callable) -> tuple[HandlerType, Callable]:
        """获取hook函数

        根据handler类型返回对应的hook函数。

        Args:
            target: 目标函数（原函数），用于构建wrap handler的调用

        Returns:
            tuple[HandlerType, Callable]: (handler类型, hook函数)
            - WRAP类型: 返回 (HandlerType.WRAP, wrap_func)
            - CONTEXT类型: 返回 (HandlerType.CONTEXT, context_func)
        """

        # 如果handler是工厂函数（有metrics配置），调用它获取实际handler

        if self._metrics_config and callable(self._hook_func):
            logger.debug("Calling metrics factory for %s", self._id)
            try:
                # 构建symbol_info传递给工厂函数
                hook_func = self._hook_func(self._metrics_config, is_async=asyncio.iscoroutinefunction(target))
                handler_type, hook_func = self._classify_hook_func(hook_func)
                if handler_type is not None:
                    self._handler_type = handler_type
            except Exception as e:
                logger.warning("Failed to create handler from factory %s: %s, using default", self._id, e)
                hook_func = None
        else:
            logger.debug("Using provided hook_func for %s", self._id)
            hook_func = self._hook_func

        if hook_func is None:
            logger.warning("Handler '%s' is None, using default", self._id)

            def hook_func(ori, *args, **kwargs):
                return ori(*args, **kwargs)

            return (HandlerType.WRAP, hook_func)
        if self._handler_type == HandlerType.WRAP:
            # WRAP类型：直接返回原始hook函数
            logger.debug("Using wrap handler for %s", self._id)
            return (HandlerType.WRAP, hook_func)
        elif self._handler_type == HandlerType.CONTEXT:
            # CONTEXT类型：返回context_func
            logger.debug("Using context handler for %s", self._id)
            return (HandlerType.CONTEXT, hook_func)
        else:
            raise ValueError(f"Invalid handler type: {self._handler_type}")

    @property
    def metrics_config(self) -> List[MetricConfig]:
        """获取metrics配置列表"""
        return self._metrics_config

    def __repr__(self) -> str:
        """字符串表示"""
        return f"MetricHandler(id={self._id}, name={self._name})"

    def equals(self, other: 'MetricHandler') -> bool:
        """
        比较两个handler是否相等（考虑配置变化）

        除了id相同外，还比较配置项是否相同。

        Args:
            other: 另一个Handler实例

        Returns:
            如果配置相同返回True，否则返回False
        """
        return (
            self._id == other._id
            and self._min_version == other._min_version
            and self._max_version == other._max_version
            and self._config_fingerprint == other._config_fingerprint
        )

    def _classify_hook_func(self, func) -> Tuple[HandlerType, Callable]:
        """
        将hook_func分类，并返回handler类型

        分类规则：
        - 生成器函数 -> context_func, 返回 HandlerType.CONTEXT
          - 1个参数(ctx): 不需要locals
          - 2个参数(ctx, local_values): 需要locals
        - ContextManager子类 -> context_func, 返回 HandlerType.CONTEXT
        - 其他 -> wrap类型, 返回 HandlerType.WRAP

        Returns:
            HandlerType: 根据函数类型确定的handler类型
        """
        if func is None:
            return None, None
        context_func = self._create_context_manager(func)
        if context_func is not None:
            return HandlerType.CONTEXT, context_func
        else:
            return HandlerType.WRAP, func

    def _create_context_manager(self, func: Callable) -> Optional[Callable]:
        """
        尝试将函数转换为上下文管理器

        Args:
            func: 待转换的函数

        Returns:
            上下文管理器函数，如果无法转换则返回None
        """
        # 检查是否是生成器函数
        if inspect.isgeneratorfunction(func):
            return contextmanager(func)

        # 检查是否是ContextManager类
        if inspect.isclass(func) and issubclass(func, ContextManager):
            return func

        return None

    @classmethod
    def from_config(
        cls,
        config: Dict,
        symbol_path: str,
        allowed_handler_module_prefixes: Sequence[str] = (),
    ) -> 'MetricHandler':
        """
        从配置创建MetricHandler实例

        配置格式：
        {
            'handler': 'module.path:function_name',  # 可选
            'name': 'handler_name',  # 可选
            'min_version': '0.1.0',  # 可选
            'max_version': '1.0.0',  # 可选
            'caller_filter': 'filter',  # 可选
            'metrics': [  # 可选
                {
                    'name': 'metric_name',
                    'type': 'timer',
                    'labels': [
                        {'name': 'label_name', 'expr': 'expression'}
                    ]
                }
            ]
        }

        如果指定了handler且metrics中有配置，handler会被视为工厂函数，
        传入symbol_info调用以获取实际的handler函数。

        Args:
            config: handler配置字典
            symbol_path: 所属symbol路径

        Returns:
            Handler实例

        Raises:
            HandlerError: 配置解析失败
        """
        # 解析metrics配置
        metrics_config = cls._parse_metrics_config(config.get('metrics', []))

        symbol_info = {
            'symbol_path': symbol_path,
            'metrics': metrics_config,
            'min_version': config.get('min_version'),
            'max_version': config.get('max_version'),
        }
        hook_func = None
        # 解析handler路径
        handler_path = config.get('handler')
        if handler_path:
            hook_func = cls._import_handler(
                handler_path,
                allowed_handler_module_prefixes,
            )
        else:
            hook_func = cls._import_handler("ms_service_metric.handlers:default_handler")

        handler_name = cls._resolve_handler_name(config)
        return cls(
            name=handler_name,
            symbol_info=symbol_info,
            hook_func=hook_func,
            min_version=config.get('min_version'),
            max_version=config.get('max_version'),
            metrics_config=metrics_config,
            lock_patch=config.get('lock_patch', False),
            config_fingerprint=cls._fingerprint_config(config),
        )

    @classmethod
    def _fingerprint_config(cls, config: Dict) -> str:
        """Derive identity from effective behavior, not YAML spelling."""
        raw_metrics = config.get("metrics", [])
        if not isinstance(raw_metrics, list):
            raw_metrics = [raw_metrics] if raw_metrics else []
        metrics = cls._parse_metrics_config(raw_metrics)
        identity = {
            "handler": config.get("handler") or "ms_service_metric.handlers:default_handler",
            "name": cls._fingerprint_handler_name(config),
            "min_version": config.get("min_version"),
            "max_version": config.get("max_version"),
            "lock_patch": config.get("lock_patch", False),
            "metrics": [
                {
                    "name": metric.name,
                    "type": metric.type.value,
                    "expr": metric.expr,
                    "buckets": metric.buckets,
                    "labels": metric.labels,
                }
                for metric in metrics
            ],
        }
        serialized = json.dumps(
            identity,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=repr,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _resolve_handler_name(config: Dict) -> str:
        """Resolve the effective Handler name used at runtime and in identity."""
        return (
            config.get("name")
            or config.get("handler")
            or ",".join(metric.get("name", "") for metric in config.get("metrics", []) if isinstance(metric, dict))
        )

    @classmethod
    def _fingerprint_handler_name(cls, config: Dict) -> Optional[str]:
        """Keep only an explicit name that changes the derived runtime name."""
        configured_name = config.get("name")
        if not configured_name:
            return None

        config_without_name = dict(config)
        config_without_name.pop("name", None)
        if configured_name == cls._resolve_handler_name(config_without_name):
            return None
        return configured_name

    @staticmethod
    def _import_handler(
        handler_path: str,
        allowed_handler_module_prefixes: Sequence[str] = (),
    ) -> Callable:
        """
        导入handler函数

        Args:
            handler_path: handler路径，格式为 "module.path:function_name"

        Returns:
            导入的函数对象

        Raises:
            HandlerError: 导入失败
        """
        try:
            # 分割模块路径和函数名
            if ':' not in handler_path:
                raise HandlerError(f"Invalid handler path format: {handler_path}, expected 'module.path:function_name'")

            module_path, func_name = handler_path.rsplit(':', 1)
            logger.debug("Importing handler: %s.%s", module_path, func_name)
            if not is_allowed_handler_module(
                module_path,
                allowed_handler_module_prefixes,
            ):
                raise HandlerError(f"Handler module is not allowed: {module_path}")

            # 导入模块
            module = importlib.import_module(module_path)

            # 获取函数
            func = getattr(module, func_name, None)
            if func is None:
                raise HandlerError(f"Handler function not found: {handler_path}")

            if not callable(func):
                raise HandlerError(f"Handler is not callable: {handler_path}")

            return func

        except ImportError as e:
            logger.error("Failed to import handler module: %s, error: %s", handler_path, e)
            raise HandlerError(f"Failed to import handler module: {handler_path}") from e

    @staticmethod
    def _parse_metrics_config(metrics_config: list) -> List[MetricConfig]:
        """
        解析metrics配置

        Args:
            metrics_config: metrics配置列表

        Returns:
            MetricConfig对象列表
        """
        configs = []
        for item in metrics_config:
            if not isinstance(item, dict):
                logger.warning("Invalid metrics config item: %s", item)
                continue

            try:
                metric_type = MetricType(item.get('type', 'timer'))
            except ValueError:
                logger.warning("Unknown metric type: %s, using 'timer'", item.get('type'))
                metric_type = MetricType.TIMER

            configs.append(
                MetricConfig(
                    name=item.get('name', 'unknown'),
                    type=metric_type,
                    expr=item.get('expr', ''),
                    buckets=item.get('buckets'),
                    labels={
                        label.get('name'): label.get('expr')
                        for label in item.get('labels', [])
                        if isinstance(label, dict)
                    },
                )
            )

        return configs
