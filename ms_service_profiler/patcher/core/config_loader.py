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
# pylint: disable=logging-fstring-interpolation

"""
ConfigLoader: 加载 YAML 配置并解析为 Handler 列表。

职责：
- 读取 config_path 对应的 yml 文件
- 将配置解析为以 symbol 为键、Handler 列表为值的结构
- 支持 yml 中配置的 handler 或默认 handler（make_default_time_hook）
- 支持模式 symbol（含 * 通配），返回 ProfilingConfig / MetricsConfig（concrete + patterns）
"""

import importlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Callable

from .utils import load_yaml_config
from .logger import logger
from .dynamic_hook import make_default_time_hook, ConfigHooker
from .metric_hook import wrap_handler_with_metrics
from .import_security import is_allowed_handler_module


def _is_pattern_symbol(symbol_path: str) -> bool:
    """判断是否为模式 symbol（含 * 通配）。"""
    return isinstance(symbol_path, str) and '*' in symbol_path


def _parse_symbol_pattern(symbol_path: str) -> Optional[Tuple[str, str, str]]:
    """解析模式 symbol，返回 (module_pattern, class_pattern, method_name)。
    格式仅支持一个冒号：module.path.*:class_pattern.method_name（或 module:function）。
    """
    if ":" not in symbol_path:
        logger.warning("Invalid symbol path format: %s", symbol_path)
        return None
    module_pattern, rest = symbol_path.split(":", 1)
    module_pattern = module_pattern.strip()
    rest = rest.strip()
    if "." not in rest:
        logger.warning("Pattern symbol must be module:class.method_name (one colon): %s", symbol_path)
        return None
    class_pattern, method_name = rest.split(".", 1)
    class_pattern, method_name = class_pattern.strip(), method_name.strip()
    if not method_name or "*" in method_name:
        logger.warning("Pattern symbol method_name must be concrete (no *): %s", symbol_path)
        return None
    return (module_pattern, class_pattern, method_name)


def _parse_symbol_path(symbol_path: str) -> Tuple[str, str, Optional[str]]:
    """解析 symbol 路径，返回 (module_path, method_name, class_name)。"""
    if ':' not in symbol_path:
        logger.warning(f"Invalid symbol path format: {symbol_path}")
        return '', '', None
    module_path, class_method = symbol_path.split(':', 1)
    if '.' in class_method:
        class_name, method_name = class_method.split('.', 1)
        return module_path, method_name, class_name
    return module_path, class_method, None


def _build_hook_points(module_path: str, method_name: str, class_name: Optional[str]) -> List[Tuple[str, str]]:
    """构建 hook 点列表。"""
    hook_point = f"{class_name}.{method_name}" if class_name else method_name
    return [(module_path, hook_point)]


def _resolve_handler_func(symbol_info: dict, method_name: str) -> Callable:
    """根据配置解析 handler 函数。

    若 yml 中定义了 handler 则导入使用；否则使用 make_default_time_hook 生成默认 handler。
    """
    handler_path = symbol_info.get('handler')

    if not handler_path:
        domain = symbol_info.get('domain', 'Default')
        name = symbol_info.get('name', method_name)
        attributes = symbol_info.get('attributes')
        return make_default_time_hook(domain=domain, name=name, attributes=attributes)

    # 自定义 handler: "module.path:func_name"
    if isinstance(handler_path, str) and ':' in handler_path:
        try:
            mod_str, func_name = handler_path.split(':', 1)
            if not is_allowed_handler_module(mod_str):
                logger.warning("Handler module '%s' is not allowed, using default", mod_str)
                raise ImportError(f"Handler module is not allowed: {mod_str}")
            mod_obj = importlib.import_module(mod_str)
            func = getattr(mod_obj, func_name, None)
            if callable(func):
                return func
            logger.warning(f"Handler '{handler_path}' is not callable, using default")
        except Exception as e:
            logger.warning(f"Failed to import handler '{handler_path}': {e}, using default")

    domain = symbol_info.get('domain', 'Default')
    name = symbol_info.get('name', method_name)
    attributes = symbol_info.get('attributes')
    return make_default_time_hook(domain=domain, name=name, attributes=attributes)


