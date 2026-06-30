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
Symbol: 代表一个需要hook的符号

职责：
- 代表一个需要hook的符号（类方法、函数等）
- 管理其handlers（不允许重复）
- 直接监听模块加载事件（不通过SymbolHandlerManager中转）
- 根据Manager状态决定是否执行hook/unhook
- 批量apply_hook，而不是每个handler变化都reapply
- 支持优雅停止（lock_patch功能）

使用示例：
    symbol = Symbol('module.path:ClassName.method_name', watcher, manager)
    symbol.add_handler(handler)
    symbol.hook()  # 如果模块已加载，应用hook
    symbol.unhook()  # 恢复原始函数
    symbol.stop()  # 停止监听并解绑
    symbol.stop_unlocked()  # 根据lock_patch停止handlers，返回(已删除ids, 保留ids)
"""

import importlib
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from ms_service_metric.utils.exceptions import SymbolError
from ms_service_metric.utils.logger import get_logger
from ms_service_metric.utils.import_security import is_allowed_symbol_module
from ms_service_metric.core.handler import MetricHandler, HandlerType
from ms_service_metric.core.hook.hook_chain import HookChain

if TYPE_CHECKING:
    from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager
    from ms_service_metric.core.module.symbol_watcher import SymbolWatcher, ModuleEvent

logger = get_logger("symbol")


class Symbol:
    """Symbol类，代表一个需要hook的符号

    每个Symbol对应一个需要hook的目标（类方法、函数等）。
    一个Symbol可以包含多个Handler，这些Handler会被组合成一个hook函数。

    Attributes:
        symbol_path: symbol完整路径，格式为 "module.path:ClassName.method_name"
        module_path: 模块路径
        handlers: 该symbol的所有handlers
        hook_applied: 是否已经应用hook
        module_loaded: 模块是否已加载
        pending_hook: 是否有待执行的hook（在批量更新期间）
    """

    def __init__(self, symbol_path: str, watcher: "SymbolWatcher", manager: "SymbolHandlerManager"):
        """
        初始化Symbol

        Args:
            symbol_path: symbol路径，格式为 "module.path:ClassName.method_name"
            watcher: SymbolWatcher实例，用于监听模块事件
            manager: SymbolHandlerManager实例，用于检查更新状态

        Raises:
            SymbolError: symbol_path格式无效
        """
        self._symbol_path = symbol_path

        # 解析symbol路径
        if ':' not in symbol_path:
            raise SymbolError(
                f"Invalid symbol path format: {symbol_path}, expected 'module.path:ClassName.method_name'"
            )

        self._module_path, self._attr_path = symbol_path.split(':', 1)

        # 初始化handlers字典，key为handler id
        self._handlers: Dict[str, MetricHandler] = {}

        # hook状态
        self._hook_applied = False
        self._hook_node: Optional[Any] = None  # HookNode实例
        self._hook_chain: Optional[Any] = None  # HookChain实例
        self._handlers_changed = False  # 标记handlers是否有变化，需要重新hook

        # 模块状态
        self._module_loaded = False
        self._pending_hook = False  # 标记是否有待执行的hook
        self._target: Optional[Any] = None  # 缓存导入的目标对象

        # 引用watcher和manager
        self._watcher = watcher
        self._manager = manager

        # 开始监听模块事件
        self._start_watching()

        logger.debug("Symbol created: %s", symbol_path)

    @property
    def symbol_path(self) -> str:
        """symbol完整路径"""
        return self._symbol_path

    @property
    def module_path(self) -> str:
        """模块路径"""
        return self._module_path

    @property
    def attr_path(self) -> str:
        """属性路径（类名.方法名）"""
        return self._attr_path

    @property
    def hook_applied(self) -> bool:
        """是否已经应用hook"""
        return self._hook_applied

    @property
    def module_loaded(self) -> bool:
        """模块是否已加载"""
        return self._module_loaded

    @property
    def pending_hook(self) -> bool:
        """是否有待执行的hook"""
        return self._pending_hook

    def _start_watching(self):
        """开始监听模块事件"""
        if self._watcher is None:
            return

        # 注册回调，如果模块已加载会立即触发回调
        self._watcher.watch_module(self._module_path, self._on_module_loaded)
        logger.debug("Symbol %s started watching module %s", self._symbol_path, self._module_path)

    def stop_watching(self):
        """停止监听模块事件"""
        if self._watcher:
            self._watcher.unwatch_module(self._module_path, self._on_module_loaded)
            logger.debug("Symbol %s stopped watching", self._symbol_path)

    def _on_module_loaded(self, event: "ModuleEvent"):
        """
        模块加载回调

        当监控的模块被加载时触发（SymbolWatcher已确保回调时就是该模块）。
        如果manager正在批量更新，则标记待处理而不是立即执行hook。

        Args:
            event: 模块事件
        """
        logger.debug("Module %s loaded, symbol: %s", event.module_name, self._symbol_path)
        self._module_loaded = True

        # 导入目标对象并缓存
        self._target = self._import_target()
        if self._target is None:
            logger.warning("Failed to import target for symbol %s", self._symbol_path)
            return

        # 如果manager不在批量更新中，立即执行hook
        if not self._manager.is_updating():
            self._apply_hook()
        else:
            # 标记待执行，由manager批量处理
            self._pending_hook = True
            logger.debug("Symbol %s marked as pending hook (updating)", self._symbol_path)

    def add_handler(self, handler: MetricHandler):
        """
        添加handler（不允许重复）

        Args:
            handler: Handler实例

        Note:
            如果handler已存在（相同id），会记录警告并忽略
        """
        if handler.id in self._handlers:
            logger.warning("MetricHandler %s already exists in symbol %s, ignoring", handler.id, self._symbol_path)
            return

        self._handlers[handler.id] = handler
        self._handlers_changed = True
        logger.debug(
            "MetricHandler %s added to symbol %s, total handlers: %s",
            handler.id,
            self._symbol_path,
            len(self._handlers),
        )

    def remove_handler(self, handler_id: str):
        """
        移除handler

        Args:
            handler_id: handler的唯一标识符
        """
        if handler_id in self._handlers:
            del self._handlers[handler_id]
            self._handlers_changed = True
            logger.debug("MetricHandler %s removed from symbol %s", handler_id, self._symbol_path)

    def update_handler(self, handler: MetricHandler):
        """
        更新handler（直接替换）

        Args:
            handler: 新的Handler实例
        """
        self._handlers[handler.id] = handler
        self._handlers_changed = True
        logger.debug("MetricHandler %s updated in symbol %s", handler.id, self._symbol_path)

    def get_handler(self, handler_id: str) -> Optional[MetricHandler]:
        """
        获取指定handler

        Args:
            handler_id: handler的唯一标识符

        Returns:
            Handler实例，如果不存在返回None
        """
        return self._handlers.get(handler_id)

    def get_all_handlers(self) -> List[MetricHandler]:
        """
        获取所有handlers

        Returns:
            Handler实例列表
        """
        return list(self._handlers.values())

    def is_empty(self) -> bool:
        """
        检查是否没有handlers

        Returns:
            如果没有handlers返回True
        """
        return len(self._handlers) == 0

    def has_handler(self, handler_id: str) -> bool:
        """
        检查是否包含指定handler

        Args:
            handler_id: handler的唯一标识符

        Returns:
            如果包含返回True
        """
        return handler_id in self._handlers

    def hook(self):
        """
        应用hook（对外接口）

        仅当满足以下条件时才会应用hook：
        1. 模块已加载
        2. 尚未应用hook 或 handlers有变化
        3. 有handlers
        """
        # 检查条件
        if not self._module_loaded:
            logger.debug("Symbol %s module not loaded yet", self._symbol_path)
            return

        if not self._handlers:
            logger.debug("Symbol %s has no handlers", self._symbol_path)
            return

        # 如果已经hook且handlers没有变化，跳过
        if self._hook_applied and not self._handlers_changed:
            logger.debug("Symbol %s already hooked and no changes", self._symbol_path)
            return

        # 如果target还没导入，尝试导入
        if self._target is None:
            self._target = self._import_target()
            if self._target is None:
                logger.warning("Failed to import target for symbol %s", self._symbol_path)
                return

        self._apply_hook()

    def _apply_hook(self):
        """
        应用或更新hook（内部核心方法）

        根据条件创建或复用chain和node，然后构建并设置hook函数。
        可以被hook()和update_hook()调用。
        """
        if not self._handlers:
            logger.debug("Symbol %s has no handlers", self._symbol_path)
            return

        if self._target is None:
            logger.warning("No target available for symbol %s", self._symbol_path)
            return

        logger.debug("Applying hook for symbol %s", self._symbol_path)

        try:
            # 收集所有handler的信息
            handlers = list(self._handlers.values())

            # 分离wrap handlers和context handlers
            wrap_funcs = []
            context_funcs = []
            for h in handlers:
                handler_type, hook_func = h.get_hook_func(self._target)
                if handler_type == HandlerType.WRAP:
                    wrap_funcs.append(hook_func)
                else:
                    context_funcs.append(hook_func)

            # 根据条件创建或复用chain和node
            if self._hook_chain is None:
                # 创建新的chain和node
                from ms_service_metric.core.hook.hook_chain import get_chain

                self._hook_chain = get_chain(self._target)
                self._hook_node = self._hook_chain.add_chain_node(insert_at_head=True)
                action = "Hooked"
            else:
                # 复用已有的chain和node
                action = "Updated"

            # 构建最终的hook函数
            final_hook = self._build_final_hook(
                self._hook_chain.ori_func, self._hook_node.ori_wrap, wrap_funcs, context_funcs, self._hook_chain
            )

            # 设置hook函数
            self._hook_node.set_hook_func(final_hook)

            self._hook_applied = True
            self._pending_hook = False
            self._handlers_changed = False  # 重置变化标志

            logger.info("%s symbol: %s (%s handlers)", action, self._symbol_path, len(handlers))

        except Exception as e:
            logger.error(
                "Failed to apply hook for %s: %s. "
                "If this issue persists, please report it to: "
                "https://gitcode.com/Ascend/msserviceprofiler/discussions",
                self._symbol_path,
                e,
            )
            logger.debug("Hook application error details: %s", e, exc_info=True)
            self._hook_applied = False

    def _build_final_hook(
        self, target: Any, ori_wrap: Any, wrap_funcs: List[Callable], context_funcs: List[Callable], chain: HookChain
    ) -> Callable:
        """构建最终的hook函数

        根据handler类型和need_locals标志，构建最终的hook函数。
        返回的函数是一个完整的包装函数，签名是(*args, **kwargs）。

        执行顺序：注入（获取locals）-> 封装 -> wrap

        Args:
            target: 真正的原函数（用于字节码注入）
            ori_wrap: 调用链中下一个函数的包装器（用于wrap handlers）
            wrap_funcs: wrap函数列表
            context_handlers: context handler函数列表
            need_locals: 是否需要访问locals

        Returns:
            最终的hook函数，签名(*args, **kwargs)
        """
        ori_wrap = target  # 默认直接调用原函数

        # 1. 需要locals的context handlers先走字节码注入（针对真正的原函数target）
        if context_funcs:
            logger.debug("Symbol %s has context handlers that need locals, using injection", self._symbol_path)
            ori_wrap = self._build_hook_with_injection(target, context_funcs, chain)

        # 3. 最后用wrap handlers包装（使用ori_wrap）
        if wrap_funcs:
            ori_wrap = self._build_wrap_chain(target, ori_wrap, wrap_funcs)

        return ori_wrap

    def _build_wrap_chain(self, target: Any, ori_wrap: Any, wrap_funcs: List[Callable]) -> Callable:
        """构建wrap函数链（洋葱模型）

        参考重构前 MultiHandlerDynamicHooker.build_wrap_hook_func 的实现。
        支持同步和异步函数。

        Args:
            target: 目标对象（或者原始函数），用于构建最内层调用ori的函数
            wrap_funcs: wrap函数列表，每个函数签名应为 (ori_func, *args, **kwargs)

        Returns:
            wrap函数链，签名是 (*args, **kwargs)
        """
        if not wrap_funcs:
            # 没有wrap handler，返回透传函数
            return ori_wrap

        import asyncio

        # 检测target是否是异步函数
        is_async = asyncio.iscoroutinefunction(target)

        if is_async:
            return self._build_async_wrap_chain(ori_wrap, wrap_funcs)
        else:
            return self._build_sync_wrap_chain(ori_wrap, wrap_funcs)

    def _build_sync_wrap_chain(self, ori_wrap: Any, wrap_funcs: List[Callable]) -> Callable:
        """构建同步wrap函数链"""

        def create_layer(wrap_func, inner_layer):
            def layer(*args, **kwargs):
                return wrap_func(inner_layer, *args, **kwargs)

            return layer

        if len(wrap_funcs) == 1:
            if wrap_funcs[0]:
                return create_layer(wrap_funcs[0], ori_wrap)
            else:
                return ori_wrap

        # 从内到外构建调用链（洋葱模型）
        chain = ori_wrap
        for wrap_func in reversed(wrap_funcs):
            chain = create_layer(wrap_func, chain)

        return chain

    def _build_async_wrap_chain(self, ori_wrap: Any, wrap_funcs: List[Callable]) -> Callable:
        """构建异步wrap函数链

        wrap_func 内部负责调用 ori 并处理结果。
        返回异步函数。
        """

        def create_layer(wrap_func, inner_layer):
            async def layer(*args, **kwargs):
                return await wrap_func(inner_layer, *args, **kwargs)

            return layer

        if len(wrap_funcs) == 1:
            if not wrap_funcs[0]:
                return ori_wrap
            return create_layer(wrap_funcs[0], ori_wrap)

        # 从内到外构建调用链（洋葱模型）
        chain = ori_wrap
        for wrap_func in reversed(wrap_funcs):
            chain = create_layer(wrap_func, chain)

        return chain

    def _build_context_wrap_handler(self, wrap_chain: Any, context_funcs: List[Callable]) -> Callable:
        """将context handlers封装成一个wrap handler

        不需要locals时，将context handlers封装成一个wrap handler，
        然后再用wrap_chain包装（洋葱模型）。

        Args:
            wrap_chain: wrap函数链，签名 (ori, *args, **kwargs)
            context_funcs: context handler函数列表

        Returns:
            最终的hook函数，签名 (*args, **kwargs)
        """
        import threading
        from ms_service_metric.utils.function_context import FunctionContext

        thread_local = threading.local()

        def context_wrap_handler(*args, **kwargs):
            """Context handler包装器

            Args:
                *args, **kwargs: 函数参数
            """
            MAX_HOOK_FAILURES = 5
            failed_hook_func = [0 for _ in context_funcs]

            def get_context():
                if not hasattr(thread_local, "context"):
                    thread_local.context = FunctionContext()
                return thread_local.context

            def exit_all_contexts(contexts, exc_type=None, exc_value=None, traceback=None):
                """退出所有context（逆序）

                Args:
                    contexts: context列表，每个元素是(原始索引, context_manager)
                    exc_type: 异常类型（正常退出时为None）
                    exc_value: 异常值（正常退出时为None）
                    traceback: 异常traceback（正常退出时为None）
                """
                for original_index, ctx_mgr in reversed(contexts):
                    try:
                        ctx_mgr.__exit__(exc_type, exc_value, traceback)
                    except Exception as e:
                        logger.error("function exit failed at index %s: %s", original_index, e)
                        if original_index not in failed_indices:
                            failed_indices.append(original_index)
                            failed_hook_func[original_index] += 1

            # 前置处理：进入所有context
            contexts = []
            failed_indices = []

            ctx = get_context()
            thread_local.hook_context_funcs = []
            for func in context_funcs:
                thread_local.hook_context_funcs.append(func(ctx))

            for running_index, func in enumerate(thread_local.hook_context_funcs):
                if failed_hook_func[running_index] >= MAX_HOOK_FAILURES:
                    continue
                try:
                    func.__enter__()  # pylint: disable=unnecessary-dunder-call
                    contexts.append((running_index, func))
                except Exception as e:
                    logger.error("function enter failed at index %s: %s", running_index, e)
                    failed_indices.append(running_index)
                    failed_hook_func[running_index] += 1

            ret = wrap_chain(*args, **kwargs)

            try:
                ctx = get_context()
                ctx.return_value = ret
                exit_all_contexts(contexts)

                return ret
            except Exception as e:
                exit_all_contexts(contexts, type(e), e, None)
                raise

        return context_wrap_handler

    def _build_hook_with_injection(
        self,
        target: Any,
        context_funcs: List[Callable],
        chain: HookChain,
    ) -> Callable:
        """构建带字节码注入的hook

        需要locals时，context handlers用字节码注入。

        Args:
            target: 目标对象（原始函数）
            context_funcs: context handler函数列表（需要locals的）
            chain: 调用链，用于构建wrap handler

        Returns:
            注入后的函数，签名 (*args, **kwargs)
        """
        from ms_service_metric.core.hook.inject import inject_function

        # 对原函数进行字节码注入（处理context_funcs）
        injected_func: Callable = inject_function(target, context_funcs)

        def wrap_handler(*args, **kwargs):
            try:
                return chain.set_last_result(injected_func(*args, **kwargs))  # pylint: disable=not-callable
            except Exception as e:
                chain.set_last_result(e)
                raise

        return wrap_handler

    def unhook(self):
        """
        恢复原始函数

        如果已经应用hook，则恢复原函数。
        """
        if not self._hook_applied:
            return

        try:
            if self._hook_node:
                self._hook_node.remove()
                self._hook_node = None

            self._hook_applied = False
            self._pending_hook = False

            logger.debug("Unhooked symbol: %s", self._symbol_path)

        except Exception as e:
            logger.error("Failed to unhook symbol %s: %s", self._symbol_path, e)

    def stop(self):
        """
        停止symbol

        停止监听模块事件并解绑。
        """
        self.stop_watching()
        self.unhook()
        logger.debug("Symbol %s stopped", self._symbol_path)

    def remove_unlocked_handlers(self) -> List[str]:
        """
        移除所有未锁定的handlers（lock_patch=false）

        Returns:
            被移除的handler_id列表
        """
        unlocked_ids = []
        for handler_id, handler in self._handlers.items():
            if not handler.lock_patch:
                unlocked_ids.append(handler_id)

        for handler_id in unlocked_ids:
            del self._handlers[handler_id]
            logger.debug("Removed unlocked handler %s from symbol %s", handler_id, self._symbol_path)

        return unlocked_ids

    def has_locked_handlers(self) -> bool:
        """检查是否还有锁定的handlers"""
        return any(handler.lock_patch for handler in self._handlers.values())

    def has_handlers(self) -> bool:
        """检查是否还有handlers"""
        return len(self._handlers) > 0

    def update_hook(self) -> bool:
        """
        更新hook函数（handlers变化后）

        直接调用_apply_hook()复用chain和node。

        Returns:
            是否成功更新
        """
        if not self._hook_applied:
            logger.warning("Symbol %s not hooked, cannot update hook", self._symbol_path)
            return False

        if not self._handlers:
            logger.debug("Symbol %s has no handlers, unhooking", self._symbol_path)
            self.unhook()
            return True

        self._apply_hook()
        return True

    def stop_unlocked(self) -> tuple[List[str], List[str]]:
        """
        停止未锁定的部分

        移除未锁定的handlers，如果还有锁定的handlers，
        直接替换node的hook_func。

        Note:
            此方法只处理handlers的分离和hook更新，不处理解绑和监听停止。
            调用方需要根据返回结果决定是否解绑symbol。

        Returns:
            tuple: (已删除的handler_id列表, 保留的handler_id列表)
        """
        # 获取所有handler IDs
        all_ids = list(self._handlers.keys())

        # 移除未锁定的handlers
        removed_ids = self.remove_unlocked_handlers()

        # 计算保留的handlers
        kept_ids = [handler_id for handler_id in all_ids if handler_id not in removed_ids]

        if not removed_ids:
            # 没有移除任何handler，无需更新hook
            return (removed_ids, kept_ids)

        # 有handlers被移除
        if kept_ids:
            # 还有锁定的handlers，更新hook_func
            if self.update_hook():
                logger.info("Symbol %s kept %s locked handlers, hook updated", self._symbol_path, len(kept_ids))
        else:
            # 没有保留的handlers，解绑
            self.unhook()
            logger.debug("Symbol %s all handlers removed, unhooked", self._symbol_path)

        return (removed_ids, kept_ids)

    def _import_target(self) -> Any:
        """
        导入目标对象

        根据symbol_path导入目标类方法或函数。

        Returns:
            目标对象（方法或函数）

        Raises:
            SymbolError: 导入失败
        """
        try:
            # 导入模块
            if not is_allowed_symbol_module(self._module_path):
                logger.error("Symbol module is not allowed: %s", self._module_path)
                return None
            module = importlib.import_module(self._module_path)

            # 解析属性路径
            parts = self._attr_path.split('.')
            target = module

            # 逐级获取属性
            for part in parts:
                target = getattr(target, part)

            return target

        except ImportError as e:
            logger.error("Failed to import module %s: %s", self._module_path, e)
            return None
        except AttributeError as e:
            logger.error("Failed to get attribute %s from %s: %s", self._attr_path, self._module_path, e)
            return None
        except Exception as e:
            logger.error("Failed to import target %s: %s", self._symbol_path, e)
            return None
