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
# pylint: disable=logging-fstring-interpolation,global-variable-not-assigned
# pylint: disable=comparison-with-callable,ungrouped-imports

import ast
import importlib
import inspect
import io
import tokenize
from dataclasses import dataclass
from typing import Tuple, List, Optional, Callable, Dict, Any

from ms_service_profiler.patcher.core.registry import add_to_hook_registry
from .logger import logger
from contextlib import contextmanager
from typing import ContextManager
from functools import partial
from packaging.version import Version

# Expose Profiler/Level at module scope so tests can patch them
try:
    from ms_service_profiler import Profiler, Level
except Exception:
    Profiler = None  # type: ignore
    Level = None  # type: ignore
from .module_hook import VLLMHookerBase, import_object_from_string
from .import_security import is_allowed_handler_module


@dataclass
class FuncCallContext:
    """函数调用上下文，封装表达式执行所需的参数。

    Attributes:
        func_obj: 被调用的函数对象
        this_obj: this 对象（通常是 self）
        args: 位置参数元组
        kwargs: 关键字参数字典
        ret_val: 函数返回值
    """

    func_obj: Any
    this_obj: Any
    args: Tuple
    kwargs: Dict
    ret_val: Any


global_mutil_handler_manager: Dict[str, "MultiHandlerDynamicHooker"] = dict()


class ConfigHooker:
    """用于在运行时基于配置注册的 Hooker。

    该类提供基于配置文件的动态 hook 功能。
    支持版本范围限制和调用者过滤。

    Attributes:
        min_version (Optional[str]): 支持的最小版本
        max_version (Optional[str]): 支持的最大版本
        hook_list (List[Tuple[str, str]]): hook 点列表
        caller_filter (Optional[str]): 调用者过滤条件
        hook_func (Callable): hook 处理函数
        framework_version (Optional[str]): 框架版本号，用于版本检查
    """

    def __init__(
        self,
        hook_list: List[Tuple[str, str]],
        hook_func: Callable,
        symbol_path: str,
        min_version: Optional[str],
        max_version: Optional[str],
        caller_filter: Optional[str],
        need_locals: bool = False,
        framework_version: Optional[str] = None,
    ):
        """初始化 ConfigHooker。

        Args:
            hook_list: hook 点列表，格式为 [(import_path, func_path), ...]
            hook_func: hook 处理函数
            min_version: 支持的最小版本
            max_version: 支持的最大版本
            caller_filter: 调用者过滤条件
            need_locals: 是否需要局部变量
            framework_version: 框架版本号，用于版本检查
        """
        self.min_version = min_version
        self.max_version = max_version
        self.applied_hook_func_name = getattr(hook_func, "__name__", str(hook_func))
        self.hook_list = list(hook_list)
        self.symbol_path = symbol_path
        self.caller_filter = caller_filter
        self.need_locals = need_locals
        self.framework_version = framework_version

        # hook_func 改为支持多个，一个hook点位支持多个hook函数
        hook_funcs = hook_func if isinstance(hook_func, list) else [hook_func]

        def create_context_manager(ori_func):
            if inspect.isgeneratorfunction(ori_func):
                return contextmanager(ori_func)
            elif inspect.isasyncgenfunction(ori_func):
                logger.debug("The handler does not support async generator functions.")
                return None
            elif isinstance(ori_func, type) and issubclass(ori_func, ContextManager):
                return ori_func
            else:
                return None

        wrap_hook_funcs = []  # 原始的hook 函数，内部会自动调用ori_func
        context_hook_funcs = []  # 新的hook 函数，内部使用yield 控制，或者本身就是ContextManager，由框架自动调用原函数~

        for x in hook_funcs:
            context_func = create_context_manager(x)
            if context_func:
                context_hook_funcs.append(context_func)
            else:
                wrap_hook_funcs.append(x)

        self.wrap_hook_func = wrap_hook_funcs[0] if wrap_hook_funcs else VLLMHookerBase.default_hook_func
        self.context_hook_funcs = context_hook_funcs

    def support_version(self) -> bool:
        """检查当前框架版本是否在支持范围内。

        Returns:
            bool: 如果版本在支持范围内返回 True，否则返回 False
        """
        min_version = self.min_version
        max_version = self.max_version

        if min_version is None and max_version is None:
            return True

        version = self.framework_version
        if version is None:
            logger.debug(f"Framework version not set for {self.applied_hook_func_name}, allowing hook")
            return True

        if min_version is not None and Version(min_version) > Version(version):
            logger.debug(
                f"min_version={min_version} > current_version={version}, skip hook {self.applied_hook_func_name}"
            )
            return False
        if max_version is not None and Version(max_version) < Version(version):
            logger.debug(
                f"max_version={max_version} < current_version={version}, skip hook {self.applied_hook_func_name}"
            )
            return False
        return True

    def init(self):
        # 版本检查：如果版本不支持，不添加 handler
        if not self.support_version():
            logger.debug(f"Skip init for {self.applied_hook_func_name} due to version mismatch")
            return

        global global_mutil_handler_manager
        mulit_handler_manager = global_mutil_handler_manager.get(self.symbol_path)
        if mulit_handler_manager is None:
            mulit_handler_manager = MultiHandlerDynamicHooker(
                self.hook_list, [], self.min_version, self.max_version, None, self.need_locals
            )
            global_mutil_handler_manager[self.symbol_path] = mulit_handler_manager

        mulit_handler_manager.add_handler(self)

    def recover(self):
        global global_mutil_handler_manager
        mulit_handler_manager = global_mutil_handler_manager.get(self.symbol_path)
        if mulit_handler_manager is None:
            return

        if mulit_handler_manager.recover_handler(self) == 0:
            del global_mutil_handler_manager[self.symbol_path]

    def register(self):
        """注册hooker到全局注册表。"""
        add_to_hook_registry(self)

    def __eq__(self, value):
        if not isinstance(value, ConfigHooker):
            return False
        return self.symbol_path == value.symbol_path and self.applied_hook_func_name == value.applied_hook_func_name

    def __hash__(self):
        return hash((self.symbol_path, self.applied_hook_func_name))


