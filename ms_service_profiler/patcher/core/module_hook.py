# -------------------------------------------------------------------------
# pylint: disable=attribute-defined-outside-init,comparison-with-callable,logging-fstring-interpolation,unnecessary-dunder-call
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

import traceback
import importlib
import inspect
import functools
import threading
from contextlib import closing
from abc import ABC, abstractmethod
from typing import Union, Tuple, List, Optional, Callable, Any
from packaging.version import Version
from .logger import logger
from .registry import add_to_hook_registry
from .utils import FunctionContext
from .import_security import is_allowed_symbol_module

MAX_HOOK_FAILURES = 5

_GET_CHAIN_FUNC = None


def _get_metric_hook_chain_getter():
    """Lazily import ms_service_metric HookChain getter to avoid import-order races."""
    global _GET_CHAIN_FUNC
    if _GET_CHAIN_FUNC is not None:
        return _GET_CHAIN_FUNC

    try:
        hook_chain_module = importlib.import_module("ms_service_metric.core.hook.hook_chain")
        _GET_CHAIN_FUNC = hook_chain_module.get_chain
        return _GET_CHAIN_FUNC
    except Exception:
        return None


def _unwrap_callable_for_location(function_ins: Any) -> Any:
    """Resolve framework wrapper callables back to the real hook target when possible."""
    current = function_ins
    visited = set()

    while current is not None and id(current) not in visited:
        visited.add(id(current))

        hook_chain = getattr(current, "_hook_chain", None)
        ori_func = getattr(hook_chain, "ori_func", None) if hook_chain is not None else None
        if callable(ori_func) and ori_func is not current:
            current = ori_func
            continue

        wrapped = getattr(current, "__wrapped__", None)
        if callable(wrapped) and wrapped is not current:
            current = wrapped
            continue

        break

    return current


def import_object_from_string(import_path: str, module_path: str) -> Any:
    """根据点分隔的路径导入对象（模块、类、函数等）。

    支持多级嵌套属性，如 "module.submodule.ClassName.method_name"

    Args:
        import_path: 模块导入路径
        module_path: 对象在模块中的路径

    Returns:
        Any: 导入的对象，失败时返回 None
    """
    if not import_path:
        logger.error("Module import_path is empty")
        return None
    if not is_allowed_symbol_module(import_path):
        logger.error("Module import_path is not allowed: %s", import_path)
        return None

    try:
        module = importlib.import_module(import_path)
    except ImportError as e:
        logger.error("Module import failed for %s: %s", module_path, e)
        return None

    current = module
    for part in module_path.split("."):
        prev = current  # For log
        current = getattr(current, part, None)
        if current is None:
            logger.error(f"Module {prev} doesn't has attribute {part}")
            return None
    return current


