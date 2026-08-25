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

import importlib
import importlib.abc
import importlib.machinery as _machinery
import inspect
import sys
import threading
from itertools import chain
from typing import Any, Dict, List, Optional, Set, Tuple

from .config_loader import MetricsConfig, PatternEntry, ProfilingConfig
from .dynamic_hook import ConfigHooker
from .logger import logger


def _module_prefix_from_pattern(module_pattern: str) -> str:
    """从 module_pattern（如 vllm.model_executor.models.*）得到用于前缀匹配的 prefix（含末尾点）。"""
    prefix = module_pattern.rstrip("*").rstrip(".")
    return prefix + "." if prefix else ""


def _pattern_matches_module(module_pattern: str, fullname: str) -> bool:
    """模块全名是否匹配模式（前缀匹配，且排除包自身）。"""
    prefix = _module_prefix_from_pattern(module_pattern)
    if not prefix:
        return False
    return fullname.startswith(prefix) and len(fullname) > len(prefix)


def discover_classes_with_method(module: Any, method_name: str, module_fullname: str) -> List[Tuple[str, str]]:
    """发现模块内定义了指定方法的类（方法须在本模块内定义），返回 [(class_name, method_name), ...]。"""
    out: List[Tuple[str, str]] = []
    for _name, cls in inspect.getmembers(module, inspect.isclass):
        if cls.__module__ != module_fullname:
            continue
        meth = getattr(cls, method_name, None)
        if not callable(meth):
            continue
        if getattr(meth, "__module__", None) != module_fullname:
            continue
        out.append((cls.__name__, method_name))
    return out


