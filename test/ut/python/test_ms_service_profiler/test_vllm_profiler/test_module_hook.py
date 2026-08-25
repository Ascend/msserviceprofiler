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
# pylint: disable=no-member,redefined-outer-name

import sys
import asyncio
import types
from unittest.mock import patch, MagicMock
import pytest


from ms_service_profiler.patcher.core.module_hook import (
    import_object_from_string,
    HookHelper,
    VLLMHookerBase,
    TrackableOriginalFunc,
    patcher,
)
from ms_service_profiler.patcher.core.registry import get_hook_registry, clear_hook_registry


# Test module setup
@pytest.fixture
def cleanup_hook_registry():
    """Clear hook registry before each test"""
    clear_hook_registry()


def _install_fake_vllm_module(module_name, module):
    old_parent = sys.modules.get("vllm")
    if old_parent is None:
        parent = types.ModuleType("vllm")
        parent.__path__ = []
        sys.modules["vllm"] = parent
    sys.modules[module_name] = module
    return old_parent


def _cleanup_fake_vllm_module(module_name, old_parent):
    sys.modules.pop(module_name, None)
    if old_parent is None:
        sys.modules.pop("vllm", None)
    else:
        sys.modules["vllm"] = old_parent


# Test cases for import_object_from_string
def test_import_object_from_string_given_valid_path_when_importing_module_then_returns_object():
    """Test importing a valid module-level function"""
    module = types.ModuleType("vllm.fake_module")
    module.target = object()
    old_parent = _install_fake_vllm_module("vllm.fake_module", module)
    try:
        result = import_object_from_string("vllm.fake_module", "target")
    finally:
        _cleanup_fake_vllm_module("vllm.fake_module", old_parent)

    assert result == module.target


def test_import_object_from_string_given_nested_attribute_when_importing_then_returns_object():
    """Test importing nested attributes"""
    module = types.ModuleType("vllm.fake_nested")

    class Target:
        value = "nested"

    module.Target = Target
    old_parent = _install_fake_vllm_module("vllm.fake_nested", module)
    try:
        result = import_object_from_string("vllm.fake_nested", "Target.value")
    finally:
        _cleanup_fake_vllm_module("vllm.fake_nested", old_parent)

    assert result == "nested"


def test_import_object_from_string_given_invalid_module_when_importing_then_returns_none():
    """Test handling of non-existent module"""
    result = import_object_from_string("vllm.nonexistent_module", "anything")
    assert result is None


def test_import_object_from_string_given_invalid_attribute_when_importing_then_returns_none():
    """Test handling of non-existent attribute"""
    module = types.ModuleType("vllm.fake_missing_attr")
    old_parent = _install_fake_vllm_module("vllm.fake_missing_attr", module)
    try:
        result = import_object_from_string("vllm.fake_missing_attr", "nonexistent_attr")
    finally:
        _cleanup_fake_vllm_module("vllm.fake_missing_attr", old_parent)
    assert result is None


def test_import_object_from_string_given_disallowed_module_when_importing_then_returns_none():
    """Test that non allow-listed symbol modules are rejected before import"""
    with patch("importlib.import_module") as mock_import:
        result = import_object_from_string("evil.module", "Payload.run")

    assert result is None
    mock_import.assert_not_called()


def test_import_object_from_string_given_empty_path_when_importing_then_returns_none():
    """Test handling of empty path"""
    result = import_object_from_string("", "")
    assert result is None


# Test cases for HookHelper
class SampleClass:
    @staticmethod
    def static_method():
        return "original static"

    @classmethod
    def class_method(cls):
        return "original class"

    def instance_method(self):
        return "original instance"


def sample_function():
    return "original function"


def test_hookhelper_get_location_given_function_when_getting_location_then_returns_correct_info():
    """Test getting location info for regular function"""
    location, attr_name = HookHelper.get_location(sample_function)
    assert attr_name == "sample_function"
    assert location.__name__.split(".")[-1] == "test_module_hook"


def test_hookhelper_get_location_given_class_method_when_getting_location_then_returns_correct_info():
    """Test getting location info for class method"""
    location, attr_name = HookHelper.get_location(SampleClass.instance_method)
    assert attr_name == "instance_method"
    assert location.__name__ == "SampleClass"


def test_hookhelper_get_location_given_hook_chain_closure_when_getting_location_then_unwraps_original():
    """Test resolving ms_service_metric HookChain closure back to the original function."""

    def execute_hook_chain():
        return "wrapped"

    execute_hook_chain.__module__ = sample_function.__module__
    execute_hook_chain.__qualname__ = "HookChain.exec_chain_closure.<locals>.execute_hook_chain"

    class FakeChain:
        ori_func = sample_function

    execute_hook_chain._hook_chain = FakeChain()

    location, attr_name = HookHelper.get_location(execute_hook_chain)
    assert attr_name == "sample_function"
    assert location.__name__.split(".")[-1] == "test_module_hook"


