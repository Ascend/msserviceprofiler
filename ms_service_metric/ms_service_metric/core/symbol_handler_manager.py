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
SymbolHandlerManager - Symbol和Handler的核心管理类

负责管理所有的handler和Symbol，根据配置动态加载和卸载handler和symbol，
将所有其他类串联起来形成完整的hook系统。

注意：Symbol和Watcher的交互已封装在Symbol内部，Manager不处理这些细节。
"""

import threading
from typing import Any, Dict, List, Optional

# Control-plane logs interpolate local symbol metadata only.
# pylint: disable=logging-fstring-interpolation

from ms_service_metric.core.config.metric_control_watch import MetricControlWatch
from ms_service_metric.core.config.provider import ProviderRegistry
from ms_service_metric.core.config.symbol_config import SymbolConfig
from ms_service_metric.core.handler import Handler, MetricHandler
from ms_service_metric.core.module.symbol_watcher import SymbolWatcher
from ms_service_metric.core.symbol import Symbol
from ms_service_metric.metrics.metrics_manager import get_metrics_manager
from ms_service_metric.utils.exceptions import ConfigError
from ms_service_metric.utils.logger import get_logger

logger = get_logger("symbol_handler_manager")


class SymbolHandlerManager:
    """Symbol和Handler的核心管理类

    职责：
    1. 管理所有的handler和Symbol
    2. 根据配置动态加载和卸载handler和symbol
    3. 基于handler的增删，自动处理symbol对象
    4. 批量apply_hook，而不是每个handler变化都reapply
    5. 处理打开时，暂停所有symbol的hook/unhook操作，完成后统一执行

    注意：Symbol和Watcher的交互已封装在Symbol内部。

    Attributes:
        _config: SymbolConfig实例，用于加载和管理配置
        _watcher: SymbolWatcher实例，用于监听模块加载事件
        _metrics_manager: MetricsManager实例，用于指标管理
        _control_watch: MetricControlWatch实例，用于控制metric开关和重启
        _symbols: symbol_path到Symbol对象的映射
        _handlers: handler_id到Handler对象的映射
        _enabled: 是否启用hook系统
        _lock: 用于保护_enabled和批量操作的原子性
        _updating: 标记是否正在批量更新
    """

    def __init__(
        self,
        current_version: Optional[str] = None,
        provider_registry: Optional[ProviderRegistry] = None,
    ):
        """初始化SymbolHandlerManager

        Args:
            current_version: 当前框架版本，用于版本控制
        """
        logger.debug(f"Initializing SymbolHandlerManager, version={current_version}")

        # 配置管理
        self._config = SymbolConfig(
            current_version=current_version,
            provider_registry=provider_registry,
        )

        # 模块监视器
        self._watcher = SymbolWatcher()

        # 指标管理器（使用全局单例）
        self._metrics_manager = get_metrics_manager()

        # 控制开关监视器（用于接收on/off/restart命令）
        self._control_watch = MetricControlWatch()

        # Symbol管理
        # key: symbol_path (如 "vllm.worker.model_runner:ModelRunner.execute_model")
        # value: Symbol实例
        self._symbols: Dict[str, Symbol] = {}

        # Handler管理
        # key: handler_id (如 "vllm.worker.model_runner:ModelRunner.execute_model:module.func")
        # value: Handler实例
        self._handlers: Dict[str, Handler] = {}

        # 状态管理
        self._enabled = False
        self._lock = threading.Lock()
        self._updating = False

        # 保存版本信息
        self._current_version = current_version

        logger.debug("SymbolHandlerManager initialized")

    def initialize(
        self,
        config_path: Optional[str] = None,
        default_config_path: Optional[str] = None,
        framework_config_is_user: bool = False,
    ):
        """初始化所有组件

        加载配置，注册回调，启动控制监视器。

        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        logger.info("Initializing SymbolHandlerManager components")

        # 1. 加载配置
        config = self._config.load(
            config_path,
            default_config_path,
            framework_config_is_user=framework_config_is_user,
        )
        logger.debug(f"Loaded config with {len(config)} symbols")

        # 2. 注册控制状态变化回调
        # 回调参数: (is_start: bool, timestamp: int)
        # is_start=True: 开启或重启（时间戳变化表示重启）
        # is_start=False: 关闭
        self._control_watch.register_callback(self._on_control_state_change)
        logger.debug("Registered control state change callback")

        # 3. 启动控制监视器
        self._control_watch.start()
        logger.info("Started MetricControlWatch")

        self._watcher.start()
        logger.info("Started SymbolWatcher")

        logger.info("SymbolHandlerManager initialized successfully")

    def shutdown(self):
        """关闭管理器

        停止所有组件，解绑所有handlers。
        """
        logger.info("Shutting down SymbolHandlerManager")

        with self._lock:
            self._enabled = False
            self._stop_all_symbols()

        # 停止控制监视器
        self._control_watch.stop()

        # 停止模块监视器
        self._watcher.stop()

        logger.info("SymbolHandlerManager shutdown complete")

    def _on_control_state_change(self, is_start: bool, timestamp: int):
        """控制状态变化回调

        处理逻辑：
        1. 关闭命令 (is_start=False):
           - 如果当前已启用，关闭所有symbols并标记为禁用
           - 如果当前已禁用，无操作

        2. 开启命令 (is_start=True):
           - 如果当前已启用且时间戳相同：重复命令，无操作
           - 如果当前已启用且时间戳不同：重启，关闭所有→重载配置→重新应用
           - 如果当前已禁用：普通开启，重载配置→应用

        Args:
            is_start: 是否开启，True=开启/重启，False=关闭
            timestamp: 命令时间戳，用于检测重启
        """
        logger.info(f"Received control state change: is_start={is_start}, timestamp={timestamp}")

        with self._lock:
            # ========== 处理关闭命令 ==========
            if not is_start:
                if not self._enabled:
                    logger.debug("Already stopped, no action needed")
                    return
                self._stop_all_symbols_graceful()
                self._enabled = False
                logger.info("Metrics collection stopped")
                return

            # ========== 处理开启命令 ==========
            # 检查是否重复命令（已启用且时间戳相同）
            if self._enabled and timestamp == self._control_watch.get_last_timestamp():
                logger.debug("Already enabled with same timestamp, no action needed")
                return

            # 标记开始批量更新
            self._updating = True
            logger.debug("Starting batch update")

            # 判断是重启还是普通开启
            is_restart = self._enabled and timestamp != self._control_watch.get_last_timestamp()
            previous_enabled = self._enabled
            teardown_started = False
            handler_update_started = False
            config_state = self._config.snapshot_state()
            try:
                # Load first so a broken Provider cannot tear down working hooks.
                config = self._config.reload()
                logger.debug(f"Reloaded config with {len(config)} symbols")
                target_handlers = self._build_target_handlers(config)

                if is_restart:
                    teardown_started = True
                    self._enabled = False
                    self._stop_all_symbols_graceful()
                    logger.debug("Restart: stopped all symbols")

                handler_update_started = True
                self._reconcile_handlers(target_handlers)
                self._enabled = True
                self._apply_all_hooks()

                action = "restarted" if is_restart else "started"
                logger.info(f"Metrics collection {action}")
            except Exception:
                if handler_update_started:
                    self._reset_live_handlers()
                self._config.restore_state(config_state)
                self._enabled = False if teardown_started or handler_update_started else previous_enabled
                logger.exception(
                    "Failed to update metric configuration; enabled=%s",
                    self._enabled,
                )
                raise
            finally:
                self._updating = False

    def _build_target_handlers(
        self,
        config: Dict[str, List[Dict]],
    ) -> Dict[str, Handler]:
        """Construct every candidate handler before changing live hooks."""
        target_handlers: Dict[str, Handler] = {}
        allowed_handler_module_prefixes = self._config.get_allowed_handler_module_prefixes()
        user_handler_root = self._config.get_user_handler_root()

        for symbol_path, handlers_config in config.items():
            if not isinstance(handlers_config, list):
                raise ConfigError(f"Invalid handlers config for {symbol_path}: expected list")

            for handler_config in handlers_config:
                if not isinstance(handler_config, dict):
                    raise ConfigError(f"Invalid handler config for {symbol_path}: expected dict")

                try:
                    handler = MetricHandler.from_config(
                        handler_config,
                        symbol_path,
                        allowed_handler_module_prefixes,
                        user_handler_root,
                    )
                except Exception as error:
                    raise ConfigError(f"Failed to create handler for {symbol_path}: {error}") from error

                if handler.id in target_handlers:
                    logger.warning(
                        "Skipping duplicate resolved handler %s",
                        handler.id,
                    )
                    continue
                target_handlers[handler.id] = handler
                logger.debug("Target handler: %s", handler.id)

        return target_handlers

    def _update_handlers(self, config: Dict[str, List[Dict]]):
        """根据配置更新handlers

        基于handler的增删，自动管理symbol生命周期。

        Args:
            config: 配置字典，key为symbol_path，value为handler配置列表
        """
        logger.debug("Updating handlers based on config")

        # 构建目标handler集合
        target_handlers = self._build_target_handlers(config)
        self._reconcile_handlers(target_handlers)

    def _reconcile_handlers(
        self,
        target_handlers: Dict[str, Handler],
    ) -> None:
        """Apply a fully constructed handler set to the live registry."""
        current_ids = set(self._handlers)
        target_ids = set(target_handlers)

        # 计算差异
        # Preserve config order when several handlers wrap the same symbol.
        to_add = [handler_id for handler_id in target_handlers if handler_id not in current_ids]
        to_remove = [handler_id for handler_id in self._handlers if handler_id not in target_ids]
        to_update = [handler_id for handler_id in target_handlers if handler_id in current_ids]

        logger.debug(f"Handler changes: +{len(to_add)}, -{len(to_remove)}, ~{len(to_update)}")

        # 新增handlers
        for handler_id in to_add:
            self._add_handler(target_handlers[handler_id])

        # 移除handlers
        for handler_id in to_remove:
            self._remove_handler(handler_id)

        # 更新的handlers（比较配置是否变化）
        for handler_id in to_update:
            if not self._handlers[handler_id].equals(target_handlers[handler_id]):
                self._update_handler(target_handlers[handler_id])

    def _add_handler(self, handler: Handler):
        """添加handler，自动管理symbol生命周期

        如果symbol不存在则创建，然后添加handler到symbol。

        Args:
            handler: Handler实例
        """
        symbol_path = handler.symbol_path
        logger.debug(f"Adding handler: {handler.id} to symbol: {symbol_path}")

        # 获取或创建symbol
        if symbol_path not in self._symbols:
            logger.debug(f"Creating new symbol: {symbol_path}")
            # Symbol内部会自动开始监听watcher
            self._symbols[symbol_path] = Symbol(
                symbol_path,
                self._watcher,
                self,
                self._config.get_allowed_symbol_module_prefixes(),
            )

        symbol = self._symbols[symbol_path]
        symbol.add_handler(handler)
        self._handlers[handler.id] = handler

        logger.debug(f"Added handler: {handler.id} to symbol: {symbol_path}")

    def _remove_handler(self, handler_id: str):
        """移除handler，如果symbol没有handlers则自动删除

        Args:
            handler_id: Handler的唯一标识符
        """
        handler = self._handlers.pop(handler_id, None)
        if handler is None:
            logger.warning(f"Handler not found for removal: {handler_id}")
            return

        symbol_path = handler.symbol_path
        symbol = self._symbols.get(symbol_path)

        if symbol:
            symbol.remove_handler(handler_id)

            # 如果symbol没有handlers，删除symbol
            if symbol.is_empty():
                logger.debug(f"Symbol {symbol_path} is empty, removing")
                symbol.stop()  # 内部会停止监听并解绑
                del self._symbols[symbol_path]

        logger.debug(f"Removed handler: {handler_id}")

    def _update_handler(self, handler: Handler):
        """更新handler（直接替换）

        Args:
            handler: 新的Handler实例
        """
        old_handler = self._handlers.get(handler.id)
        if old_handler is None:
            logger.warning(f"Handler not found for update: {handler.id}")
            return

        symbol_path = handler.symbol_path
        symbol = self._symbols.get(symbol_path)

        if symbol:
            symbol.update_handler(handler)
            self._handlers[handler.id] = handler
            logger.debug(f"Updated handler: {handler.id}")

    def _apply_all_hooks(self):
        """批量应用所有symbols的hooks

        调用每个symbol的hook方法，由symbol内部判断是否应用。
        """
        logger.debug("Applying all hooks")

        hooked_count = 0
        for symbol in self._symbols.values():
            symbol.hook()
            if symbol.hook_applied:
                hooked_count += 1

        logger.info(f"Applied hooks to {hooked_count}/{len(self._symbols)} symbols")

        # debug打印所有symbol的hook情况
        for symbol in self._symbols.values():
            status = "hooked" if symbol.hook_applied else "not hooked"
            handler_count = len(symbol.get_all_handlers())
            logger.info(f"Symbol {symbol.symbol_path}: {status}, handlers: {handler_count}")

    def _reset_live_handlers(self):
        """Stop and discard a partially reconciled live Handler registry."""
        for symbol in self._symbols.values():
            symbol.stop()
        self._symbols.clear()
        self._handlers.clear()
        logger.info("Cleared live handlers after a failed metric update")

    def _stop_all_symbols(self):
        """停止所有symbols

        对每个symbol执行stop操作（停止监听并解绑）。
        """
        logger.debug("Stopping all symbols")

        for symbol in self._symbols.values():
            symbol.stop()

        logger.info(f"Stopped all symbols ({len(self._symbols)} symbols)")

    def _stop_all_symbols_graceful(self):
        """优雅地停止所有symbols

        根据handler的lock_patch属性决定是否保留：
        - lock_patch=True: 保留handler，不解绑symbol
        - lock_patch=False: 删除handler，如果symbol没有handlers则解绑
        """
        logger.debug("Stopping all symbols gracefully")

        symbols_to_remove = []
        handlers_to_remove = []

        for symbol_path, symbol in self._symbols.items():
            # 停止未锁定的部分，返回(已删除handlers, 保留handlers)
            removed_ids, kept_ids = symbol.stop_unlocked()

            # 收集已删除的handlers
            handlers_to_remove.extend(removed_ids)

            if kept_ids:
                # 还有锁定的handlers，保留symbol，继续监听
                logger.debug(f"Symbol {symbol_path} kept {len(kept_ids)} locked handlers")
            else:
                # 没有锁定的handlers，已经解绑，只需停止监听
                symbol.stop_watching()
                symbols_to_remove.append(symbol_path)

        # 删除没有锁定handlers的symbols
        for symbol_path in symbols_to_remove:
            del self._symbols[symbol_path]
            logger.debug(f"Removed symbol {symbol_path} (no locked handlers)")

        # 从registry中删除handlers（确保没有遗漏）
        for handler_id in handlers_to_remove:
            if handler_id in self._handlers:
                del self._handlers[handler_id]
                logger.debug(f"Removed handler {handler_id} from registry")

        logger.info(
            f"Graceful stop complete: removed {len(symbols_to_remove)} symbols, "
            f"removed {len(handlers_to_remove)} handlers, "
            f"kept {len(self._symbols)} symbols"
        )

    def is_updating(self) -> bool:
        """检查是否正在批量更新

        用于Symbol判断是否应该立即执行hook或标记待处理。

        Returns:
            是否正在批量更新
        """
        return self._updating

    def is_enabled(self) -> bool:
        """检查是否启用

        Returns:
            是否启用hook系统
        """
        return self._enabled

    def get_symbol(self, symbol_path: str) -> Optional[Symbol]:
        """获取指定symbol

        Args:
            symbol_path: Symbol路径

        Returns:
            Symbol实例或None
        """
        return self._symbols.get(symbol_path)

    def get_handler(self, handler_id: str) -> Optional[Handler]:
        """获取指定handler

        Args:
            handler_id: Handler唯一标识符

        Returns:
            Handler实例或None
        """
        return self._handlers.get(handler_id)

    def get_all_symbols(self) -> Dict[str, Symbol]:
        """获取所有symbols

        Returns:
            symbol_path到Symbol的映射字典
        """
        return self._symbols.copy()

    def get_all_handlers(self) -> Dict[str, Handler]:
        """获取所有handlers

        Returns:
            handler_id到Handler的映射字典
        """
        return self._handlers.copy()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            包含各种统计信息的字典
        """
        return {
            "enabled": self._enabled,
            "updating": self._updating,
            "symbol_count": len(self._symbols),
            "handler_count": len(self._handlers),
            "hooked_symbols": sum(1 for s in self._symbols.values() if s.hook_applied),
        }
