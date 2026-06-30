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

import pytest

pytest.importorskip("ms_service_metric.core.symbol")
pytest.importorskip("ms_service_metric.metrics.metrics_manager")

from ms_service_metric.core.handler import HandlerType, MetricHandler
from ms_service_metric.utils.exceptions import HandlerError


def sample_wrap_handler(ori_func, *args, **kwargs):
    return ori_func(*args, **kwargs)


def sample_context_handler(ctx):
    yield


def sample_context_with_locals(ctx, local_values):
    yield


class TestMetricHandlerGivenWrapFunction:
    def test_given_wrap_callable_when_get_hook_then_type_is_wrap(self):
        symbol_info = {"symbol_path": "module:func"}
        handler = MetricHandler("test", symbol_info, sample_wrap_handler)
        hook_type, _ = handler.get_hook_func(lambda: None)
        assert hook_type == HandlerType.WRAP

    def test_given_wrap_callable_when_constructed_then_id_is_non_empty(self):
        symbol_info = {"symbol_path": "module:func"}
        handler = MetricHandler("test", symbol_info, sample_wrap_handler)
        assert handler.id is not None
        assert len(handler.id) > 0


class TestMetricHandlerGivenContextFunction:
    def test_given_single_arg_context_generator_when_get_hook_then_type_is_context(self):
        symbol_info = {"symbol_path": "module:func"}
        handler = MetricHandler("test", symbol_info, sample_context_handler)
        hook_type, _ = handler.get_hook_func(lambda: None)
        assert hook_type == HandlerType.CONTEXT

    def test_given_context_generator_with_locals_param_when_get_hook_then_type_is_context(self):
        symbol_info = {"symbol_path": "module:func"}
        handler = MetricHandler("test", symbol_info, sample_context_with_locals)
        hook_type, _ = handler.get_hook_func(lambda: None)
        assert hook_type == HandlerType.CONTEXT


class TestMetricHandlerGivenInvalidInput:
    def test_given_none_handler_callable_when_get_hook_then_fallback_wrap_type_with_callable(self):
        symbol_info = {"symbol_path": "module:func"}
        handler = MetricHandler("test", symbol_info, None)
        hook_type, hook_func = handler.get_hook_func(lambda: None)
        assert hook_type == HandlerType.WRAP
        assert callable(hook_func)


class TestMetricHandlerProperties:
    def test_given_named_handler_when_access_name_then_returns_configured(self):
        symbol_info = {"symbol_path": "module:func"}
        handler = MetricHandler("test_name", symbol_info, sample_wrap_handler)
        assert handler.name == "test_name"

    def test_given_symbol_info_when_access_symbol_path_then_returns_path(self):
        symbol_info = {"symbol_path": "module:Class.method"}
        handler = MetricHandler("test", symbol_info, sample_wrap_handler)
        assert handler.symbol_path == "module:Class.method"

    def test_given_min_version_kwarg_when_access_min_version_then_returns_value(self):
        symbol_info = {"symbol_path": "module:func"}
        handler = MetricHandler("test", symbol_info, sample_wrap_handler, min_version="1.0.0")
        assert handler.min_version == "1.0.0"

    def test_given_max_version_kwarg_when_access_max_version_then_returns_value(self):
        symbol_info = {"symbol_path": "module:func"}
        handler = MetricHandler("test", symbol_info, sample_wrap_handler, max_version="2.0.0")
        assert handler.max_version == "2.0.0"


class TestMetricHandlerEquality:
    def test_given_same_hook_callable_different_symbols_when_eq_then_not_equal_and_distinct_hash(self):
        symbol_info1 = {"symbol_path": "module:func1"}
        symbol_info2 = {"symbol_path": "module:func2"}
        handler1 = MetricHandler("test", symbol_info1, sample_wrap_handler)
        handler2 = MetricHandler("test", symbol_info2, sample_wrap_handler)
        assert handler1 != handler2
        assert hash(handler1) != hash(handler2)
        assert handler1.id != handler2.id


class TestMetricHandlerFromConfig:
    def test_given_minimal_handler_config_when_from_config_then_instance_has_name(self):
        config = {"handler": "ms_service_metric.handlers:default_handler"}
        handler = MetricHandler.from_config(config, "module:func")
        assert handler is not None
        assert handler.name is not None

    def test_given_config_with_metrics_list_when_from_config_then_one_metric_config(self):
        config = {
            "handler": "ms_service_metric.handlers:default_handler",
            "name": "test_handler",
            "metrics": [{"name": "test_metric", "type": "counter"}],
        }
        handler = MetricHandler.from_config(config, "module:func")
        assert handler is not None
        assert len(handler.metrics_config) == 1


def test_given_invalid_symbol_path_none_when_constructed_then_symbol_path_is_none():
    symbol_info = {"symbol_path": None}
    handler = MetricHandler("test", symbol_info, sample_wrap_handler)
    assert handler.symbol_path is None


def test_given_empty_symbol_info_when_constructed_then_symbol_path_is_none():
    symbol_info = {}
    handler = MetricHandler("test", symbol_info, sample_wrap_handler)
    assert handler.symbol_path is None


def test_given_lock_patch_true_when_constructed_then_lock_patch_is_true():
    symbol_info = {"symbol_path": "module:func"}
    handler = MetricHandler("test", symbol_info, sample_wrap_handler, lock_patch=True)
    assert handler.lock_patch is True


def test_given_lock_patch_false_when_constructed_then_lock_patch_is_false():
    symbol_info = {"symbol_path": "module:func"}
    handler = MetricHandler("test", symbol_info, sample_wrap_handler, lock_patch=False)
    assert handler.lock_patch is False


def test_given_invalid_handler_path_when_from_config_then_raises_handler_error():
    config = {"handler": "invalid_module:invalid_func"}
    with pytest.raises(HandlerError):
        MetricHandler.from_config(config, "module:func")


def test_given_disallowed_handler_module_when_import_then_raises_handler_error():
    with pytest.raises(HandlerError, match="not allowed"):
        MetricHandler._import_handler("evil.module:payload")


def test_given_empty_config_when_from_config_then_uses_default_handler():
    config = {}
    handler = MetricHandler.from_config(config, "module:func")
    assert handler is not None
