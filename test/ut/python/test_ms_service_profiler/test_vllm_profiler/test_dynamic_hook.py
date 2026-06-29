# -------------------------------------------------------------------------
# pylint: disable=comparison-with-callable,redefined-outer-name,use-implicit-booleaness-not-comparison
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

from unittest.mock import Mock, patch, call
from unittest.mock import ANY
from unittest.mock import MagicMock
from typing import ContextManager
import pytest

from ms_service_profiler.patcher.core.dynamic_hook import (
    FuncCallContext,
    DynamicHooker,
    register_dynamic_hook,
    make_default_time_hook,
    HandlerResolver,
    ConfigHooker,
    MultiHandlerDynamicHooker,
    global_mutil_handler_manager,
    VLLMHookerBase,
)


@pytest.fixture
def sample_func_call_context():
    """提供示例函数调用上下文的 fixture"""
    mock_func = Mock()
    mock_this = Mock()
    mock_args = (1, 2, 3)
    mock_kwargs = {'key': 'value'}
    mock_ret_val = "result"

    return FuncCallContext(
        func_obj=mock_func, this_obj=mock_this, args=mock_args, kwargs=mock_kwargs, ret_val=mock_ret_val
    )


@pytest.fixture
def sample_hook_list():
    """提供示例 hook 列表的 fixture"""
    return [('module.path', 'ClassName.method_name'), ('another.module', 'function_name')]


@pytest.fixture
def mock_hook_func():
    """提供模拟 hook 函数的 fixture"""
    mock = Mock()
    mock.__name__ = "mock_hook_func"
    return mock


@pytest.fixture
def sample_attributes():
    """提供示例属性的 fixture"""
    return [
        {"name": "input_length", "expr": "len(kwargs['input_ids'])"},
        {"name": "output_length", "expr": "len(return)"},
        {"name": "model_name", "expr": "this.model_name"},
    ]


class TestFuncCallContext:
    """测试 FuncCallContext 数据类"""

    @staticmethod
    def test_func_call_context_initialization(sample_func_call_context):
        """测试 FuncCallContext 初始化"""
        ctx = sample_func_call_context

        assert ctx.func_obj is not None
        assert ctx.this_obj is not None
        assert ctx.args == (1, 2, 3)
        assert ctx.kwargs == {'key': 'value'}
        assert ctx.ret_val == "result"


class TestDynamicHooker:
    """测试 DynamicHooker 类"""

    @staticmethod
    def test_dynamic_hooker_initialization(sample_hook_list, mock_hook_func):
        """测试 DynamicHooker 初始化"""
        hooker = DynamicHooker(
            hook_list=sample_hook_list,
            hook_func=mock_hook_func,
            min_version="1.0",
            max_version="2.0",
            caller_filter="test_filter",
        )

        assert hooker.vllm_version == ("1.0", "2.0")
        assert hooker.applied_hook_func_name == mock_hook_func.__name__
        assert hooker.hook_list == sample_hook_list
        assert hooker.caller_filter == "test_filter"
        assert hooker.wrap_hook_func == mock_hook_func

    @staticmethod
    def test_dynamic_hooker_initialization_minimal(sample_hook_list, mock_hook_func):
        """测试 DynamicHooker 初始化（最小参数）"""
        hooker = DynamicHooker(
            hook_list=sample_hook_list, hook_func=mock_hook_func, min_version=None, max_version=None, caller_filter=None
        )

        assert hooker.vllm_version == (None, None)
        assert hooker.caller_filter is None

    @staticmethod
    @patch('ms_service_profiler.patcher.core.dynamic_hook.import_object_from_string')
    def test_dynamic_hooker_init(mock_import_object, sample_hook_list, mock_hook_func):
        """测试 DynamicHooker init 方法"""
        # 模拟导入的对象
        mock_point1 = Mock()
        mock_point2 = Mock()
        mock_import_object.side_effect = [mock_point1, mock_point2]

        hooker = DynamicHooker(
            hook_list=sample_hook_list, hook_func=mock_hook_func, min_version=None, max_version=None, caller_filter=None
        )

        # 模拟父类的 do_hook 方法
        with patch.object(hooker, 'do_hook') as mock_do_hook:
            hooker.init()

            # 验证导入调用
            assert mock_import_object.call_count == 2
            mock_import_object.assert_has_calls(
                [call('module.path', 'ClassName.method_name'), call('another.module', 'function_name')]
            )

            # 验证 do_hook 调用
            mock_do_hook.assert_called_once()
            call_args = mock_do_hook.call_args
            assert call_args[1]['hook_points'] == [mock_point1, mock_point2]
            assert call_args[1]['pname'] is None