def test_hookhelper_replace_given_function_when_replacing_then_successful():
    """Test function replacement"""
    original = sample_function

    def new_func():
        return "new function"

    helper = HookHelper(original, new_func)
    helper.replace()
    assert sample_function() == "new function"
    helper.recover()


def test_hookhelper_replace_given_static_method_when_replacing_then_successful():
    """Test static method replacement"""
    original = SampleClass.static_method

    def new_func():
        return "new static"

    helper = HookHelper(original, new_func)
    helper.replace()
    assert SampleClass.static_method() == "new static"
    helper.recover()


def test_hookhelper_replace_given_non_callable_when_initializing_then_raises_error():
    """Test handling of non-callable replacement"""
    with pytest.raises(ValueError):
        HookHelper("not a function", lambda x: x)


# Test cases for VLLMHookerBase
class FakeHooker(VLLMHookerBase):
    def init(self):
        def profiler_maker(ori_func):
            return lambda *args, **kwargs: "profiled:" + ori_func(*args, **kwargs)

        self.do_hook([sample_function], profiler_maker)


def test_vllmhookerbase_support_version_given_version_in_range_when_checking_then_returns_true():
    """Test version support within range"""
    hooker = FakeHooker()
    hooker.vllm_version = ("1.0.0", "2.0.0")
    assert hooker.support_version("1.5.0")


def test_vllmhookerbase_support_version_given_version_out_of_range_when_checking_then_returns_false():
    """Test version support outside range"""
    hooker = FakeHooker()
    hooker.vllm_version = ("1.0.0", "2.0.0")
    assert not hooker.support_version("3.0.0")


def test_vllmhookerbase_do_hook_given_hook_points_when_applying_then_functions_replaced(cleanup_hook_registry):
    """Test hook application"""
    hooker = FakeHooker()
    hooker.init()
    assert sample_function().startswith("profiled:")
    hooker.hooks[0].recover()


def test_vllmhookerbase_do_hook_given_around_hook_when_calling_then_wraps_target(cleanup_hook_registry):
    """The optional tracing layer surrounds the existing callable."""
    events = []

    def around_factory(next_func, original_func):
        def wrapper(*args, **kwargs):
            events.append(("enter", args))
            result = next_func(*args, **kwargs)
            events.append(("exit", result))
            return result

        return wrapper

    class AroundHooker(VLLMHookerBase):
        def init(self):
            self.around_hook_factory = around_factory
            self.do_hook([sample_function], lambda ori_func: ori_func)

    hooker = AroundHooker()
    hooker.init()
    try:
        assert sample_function() == "original function"
        assert events == [("enter", ()), ("exit", "original function")]
    finally:
        hooker.hooks[0].recover()


def test_vllmhookerbase_around_hook_does_not_retry_business_exception(cleanup_hook_registry):
    calls = []
    expected = RuntimeError("business failed")

    def business_function():
        calls.append("called")
        raise expected

    def around_factory(next_func, original_func):
        def wrapper(*args, **kwargs):
            return next_func(*args, **kwargs)

        return wrapper

    class ExceptionHooker(VLLMHookerBase):
        def init(self):
            return None

    hooker = ExceptionHooker()
    hooker.around_hook_factory = around_factory
    hooker.do_hook([business_function], lambda ori_func: ori_func)
    try:
        with pytest.raises(RuntimeError) as error:
            hooker.hooks[0].new_function()
        assert error.value is expected
        assert calls == ["called"]
    finally:
        hooker.hooks[0].recover()


# Test cases for vllm_hook decorator
@patcher(
    hook_points=[("patcher.core.module_hook", "sample_function")],
    min_version="1.0.0",
    max_version="2.0.0",
)
def sample_profiler(ori_func, *args, **kwargs):
    return "decorator:" + ori_func(*args, **kwargs)


# Additional edge case tests
def test_hookhelper_replace_given_missing_parent_class_when_replacing_then_raises_error():
    """Test handling of missing parent class during replacement"""

    class FakeFunc:
        __module__ = "builtins"
        __qualname__ = "NonExistentClass.method"

    with pytest.raises(ValueError):
        HookHelper(FakeFunc(), lambda x: x)


def test_import_object_from_string_given_malformed_path_when_importing_then_returns_none():
    """Test handling of malformed import path"""
    result = import_object_from_string("os.path", "join..split")
    assert result is None