class HookHelper:
    """辅助类，用于函数替换操作。

    该类封装了函数替换的核心逻辑，包括：
    - 获取原始函数的位置信息
    - 执行函数替换
    - 恢复原始函数

    Attributes:
        new_function: 新的替换函数
        ori_function: 原始函数
        location: 函数所在的位置对象
        attr_name: 函数属性名称
    """

    def __init__(self, ori_function_define, new_function):
        """初始化 HookHelper。

        Args:
            ori_function_define: 原始函数定义
            new_function: 新的替换函数

        Raises:
            ValueError: 当初始化失败时抛出
        """
        self.new_function = new_function
        self.ori_function = None
        self.location = None
        self.attr_name = None

        if ori_function_define is None:
            return

        if inspect.isfunction(ori_function_define) or inspect.ismethod(ori_function_define):
            self.ori_function = ori_function_define
            self.location, self.attr_name = self.get_location(self.ori_function)
        elif callable(ori_function_define):
            self.ori_function = ori_function_define.__call__
            self.location, self.attr_name = self.get_location(self.ori_function)

        # Allow initialization without new_function; validation will occur in replace()/recover()
        if not all([self.ori_function, self.location, self.attr_name]):
            warn_msg = f"{ori_function_define} initialization failed."
            logger.error(warn_msg)
            raise ValueError(warn_msg)

    @staticmethod
    def get_location(function_ins):
        """获取函数的位置信息。

        Args:
            function_ins: 函数实例

        Returns:
            Tuple: (location, attr_name) 元组

        Raises:
            ValueError: 当无法获取位置信息时抛出
        """
        resolved_func = _unwrap_callable_for_location(function_ins)
        if not hasattr(resolved_func, "__module__"):
            warning_msg = f"function {str(resolved_func)} has no __module__."
            logger.error(warning_msg)
            raise ValueError(warning_msg)

        module = importlib.import_module(resolved_func.__module__)
        qualified_name = [part for part in resolved_func.__qualname__.split(".") if part != "<locals>"]
        classes = qualified_name[:-1]
        attr_name = qualified_name[-1]
        location = module

        for class_name in classes:
            location = getattr(location, class_name, None)
            if location is None:
                break

        if location is None:
            warning_msg = f"{'.'.join(classes)} does not exist"
            logger.error(warning_msg)
            raise ValueError(warning_msg)

        return location, attr_name

    def replace(self):
        """执行函数替换操作。

        Raises:
            Exception: 当替换失败时抛出
        """
        if not self._has_valid_attributes():
            return

        try:
            setattr(self.location, self.attr_name, self._get_method(self.new_function))
            logger.debug(f"Successfully replaced {self.attr_name} in {self.location}")
        except Exception as e:
            logger.error(f"Failed to replace {self.attr_name} in {self.location}: {e}")
            raise

    def recover(self):
        """恢复原始函数。

        Raises:
            Exception: 当恢复失败时抛出
        """
        if not self._has_valid_attributes():
            return

        try:
            setattr(self.location, self.attr_name, self._get_method(self.ori_function))
            logger.debug(f"Successfully recovered {self.attr_name} in {self.location}")
        except Exception as e:
            logger.error(f"Failed to recover {self.attr_name} in {self.location}: {e}")
            raise

    def _get_method(self, func):
        """获取适当的方法类型（staticmethod 或 classmethod）。

        Args:
            func: 函数对象

        Returns:
            适当的方法类型包装
        """
        if inspect.isclass(self.location):
            try:
                func_cls_name = inspect.getattr_static(self.location, self.attr_name).__class__.__name__
                if func_cls_name in ("staticmethod", "classmethod"):
                    return staticmethod(func)
            except AttributeError:
                pass
        return func

    def _has_valid_attributes(self) -> bool:
        """检查替换/恢复所需的关键属性是否齐全。"""
        for attr in (
            self.ori_function,
            self.location,
            self.attr_name,
            self.new_function,
        ):
            if attr is None:
                return False
        return True


def get_parents_name(ori_func, index=1):
    """获取调用栈中的父级函数名。

    Args:
        ori_func: 原始函数
        index: 调用栈索引，默认为 1

    Returns:
        Optional[str]: 父级函数名，失败时返回 None
    """
    frame = None
    try:
        with closing(traceback.walk_stack(None)) as gen:
            for _ in range(index + 1):
                frame, _ = next(gen)
            return frame.f_code.co_name if frame else None
    except StopIteration:
        return None
    finally:
        frame = None