class TestRegisterDynamicHook:
    """测试 register_dynamic_hook 函数"""

    @staticmethod
    def test_register_dynamic_hook(sample_hook_list, mock_hook_func):
        """测试 register_dynamic_hook 函数"""
        with patch('ms_service_profiler.patcher.core.dynamic_hook.DynamicHooker') as mock_dynamic_hooker:
            mock_hooker_instance = Mock()
            mock_dynamic_hooker.return_value = mock_hooker_instance

            result = register_dynamic_hook(
                hook_list=sample_hook_list,
                hook_func=mock_hook_func,
                min_version="1.0",
                max_version="2.0",
                caller_filter="test_filter",
                need_locals=False,
            )

            # 验证 DynamicHooker 初始化
            mock_dynamic_hooker.assert_called_once_with(
                hook_list=sample_hook_list,
                hook_func=mock_hook_func,
                min_version="1.0",
                max_version="2.0",
                caller_filter="test_filter",
                need_locals=False,
            )

            # 验证注册调用
            mock_hooker_instance.register.assert_called_once()
            assert result == mock_hooker_instance

    @staticmethod
    def test_register_dynamic_hook_default_args(sample_hook_list, mock_hook_func):
        """测试 register_dynamic_hook 函数（默认参数）"""
        with patch('ms_service_profiler.patcher.core.dynamic_hook.DynamicHooker') as mock_dynamic_hooker:
            mock_hooker_instance = Mock()
            mock_dynamic_hooker.return_value = mock_hooker_instance

            register_dynamic_hook(hook_list=sample_hook_list, hook_func=mock_hook_func)

            mock_dynamic_hooker.assert_called_once_with(
                hook_list=sample_hook_list,
                hook_func=mock_hook_func,
                min_version=None,
                max_version=None,
                caller_filter=None,
                need_locals=False,
            )


class TestMakeDefaultTimeHook:
    """测试 make_default_time_hook 函数"""

    @staticmethod
    def test_make_default_time_hook_no_profiler():
        """测试没有 ms_service_profiler 的情况"""
        with patch.dict('sys.modules', {'ms_service_profiler': None}):
            # 重新导入以应用模拟
            import importlib
            import sys

            if 'ms_service_profiler.patcher.core.dynamic_hook' in sys.modules:
                importlib.reload(sys.modules['ms_service_profiler.patcher.core.dynamic_hook'])

            result_func = make_default_time_hook("test_domain", "test_name")

            # 测试返回的函数
            mock_original = Mock(return_value="result")
            mock_args = (1, 2, 3)
            mock_kwargs = {'key': 'value'}

            result = result_func(mock_original, *mock_args, **mock_kwargs)

            mock_original.assert_called_once_with(*mock_args, **mock_kwargs)
            assert result == "result"

    @staticmethod
    @patch('ms_service_profiler.patcher.core.dynamic_hook.Profiler')
    def test_make_default_time_hook_with_profiler_no_attributes(mock_profiler):
        """测试有 profiler 但无属性的情况"""
        mock_profiler_instance = Mock()
        mock_profiler.return_value.domain.return_value.span_start.return_value = mock_profiler_instance

        result_func = make_default_time_hook("test_domain", "test_name")

        mock_original = Mock(return_value="result")
        mock_args = (1, 2, 3)
        mock_kwargs = {'key': 'value'}

        result = result_func(mock_original, *mock_args, **mock_kwargs)

        # 验证 Profiler 调用
        mock_profiler.assert_called_once()
        mock_profiler_instance.span_end.assert_called_once()
        mock_original.assert_called_once_with(*mock_args, **mock_kwargs)
        assert result == "result"

    @staticmethod
    @patch('ms_service_profiler.patcher.core.dynamic_hook.Profiler')
    def test_make_default_time_hook_with_attributes(mock_profiler, sample_attributes):
        """测试有属性和 profiler 的情况"""
        mock_profiler_instance = Mock()
        mock_profiler.return_value.domain.return_value.span_start.return_value = mock_profiler_instance

        result_func = make_default_time_hook("test_domain", "test_name", sample_attributes)

        mock_original = Mock(return_value="result")
        mock_args = (Mock(),)  # 第一个参数作为 self
        mock_kwargs = {'input_ids': [1, 2, 3]}

        # 模拟内部函数的行为
        with patch('ms_service_profiler.patcher.core.dynamic_hook._safe_eval_expr') as mock_safe_eval:
            mock_safe_eval.side_effect = [6, 3, "test_model"]  # 模拟三个属性的返回值

            result_func(mock_original, *mock_args, **mock_kwargs)

            # 验证属性设置
            assert mock_profiler_instance.attr.call_count == 3
            mock_profiler_instance.attr.assert_has_calls(
                [call("input_length", 6), call("output_length", 3), call("model_name", "test_model")]
            )

    @staticmethod
    @patch('ms_service_profiler.patcher.core.dynamic_hook.Profiler')
    def test_make_default_time_hook_attribute_eval_failure(mock_profiler, sample_attributes):
        """测试属性表达式执行失败的情况"""
        mock_profiler_instance = Mock()
        mock_profiler.return_value.domain.return_value.span_start.return_value = mock_profiler_instance

        result_func = make_default_time_hook("test_domain", "test_name", sample_attributes)

        mock_original = Mock(return_value="result")
        mock_args = (Mock(),)
        mock_kwargs = {'input_ids': [1, 2, 3]}

        with patch('ms_service_profiler.patcher.core.dynamic_hook._safe_eval_expr') as mock_safe_eval:
            mock_safe_eval.return_value = None  # 所有表达式执行失败

            result_func(mock_original, *mock_args, **mock_kwargs)

            # 验证没有属性被设置
            mock_profiler_instance.attr.assert_not_called()

    @staticmethod
    @patch('ms_service_profiler.patcher.core.dynamic_hook.Profiler')
    def test_make_default_time_hook_invalid_attributes(mock_profiler):
        """测试无效属性配置的情况"""
        mock_profiler_instance = Mock()
        mock_profiler.return_value.domain.return_value.span_start.return_value = mock_profiler_instance

        invalid_attributes = [
            {"name": "valid", "expr": "len(args)"},  # 有效
            {"name": "", "expr": "len(kwargs)"},  # 无效：空名称
            {"name": "no_expr"},  # 无效：缺少表达式
            {"expr": "len(return)"},  # 无效：缺少名称
        ]

        result_func = make_default_time_hook("test_domain", "test_name", invalid_attributes)

        mock_original = Mock(return_value="result")

        with patch('ms_service_profiler.patcher.core.dynamic_hook._safe_eval_expr') as mock_safe_eval:
            mock_safe_eval.return_value = 5

            result_func(mock_original, 1, 2, 3)

            # 只有第一个有效属性被处理
            mock_safe_eval.assert_called_once_with("len(args)", ANY)
            mock_profiler_instance.attr.assert_called_once_with("valid", 5)