class DynamicHooker(VLLMHookerBase):
    """用于在运行时基于配置注册的 Hooker。

    该类继承自 VLLMHookerBase，提供基于配置文件的动态 hook 功能。
    支持版本范围限制和调用者过滤。

    Attributes:
        vllm_version (Tuple[Optional[str], Optional[str]]): 支持的 vLLM 版本范围
        applied_hook_func_name (str): 应用的 hook 函数名称
        hook_list (List[Tuple[str, str]]): hook 点列表
        caller_filter (Optional[str]): 调用者过滤条件
        hook_func (Callable): hook 处理函数
    """

    def __init__(
        self,
        hook_list: List[Tuple[str, str]],
        hook_func: Callable,
        min_version: Optional[str],
        max_version: Optional[str],
        caller_filter: Optional[str],
        need_locals: bool = False,
    ):
        """初始化 DynamicHooker。

        Args:
            hook_list: hook 点列表，格式为 [(import_path, func_path), ...]
            hook_func: hook 处理函数
            min_version: 支持的最小版本
            max_version: 支持的最大版本
            caller_filter: 调用者过滤条件
        """
        super().__init__()
        self.vllm_version = (min_version, max_version)
        self.applied_hook_func_name = getattr(hook_func, "__name__", str(hook_func))
        self.hook_list = list(hook_list)
        self.caller_filter = caller_filter
        self.need_locals = need_locals

        # hook_func 改为支持多个，一个hook点位支持多个hook函数
        hook_funcs = hook_func if isinstance(hook_func, list) else [hook_func]

        def create_context_manager(ori_func):
            if inspect.isgeneratorfunction(ori_func):
                return contextmanager(ori_func)
            elif inspect.isasyncgenfunction(ori_func):
                logger.debug("The handler does not support async generator functions.")
                return None
            elif isinstance(ori_func, type) and issubclass(ori_func, ContextManager):
                return ori_func
            else:
                return None

        wrap_hook_funcs = []  # 原始的hook 函数，内部会自动调用ori_func
        context_hook_funcs = []  # 新的hook 函数，内部使用yield 控制，或者本身就是ContextManager，由框架自动调用原函数~

        for x in hook_funcs:
            context_func = create_context_manager(x)
            if context_func:
                context_hook_funcs.append(context_func)
            else:
                wrap_hook_funcs.append(x)

        self.wrap_hook_func = wrap_hook_funcs[0] if wrap_hook_funcs else VLLMHookerBase.default_hook_func
        self.context_hook_funcs = context_hook_funcs

    def init(self):
        """初始化 hook 点并应用 hooks。

        从 hook_list 中导入目标对象，然后应用 hook 处理函数。
        """
        points = [import_object_from_string(import_path, func_path) for import_path, func_path in self.hook_list]
        self.do_hook(
            hook_points=points,
            profiler_func_maker=lambda ori_func: lambda *args, **kwargs: self.wrap_hook_func(ori_func, *args, **kwargs),
            pname=self.caller_filter,
        )