class TrackableOriginalFunc:
    """可追踪的原函数包装器，用于避免重复执行原函数。

    当 hook 函数内部已经调用了原函数，但在后处理逻辑中出错时，
    可以通过此包装器检测原函数是否已执行，避免在异常处理中重复调用。

    Attributes:
        original_func: 原始函数
        executed: 是否已执行
        cached_result: 缓存的执行结果
        cached_exception: 缓存的异常（如果执行时抛出）
    """

    def __init__(self, original_func):
        """初始化可追踪的原函数包装器。

        Args:
            original_func: 原始函数
        """
        self.original_func = original_func
        self.executed = False
        self.cached_result = None
        self.cached_exception = None
        self.__name__ = getattr(original_func, "__name__", "TrackableOriginalFunc")

    def __call__(self, *args, **kwargs):
        """调用原函数并缓存结果。

        支持同步和异步函数：
        - 如果是异步函数，返回协程对象
        - 如果是同步函数，直接返回结果

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            原函数的返回值（同步）或协程对象（异步）

        Raises:
            原函数抛出的异常
        """
        cached = self._check_cached_result()
        if cached is not None:
            return cached

        # 检查原函数是否是异步函数
        if inspect.iscoroutinefunction(self.original_func):
            # 异步函数，返回协程对象，由调用者 await
            return self._execute_and_cache_async(*args, **kwargs)
        else:
            # 同步函数，直接执行并缓存结果
            return self._execute_and_cache_sync(*args, **kwargs)

    def reset(self):
        """重置执行状态，用于每次新的函数调用。

        每次 wrapper 被调用时应该调用此方法，以确保每次调用都是独立的。
        """
        self.executed = False
        self.cached_result = None
        self.cached_exception = None

    def call_with_reset(self, func):
        """装饰器：在每次函数调用时自动重置执行状态。

        使用此装饰器装饰 wrapper 函数，可以确保每次调用时都会自动重置状态。

        Args:
            func: 要装饰的函数（可以是同步或异步函数）

        Returns:
            装饰后的函数
        """
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                self.reset()
                return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                self.reset()
                return func(*args, **kwargs)

            return sync_wrapper

    def _check_cached_result(self):
        """检查并返回缓存的结果。

        Returns:
            缓存的返回值

        Raises:
            如果执行时抛出异常，重新抛出该异常
        """
        if self.executed:
            if self.cached_exception is not None:
                raise self.cached_exception
            return self.cached_result
        return None

    def _execute_and_cache_sync(self, *args, **kwargs):
        """执行同步函数并缓存结果。

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            原函数的返回值

        Raises:
            原函数抛出的异常
        """
        try:
            self.cached_result = self.original_func(*args, **kwargs)
            self.executed = True
            return self.cached_result
        except Exception as e:
            self.cached_exception = e
            self.executed = True
            raise

    async def _execute_and_cache_async(self, *args, **kwargs):
        """执行异步函数并缓存结果。

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            原函数的返回值

        Raises:
            原函数抛出的异常
        """
        try:
            self.cached_result = await self.original_func(*args, **kwargs)
            self.executed = True
            return self.cached_result
        except Exception as e:
            self.cached_exception = e
            self.executed = True
            raise