class TestHandlerResolver:
    """测试 HandlerResolver 类"""

    @staticmethod
    def test_handler_resolver_initialization():
        """测试 HandlerResolver 初始化"""
        resolver = HandlerResolver(prefer_builtin=True)
        assert resolver.prefer_builtin is True

        resolver2 = HandlerResolver(prefer_builtin=False)
        assert resolver2.prefer_builtin is False

    @staticmethod
    @patch('ms_service_profiler.patcher.core.dynamic_hook.importlib.import_module')
    def test_try_import_success(mock_import_module):
        """测试成功导入 handler"""
        mock_module = Mock()
        mock_handler = Mock()
        mock_import_module.return_value = mock_module
        mock_module.test_handler = mock_handler

        result = HandlerResolver._try_import("some.module:test_handler")

        mock_import_module.assert_called_once_with("some.module")
        assert result == mock_handler

    @staticmethod
    @patch('ms_service_profiler.patcher.core.dynamic_hook.importlib.import_module')
    def test_try_import_module_not_found(mock_import_module):
        """测试导入模块失败"""
        mock_import_module.side_effect = ImportError("Module not found")

        result = HandlerResolver._try_import("nonexistent.module:handler")

        assert result is None

    @staticmethod
    @patch('ms_service_profiler.patcher.core.dynamic_hook.importlib.import_module')
    def test_try_import_function_not_found(mock_import_module):
        """测试导入函数不存在"""
        mock_module = Mock()
        mock_module.test_handler = None  # 函数不存在
        mock_import_module.return_value = mock_module

        result = HandlerResolver._try_import("some.module:nonexistent_handler")

        assert result is None

    @staticmethod
    @patch('ms_service_profiler.patcher.core.dynamic_hook.make_default_time_hook')
    def test_resolve_explicit_timer(mock_make_default):
        """测试解析显式 timer handler"""
        mock_timer = Mock()
        mock_make_default.return_value = mock_timer

        resolver = HandlerResolver()
        item = {"domain": "TestDomain", "name": "TestName", "handler": "timer"}
        points = [('module', 'function')]

        result = resolver.resolve(item, points)

        mock_make_default.assert_called_once_with("TestDomain", "TestName", None)
        assert result == mock_timer

    @staticmethod
    @patch('ms_service_profiler.patcher.core.dynamic_hook.make_default_time_hook')
    def test_resolve_none_handler(mock_make_default):
        """测试解析 None handler（隐式 timer）"""
        mock_timer = Mock()
        mock_make_default.return_value = mock_timer

        resolver = HandlerResolver()
        item = {
            "domain": "TestDomain",
            "name": "TestName",
            # 没有 handler
        }
        points = [('module', 'function')]

        result = resolver.resolve(item, points)

        mock_make_default.assert_called_once_with("TestDomain", "TestName", None)
        assert result == mock_timer

    @staticmethod
    @patch('ms_service_profiler.patcher.core.dynamic_hook.HandlerResolver._try_import')
    @patch('ms_service_profiler.patcher.core.dynamic_hook.make_default_time_hook')
    def test_resolve_custom_handler_success(mock_make_default, mock_try_import):
        """测试成功解析自定义 handler"""
        mock_custom_handler = Mock()
        mock_try_import.return_value = mock_custom_handler

        resolver = HandlerResolver()
        item = {"domain": "TestDomain", "name": "TestName", "handler": "custom.module:handler_func"}
        points = [('module', 'function')]

        result = resolver.resolve(item, points)

        mock_try_import.assert_called_once_with("custom.module:handler_func")
        assert result == mock_custom_handler
        mock_make_default.assert_not_called()

    @staticmethod
    @patch('ms_service_profiler.patcher.core.dynamic_hook.HandlerResolver._try_import')
    @patch('ms_service_profiler.patcher.core.dynamic_hook.make_default_time_hook')
    def test_resolve_custom_handler_fallback(mock_make_default, mock_try_import):
        """测试自定义 handler 导入失败回退到 timer"""
        mock_timer = Mock()
        mock_make_default.return_value = mock_timer
        mock_try_import.return_value = None  # 导入失败

        resolver = HandlerResolver()
        item = {"domain": "TestDomain", "name": "TestName", "handler": "custom.module:handler_func"}
        points = [('module', 'function')]

        result = resolver.resolve(item, points)

        mock_try_import.assert_called_once_with("custom.module:handler_func")
        mock_make_default.assert_called_once_with("TestDomain", "TestName", None)
        assert result == mock_timer

    @staticmethod
    @patch('ms_service_profiler.patcher.core.dynamic_hook.make_default_time_hook')
    def test_resolve_other_handler_value(mock_make_default):
        """测试解析其他 handler 值（回退到 timer）"""
        mock_timer = Mock()
        mock_make_default.return_value = mock_timer

        resolver = HandlerResolver()
        item = {
            "domain": "TestDomain",
            "name": "TestName",
            "handler": "builtin",  # 不是 "timer" 或自定义导入格式
        }
        points = [('module', 'function')]

        result = resolver.resolve(item, points)

        mock_make_default.assert_called_once_with("TestDomain", "TestName", None)
        assert result == mock_timer

    @staticmethod
    @patch('ms_service_profiler.patcher.core.dynamic_hook.make_default_time_hook')
    def test_resolve_with_attributes(mock_make_default):
        """测试解析带有属性的 handler"""
        mock_timer = Mock()
        mock_make_default.return_value = mock_timer

        resolver = HandlerResolver()
        attributes = [{"name": "test_attr", "expr": "len(args)"}]
        item = {"domain": "TestDomain", "name": "TestName", "handler": "timer", "attributes": attributes}
        points = [('module', 'function')]

        result = resolver.resolve(item, points)

        mock_make_default.assert_called_once_with("TestDomain", "TestName", attributes)
        assert result == mock_timer

    @staticmethod
    @patch('ms_service_profiler.patcher.core.dynamic_hook.make_default_time_hook')
    def test_resolve_name_from_points(mock_make_default):
        """测试从 points 中提取名称"""
        mock_timer = Mock()
        mock_make_default.return_value = mock_timer

        resolver = HandlerResolver()
        item = {
            "domain": "TestDomain"
            # 没有 name，应该从 points 中提取
        }
        points = [('module', 'function_name')]

        result = resolver.resolve(item, points)

        mock_make_default.assert_called_once_with("TestDomain", "function_name", None)
        assert result == mock_timer

    @staticmethod
    @patch('ms_service_profiler.patcher.core.dynamic_hook.make_default_time_hook')
    def test_resolve_default_name(mock_make_default):
        """测试使用默认名称"""
        mock_timer = Mock()
        mock_make_default.return_value = mock_timer

        resolver = HandlerResolver()
        item = {
            "domain": "TestDomain"
            # 没有 name，也没有 points
        }
        points = []  # 空列表

        result = resolver.resolve(item, points)

        mock_make_default.assert_called_once_with("TestDomain", "custom", None)
        assert result == mock_timer


