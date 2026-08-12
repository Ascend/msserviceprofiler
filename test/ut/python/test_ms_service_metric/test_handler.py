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

    def test_given_same_handler_with_distinct_metrics_then_internal_ids_differ(self):
        first = MetricHandler.from_config(
            {
                "handler": "ms_service_metric.handlers:default_handler",
                "metrics": [{"name": "first_metric"}],
            },
            "module:func",
        )
        second = MetricHandler.from_config(
            {
                "handler": "ms_service_metric.handlers:default_handler",
                "metrics": [{"name": "second_metric"}],
            },
            "module:func",
        )

        assert first.id != second.id

    def test_given_same_config_with_different_key_order_then_internal_ids_match(self):
        first = MetricHandler.from_config(
            {
                "handler": "ms_service_metric.handlers:default_handler",
                "metrics": [{"name": "metric", "type": "counter"}],
            },
            "module:func",
        )
        second = MetricHandler.from_config(
            {
                "metrics": [{"type": "counter", "name": "metric"}],
                "handler": "ms_service_metric.handlers:default_handler",
            },
            "module:func",
        )

        assert first.id == second.id

    def test_given_equivalent_explicit_defaults_then_internal_ids_match(self):
        implicit = MetricHandler.from_config(
            {"metrics": [{"name": "duration"}]},
            "module:func",
        )
        explicit = MetricHandler.from_config(
            {
                "handler": "ms_service_metric.handlers:default_handler",
                "type": "wrap",
                "enabled": True,
                "need_locals": False,
                "lock_patch": False,
                "metrics": [
                    {
                        "name": "duration",
                        "type": "timer",
                        "expr": "ignored-for-timer",
                        "labels": [],
                    }
                ],
            },
            "module:func",
        )

        assert implicit.id == explicit.id

    def test_given_explicit_effective_name_when_fingerprinted_then_matches_implicit_name(self):
        handler_path = "ms_service_metric.handlers:default_handler"
        implicit = MetricHandler.from_config(
            {
                "handler": handler_path,
                "metrics": [{"name": "duration"}],
            },
            "module:func",
        )
        explicit = MetricHandler.from_config(
            {
                "name": handler_path,
                "handler": handler_path,
                "metrics": [{"name": "duration"}],
            },
            "module:func",
        )

        assert implicit.id == explicit.id


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


def test_given_external_handler_root_when_from_config_then_loads_handler_without_sys_path_change(
    tmp_path,
):
    handler_file = tmp_path / "custom_handler.py"
    handler_file.write_text(
        "def record(ctx):\n    yield\n",
        encoding="utf-8",
    )
    original_sys_path = list(__import__("sys").path)

    handler = MetricHandler.from_config(
        {"handler": "custom_handler:record"},
        "module:func",
        user_handler_root=str(tmp_path),
    )

    assert handler._hook_func.__name__ == "record"
    assert __import__("sys").path == original_sys_path


def test_given_nested_external_handler_when_from_config_then_maps_dotted_module_to_file(
    tmp_path,
):
    nested = tmp_path / "custom" / "handlers.py"
    nested.parent.mkdir()
    nested.write_text("def record(ctx):\n    yield\n", encoding="utf-8")

    handler = MetricHandler.from_config(
        {"handler": "custom.handlers:record"},
        "module:func",
        user_handler_root=str(tmp_path),
    )

    assert handler._hook_func.__name__ == "record"


@pytest.mark.parametrize(
    "handler_path",
    [
        "../outside:record",
        "custom/handler:record",
        ".custom:record",
    ],
)
def test_given_unsafe_external_module_path_when_import_then_rejects(
    tmp_path,
    handler_path,
):
    with pytest.raises(HandlerError, match="Invalid external Handler module path"):
        MetricHandler._import_handler(
            handler_path,
            user_handler_root=str(tmp_path),
        )


def test_given_missing_external_handler_function_when_import_then_raises(tmp_path):
    (tmp_path / "custom.py").write_text("VALUE = 1\n", encoding="utf-8")

    with pytest.raises(HandlerError, match="function not found"):
        MetricHandler._import_handler(
            "custom:record",
            user_handler_root=str(tmp_path),
        )


def test_given_failed_external_module_load_when_file_fixed_then_retry_succeeds(tmp_path):
    handler_file = tmp_path / "custom.py"
    handler_file.write_text("raise RuntimeError('broken')\n", encoding="utf-8")

    with pytest.raises(HandlerError, match="Failed to load external Handler module"):
        MetricHandler._import_handler(
            "custom:record",
            user_handler_root=str(tmp_path),
        )

    handler_file.write_text("def record(ctx):\n    yield\n", encoding="utf-8")
    handler = MetricHandler._import_handler(
        "custom:record",
        user_handler_root=str(tmp_path),
    )
    assert handler.__name__ == "record"


def test_given_missing_external_handler_root_when_import_then_raises(tmp_path):
    with pytest.raises(HandlerError, match="root does not exist"):
        MetricHandler._import_handler(
            "custom:record",
            user_handler_root=str(tmp_path / "missing"),
        )


def test_given_external_handler_symlink_escape_when_import_then_rejects(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}_outside.py"
    outside.write_text("def record(ctx):\n    yield\n", encoding="utf-8")
    link = tmp_path / "linked.py"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Creating file symlinks is not permitted on this platform")

    with pytest.raises(HandlerError, match="not found under configured root"):
        MetricHandler._import_handler(
            "linked:record",
            user_handler_root=str(tmp_path),
        )


def test_given_different_external_roots_when_build_handlers_then_ids_are_distinct(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    for root in (first, second):
        (root / "custom.py").write_text("def record(ctx):\n    yield\n", encoding="utf-8")

    first_handler = MetricHandler.from_config(
        {"handler": "custom:record"},
        "module:func",
        user_handler_root=str(first),
    )
    second_handler = MetricHandler.from_config(
        {"handler": "custom:record"},
        "module:func",
        user_handler_root=str(second),
    )

    assert first_handler.id != second_handler.id


def test_given_empty_config_when_from_config_then_uses_default_handler():
    config = {}
    handler = MetricHandler.from_config(config, "module:func")
    assert handler is not None