def test_vllm_hook_given_empty_hook_points_when_registering_then_no_error(cleanup_hook_registry):
    """Test handling of empty hook points"""

    @patcher(hook_points=[])
    def empty_profiler(ori_func, *args, **kwargs):
        pass

    assert len(get_hook_registry()) == 1
    # Shouldn't raise when init is called
    get_hook_registry()[0].init()


def test_vllmhookerbase_do_hook_given_caller_filter_when_calling_then_filters_correctly():
    """Test caller filter functionality"""

    class FilterHooker(VLLMHookerBase):
        def init(self):
            def profiler_maker(ori_func):
                return lambda *args, **kwargs: "filtered"

            self.do_hook([sample_function], profiler_maker, pname="test_caller")

    def test_caller():
        return sample_function()

    hooker = FilterHooker()
    hooker.init()

    flag = {"match": False}

    def fake_get_parents_name(*args, **kwargs):
        return "test_caller" if flag["match"] else "non_match"

    with patch(
        "ms_service_profiler.patcher.core.module_hook.get_parents_name",
        side_effect=fake_get_parents_name,
    ):
        # When caller name does not match, the hook should be bypassed.
        assert sample_function() == "original function"

        # Flip the flag so that the next invocation reports the expected caller.
        flag["match"] = True
        assert test_caller() == "filtered"

    hooker.hooks[0].recover()