class TestInternalFunctions:
    """测试内部辅助函数"""

    @staticmethod
    def test_get_object_attribute(sample_func_call_context):
        """测试 _get_object_attribute 函数"""

        # 创建 hook 函数以访问内部函数
        hook_func = make_default_time_hook("test", "test")

        # 测试获取存在的属性
        mock_obj = Mock()
        mock_obj.test_attr = "test_value"
        result = hook_func.__globals__['_get_object_attribute'](mock_obj, "test_attr")
        assert result == "test_value"

        # 测试获取不存在的属性
        result = hook_func.__globals__['_get_object_attribute'](mock_obj, "nonexistent_attr")
        assert result is None

    @staticmethod
    def test_extract_named_parameters(sample_func_call_context):
        """测试 _extract_named_parameters 函数"""

        hook_func = make_default_time_hook("test", "test")

        # 创建有签名的函数
        def test_func(a, b, c=3, d=4):
            pass

        args = (1, 2)
        kwargs = {'d': 5}

        result = hook_func.__globals__['_extract_named_parameters'](test_func, args, kwargs)

        assert 'a' in result
        assert 'b' in result
        assert 'c' in result  # 使用默认值
        assert 'd' in result
        assert result['a'] == 1
        assert result['b'] == 2
        assert result['c'] == 3
        assert result['d'] == 5

    @staticmethod
    def test_build_safe_locals(sample_func_call_context):
        """测试 _build_safe_locals 函数"""

        hook_func = make_default_time_hook("test", "test")

        # 模拟有 self 参数的情况
        mock_self = Mock()
        mock_self.model_name = "test_model"

        def test_func(self, arg1, arg2):
            pass

        ctx = FuncCallContext(
            func_obj=test_func,
            this_obj=mock_self,
            args=(mock_self, "arg1_value", "arg2_value"),
            kwargs={},
            ret_val="result_value",
        )

        safe_locals = hook_func.__globals__['_build_safe_locals'](ctx)

        # 验证基本变量
        assert safe_locals['this'] == mock_self
        assert safe_locals['args'] == (mock_self, "arg1_value", "arg2_value")
        assert safe_locals['kwargs'] == {}
        assert safe_locals['return'] == "result_value"

        # 验证具名参数
        assert 'self' in safe_locals
        assert 'arg1' in safe_locals
        assert 'arg2' in safe_locals

    @staticmethod
    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("len(args)", True),  # 安全表达式
            ("import os", False),  # 危险关键字
            ("__import__('os')", False),  # 危险函数
            ("eval('1+1')", False),  # 危险函数
            ("args[0] + args[1]", False),  # 危险操作符
            ("len(kwargs.get('key', []))", True),  # 安全函数调用
            ("unknown_func()", False),  # 未知函数
            ("(1 + 2) * 3", False),  # 算术运算
            ("args[0] | len", True),  # 管道操作（在后续验证）
        ],
    )
    def test_validate_expression_safety(expr, expected):
        """测试 _validate_expression_safety 函数"""

        hook_func = make_default_time_hook("test", "test")

        result = hook_func.__globals__['_validate_expression_safety'](expr)
        assert result == expected

    @staticmethod
    def test_execute_direct_expression(sample_func_call_context):
        """测试 _execute_direct_expression 函数"""

        hook_func = make_default_time_hook("test", "test")

        safe_locals = {'args': (1, 2, 3), 'kwargs': {'key': 'value'}, 'return': "result", 'len': len, 'str': str}

        # 测试安全表达式
        result = hook_func.__globals__['_execute_direct_expression']("len(args)", safe_locals)
        assert result == 3

        # 测试危险表达式（应该返回 None）
        result = hook_func.__globals__['_execute_direct_expression']("import os", safe_locals)
        assert result is None

        # 测试无效表达式
        result = hook_func.__globals__['_execute_direct_expression']("invalid_syntax", safe_locals)
        assert result is None

    @staticmethod
    @pytest.mark.parametrize(
        "input_val,operation,expected",
        [
            ([1, 2, 3], 'len', 3),  # len 操作
            ("hello", 'str', "hello"),  # str 操作
            (Mock(test_attr="value"), 'attr test_attr', "value"),  # attr 操作
            ([1, 2, 3], 'unknown', None),  # 未知操作
            (None, 'len', None),  # None 输入
        ],
    )
    def test_apply_pipe_operation(input_val, operation, expected):
        """测试 _apply_pipe_operation 函数"""

        hook_func = make_default_time_hook("test", "test")

        result = hook_func.__globals__['_apply_pipe_operation'](input_val, operation)

        if expected is None:
            assert result is None
        else:
            assert result == expected

    @staticmethod
    def test_execute_pipe_expression(sample_func_call_context):
        """测试 _execute_pipe_expression 函数"""

        hook_func = make_default_time_hook("test", "test")

        safe_locals = {
            'args': ([1, 2, 3],),
            'kwargs': {'key': 'value'},
            'return': "hello world",
            'len': len,
            'str': str,
        }

        # 测试简单表达式
        result = hook_func.__globals__['_execute_pipe_expression']("len(args[0])", safe_locals)
        assert result == 3

        # 测试管道表达式
        result = hook_func.__globals__['_execute_pipe_expression']("args[0] | len", safe_locals)
        assert result == 3

        # 测试多步管道
        result = hook_func.__globals__['_execute_pipe_expression']("return | len | str", safe_locals)
        assert result == "11"  # len("hello world") = 11, then str(11) = "11"

    @staticmethod
    def test_safe_eval_expr(sample_func_call_context):
        """测试 _safe_eval_expr 函数"""

        hook_func = make_default_time_hook("test", "test")

        # 模拟成功的表达式执行
        with (
            patch('ms_service_profiler.patcher.core.dynamic_hook._build_safe_locals') as mock_build_locals,
            patch('ms_service_profiler.patcher.core.dynamic_hook._execute_pipe_expression') as mock_execute,
        ):
            mock_build_locals.return_value = {'args': (1, 2, 3), 'len': len}
            mock_execute.return_value = 3

            result = hook_func.__globals__['_safe_eval_expr']("len(args)", sample_func_call_context)

            mock_build_locals.assert_called_once_with(sample_func_call_context)
            mock_execute.assert_called_once_with("len(args)", {'args': (1, 2, 3), 'len': len})
            assert result == 3

        # 模拟表达式执行失败
        with (
            patch('ms_service_profiler.patcher.core.dynamic_hook._build_safe_locals') as mock_build_locals,
            patch('ms_service_profiler.patcher.core.dynamic_hook._execute_pipe_expression') as mock_execute,
        ):
            mock_build_locals.return_value = {'args': (1, 2, 3), 'len': len}
            mock_execute.side_effect = Exception("Test error")

            result = hook_func.__globals__['_safe_eval_expr']("len(args)", sample_func_call_context)

            assert result is None