class VLLMHookerBase(ABC):
    """Hooker基类，提供核心功能。

    该类是所有 hooker 的基类，提供：
    - 版本支持检查
    - hook 应用和恢复
    - 异常处理和回退机制
    - 异步和同步函数支持

    Attributes:
        vllm_version (Tuple[Optional[str], Optional[str]]): 支持的 vLLM 版本范围
        applied_hook_func_name (str): 应用的 hook 函数名称
        hooks (List): hook 实例列表
        hook_list (List[Tuple[str, str]]): hook 点列表
        caller_filter (Optional[str]): 调用者过滤条件
        hook_func (Optional[Callable]): hook 处理函数
    """

    @staticmethod
    def default_hook_func(ori_func, *args, **kwargs):
        return ori_func(*args, **kwargs)

    vllm_version = (None, None)  # (min_version, max_version)
    applied_hook_func_name = ""

    def __init__(self):
        """初始化 VLLMHookerBase。"""
        self.hooks = []
        # 记录文本形式的 hook 点（未解析成对象前的 (import_path, attr_path) 列表）
        self.hook_list: List[Tuple[str, str]] = []
        self.caller_filter: Optional[str] = None
        # 对应的 hook 处理函数，用于配置化时复用
        self.wrap_hook_func: Optional[Callable] = None
        self.context_hook_funcs: List[Callable] = []
        # Optional outer wrapper used by independent instrumentation such as
        # Hook tracing.  It is applied after the existing profiling callable
        # is built, so the profiling/context-hook execution model is unchanged.
        self.around_hook_factory: Optional[Callable] = None
        self.need_locals = False

    @abstractmethod
    def init(self):
        """初始化hook点，子类必须实现。

        该方法由子类实现，用于初始化具体的 hook 点。
        """
        pass

    @staticmethod
    def hook_func_not_need_locals(trackable_ori_func, ori_func, context_hook_funcs, wrap_hook_func):
        thread_local = threading.local()
        thread_local.context = FunctionContext()
        failed_hook_func = [0 for x in context_hook_funcs]

        def get_context():
            if not hasattr(thread_local, "context"):
                thread_local.context = FunctionContext()
            return thread_local.context

        def before_ori_func():
            try:
                ctx = get_context()
                thread_local.hook_context_funcs = []
                for func in context_hook_funcs:
                    thread_local.hook_context_funcs.append(func(ctx))

                running_index = None
                for running_index, func in enumerate(thread_local.hook_context_funcs):
                    if failed_hook_func[running_index] >= MAX_HOOK_FAILURES:
                        continue
                    func.__enter__()
            except Exception as e:
                logger.error(f"function enter failed: {e}")
                if running_index is not None:
                    failed_hook_func[running_index] += 1

        def after_ori_func(ret):
            try:
                ctx = get_context()
                ctx.return_value = ret
                running_index = None
                for reversed_running_index, func in enumerate(reversed(thread_local.hook_context_funcs)):
                    running_index = len(thread_local.hook_context_funcs) - 1 - reversed_running_index
                    if failed_hook_func[running_index] >= MAX_HOOK_FAILURES:
                        continue
                    func.__exit__(None, None, None)
            except Exception as e:
                logger.error(f"function exit failed: {e}")
                if running_index is not None:
                    failed_hook_func[running_index] += 1

        def wrapper(*args, **kwargs):
            before_ori_func()
            ret = ori_func(*args, **kwargs)
            after_ori_func(ret)
            return ret

        async def wrapper_async(*args, **kwargs):
            before_ori_func()
            ret = await ori_func(*args, **kwargs)
            after_ori_func(ret)
            return ret

        def wrapper_with_wrap_hook(*args, **kwargs):
            before_ori_func()
            ret = wrap_hook_func(trackable_ori_func, *args, **kwargs)
            after_ori_func(ret)
            return ret

        async def wrapper_with_wrap_hook_async(*args, **kwargs):
            before_ori_func()
            ret = await wrap_hook_func(trackable_ori_func, *args, **kwargs)
            after_ori_func(ret)
            return ret

        if wrap_hook_func == VLLMHookerBase.default_hook_func:
            return wrapper_async if inspect.iscoroutinefunction(ori_func) else wrapper
        else:
            return wrapper_with_wrap_hook_async if inspect.iscoroutinefunction(ori_func) else wrapper_with_wrap_hook

    def replace_func(
        self, trackable_ori_func: TrackableOriginalFunc, pname, profiler_func, on_recover: Optional[Callable] = None
    ):
        """创建替换函数，带失败回退机制。

        功能特性：
        - 任一 hook 执行抛异常时，不影响业务逻辑：返回原始函数结果
        - 连续失败达到 MAX_HOOK_FAILURES 次，自动回退为原始函数（若提供 on_recover 则调用以执行恢复）
        - 支持 context manager 的特殊处理
        - 避免重复执行原函数：如果 hook 函数内部已调用原函数，异常处理时不会重复调用

        Args:
            trackable_ori_func: 可追踪的原函数包装器
            pname: 调用者过滤名称
            profiler_func: profiler 函数
            on_recover: 恢复回调函数，可选

        Returns:
            Callable: 替换函数
        """
        # 从 trackable_ori_func 获取原始函数用于类型检测
        ori_func = trackable_ori_func.original_func
        # 检测函数类型
        is_context_manager_func = inspect.isgeneratorfunction(profiler_func)
        is_async_func = inspect.iscoroutinefunction(ori_func) or inspect.iscoroutinefunction(profiler_func)

        if is_async_func:
            return self._create_async_wrapper(
                trackable_ori_func, profiler_func, pname, on_recover, is_context_manager_func
            )
        else:
            return self._create_sync_wrapper(
                trackable_ori_func, profiler_func, pname, on_recover, is_context_manager_func
            )

    def do_hook(self, hook_points, profiler_func_maker, pname=None):
        """执行实际的hook操作。

        Args:
            hook_points: hook 点列表
            profiler_func_maker: profiler 函数生成器
            pname: 调用者过滤名称，可选
        """
        get_chain = _get_metric_hook_chain_getter()
        for ori_func in hook_points:
            if ori_func is None:
                continue

            hook_node = get_chain(ori_func).add_chain_node() if get_chain is not None else None
            if hook_node is not None:
                ori_func = hook_node.ori_wrap

            # 创建可追踪的原函数包装器，用于避免重复执行
            trackable_ori_func = TrackableOriginalFunc(ori_func)

            if self.wrap_hook_func == VLLMHookerBase.default_hook_func:
                # 如果都没有原始的 wrap_hook_func, 就直接使用原函数，拜托一层一层的封装
                # An around hook must call the trackable wrapper so a business
                # exception is never retried as an instrumentation failure.
                profiler_func = trackable_ori_func if self.around_hook_factory else ori_func
            else:
                # 如果有原始的 wrap_hook_func, 就使用修改前的方式
                profiler_func = profiler_func_maker(trackable_ori_func)

            if self.around_hook_factory is not None:
                profiler_func = self.around_hook_factory(profiler_func, ori_func)

            if hook_node is not None:

                def _recover_current(cur_hook_ref=hook_node):
                    try:
                        cur_hook_ref.recover()
                    except Exception as e:
                        logger.error(f"Recover call failed: {e}")

                wrapped = self.replace_func(trackable_ori_func, pname, profiler_func, on_recover=_recover_current)
                hook_node.set_hook_func(wrapped)

                self.hooks.append(hook_node)
            else:
                cur_hook = HookHelper(ori_func, None)

                def _recover_current(cur_hook_ref=cur_hook):
                    try:
                        cur_hook_ref.recover()
                    except Exception as e:
                        logger.error(f"Recover call failed: {e}")

                wrapped = self.replace_func(trackable_ori_func, pname, profiler_func, on_recover=_recover_current)
                cur_hook.new_function = wrapped
                cur_hook.replace()
                self.hooks.append(cur_hook)
                logger.debug(f"replacing {ori_func} with {self.applied_hook_func_name}")

    def recover(self):
        try:
            for hook_helper in self.hooks:
                hook_helper.recover()
            logger.debug("Recovered hooker for removed symbol")
        except Exception as e:
            logger.error(f"Failed to recover hooker: {e}")

    def support_version(self, version):
        """检查当前版本是否支持。

        Args:
            version: 要检查的版本号

        Returns:
            bool: 如果支持则返回 True，否则返回 False
        """
        min_version = self.vllm_version[0]
        max_version = self.vllm_version[1]

        if min_version is not None and Version(min_version) > Version(version):
            logger.debug(f"min_version={min_version} is less than version={version}, skip")
            return False
        if max_version is not None and Version(max_version) < Version(version):
            logger.debug(f"max_version={max_version} is larger than version={version}, skip")
            return False
        return True

    def register(self):
        """注册hooker到全局注册表。"""
        add_to_hook_registry(self)

    def _log_hook_exception(self, trackable_ori_func: TrackableOriginalFunc, e: Exception, failures: int):
        """记录 hook 执行异常。

        Args:
            trackable_ori_func: 可追踪的原函数包装器
            e: 异常对象
            failures: 失败次数
        """
        ori_func = trackable_ori_func.original_func
        logger.error(f"Hook execution failed ({failures}/{MAX_HOOK_FAILURES}) for {ori_func}: {e}")
        logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")

    def _handle_context_manager_failure(
        self, trackable_ori_func: TrackableOriginalFunc, on_recover: Optional[Callable], is_async: bool
    ):
        """处理 context manager 函数失败的情况。

        Args:
            trackable_ori_func: 可追踪的原函数包装器
            on_recover: 恢复回调函数
            is_async: 是否为异步函数

        Returns:
            Callable: 返回原始函数的包装器
        """
        ori_func = trackable_ori_func.original_func
        logger.warning(f"Context manager hook failed, immediately reverting to original for {ori_func}")
        try:
            if callable(on_recover):
                on_recover()
        except Exception as re:
            logger.error(f"Failed to recover original function for {ori_func}: {re}")

        # 对于 context manager，使用 trackable_ori_func 获取结果或执行原函数
        if is_async:

            async def _return_original_async(*args, **kwargs):
                return await trackable_ori_func(*args, **kwargs)

            return _return_original_async
        else:

            def _return_original_sync(*args, **kwargs):
                return trackable_ori_func(*args, **kwargs)

            return _return_original_sync

    def _handle_permanent_fallback(
        self, trackable_ori_func: TrackableOriginalFunc, on_recover: Optional[Callable], failures: int
    ):
        """处理永久回退的情况。

        Args:
            trackable_ori_func: 可追踪的原函数包装器
            on_recover: 恢复回调函数
            failures: 失败次数
        """
        ori_func = trackable_ori_func.original_func
        if failures >= MAX_HOOK_FAILURES:
            try:
                if callable(on_recover):
                    on_recover()
                logger.warning(
                    f"Hook permanently reverted to original for {ori_func} after {MAX_HOOK_FAILURES} failures"
                )
            except Exception as re:
                logger.error(f"Failed to recover original function for {ori_func}: {re}")

    def _create_async_wrapper(
        self,
        trackable_ori_func: TrackableOriginalFunc,
        profiler_func,
        pname: Optional[str],
        on_recover: Optional[Callable],
        is_context_manager_func: bool,
    ):
        """创建异步函数包装器。

        Args:
            trackable_ori_func: 可追踪的原函数包装器
            profiler_func: profiler 函数
            pname: 调用者过滤名称
            on_recover: 恢复回调函数
            is_context_manager_func: 是否为 context manager 函数

        Returns:
            Callable: 异步包装器函数
        """
        ori_func = trackable_ori_func.original_func
        failures = 0

        @functools.wraps(ori_func)
        @trackable_ori_func.call_with_reset
        async def async_wrapper(*args, **kwargs):
            # 检查调用者过滤
            if pname is not None and get_parents_name(ori_func) != pname:
                logger.debug(f"calling {ori_func}")
                return await trackable_ori_func(*args, **kwargs)

            nonlocal failures
            if failures >= MAX_HOOK_FAILURES:
                return await trackable_ori_func(*args, **kwargs)

            try:
                logger.debug(f"calling profiler_func={self.applied_hook_func_name} for {ori_func}")
                return await profiler_func(*args, **kwargs)
            except Exception as e:
                if trackable_ori_func.executed and trackable_ori_func.cached_exception is e:
                    raise
                failures += 1
                self._log_hook_exception(trackable_ori_func, e, failures)

                # 对于 context manager 函数，第一次失败就立即回退
                if is_context_manager_func:
                    handler = self._handle_context_manager_failure(trackable_ori_func, on_recover, True)
                    return await handler(*args, **kwargs)

                # 使用 trackable_ori_func 获取结果或执行原函数（避免重复执行）
                try:
                    result = await trackable_ori_func(*args, **kwargs)
                except Exception as orig_e:
                    logger.error(f"Original function also failed for {ori_func}: {orig_e}")
                    # 检查是否需要永久回退（在重新抛出异常前）
                    self._handle_permanent_fallback(trackable_ori_func, on_recover, failures)
                    # 重新抛出原始函数的异常，让调用者处理
                    raise orig_e

                # 检查是否需要永久回退
                self._handle_permanent_fallback(trackable_ori_func, on_recover, failures)
                return result

        return async_wrapper

    def _create_sync_wrapper(
        self,
        trackable_ori_func: TrackableOriginalFunc,
        profiler_func,
        pname: Optional[str],
        on_recover: Optional[Callable],
        is_context_manager_func: bool,
    ):
        """创建同步函数包装器。

        Args:
            trackable_ori_func: 可追踪的原函数包装器
            profiler_func: profiler 函数
            pname: 调用者过滤名称
            on_recover: 恢复回调函数
            is_context_manager_func: 是否为 context manager 函数

        Returns:
            Callable: 同步包装器函数
        """
        ori_func = trackable_ori_func.original_func
        failures = 0

        @functools.wraps(ori_func)
        @trackable_ori_func.call_with_reset
        def wrapper(*args, **kwargs):
            # 检查调用者过滤
            if pname is not None and get_parents_name(ori_func) != pname:
                logger.debug(f"calling {ori_func}")
                return trackable_ori_func(*args, **kwargs)

            nonlocal failures
            if failures >= MAX_HOOK_FAILURES:
                return trackable_ori_func(*args, **kwargs)

            try:
                logger.debug(f"calling profiler_func={self.applied_hook_func_name} for {ori_func}")
                return profiler_func(*args, **kwargs)
            except Exception as e:
                if trackable_ori_func.executed and trackable_ori_func.cached_exception is e:
                    raise
                failures += 1
                self._log_hook_exception(trackable_ori_func, e, failures)

                # 对于 context manager 函数，第一次失败就立即回退
                if is_context_manager_func:
                    return self._handle_context_manager_failure(trackable_ori_func, on_recover, False)(*args, **kwargs)

                # 使用 trackable_ori_func 获取结果或执行原函数（避免重复执行）
                try:
                    result = trackable_ori_func(*args, **kwargs)
                except Exception as orig_e:
                    logger.error(f"Original function also failed for {ori_func}: {orig_e}")
                    # 检查是否需要永久回退（在重新抛出异常前）
                    self._handle_permanent_fallback(trackable_ori_func, on_recover, failures)
                    # 重新抛出原始函数的异常，让调用者处理
                    raise orig_e

                # 检查是否需要永久回退
                self._handle_permanent_fallback(trackable_ori_func, on_recover, failures)
                return result

        return wrapper