def _metrics_noop_handler(original_func, *args, **kwargs):
    """供 metrics 使用的透传 handler，无 handler_path 时仅由 wrap_handler_with_metrics 封装。"""
    return original_func(*args, **kwargs)


def _profiling_noop_handler(original_func, *args, **kwargs):
    """Trace-only passthrough; it keeps profiling handlers out of the process."""
    return original_func(*args, **kwargs)


def _resolve_metrics_handler_func(symbol_info: dict, method_name: str) -> Callable:
    """解析 metrics 配置的 handler：无 handler_path 时用 wrap_handler_with_metrics 封装透传函数；
    有 handler_path 且为 "module:func" 时导入并直接返回该函数（不再包装）。
    """
    handler_path = symbol_info.get('handler')
    if not handler_path:
        return wrap_handler_with_metrics(_metrics_noop_handler, symbol_info)
    if isinstance(handler_path, str) and ':' in handler_path:
        try:
            mod_str, func_name = handler_path.split(':', 1)
            if not is_allowed_handler_module(mod_str):
                logger.warning("Metrics handler module '%s' is not allowed, using wrap_handler_with_metrics", mod_str)
                raise ImportError(f"Metrics handler module is not allowed: {mod_str}")
            mod_obj = importlib.import_module(mod_str)
            func = getattr(mod_obj, func_name, None)
            if callable(func):
                return func
            logger.warning(f"Metrics handler '{handler_path}' is not callable, using wrap_handler_with_metrics")
        except Exception as e:
            logger.warning(f"Failed to import metrics handler '{handler_path}': {e}, using wrap_handler_with_metrics")
    return wrap_handler_with_metrics(_metrics_noop_handler, symbol_info)


@dataclass
class PatternEntry:
    """一条模式配置，在模块加载时再解析为具体 hook 点。"""

    module_pattern: str
    method_name: str
    class_pattern: str
    name: str
    domain: str
    handler_func: Callable
    min_version: Optional[str] = None
    max_version: Optional[str] = None
    caller_filter: Optional[str] = None
    need_locals: bool = False
    pattern_id: str = ""
    around_hook_factory: Optional[Callable] = None


def _make_trace_factory(item, method_name, symbol_path, traced_symbols, enable_tracing):
    """Build one tracing wrapper while keeping profiling parsing shallow."""
    if not enable_tracing:
        return None

    from .trace_hook import make_trace_around_factory, parse_hook_trace_spec

    try:
        trace_spec = parse_hook_trace_spec(item, method_name)
    except ValueError as exc:
        logger.warning("Skip invalid tracing metadata for %s: %s", symbol_path, exc)
        return None

    if trace_spec is None:
        return None
    if symbol_path in traced_symbols:
        logger.warning("Ignore duplicate tracing definition for %s", symbol_path)
        return None

    traced_symbols.add(symbol_path)
    return make_trace_around_factory(trace_spec)


def _merge_config_impl(
    configs: Tuple[Optional[Any], ...],
    concrete_attr: str = "concrete",
    patterns_attr: str = "patterns",
) -> Tuple[Dict[str, List[ConfigHooker]], List[PatternEntry]]:
    """合并多份配置的 concrete 与 patterns。仅接受 Config 类型或 None。"""
    merged_concrete: Dict[str, List[ConfigHooker]] = {}
    merged_patterns: List[PatternEntry] = []
    for c in configs:
        if c is None:
            continue
        for sym, handlers in (getattr(c, concrete_attr, None) or {}).items():
            merged_concrete.setdefault(sym, []).extend(handlers)
        merged_patterns.extend(getattr(c, patterns_attr, None) or [])
    return merged_concrete, merged_patterns