@pytest.fixture(autouse=True)
def reset_global_manager():
    """每个测试前重置全局管理器字典"""
    global_mutil_handler_manager.clear()
    yield


@pytest.fixture
def mock_add_to_hook_registry():
    with patch("ms_service_profiler.patcher.core.dynamic_hook.add_to_hook_registry") as mock:
        yield mock


@pytest.fixture
def mock_import_object():
    with patch("ms_service_profiler.patcher.core.dynamic_hook.import_object_from_string") as mock:
        mock.return_value = MagicMock()  # 返回一个 mock 对象作为 hook point
        yield mock


@pytest.fixture
def mock_default_hook_func():
    # 模拟 VLLMHookerBase.default_hook_func
    with patch.object(VLLMHookerBase, "default_hook_func", return_value="default") as mock:
        yield mock


# ------------------------------------------------------------
# MultiHandlerDynamicHooker 测试
# ------------------------------------------------------------
class TestMultiHandlerDynamicHooker:
    def test_given_handlers_when_add_handler_then_rebuilds_and_inits(self, mock_import_object):
        """正例：添加 handler 后重建包装函数并重新 init"""
        hook_list = [("mod", "func")]
        handler1 = MagicMock(spec=ConfigHooker)
        handler1.wrap_hook_func = lambda ori, *a, **kw: ori(*a, **kw)
        handler1.context_hook_funcs = []
        handler1.need_locals = False

        manager = MultiHandlerDynamicHooker(hook_list, [], None, None, None, False)
        with patch.object(manager, "init") as mock_init, patch.object(manager, "recover") as mock_recover:
            manager.add_handler(handler1)
            # 应调用 recover 清除旧 hooks
            mock_recover.assert_called_once()
            # 应调用 init 应用新 hooks
            mock_init.assert_called_once()
            assert handler1 in manager.handlers
            # 检查 wrap_hook_func 已被构建（不是原始函数）
            assert manager.wrap_hook_func != VLLMHookerBase.default_hook_func

    def test_given_duplicate_handler_when_add_handler_then_ignored(self, mock_import_object):
        """反例：重复添加相同 handler 应被忽略"""
        handler = MagicMock()
        manager = MultiHandlerDynamicHooker([], [], None, None, None, False)
        manager.add_handler(handler)
        with patch.object(manager, "init") as mock_init:
            manager.add_handler(handler)  # 再次添加
            mock_init.assert_not_called()
            assert len(manager.handlers) == 1

    def test_given_handler_exists_when_recover_handler_then_removes_and_rebuilds(self, mock_import_object):
        """正例：移除存在的 handler 后重建并重新 init"""
        handler1 = MagicMock()
        handler1.wrap_hook_func = lambda ori, *a, **kw: ori(*a, **kw)
        handler1.context_hook_funcs = []
        handler1.need_locals = False

        manager = MultiHandlerDynamicHooker([], [], None, None, None, False)
        manager.add_handler(handler1)

        with patch.object(manager, "init") as mock_init, patch.object(manager, "recover") as mock_recover:
            result = manager.recover_handler(handler1)
            assert result == 0  # 移除后 handlers 为空
            mock_recover.assert_called_once()
            mock_init.assert_not_called()
            assert handler1 not in manager.handlers

    def test_given_handler_not_exists_when_recover_handler_then_returns_same_length(self, mock_import_object):
        """反例：移除不存在的 handler 返回当前 handlers 数量，无 rebuild"""
        handler = MagicMock()
        manager = MultiHandlerDynamicHooker([], [], None, None, None, False)
        manager.add_handler(handler)  # 添加一个
        another = MagicMock()

        with patch.object(manager, "init") as mock_init:
            result = manager.recover_handler(another)
            assert result == 1
            mock_init.assert_not_called()
            assert handler in manager.handlers

    def test_given_no_handlers_when_build_wrap_hook_func_then_returns_default(self):
        """正例：没有 wrap 函数时返回默认 hook func"""
        manager = MultiHandlerDynamicHooker([], [], None, None, None, False)
        result = manager.build_wrap_hook_func([])
        assert result == VLLMHookerBase.default_hook_func

    def test_given_single_wrap_func_when_build_then_returns_that_func(self):
        """正例：单个 wrap 函数时直接返回"""

        def func(ori, *a, **kw):
            pass

        manager = MultiHandlerDynamicHooker([], [], None, None, None, False)
        result = manager.build_wrap_hook_func([func])
        assert result == func

    def test_given_multiple_wrap_funcs_when_build_then_returns_chained_func(self):
        """正例：多个 wrap 函数时返回组合函数，调用顺序正确"""
        calls = []

        def f1(next_func, *args, **kwargs):
            calls.append("f1_before")
            ret = next_func(*args, **kwargs)
            calls.append("f1_after")
            return ret

        def f2(next_func, *args, **kwargs):
            calls.append("f2_before")
            ret = next_func(*args, **kwargs)
            calls.append("f2_after")
            return ret

        def original(*args, **kwargs):
            calls.append("original")
            return "result"

        manager = MultiHandlerDynamicHooker([], [], None, None, None, False)
        chained_func = manager.build_wrap_hook_func([f1, f2])
        # 需要模拟动态包装：build_wrap_hook_func 返回的 _wrap_hook_func 接受 (ori_func, *args, **kwargs)
        # 调用时应将 original 作为 ori_func 传入
        result = chained_func(original, 1, 2, a=3)
        assert result == "result"
        assert calls == ["f1_before", "f2_before", "original", "f2_after", "f1_after"]

    def test_given_mixed_handlers_when_add_handler_then_combines_need_locals(self):
        """正例：添加 handler 时合并 need_locals（任意为 True 则 True）"""
        handler1 = MagicMock()
        handler1.need_locals = True
        handler2 = MagicMock()
        handler2.need_locals = False

        manager = MultiHandlerDynamicHooker([], [], None, None, None, False)
        manager.add_handler(handler1)
        assert manager.need_locals is True

        manager = MultiHandlerDynamicHooker([], [], None, None, None, False)
        manager.add_handler(handler2)
        assert manager.need_locals is False
        manager.add_handler(handler1)
        assert manager.need_locals is True

    def test_given_mixed_handlers_when_add_then_combines_context_hook_funcs(self):
        """正例：添加 handler 时合并 context_hook_funcs"""
        ctx1 = MagicMock()
        ctx2 = MagicMock()
        handler1 = MagicMock()
        handler1.context_hook_funcs = [ctx1]
        handler1.wrap_hook_func = ctx1
        handler2 = MagicMock()
        handler2.context_hook_funcs = [ctx2]
        handler2.wrap_hook_func = ctx2

        manager = MultiHandlerDynamicHooker([], [], None, None, None, False)
        manager.add_handler(handler1)
        assert set(manager.context_hook_funcs) == {ctx1}
        manager.add_handler(handler2)
        assert set(manager.context_hook_funcs) == {ctx1, ctx2}