class MultiHandlerDynamicHooker(DynamicHooker):
    def __init__(
        self,
        hook_list: List[Tuple[str, str]],
        hook_func: Callable,
        min_version: Optional[str],
        max_version: Optional[str],
        caller_filter: Optional[str],
        need_locals: bool = False,
    ):
        super().__init__(hook_list, hook_func, min_version, max_version, caller_filter, need_locals)
        self.handlers = set()

    def build_wrap_hook_func(self, handler_wrap_hook_funcs):
        handler_wrap_hook_funcs = [
            x for x in handler_wrap_hook_funcs if x is not None and x != VLLMHookerBase.default_hook_func
        ]
        if handler_wrap_hook_funcs == []:
            return VLLMHookerBase.default_hook_func
        elif len(handler_wrap_hook_funcs) == 1:
            return handler_wrap_hook_funcs[0]
        else:
            pass

        class DynamicWrapHookFunc:
            def __init__(self):
                self.ori_func = None

            def __call__(self, *args, **kwargs):
                if self.ori_func is None:
                    logger.error("Original function not set for DynamicWrapHookFunc")
                    return None
                return self.ori_func(*args, **kwargs)  # 默认调用原函数，保证原函数的执行

            def set_ori_func(self, ori_func):
                self.ori_func = ori_func

        dynamic_ori_func = DynamicWrapHookFunc()
        wrap_hook_func = dynamic_ori_func
        for func in reversed(handler_wrap_hook_funcs):
            wrap_hook_func = partial(func, wrap_hook_func)

        def _wrap_hook_func(ori_func, *args, **kwargs):
            dynamic_ori_func.set_ori_func(ori_func)
            return wrap_hook_func(*args, **kwargs)  # 先调用外层的hook函数，内部会自动调用ori_func

        return _wrap_hook_func

    def add_handler(self, handler: ConfigHooker):
        if handler in self.handlers:
            return

        self.recover()
        self.handlers.add(handler)
        self.wrap_hook_func = self.build_wrap_hook_func(x.wrap_hook_func for x in self.handlers)
        self.context_hook_funcs = sum((x.context_hook_funcs for x in self.handlers), [])
        self.need_locals = any((x.need_locals for x in self.handlers))
        self.init()

    def recover_handler(self, handler: ConfigHooker):
        if handler not in self.handlers:
            return len(self.handlers)

        self.recover()
        self.handlers.remove(handler)
        if len(self.handlers) == 0:
            return 0

        self.wrap_hook_func = self.build_wrap_hook_func(x.wrap_hook_func for x in self.handlers)
        self.context_hook_funcs = sum((x.context_hook_funcs for x in self.handlers), [])
        self.need_locals = any((x.need_locals for x in self.handlers))
        self.init()

        return len(self.handlers)