def patcher(
    hook_points: Union[Tuple[str, str], List[Tuple[str, str]]],
    min_version: Optional[str] = None,
    max_version: Optional[str] = None,
    caller_filter: Optional[str] = None,
) -> Callable:
    """装饰器工厂函数，用于简化hooker创建。

    Args:
        hook_points: hook点列表，格式为(模块名, 属性路径)
        min_version: 支持的最小版本
        max_version: 支持的最大版本
        caller_filter: 调用者过滤条件

    Returns:
        Callable: 装饰器函数
    """

    def decorator(hook_func):
        logger.debug(f"Handling {hook_func}")

        class AutoHooker(VLLMHookerBase):
            vllm_version = (min_version, max_version)
            applied_hook_func_name = getattr(hook_func, "__name__", str(hook_func))

            def init(self):
                hook_list = [hook_points] if isinstance(hook_points, tuple) else hook_points
                points = [import_object_from_string(import_path, func_path) for import_path, func_path in hook_list]
                self.do_hook(
                    hook_points=points,
                    profiler_func_maker=lambda ori_func: lambda *args, **kwargs: hook_func(ori_func, *args, **kwargs),
                    pname=caller_filter,
                )

        hooker = AutoHooker()
        # 在注册阶段即缓存文本点位与处理函数，便于配置化复用
        try:
            hook_list_local = [hook_points] if isinstance(hook_points, tuple) else list(hook_points)
        except Exception:
            hook_list_local = []
        hooker.hook_list = hook_list_local
        hooker.caller_filter = caller_filter
        hooker.hook_func = hook_func
        hooker.register()
        return hook_func

    return decorator