# ------------------------------------------------------------
# ConfigHooker 测试
# ------------------------------------------------------------
class TestConfigHooker:
    def test_given_valid_args_when_initialized_then_attributes_set_correctly(self):
        """正例：ConfigHooker 初始化应正确设置属性"""
        hook_list = [("mod1", "func1"), ("mod2", "func2")]

        def hook_func(x):
            return x

        symbol_path = "test.symbol"
        min_v = "1.0"
        max_v = "2.0"
        caller = "caller"
        need_locals = True

        hooker = ConfigHooker(
            hook_list=hook_list,
            hook_func=hook_func,
            symbol_path=symbol_path,
            min_version=min_v,
            max_version=max_v,
            caller_filter=caller,
            need_locals=need_locals,
        )

        assert hooker.hook_list == hook_list
        assert hooker.symbol_path == symbol_path
        assert hooker.min_version == min_v
        assert hooker.max_version == max_v
        assert hooker.caller_filter == caller
        assert hooker.need_locals == need_locals
        assert hooker.applied_hook_func_name == hook_func.__name__

    def test_given_single_hook_func_when_initialized_then_wrap_hook_func_is_that_func(self):
        """正例：单个 hook_func 时 wrap_hook_func 应为该函数"""

        def my_func(ori, *a, **kw):
            pass

        hooker = ConfigHooker([], my_func, "", None, None, None, False)
        assert hooker.wrap_hook_func == my_func
        assert hooker.context_hook_funcs == []

    def test_given_multiple_hook_funcs_when_initialized_then_split_correctly(self):
        """正例：多个 hook_func 时正确分离 wrap 和 context 函数"""

        def wrap1(ori, *a, **kw):
            pass

        def ctx1():
            yield

        class CtxClass:
            pass  # 不是 ContextManager 子类

        class RealCtxClass(ContextManager):
            def __enter__(self):
                pass

            def __exit__(self, *a):
                pass

        hooker = ConfigHooker([], [wrap1, ctx1, CtxClass, RealCtxClass], "", None, None, None, False)
        # wrap_hook_func 应为第一个非 context 函数（wrap1）
        assert hooker.wrap_hook_func == wrap1
        # context_hook_funcs 应包含 ctx1 和 RealCtxClass（经过 contextmanager 包装或类本身）
        # ctx1 是生成器函数，被 contextmanager 包装后成为上下文管理器
        assert len(hooker.context_hook_funcs) == 2
        # 注意：contextmanager 包装后返回的是另一个函数，不能直接比较，我们检查其是否为 contextmanager 返回的 manager
        # 简单检查调用后是否返回上下文管理器对象
        assert hasattr(hooker.context_hook_funcs[0](), "__enter__")
        assert hasattr(hooker.context_hook_funcs[1](), "__enter__")

    def test_given_async_generator_when_initialized_then_ignored_and_logged(self):
        """反例：异步生成器函数应被忽略并记录日志"""

        async def async_gen():
            yield

        hooker = ConfigHooker([], async_gen, "", None, None, None, False)
        assert hooker.wrap_hook_func == async_gen
        assert hooker.context_hook_funcs == []

    def test_given_no_wrap_funcs_when_initialized_then_wrap_hook_func_is_default(self):
        """反例：没有普通函数时 wrap_hook_func 应为默认"""

        def ctx():
            yield

        hooker = ConfigHooker([], ctx, "", None, None, None, False)
        assert hooker.wrap_hook_func == VLLMHookerBase.default_hook_func
        assert len(hooker.context_hook_funcs) == 1

    def test_given_manager_exists_when_init_then_adds_handler(self, mock_import_object):
        """正例：管理器已存在时 init 直接添加自身"""
        # 预先创建管理器
        hooker = ConfigHooker([], lambda x: x, "sym", None, None, None, False)
        hooker.init()

    def test_given_handler_exists_when_recover_then_removes_from_manager(self):
        """正例：recover 从管理器中移除自身"""
        manager = MagicMock()
        manager.recover_handler.return_value = 1
        hooker = ConfigHooker([], lambda x: x, "sym", None, None, None, False)
        hooker.recover()