@dataclass
class ProfilingConfig:
    """Profiling 配置：精确 symbol 的 handler 字典 + 模式列表。"""

    concrete: Dict[str, List[ConfigHooker]] = field(default_factory=dict)
    patterns: List[PatternEntry] = field(default_factory=list)

    @classmethod
    def merge(cls, *configs: Optional["ProfilingConfig"]) -> "ProfilingConfig":
        """合并多个 ProfilingConfig（concrete 按 symbol 合并列表，patterns 拼接）。"""
        merged_concrete, merged_patterns = _merge_config_impl(configs)
        return cls(concrete=merged_concrete, patterns=merged_patterns)


@dataclass
class MetricsConfig:
    """Metrics 配置：精确 symbol 的 handler 字典 + 模式列表。"""

    concrete: Dict[str, List[ConfigHooker]] = field(default_factory=dict)
    patterns: List[PatternEntry] = field(default_factory=list)

    @classmethod
    def merge(cls, *configs: Optional["MetricsConfig"]) -> "MetricsConfig":
        """合并多个 MetricsConfig。"""
        merged_concrete, merged_patterns = _merge_config_impl(configs)
        return cls(concrete=merged_concrete, patterns=merged_patterns)


class ConfigLoader:
    """配置加载器：读取 yml 文件，返回以 symbol 为粒度的 Handler 列表。

    将 yml 配置加载为 handler 列表，以 handler 为粒度，每个 handler 对应自己的 symbol。
    - 若 yml 中对同一 symbol 配置了多个 handler，则放在同一列表中
    - 若 yml 中只定义了 symbol 而未定义 handler，则使用 make_default_time_hook 生成默认 handler
    - Handler 为 DynamicHooker 类实例（继承自 VLLMHookerBase，类似 AutoHooker）

    Attributes:
        _config_path: 配置文件路径
        _framework_version: 框架版本号，用于版本检查
    """

    def __init__(self, config_path: str, framework_version: Optional[str] = None):
        """初始化 ConfigLoader。

        Args:
            config_path: yml 配置文件路径
            framework_version: 框架版本号，如 "0.9.1"，用于版本检查
        """
        self._config_path = config_path
        self._framework_version = framework_version

    def load_profiling(self, enable_profiling: bool = True, enable_tracing: bool = False) -> ProfilingConfig:
        """加载 profiling yml 配置并解析为 Handler 列表与模式列表。

        Returns:
            ProfilingConfig: concrete (symbol_path -> Handler 列表) + patterns (模式列表)。
        """
        raw_config = load_yaml_config(self._config_path)
        if not raw_config:
            return ProfilingConfig()

        if not isinstance(raw_config, list):
            logger.warning("Config should be a list of symbol configurations")
            return ProfilingConfig()

        result: Dict[str, List[ConfigHooker]] = {}
        pattern_entries: List[PatternEntry] = []
        traced_symbols = set()
        for item in raw_config:
            if not isinstance(item, dict) or 'symbol' not in item:
                logger.warning("Skip invalid config item: missing 'symbol'")
                continue

            symbol_path = item['symbol']
            # Trace adapters use their independent around-call wrapper. Keep the
            # bytecode/local-variable path exclusive to existing profiling handlers.
            need_locals = enable_profiling and ("expr" in json.dumps(item) or "handler" in json.dumps(item))

            if _is_pattern_symbol(symbol_path):
                parsed = _parse_symbol_pattern(symbol_path)
                if not parsed:
                    continue
                module_pattern, class_pattern, method_name = parsed
                handler_func = _resolve_handler_func(item, method_name) if enable_profiling else _profiling_noop_handler
                around_hook_factory = _make_trace_factory(
                    item, method_name, symbol_path, traced_symbols, enable_tracing
                )
                if not enable_profiling and around_hook_factory is None:
                    continue
                name = item.get('name', method_name)
                domain = item.get('domain', 'Default')
                pattern_entries.append(
                    PatternEntry(
                        module_pattern=module_pattern,
                        method_name=method_name,
                        class_pattern=class_pattern,
                        name=name,
                        domain=domain,
                        handler_func=handler_func,
                        min_version=item.get('min_version'),
                        max_version=item.get('max_version'),
                        caller_filter=item.get('caller_filter'),
                        need_locals=need_locals,
                        pattern_id=symbol_path,
                        around_hook_factory=around_hook_factory,
                    )
                )
                continue

            module_path, method_name, class_name = _parse_symbol_path(symbol_path)
            if not module_path:
                continue

            hook_points = _build_hook_points(module_path, method_name, class_name)
            handler_func = _resolve_handler_func(item, method_name) if enable_profiling else _profiling_noop_handler
            around_hook_factory = _make_trace_factory(item, method_name, symbol_path, traced_symbols, enable_tracing)
            if not enable_profiling and around_hook_factory is None:
                continue

            handler_instance = ConfigHooker(
                hook_list=hook_points,
                symbol_path=symbol_path,
                hook_func=handler_func,
                min_version=item.get('min_version'),
                max_version=item.get('max_version'),
                caller_filter=item.get('caller_filter'),
                need_locals=need_locals,
                framework_version=self._framework_version,
                around_hook_factory=around_hook_factory,
            )

            if symbol_path not in result:
                result[symbol_path] = []
            result[symbol_path].append(handler_instance)

        logger.debug(
            f"ConfigLoader loaded {len(result)} profiling symbols, {len(pattern_entries)} patterns from {self._config_path}"
        )
        return ProfilingConfig(concrete=result, patterns=pattern_entries)

    def load_metrics(self) -> MetricsConfig:
        """加载 metrics yml 并解析为 Handler 列表与模式列表（每个 handler 经 wrap_handler_with_metrics 包装）。

        Returns:
            MetricsConfig: concrete + patterns，格式与 load_profiling 对称。
        """
        raw_config = load_yaml_config(self._config_path)
        if not raw_config:
            return MetricsConfig()
        if not isinstance(raw_config, list):
            logger.warning("Metrics config should be a list of symbol configurations")
            return MetricsConfig()
        result: Dict[str, List[ConfigHooker]] = {}
        pattern_entries: List[PatternEntry] = []
        for item in raw_config:
            if not isinstance(item, dict) or 'symbol' not in item:
                logger.warning("Skip invalid metrics config item: missing 'symbol'")
                continue
            symbol_path = item['symbol']
            need_locals = "expr" in json.dumps(item) or "handler" in json.dumps(item)

            if _is_pattern_symbol(symbol_path):
                parsed = _parse_symbol_pattern(symbol_path)
                if not parsed:
                    continue
                module_pattern, class_pattern, method_name = parsed
                handler_func = _resolve_metrics_handler_func(item, method_name)
                name = item.get('name', method_name)
                domain = item.get('domain', 'Default')
                pattern_entries.append(
                    PatternEntry(
                        module_pattern=module_pattern,
                        method_name=method_name,
                        class_pattern=class_pattern,
                        name=name,
                        domain=domain,
                        handler_func=handler_func,
                        min_version=item.get('min_version'),
                        max_version=item.get('max_version'),
                        caller_filter=item.get('caller_filter'),
                        need_locals=need_locals,
                        pattern_id=symbol_path,
                    )
                )
                continue

            module_path, method_name, class_name = _parse_symbol_path(symbol_path)
            if not module_path:
                continue
            hook_points = _build_hook_points(module_path, method_name, class_name)
            handler_func = _resolve_metrics_handler_func(item, method_name)
            handler_instance = ConfigHooker(
                hook_list=hook_points,
                symbol_path=symbol_path,
                hook_func=handler_func,
                min_version=item.get('min_version'),
                max_version=item.get('max_version'),
                caller_filter=item.get('caller_filter'),
                need_locals=need_locals,
                framework_version=self._framework_version,
            )
            if symbol_path not in result:
                result[symbol_path] = []
            result[symbol_path].append(handler_instance)
        logger.debug(
            f"ConfigLoader loaded {len(result)} metrics symbols, {len(pattern_entries)} patterns from {self._config_path}"
        )
        return MetricsConfig(concrete=result, patterns=pattern_entries)