class SymbolWatchFinder(importlib.abc.MetaPathFinder):
    """监听配置中的 symbol 模块导入，动态应用 hooks。

    使用 ConfigLoader 加载的 Handler 列表，以 handler 为粒度监听模块导入并应用 hooks。

    Attributes:
        _symbol_handlers_profiling (Dict): symbol_path -> List[DynamicHooker]，profiling 配置
        _symbol_handlers_metrics (Dict): symbol_path -> List[DynamicHooker]，metrics 配置
        _config_loaded (bool): 配置是否已加载
        _applied_hooks (Set): 已准备的 symbol 集合
    """

    def __init__(self):
        """初始化 SymbolWatchFinder。"""
        self._symbol_handlers_profiling: Dict[str, List] = {}
        self._symbol_handlers_metrics: Dict[str, List] = {}
        self._pattern_handlers_profiling: List[PatternEntry] = []
        self._pattern_handlers_metrics: List[PatternEntry] = []
        self._pattern_to_concrete_profiling: Dict[str, List[Tuple[str, ConfigHooker]]] = {}
        self._pattern_to_concrete_metrics: Dict[str, List[Tuple[str, ConfigHooker]]] = {}
        self._module_matching_pattern_cache: Dict[str, List[Tuple[PatternEntry, Dict]]] = {}
        self._config_loaded = False
        self._applied_hooks = set()
        self._prepared_hookers: Set = set()
        self._applied_hookers: List = []
        self._symbol_to_hooker: Dict[str, List] = {}
        self._auto_apply_enabled = False
        self._lock = threading.Lock()

    def set_auto_apply(self, enabled: bool):
        """设置是否在 hook 准备完成后立刻应用（init）。"""
        self._auto_apply_enabled = bool(enabled)

    def get_applied_hookers(self):
        """获取所有已实际应用过的 hookers。"""
        with self._lock:
            return list(self._applied_hookers)

    def get_current_profiling_handlers(self) -> ProfilingConfig:
        """返回当前已加载的 profiling 配置（含 concrete 与 patterns），供 update_metrics_handlers 使用。"""
        with self._lock:
            return ProfilingConfig(
                concrete=dict(self._symbol_handlers_profiling),
                patterns=list(self._pattern_handlers_profiling),
            )

    def get_current_metrics_handlers(self) -> MetricsConfig:
        """返回当前已加载的 metrics 配置（含 concrete 与 patterns），供 enable(metrics_handlers=None) 时保留。"""
        with self._lock:
            return MetricsConfig(
                concrete=dict(self._symbol_handlers_metrics),
                patterns=list(self._pattern_handlers_metrics),
            )

    def _get_hookers_for_symbol(self, symbol_path: str) -> List:
        """获取 symbol 对应的 hooker 列表。"""
        val = self._symbol_to_hooker.get(symbol_path)
        if val is None:
            return []
        return val if isinstance(val, list) else [val]

    def recover_hookers_for_symbols(self, symbol_paths: set):
        """恢复指定 symbol 路径对应的已应用 hookers。"""
        with self._lock:
            hookers_to_recover = []
            for symbol_path in symbol_paths:
                for hooker in self._get_hookers_for_symbol(symbol_path):
                    if hooker in self._applied_hookers:
                        hookers_to_recover.append(hooker)

            for hooker in hookers_to_recover:
                hooker.recover()

    def _get_combined_symbol_paths(self):
        """返回当前已加载的 profiling 与 metrics 的 symbol 路径并集。"""
        return set(self._symbol_handlers_profiling.keys()) | set(self._symbol_handlers_metrics.keys())

    def _get_handlers_for_symbol(self, symbol_path: str) -> List:
        """返回某 symbol 的 handler 列表（profiling 优先，metrics 在后，保证最终替换为 metrics）。"""
        p = self._symbol_handlers_profiling.get(symbol_path) or []
        m = self._symbol_handlers_metrics.get(symbol_path) or []
        return p + m

    def _apply_one_pattern_hook(
        self,
        module_fullname: str,
        class_name: str,
        method_name: str,
        entry: PatternEntry,
        pattern_to_concrete: Dict[str, List[Tuple[str, ConfigHooker]]],
    ) -> None:
        """为模式发现的一个 (模块, 类, 方法) 创建并应用 ConfigHooker，并登记到 pattern_to_concrete。"""
        symbol_path = f"{module_fullname}:{class_name}:{method_name}"
        if symbol_path in self._symbol_to_hooker:
            return
        hook_list = [(module_fullname, f"{class_name}.{method_name}")]
        handler = ConfigHooker(
            hook_list=hook_list,
            symbol_path=symbol_path,
            hook_func=entry.handler_func,
            min_version=entry.min_version,
            max_version=entry.max_version,
            caller_filter=entry.caller_filter,
            need_locals=entry.need_locals,
            around_hook_factory=entry.around_hook_factory,
        )
        handler.register()
        self._prepared_hookers.add(handler)
        self._symbol_to_hooker.setdefault(symbol_path, []).append(handler)
        self._applied_hooks.add(symbol_path)
        pattern_to_concrete.setdefault(entry.pattern_id, []).append((symbol_path, handler))
        if self._auto_apply_enabled:
            try:
                handler.init()
                with self._lock:
                    if handler not in self._applied_hookers:
                        self._applied_hookers.append(handler)
                logger.debug("Auto-applied pattern handler for %s", symbol_path)
            except Exception as e:
                logger.error("Failed to auto-apply handler for %s: %s", symbol_path, e)
        logger.debug("Prepared pattern handler for %s (pattern %s)", symbol_path, entry.pattern_id)

    def _recover_and_remove_pattern_hookers(
        self,
        pattern_to_concrete: Dict[str, List[Tuple[str, ConfigHooker]]],
        removed_pattern_ids: Set[str],
        hooks_enabled: bool,
    ) -> None:
        """恢复并移除已删除的 pattern 对应的 hooker，并清理 _symbol_to_hooker / _applied_hooks。"""
        for pattern_id in removed_pattern_ids:
            for symbol_path, hooker in pattern_to_concrete.get(pattern_id, []):
                if hooker in self._prepared_hookers:
                    self._prepared_hookers.remove(hooker)
                if hooker in self._applied_hookers:
                    if hooks_enabled:
                        hooker.recover()
                    self._applied_hookers.remove(hooker)
                if symbol_path in self._symbol_to_hooker:
                    lst = self._symbol_to_hooker[symbol_path]
                    if hooker in lst:
                        lst.remove(hooker)
                    if not lst:
                        del self._symbol_to_hooker[symbol_path]
                        self._applied_hooks.discard(symbol_path)
            if pattern_id in pattern_to_concrete:
                del pattern_to_concrete[pattern_id]

    def load_handlers(
        self,
        profiling_handlers: Optional[ProfilingConfig] = None,
        metrics_handlers: Optional[MetricsConfig] = None,
        hooks_enabled: bool = False,
    ) -> None:
        """加载 profiling 与 metrics 两路配置（ProfilingConfig / MetricsConfig），分别存储并参与后续处理。

        Args:
            profiling_handlers: 由 ConfigLoader.load_profiling() 返回，含 concrete 与 patterns
            metrics_handlers: 由 ConfigLoader.load_metrics() 返回，含 concrete 与 patterns
            hooks_enabled: hooks 是否当前已启用，用于配置变更时的恢复逻辑
        """
        concrete_profiling = (profiling_handlers.concrete if profiling_handlers else {}).copy()
        patterns_profiling = list(profiling_handlers.patterns if profiling_handlers else [])
        concrete_metrics = (metrics_handlers.concrete if metrics_handlers else {}).copy()
        patterns_metrics = list(metrics_handlers.patterns if metrics_handlers else [])

        new_symbol_paths = set(concrete_profiling.keys()) | set(concrete_metrics.keys())
        new_pattern_ids_profiling = {p.pattern_id for p in patterns_profiling}
        new_pattern_ids_metrics = {p.pattern_id for p in patterns_metrics}
        new_config_handlers = set(chain.from_iterable(concrete_profiling.values())) | set(
            chain.from_iterable(concrete_metrics.values())
        )
        ori_config_handlers = set(chain.from_iterable(self._symbol_handlers_profiling.values())) | set(
            chain.from_iterable(self._symbol_handlers_metrics.values())
        )

        if self._config_loaded:
            removed_symbols = self._applied_hooks - new_symbol_paths
            removed_handlers = ori_config_handlers - new_config_handlers
            if removed_symbols:
                self._applied_hooks -= removed_symbols
            if removed_symbols or removed_handlers:
                with self._lock:
                    if removed_handlers:
                        logger.debug(
                            "Removing %d handlers from config (%d symbols no longer in config)",
                            len(removed_handlers),
                            len(removed_symbols),
                        )
                        for hooker in removed_handlers:
                            if hooks_enabled:
                                hooker.recover()
                            if hooker in self._prepared_hookers:
                                self._prepared_hookers.remove(hooker)
                            if hooker in self._applied_hookers:
                                self._applied_hookers.remove(hooker)
                        for symbol_path in list(self._symbol_to_hooker.keys()):
                            lst = self._symbol_to_hooker[symbol_path]
                            for h in removed_handlers:
                                if h in lst:
                                    lst.remove(h)
                            if not lst:
                                del self._symbol_to_hooker[symbol_path]
                                self._applied_hooks.discard(symbol_path)
                    self._recover_and_remove_pattern_hookers(
                        self._pattern_to_concrete_profiling,
                        set(self._pattern_to_concrete_profiling.keys()) - new_pattern_ids_profiling,
                        hooks_enabled,
                    )
                    self._recover_and_remove_pattern_hookers(
                        self._pattern_to_concrete_metrics,
                        set(self._pattern_to_concrete_metrics.keys()) - new_pattern_ids_metrics,
                        hooks_enabled,
                    )

        self._symbol_handlers_profiling = concrete_profiling
        self._symbol_handlers_metrics = concrete_metrics
        self._pattern_handlers_profiling = patterns_profiling
        self._pattern_handlers_metrics = patterns_metrics
        self._module_matching_pattern_cache.clear()
        self._config_loaded = True
        logger.debug(
            "Loaded handlers for %d symbols (profiling: %d, metrics: %d), %d profiling patterns, %d metrics patterns",
            len(new_symbol_paths),
            len(self._symbol_handlers_profiling),
            len(self._symbol_handlers_metrics),
            len(self._pattern_handlers_profiling),
            len(self._pattern_handlers_metrics),
        )

    def find_spec(self, fullname, path, target=None):
        """查找模块规范，实现模块导入监听。"""
        if not self._is_target_symbol(fullname):
            return None

        spec = _machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return spec

        if getattr(spec.loader, "_vllm_profiler_wrapped", False):
            return spec

        orig_loader = spec.loader

        class LoaderWrapper(importlib.abc.Loader):
            _vllm_profiler_wrapped = True

            def __init__(self, finder):
                self._finder = finder

            def create_module(self, spec):
                if hasattr(orig_loader, "create_module"):
                    return orig_loader.create_module(spec)
                return None

            def exec_module(self, module):
                orig_loader.exec_module(module)
                self._finder.on_symbol_module_loaded(fullname)

        wrapper = LoaderWrapper(self)
        spec.loader = wrapper
        return spec

    def _is_target_symbol(self, fullname):
        """检查是否是配置中的目标 symbol 模块（精确 symbol 或模式匹配），
        并在命中时缓存该模块匹配的 pattern 列表，供 _prepare_hooks_for_module 直接使用。
        """
        if not self._config_loaded:
            return False
        concrete_match = False
        for symbol_path in self._get_combined_symbol_paths():
            module_path = symbol_path.split(':')[0]
            if fullname == module_path or module_path.startswith(fullname + '.'):
                concrete_match = True
                break
        all_pattern_entries = self._pattern_handlers_profiling + self._pattern_handlers_metrics
        matching = [e for e in all_pattern_entries if _pattern_matches_module(e.module_pattern, fullname)]
        if concrete_match or matching:
            self._module_matching_pattern_cache[fullname] = [
                (
                    e,
                    self._pattern_to_concrete_profiling
                    if e in self._pattern_handlers_profiling
                    else self._pattern_to_concrete_metrics,
                )
                for e in matching
            ]
            return True
        return False

    def on_symbol_module_loaded(self, fullname: str):
        """当 symbol 模块加载完成时的回调。"""
        logger.debug("SymbolWatchFinder: Module loaded callback for %s", fullname)
        self._prepare_hooks_for_module(fullname)

    def _prepare_hooks_for_module(self, fullname: str):
        """准备模块的 hooks（精确 symbol + 模式动态发现的 hook）。"""
        module_handlers: List[Tuple[str, List]] = []
        for symbol_path in self._get_combined_symbol_paths():
            module_path = symbol_path.split(':')[0]
            if fullname == module_path:
                handler_list = self._get_handlers_for_symbol(symbol_path)
                if handler_list:
                    module_handlers.append((symbol_path, handler_list))

        module_obj = sys.modules.get(fullname)
        matching_data = self._module_matching_pattern_cache.pop(fullname, [])
        for entry, pattern_to_concrete in matching_data:
            if not module_obj:
                continue
            discovered = discover_classes_with_method(module_obj, entry.method_name, fullname)
            for class_name, method_name in discovered:
                self._apply_one_pattern_hook(fullname, class_name, method_name, entry, pattern_to_concrete)

        if module_handlers:
            logger.debug(
                "Detected symbol module loaded: %s, preparing %d handler groups", fullname, len(module_handlers)
            )
            self._prepare_handlers_for_module(fullname, module_handlers)

    def _prepare_handlers_for_module(self, module_name: str, module_handlers: List[Tuple[str, List]]):
        """为特定模块准备 Handler。"""
        try:
            for symbol_path, handler_list in module_handlers:
                hookers_for_symbol = []
                for handler in handler_list:
                    handler.register()
                    self._prepared_hookers.add(handler)
                    hookers_for_symbol.append(handler)
                    if self._auto_apply_enabled:
                        try:
                            handler.init()
                            with self._lock:
                                if handler not in self._applied_hookers:
                                    self._applied_hookers.append(handler)
                            logger.debug("Auto-applied handler for symbol %s", symbol_path)
                        except Exception as e:
                            logger.error("Failed to auto-apply handler for %s: %s", symbol_path, e)
                self._symbol_to_hooker[symbol_path] = hookers_for_symbol
                self._applied_hooks.add(symbol_path)
                logger.debug("Prepared %d handler(s) for symbol %s", len(handler_list), symbol_path)
        except Exception as e:
            logger.error("Failed to prepare handlers for module %s: %s", module_name, e)

    def apply_all_hooks(self):
        """应用所有准备好的 hooks。"""
        self.set_auto_apply(True)
        logger.info("Applying %d prepared hooks...", len(self._prepared_hookers))
        applied_now = 0
        for hooker in list(self._prepared_hookers):
            try:
                hooker.init()
                with self._lock:
                    if hooker not in self._applied_hookers:
                        self._applied_hookers.append(hooker)
                applied_now += 1
                logger.debug("Applied hooker: %s", hooker.applied_hook_func_name)
            except Exception as e:
                logger.error("Failed to apply hooker %s: %s", hooker.applied_hook_func_name, e)
        logger.info("Successfully applied %d hooks", applied_now)
        return self.get_applied_hookers()

    def check_and_apply_existing_modules(self) -> bool:
        """检查目标模块是否已经被导入，如果是则立即准备 hooks（含模式匹配的模块）。"""
        logger.debug("Checking for already loaded modules...")
        seen = set()
        # concrete symbol处理逻辑
        for symbol_path in self._get_combined_symbol_paths():
            module_path = symbol_path.split(":")[0]
            if module_path in sys.modules and module_path not in seen:
                seen.add(module_path)
                logger.debug("Module %s already loaded, preparing handlers", module_path)
                self.on_symbol_module_loaded(module_path)
        # pattern symbol处理逻辑
        for fullname in list(sys.modules.keys()):
            if not fullname or fullname in seen:
                continue
            if self._is_target_symbol(fullname):
                seen.add(fullname)
                logger.debug("Module %s matches pattern, preparing handlers", fullname)
                self.on_symbol_module_loaded(fullname)
        return True