class TestHookFuncNotNeedLocals:
    """测试 VLLMHookerBase.hook_func_not_need_locals 方法。

    测试策略：
    - 正例：测试正常执行流程
    - 反例：测试异常处理流程
    - 测试同步和异步函数
    - 测试不同的包装函数类型
    """

    def test_given_sync_function_and_no_wrap_hook_when_call_wrapper_then_execute_context_hooks_and_original_function(
        self,
    ):
        """Given: 同步函数，使用默认的包装函数
        When: 调用生成的包装器
        Then: 应该按顺序执行 context hooks 的 enter 和 exit，并返回原函数结果
        """
        # Given
        mock_enter = MagicMock(return_value=None)
        mock_exit = MagicMock(return_value=None)

        # 创建 mock context hook 函数
        def create_context_hook(ctx):
            class ContextHook:
                def __enter__(self):
                    mock_enter()
                    return self

                def __exit__(self, *args):
                    mock_exit()

            return ContextHook()

        context_hook_funcs = [create_context_hook]

        # 原始函数
        def original_func(x, y):
            return x + y

        trackable_ori_func = TrackableOriginalFunc(original_func)

        # When
        wrapper = VLLMHookerBase.hook_func_not_need_locals(
            trackable_ori_func, original_func, context_hook_funcs, VLLMHookerBase.default_hook_func
        )

        result = wrapper(3, 5)

        # Then
        assert result == 8
        mock_enter.assert_called_once()
        mock_exit.assert_called_once()

    def test_given_sync_function_with_wrap_hook_when_call_wrapper_then_execute_context_hooks_and_wrap_hook(self):
        """Given: 同步函数，使用自定义的包装函数
        When: 调用生成的包装器
        Then: 应该按顺序执行 context hooks 的 enter 和 exit，并返回 wrap hook 结果
        """
        # Given
        mock_enter = MagicMock(return_value=None)
        mock_exit = MagicMock(return_value=None)
        mock_wrap_hook = MagicMock(return_value=100)

        def create_context_hook(ctx):
            class ContextHook:
                def __enter__(self):
                    mock_enter()
                    return self

                def __exit__(self, *args):
                    mock_exit()

            return ContextHook()

        context_hook_funcs = [create_context_hook]

        def original_func(x, y):
            return x + y

        trackable_ori_func = TrackableOriginalFunc(original_func)

        # When
        wrapper = VLLMHookerBase.hook_func_not_need_locals(
            trackable_ori_func, original_func, context_hook_funcs, mock_wrap_hook
        )

        result = wrapper(3, 5)

        # Then
        assert result == 100
        mock_enter.assert_called_once()
        mock_exit.assert_called_once()
        mock_wrap_hook.assert_called_once_with(trackable_ori_func, 3, 5)

    @pytest.mark.asyncio
    async def test_given_async_function_and_no_wrap_hook_when_call_wrapper_then_execute_context_hooks_and_original_function(
        self,
    ):
        """Given: 异步函数，使用默认的包装函数
        When: 调用生成的包装器
        Then: 应该按顺序执行 context hooks 的 enter 和 exit，并返回原函数结果
        """
        # Given
        mock_enter = MagicMock(return_value=None)
        mock_exit = MagicMock(return_value=None)

        def create_context_hook(ctx):
            class ContextHook:
                def __enter__(self):
                    mock_enter()
                    return self

                def __exit__(self, *args):
                    mock_exit()

            return ContextHook()

        context_hook_funcs = [create_context_hook]

        async def async_original_func(x, y):
            await asyncio.sleep(0.01)
            return x + y

        trackable_ori_func = TrackableOriginalFunc(async_original_func)

        # When
        wrapper = VLLMHookerBase.hook_func_not_need_locals(
            trackable_ori_func, async_original_func, context_hook_funcs, VLLMHookerBase.default_hook_func
        )

        result = await wrapper(3, 5)

        # Then
        assert result == 8
        mock_enter.assert_called_once()
        mock_exit.assert_called_once()

    @pytest.mark.asyncio
    async def test_given_async_function_with_wrap_hook_when_call_wrapper_then_execute_context_hooks_and_wrap_hook(self):
        """Given: 异步函数，使用自定义的包装函数
        When: 调用生成的包装器
        Then: 应该按顺序执行 context hooks 的 enter 和 exit，并返回 wrap hook 结果
        """
        # Given
        mock_enter = MagicMock(return_value=None)
        mock_exit = MagicMock(return_value=None)

        # 创建一个异步的 wrap hook 函数
        async def async_wrap_hook(trackable_func, *args, **kwargs):
            await asyncio.sleep(0.01)  # 模拟异步操作
            return 100

        def create_context_hook(ctx):
            class ContextHook:
                def __enter__(self):
                    mock_enter()
                    return self

                def __exit__(self, *args):
                    mock_exit()

            return ContextHook()

        context_hook_funcs = [create_context_hook]

        async def async_original_func(x, y):
            await asyncio.sleep(0.01)
            return x + y

        trackable_ori_func = TrackableOriginalFunc(async_original_func)

        # When
        wrapper = VLLMHookerBase.hook_func_not_need_locals(
            trackable_ori_func,
            async_original_func,
            context_hook_funcs,
            async_wrap_hook,  # 使用异步的 wrap hook 函数
        )

        result = await wrapper(3, 5)

        # Then
        assert result == 100
        mock_enter.assert_called_once()
        mock_exit.assert_called_once()

    def test_given_multiple_context_hooks_when_call_wrapper_then_execute_all_hooks_in_order(self):
        """Given: 多个 context hook 函数
        When: 调用生成的包装器
        Then: 应该按顺序执行所有 context hooks 的 enter 和 exit
        """
        # Given
        execution_order = []

        def create_context_hook(name):
            def hook_factory(ctx):
                class ContextHook:
                    def __enter__(self):
                        execution_order.append(f"{name}_enter")
                        return self

                    def __exit__(self, *args):
                        execution_order.append(f"{name}_exit")

                return ContextHook()

            return hook_factory

        context_hook_funcs = [create_context_hook("hook1"), create_context_hook("hook2"), create_context_hook("hook3")]

        def original_func():
            execution_order.append("original")
            return "done"

        trackable_ori_func = TrackableOriginalFunc(original_func)

        # When
        wrapper = VLLMHookerBase.hook_func_not_need_locals(
            trackable_ori_func, original_func, context_hook_funcs, VLLMHookerBase.default_hook_func
        )

        result = wrapper()

        # Then
        assert result == "done"
        assert execution_order == [
            "hook1_enter",
            "hook2_enter",
            "hook3_enter",
            "original",
            "hook3_exit",
            "hook2_exit",
            "hook1_exit",
        ]

    def test_given_context_hook_enter_throws_exception_when_call_wrapper_then_log_error_and_increment_failure_counter(
        self,
    ):
        """Given: context hook 的 __enter__ 方法抛出异常
        When: 调用生成的包装器
        Then: 应该记录错误，增加失败计数，但仍然执行后续操作
        """

        # Given
        def create_failing_hook():
            class FailingHook:
                def __enter__(self):
                    raise ValueError("Enter failed")

                def __exit__(self, *args):
                    pass

            def failing_hook(ctx):
                return FailingHook()

            return failing_hook

        def create_normal_hook():
            mock_enter = MagicMock()

            class NormalHook:
                def __enter__(self):
                    mock_enter()
                    return self

                def __exit__(self, *args):
                    pass

            def normal_hook(ctx):
                return NormalHook()

            return normal_hook

        context_hook_funcs = [create_failing_hook(), create_normal_hook()]

        def original_func():
            return 42

        trackable_ori_func = TrackableOriginalFunc(original_func)

        # When
        with patch('ms_service_profiler.patcher.core.module_hook.logger') as mock_logger:
            wrapper = VLLMHookerBase.hook_func_not_need_locals(
                trackable_ori_func, original_func, context_hook_funcs, VLLMHookerBase.default_hook_func
            )

            result = wrapper()

        # Then
        assert result == 42
        mock_logger.error.assert_called_once()
        assert "function enter failed" in mock_logger.error.call_args[0][0]