def register_dynamic_hook(
    hook_list: List[Tuple[str, str]],
    hook_func: Callable,
    min_version: Optional[str] = None,
    max_version: Optional[str] = None,
    caller_filter: Optional[str] = None,
    need_locals: bool = False,
):
    """注册一个基于配置文件的动态 Hooker。

    Args:
        hook_list: hook 点列表，格式为 [(import_path, func_path), ...]
        hook_func: hook 处理函数
        min_version: 支持的最小版本，默认为 None
        max_version: 支持的最大版本，默认为 None
        caller_filter: 调用者过滤条件，默认为 None

    Returns:
        DynamicHooker: 注册的 hooker 实例
    """
    hooker = DynamicHooker(
        hook_list=hook_list,
        hook_func=hook_func,
        min_version=min_version,
        max_version=max_version,
        caller_filter=caller_filter,
        need_locals=need_locals,
    )
    hooker.register()
    return hooker


def _get_object_attribute(obj, attr_name):
    """获取对象属性。对于不存在的属性返回 None"""
    try:
        return object.__getattribute__(obj, attr_name)
    except Exception:
        return None


def _extract_named_parameters(func_obj, args_tuple, kwargs_dict):
    """提取函数的具名参数。"""
    try:
        sig = inspect.signature(func_obj)
        bound = sig.bind_partial(*args_tuple, **kwargs_dict)
        try:
            bound.apply_defaults()
        except Exception as e:
            logger.debug("apply_defaults failed: %s", e)
        return dict(bound.arguments)
    except Exception:
        return {}


def _build_safe_locals(ctx: FuncCallContext):
    """构建安全的本地变量环境。"""
    named_params = _extract_named_parameters(ctx.func_obj, ctx.args, ctx.kwargs)
    self_obj = named_params.get("self", ctx.this_obj)
    safe_locals = {
        "this": self_obj,
        "args": ctx.args,
        "kwargs": ctx.kwargs,
        "return": ctx.ret_val,
        "ret": ctx.ret_val,
        "self": self_obj,
    }
    return safe_locals


_SAFE_EXPR_FUNCTIONS = {
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
}


def _normalize_expr(expr_str: str) -> str:
    """Keep YAML compatibility for the 'return' pseudo variable.

    Replace only standalone NAME tokens so string literals like "return"
    keep their original meaning.
    """
    try:
        tokens = []
        for token in tokenize.generate_tokens(io.StringIO(expr_str).readline):
            if token.type == tokenize.NAME and token.string == "return":
                token = tokenize.TokenInfo(token.type, "ret", token.start, token.end, token.line)
            tokens.append(token)
        return tokenize.untokenize(tokens)
    except tokenize.TokenError:
        return expr_str


def _is_safe_attribute_name(attr_name: str) -> bool:
    return isinstance(attr_name, str) and attr_name and not attr_name.startswith("_") and "__" not in attr_name


class _SafeExpressionEvaluator:
    """AST evaluator for profiler attribute expressions."""

    def __init__(self, safe_locals: Dict[str, Any]):
        self.safe_locals = safe_locals

    def validate(self, node: ast.AST) -> None:
        if isinstance(node, ast.Expression):
            self.validate(node.body)
            return
        if isinstance(node, (ast.Constant, ast.Name)):
            return
        if isinstance(node, (ast.Tuple, ast.List)):
            for item in node.elts:
                self.validate(item)
            return
        if isinstance(node, ast.Subscript):
            self.validate(node.value)
            self.validate(node.slice)
            return
        if isinstance(node, ast.Attribute):
            if not _is_safe_attribute_name(node.attr):
                raise ValueError(f"Unsafe attribute access: {node.attr}")
            self.validate(node.value)
            return
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_EXPR_FUNCTIONS:
                raise ValueError("Only simple allow-listed function calls are supported")
            if node.keywords:
                raise ValueError("Keyword arguments are not supported")
            for arg in node.args:
                if isinstance(arg, ast.Call):
                    raise ValueError("Nested function calls are not supported")
                self.validate(arg)
            return
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    def evaluate(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return self.evaluate(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in _SAFE_EXPR_FUNCTIONS:
                raise ValueError(f"Function name cannot be used as a value: {node.id}")
            if node.id not in self.safe_locals:
                raise NameError(f"Undefined params: {node.id}")
            value = self.safe_locals[node.id]
            if callable(value):
                raise ValueError(f"Callable value is not allowed: {node.id}")
            return value
        if isinstance(node, ast.Tuple):
            return tuple(self.evaluate(item) for item in node.elts)
        if isinstance(node, ast.List):
            return [self.evaluate(item) for item in node.elts]
        if isinstance(node, ast.Subscript):
            return self.evaluate(node.value)[self.evaluate(node.slice)]
        if isinstance(node, ast.Attribute):
            value = getattr(self.evaluate(node.value), node.attr)
            if callable(value):
                raise ValueError(f"Callable attribute is not allowed: {node.attr}")
            return value
        if isinstance(node, ast.Call):
            func = _SAFE_EXPR_FUNCTIONS[node.func.id]
            return func(*(self.evaluate(arg) for arg in node.args))
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def _parse_safe_expression(expr_str: str) -> ast.Expression:
    return ast.parse(_normalize_expr(expr_str), mode="eval")


def _validate_direct_expression(expr_str: str) -> bool:
    try:
        tree = _parse_safe_expression(expr_str)
        _SafeExpressionEvaluator({}).validate(tree)
        return True
    except Exception as e:
        logger.warning(f"Expression validation failed: {expr_str}, err={e}")
        return False


def _validate_expression_safety(expr_str):
    """验证表达式安全性，只允许预定义的安全操作。"""
    if '|' not in expr_str:
        return _validate_direct_expression(expr_str)
    parts = [part.strip() for part in expr_str.split('|')]
    if len(parts) < 2 or not parts[0]:
        return _validate_direct_expression(expr_str)
    if not _validate_direct_expression(parts[0]):
        return False
    for operation in parts[1:]:
        if operation in ("len", "str"):
            continue
        if operation.startswith("attr "):
            attr_name = operation[5:].strip()
            if _is_safe_attribute_name(attr_name):
                continue
        logger.warning(f"Pipe operation not allowed: {operation}")
        return False
    return True


def _execute_safe_expression(expr_str, safe_locals):
    """Execute a safe AST expression with optional len/str pipe operations."""
    if not _validate_expression_safety(expr_str):
        return None
    if '|' not in expr_str:
        return _execute_direct_expression_ast(expr_str, safe_locals)
    parts = [part.strip() for part in expr_str.split('|')]
    if len(parts) < 2 or not parts[0]:
        return _execute_direct_expression_ast(expr_str, safe_locals)
    result = _execute_direct_expression_ast(parts[0], safe_locals)
    for operation in parts[1:]:
        if operation == "len":
            result = len(result) if result is not None else None
        elif operation == "str":
            result = str(result)
        elif operation.startswith("attr "):
            attr_name = operation[5:].strip()
            if not _is_safe_attribute_name(attr_name):
                logger.warning(f"Pipe operation not allowed: {operation}")
                return None
            result = _get_object_attribute(result, attr_name)
        else:
            logger.warning(f"Pipe operation not allowed: {operation}")
            return None
        if result is None:
            break
    return result


def _execute_direct_expression_ast(expr_str, safe_locals):
    try:
        trimmed = expr_str.strip()
        if trimmed == 'return':
            return safe_locals.get('return')
        tree = _parse_safe_expression(expr_str)
        evaluator = _SafeExpressionEvaluator(safe_locals)
        evaluator.validate(tree)
        return evaluator.evaluate(tree)
    except Exception as e:
        logger.warning(f"Safe eval failed: {expr_str}, err={e}")
        return None


def _safe_eval_expr(expr: str, ctx: FuncCallContext):
    """安全执行表达式，支持 len/str 管道操作。"""
    try:
        safe_locals = _build_safe_locals(ctx)
        return _execute_safe_expression(expr, safe_locals)
    except Exception as e:
        logger.warning(f"Pipe eval failed: {expr}, err={e}")
        return None


def make_default_time_hook(domain: str, name: str, attributes: Optional[List[Dict[str, Any]]] = None) -> Callable:
    """生成一个默认的耗时统计 hook 处理函数，并支持自定义属性采集。

    该函数创建一个用于性能分析的 hook 处理函数，支持：
    - 基本的耗时统计
    - 自定义属性采集
    - 安全的表达式执行

    Args:
        domain: 性能分析域名称
        name: hook 名称
        attributes: 自定义属性采集配置列表，可选。每个属性包含：
            - name (str): 采集项名称
            - expr (str): 表达式，如 "len(kwargs['input_ids'])"、"str(args[0])"、"kwargs['any'].attr"

    Returns:
        Callable: hook 处理函数

    Note:
        attributes 结构示例：
        [
            {"name": "input_length", "expr": "len(kwargs['input_ids'])"},
            {"name": "output_length", "expr": "len(return)"},
            {"name": "model_name", "expr": "this.model_name"}
        ]
    """
    if Profiler is None:

        def _noop(original_func, *args, **kwargs):
            return original_func(*args, **kwargs)

        return _noop

    def _default(original_func, *args, **kwargs):
        """默认的 hook 处理函数。

        Args:
            original_func: 原始函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            原始函数的返回值
        """
        level_val = getattr(Level, 'INFO', None) if Level is not None else None
        prof = Profiler(level_val).domain(domain).span_start(name)
        ret = original_func(*args, **kwargs)

        if isinstance(attributes, list):
            for item in attributes:
                attr_name = item.get("name")
                expr = item.get("expr")
                if not attr_name or not expr:
                    continue
                # Use args/kwargs/return in expr to identify the data source.
                ctx = FuncCallContext(
                    func_obj=original_func,
                    this_obj=args[0] if len(args) > 0 else None,
                    args=args,
                    kwargs=kwargs,
                    ret_val=ret,
                )
                val = _safe_eval_expr(expr, ctx)
                if val is not None:
                    prof.attr(attr_name, val)

        prof.span_end()
        return ret

    return _default


class HandlerResolver:
    """Handler解析器：有可导入的自定义 handler 则用之，否则使用 timer。

    该类负责根据配置解析 handler 函数，支持：
    - 内置 timer handler
    - 自定义导入的 handler
    - 自动回退机制

    Attributes:
        prefer_builtin (bool): 是否优先使用内置 handler
    """

    def __init__(self, prefer_builtin: bool = True):
        """初始化 HandlerResolver。

        Args:
            prefer_builtin: 是否优先使用内置 handler，默认为 True
        """
        self.prefer_builtin = prefer_builtin

    @staticmethod
    def resolve(item: Dict[str, Any], points: List[Tuple[str, str]]) -> Callable:
        """根据配置解析handler函数。

        Args:
            item: 配置项字典
            points: hook 点列表

        Returns:
            Callable: 解析出的 handler 函数
        """
        domain = item.get("domain") or "Custom"
        name = item.get("name") or (points[0][1] if points else "custom")
        attributes = item.get("attributes")  # 新增：自定义属性采集配置
        handler_val = item.get("handler")
        handler_lower = handler_val.lower() if isinstance(handler_val, str) else None

        # 显式 timer
        if handler_lower == "timer" or handler_val is None:
            return make_default_time_hook(domain, name, attributes)

        # 自定义 import 形式
        if isinstance(handler_val, str) and ":" in handler_val:
            func = HandlerResolver._try_import(handler_val)
            if func is not None:
                return func
            logger.warning(f"Failed to import handler '{handler_val}', fallback to timer")
            return make_default_time_hook(domain, name, attributes)

        # 其他值（含 builtin）一律按 timer 处理
        return make_default_time_hook(domain, name, attributes)

    @staticmethod
    def _try_import(handler_val: str) -> Optional[Callable]:
        """尝试按 'pkg.mod:func' 导入自定义 handler，失败返回 None。

        Args:
            handler_val: handler 路径字符串，格式为 'pkg.mod:func'

        Returns:
            Optional[Callable]: 导入的 handler 函数，失败时返回 None
        """
        try:
            mod, func_name = handler_val.split(":", 1)
            if not is_allowed_handler_module(mod):
                logger.warning("Handler module '%s' is not allowed", mod)
                return None
            mod_obj = importlib.import_module(mod)
            # Avoid Mock auto-creation: inspect module dict directly
            value = getattr(mod_obj, "__dict__", {}).get(func_name, None)
            return value if callable(value) else None
        except Exception:
            return None
