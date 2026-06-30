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
# pylint: disable=no-member,unspecified-encoding,attribute-defined-outside-init

import importlib
import os
import shutil
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from ms_service_profiler.patcher.core.config_loader import (
    _parse_symbol_path,
    _build_hook_points,
    _resolve_handler_func,
    _resolve_metrics_handler_func,
    _is_pattern_symbol,
    _parse_symbol_pattern,
    ConfigLoader,
    ProfilingConfig,
    MetricsConfig,
)


class TestParseSymbolPath:
    """测试_parse_symbol_path函数"""

    @pytest.mark.parametrize(
        "symbol_path,expected",
        [
            ("my_module.path:MyClass.my_method", ("my_module.path", "my_method", "MyClass")),
            ("my_module.path:my_function", ("my_module.path", "my_function", None)),
            ("module.path.ClassName.methodName", ("", "", None)),
            ("", ("", "", None)),
            ("my_module.path:MyClass.method.name.with.dots", ("my_module.path", "method.name.with.dots", "MyClass")),
        ],
    )
    def test_parse_symbol_path(self, symbol_path, expected):
        assert _parse_symbol_path(symbol_path) == expected


class TestBuildHookPoints:
    """测试_build_hook_points函数"""

    @pytest.mark.parametrize(
        "module_path,method_name,class_name,expected",
        [
            ("my_module.path", "my_method", "MyClass", [("my_module.path", "MyClass.my_method")]),
            ("my_module.path", "my_function", None, [("my_module.path", "my_function")]),
            ("", "", None, [("", "")]),
        ],
    )
    def test_build_hook_points(self, module_path, method_name, class_name, expected):
        assert _build_hook_points(module_path, method_name, class_name) == expected


class TestIsPatternSymbol:
    """测试 _is_pattern_symbol 函数"""

    @pytest.mark.parametrize(
        "symbol_path,expected",
        [
            ("vllm.model_executor.models.*:*.embed_multimodal", True),
            ("module.path:ClassName.method_name", False),
            ("module.*:*.foo", True),
            ("", False),
        ],
    )
    def test_is_pattern_symbol(self, symbol_path, expected):
        assert _is_pattern_symbol(symbol_path) == expected

    def test_is_pattern_symbol_non_string_returns_false(self):
        assert _is_pattern_symbol(123) is False


class TestParseSymbolPattern:
    """测试 _parse_symbol_pattern 函数"""

    def test_parse_pattern_valid_class_method(self):
        r = _parse_symbol_pattern("vllm.model_executor.models.*:*.embed_multimodal")
        assert r == ("vllm.model_executor.models.*", "*", "embed_multimodal")

    def test_parse_pattern_valid_class_dot_method(self):
        r = _parse_symbol_pattern("pkg.mod:Cls.method")
        assert r == ("pkg.mod", "Cls", "method")

    def test_parse_pattern_no_dot_in_rest_returns_none(self):
        with patch("ms_service_profiler.patcher.core.config_loader.logger"):
            assert _parse_symbol_pattern("some.module:func_name") is None

    @pytest.mark.parametrize(
        "symbol_path",
        [
            "no_colon",
            "module:*",
        ],
    )
    def test_parse_pattern_invalid_returns_none(self, symbol_path):
        with patch("ms_service_profiler.patcher.core.config_loader.logger"):
            assert _parse_symbol_pattern(symbol_path) is None

    def test_parse_pattern_method_contains_star_returns_none(self):
        """method_name 中不允许含 *"""
        with patch("ms_service_profiler.patcher.core.config_loader.logger"):
            assert _parse_symbol_pattern("mod:Cls.method_*") is None


class TestResolveHandlerFunc:
    """测试_resolve_handler_func函数"""

    def test_resolve_handler_func_import_success_returns_handler(self):
        mock_module = MagicMock()
        mock_handler = MagicMock()
        mock_module.my_handler = mock_handler
        with patch("importlib.import_module", return_value=mock_module):
            result = _resolve_handler_func({"handler": "ms_service_profiler.handlers:my_handler"}, "my_method")
            assert result == mock_handler
            importlib.import_module.assert_called_once_with("ms_service_profiler.handlers")

    def test_resolve_handler_func_import_fails_returns_default(self):
        # make_default_time_hook 必须先 patch（外层），否则 patch 字符串目标解析会调用
        # 已被 mock 的 importlib.import_module 而失败
        with patch("ms_service_profiler.patcher.core.config_loader.make_default_time_hook") as m:
            default_h = MagicMock()
            m.return_value = default_h
            with patch("importlib.import_module", side_effect=ImportError("No module")):
                result = _resolve_handler_func(
                    {"handler": "x:y", "domain": "TestDomain", "name": "custom_name"}, "my_method"
                )
                assert result == default_h
                m.assert_called_once_with(domain="TestDomain", name="custom_name", attributes=None)

    def test_resolve_handler_func_not_callable_returns_default(self):
        mock_module = MagicMock()
        mock_module.my_handler = "not_a_function"
        with patch("ms_service_profiler.patcher.core.config_loader.make_default_time_hook") as m:
            default_h = MagicMock()
            m.return_value = default_h
            with patch("importlib.import_module", return_value=mock_module):
                result = _resolve_handler_func(
                    {"handler": "ms_service_profiler.handlers:my_handler", "domain": "TestDomain"}, "my_method"
                )
                assert result == default_h
                m.assert_called_once_with(domain="TestDomain", name="my_method", attributes=None)

    def test_resolve_handler_func_disallowed_module_returns_default(self):
        with patch("ms_service_profiler.patcher.core.config_loader.make_default_time_hook") as m:
            default_h = MagicMock()
            m.return_value = default_h
            with patch("importlib.import_module") as mock_import:
                result = _resolve_handler_func({"handler": "evil.module:payload", "domain": "TestDomain"}, "my_method")
                assert result == default_h
                mock_import.assert_not_called()
                m.assert_called_once_with(domain="TestDomain", name="my_method", attributes=None)

    def test_resolve_handler_func_no_handler_returns_default(self):
        with patch("ms_service_profiler.patcher.core.config_loader.make_default_time_hook") as m:
            default_h = MagicMock()
            m.return_value = default_h
            result = _resolve_handler_func(
                {"domain": "TestDomain", "name": "test_name", "attributes": {"attr1": "value1"}}, "my_method"
            )
            assert result == default_h
            m.assert_called_once_with(domain="TestDomain", name="test_name", attributes={"attr1": "value1"})

    def test_resolve_handler_func_invalid_format_returns_default(self):
        with patch("ms_service_profiler.patcher.core.config_loader.make_default_time_hook") as m:
            default_h = MagicMock()
            m.return_value = default_h
            result = _resolve_handler_func(
                {"handler": "invalid_format_without_colon", "domain": "TestDomain"}, "my_method"
            )
            assert result == default_h
            m.assert_called_once_with(domain="TestDomain", name="my_method", attributes=None)


class TestConfigLoader:
    """测试ConfigLoader类"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.yaml")
        self.loader = ConfigLoader(self.config_path)

    def teardown_method(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_test_config(self, content):
        with open(self.config_path, 'w') as f:
            f.write(content)

    def test_config_loader_init_stores_path(self):
        loader = ConfigLoader("/path/to/config.yaml")
        assert loader._config_path == "/path/to/config.yaml"

    def test_load_valid_yaml_returns_handler_dict(self):
        self._create_test_config("- symbol: a\n  domain: D\n")
        raw = [
            {
                "symbol": "module.path:ClassName.method_name",
                "domain": "TestDomain",
                "name": "test_name",
                "min_version": "1.0.0",
                "max_version": "2.0.0",
                "attributes": {"attr1": "value1", "attr2": "value2"},
            },
            {"symbol": "another.module:function_name", "handler": "custom.handlers:my_handler"},
        ]
        with patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config", return_value=raw):
            with patch("ms_service_profiler.patcher.core.config_loader.ConfigHooker") as MockDH:
                h1, h2 = MagicMock(), MagicMock()
                MockDH.side_effect = [h1, h2]
                result = self.loader.load_profiling()
        assert isinstance(result, ProfilingConfig)
        assert result.concrete["module.path:ClassName.method_name"] == [h1]
        assert result.concrete["another.module:function_name"] == [h2]

    def test_load_multiple_handlers_same_symbol_returns_all(self):
        self._create_test_config("")
        with patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config") as mock_yaml:
            mock_yaml.return_value = [
                {"symbol": "module.path:ClassName.method_name", "domain": "FirstHandler"},
                {"symbol": "module.path:ClassName.method_name", "domain": "SecondHandler"},
            ]
            with patch("ms_service_profiler.patcher.core.config_loader.ConfigHooker") as MockDH:
                h1, h2 = MagicMock(), MagicMock()
                MockDH.side_effect = [h1, h2]
                result = self.loader.load_profiling()
        assert result.concrete["module.path:ClassName.method_name"] == [h1, h2]

    @pytest.mark.parametrize("yaml_return", [[], None, {"key": "value"}])
    def test_load_empty_or_invalid_returns_empty_dict(self, yaml_return):
        with patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config", return_value=yaml_return):
            result = self.loader.load_profiling()
            assert isinstance(result, ProfilingConfig)
            assert not result.concrete and not result.patterns

    @pytest.mark.parametrize(
        "raw_config",
        [
            [
                {"domain": "TestDomain", "name": "test"},
                {"symbol": "module.path:ClassName.method_name", "domain": "Valid"},
            ],
            [
                {"symbol": "invalid_format_without_colon"},
                {"symbol": "module.path:ClassName.method_name", "domain": "Valid"},
            ],
        ],
    )
    def test_load_skips_invalid_items(self, raw_config):
        with patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config", return_value=raw_config):
            with patch("ms_service_profiler.patcher.core.config_loader.ConfigHooker") as MockDH:
                MockDH.return_value = MagicMock()
                result = self.loader.load_profiling()
        assert len(result.concrete) == 1
        assert "module.path:ClassName.method_name" in result.concrete

    def test_load_real_yaml_parses_correctly(self):
        self._create_test_config(
            '- symbol: "sglang.srt.managers.scheduler:Scheduler.get_next_batch_to_run"\n  domain: "Schedule"\n'
            '- symbol: "sglang.srt.managers.scheduler:Scheduler.run_batch"\n  domain: "ModelExecute"\n'
        )
        with patch("ms_service_profiler.patcher.core.config_loader.ConfigHooker") as MockDH:
            h1, h2 = MagicMock(), MagicMock()
            MockDH.side_effect = [h1, h2]
            result = self.loader.load_profiling()
        assert len(result.concrete) == 2
        assert "sglang.srt.managers.scheduler:Scheduler.get_next_batch_to_run" in result.concrete
        assert "sglang.srt.managers.scheduler:Scheduler.run_batch" in result.concrete

    def test_load_logs_debug(self):
        with patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config") as mock_yaml:
            mock_yaml.return_value = [{"symbol": "module.path:ClassName.method_name", "domain": "TestDomain"}]
            with patch("ms_service_profiler.patcher.core.config_loader.ConfigHooker"):
                with patch("ms_service_profiler.patcher.core.config_loader.logger") as mock_logger:
                    self.loader.load_profiling()
                    mock_logger.debug.assert_called()
                    assert self.config_path in mock_logger.debug.call_args[0][0]

    def test_load_profiling_with_pattern_symbol_returns_patterns(self):
        """含模式 symbol 的配置应解析出 patterns 列表"""
        raw = [
            {"symbol": "vllm.model_executor.models.*:*.embed_multimodal", "name": "multimodalEmbedding", "domain": "M"},
        ]
        with patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config", return_value=raw):
            with patch("ms_service_profiler.patcher.core.config_loader.make_default_time_hook") as m:
                m.return_value = MagicMock()
                result = self.loader.load_profiling()
        assert isinstance(result, ProfilingConfig)
        assert len(result.patterns) == 1
        assert result.patterns[0].module_pattern == "vllm.model_executor.models.*"
        assert result.patterns[0].method_name == "embed_multimodal"
        assert result.patterns[0].pattern_id == "vllm.model_executor.models.*:*.embed_multimodal"


class TestProfilingConfigMetricsConfigMerge:
    """测试 ProfilingConfig.merge / MetricsConfig.merge"""

    def test_profiling_config_merge(self):
        h1, h2 = MagicMock(), MagicMock()
        c1 = ProfilingConfig(concrete={"a": [h1]}, patterns=[])
        c2 = ProfilingConfig(concrete={"b": [h2], "a": [h2]}, patterns=[])
        merged = ProfilingConfig.merge(c1, c2)
        assert merged.concrete["a"] == [h1, h2]
        assert merged.concrete["b"] == [h2]

    def test_metrics_config_merge(self):
        h = MagicMock()
        c1 = MetricsConfig(concrete={"x": [h]}, patterns=[])
        c2 = None
        merged = MetricsConfig.merge(c1, c2)
        assert merged.concrete["x"] == [h]


class TestResolveMetricsHandlerFunc:
    """测试 _resolve_metrics_handler_func 函数"""

    def test_resolve_metrics_handler_func_with_handler_path_returns_imported_func(self):
        """有 handler 且为 module:func 时直接导入并返回该函数（不包装）"""
        with patch("ms_service_profiler.patcher.core.config_loader.importlib.import_module") as mock_import:
            imported_func = MagicMock()
            mock_mod = MagicMock()
            mock_mod.my_func = imported_func
            mock_import.return_value = mock_mod
            symbol_info = {"handler": "ms_service_metric.handlers:my_func", "metrics": []}
            result = _resolve_metrics_handler_func(symbol_info, "my_method")
            mock_import.assert_called_once_with("ms_service_metric.handlers")
            assert result is imported_func

    def test_resolve_metrics_handler_func_disallowed_module_wraps_noop(self):
        # wrap_handler_with_metrics 必须先 patch（外层），避免其字符串目标解析被
        # 已 mock 的 importlib.import_module 干扰
        with patch("ms_service_profiler.patcher.core.config_loader.wrap_handler_with_metrics") as mock_wrap:
            wrapped = MagicMock()
            mock_wrap.return_value = wrapped
            with patch("ms_service_profiler.patcher.core.config_loader.importlib.import_module") as mock_import:
                result = _resolve_metrics_handler_func({"handler": "evil.module:payload", "metrics": []}, "my_method")
                mock_import.assert_not_called()
                mock_wrap.assert_called_once()
                assert mock_wrap.call_args[0][0].__name__ == "_metrics_noop_handler"
                assert result == wrapped

    def test_resolve_metrics_handler_func_no_handler_wraps_noop(self):
        """无 handler 时用 wrap_handler_with_metrics 封装透传函数"""
        with patch("ms_service_profiler.patcher.core.config_loader.wrap_handler_with_metrics") as mock_wrap:
            wrapped = MagicMock()
            mock_wrap.return_value = wrapped
            result = _resolve_metrics_handler_func({"domain": "D", "name": "n"}, "method")
            mock_wrap.assert_called_once()
            assert mock_wrap.call_args[0][0].__name__ == "_metrics_noop_handler"
            assert mock_wrap.call_args[0][1] == {"domain": "D", "name": "n"}
            assert result == wrapped


class TestConfigLoaderLoadMetrics:
    """测试 ConfigLoader.load_metrics 方法"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_metrics.yaml")
        self.loader = ConfigLoader(self.config_path)

    def teardown_method(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_load_metrics_valid_returns_handler_dict(self):
        """合法 metrics 列表配置返回 symbol -> Handler 列表"""
        raw = [
            {"symbol": "module.path:ClassName.method_name", "domain": "TestDomain"},
            {"symbol": "other.module:func", "metrics": [{"name": "m1", "type": "timer"}]},
        ]
        with patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config", return_value=raw):
            with patch("ms_service_profiler.patcher.core.config_loader.wrap_handler_with_metrics") as mock_wrap:
                mock_wrap.side_effect = lambda h, _: h
                with patch("ms_service_profiler.patcher.core.config_loader.ConfigHooker") as MockDH:
                    h1, h2 = MagicMock(), MagicMock()
                    MockDH.side_effect = [h1, h2]
                    result = self.loader.load_metrics()
        assert isinstance(result, MetricsConfig)
        assert "module.path:ClassName.method_name" in result.concrete
        assert "other.module:func" in result.concrete
        assert len(result.concrete["module.path:ClassName.method_name"]) == 1
        assert len(result.concrete["other.module:func"]) == 1

    @pytest.mark.parametrize("yaml_return", [[], None, {"key": "value"}])
    def test_load_metrics_empty_or_invalid_returns_empty_dict(self, yaml_return):
        """空或非列表配置返回空 MetricsConfig"""
        with patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config", return_value=yaml_return):
            result = self.loader.load_metrics()
            assert isinstance(result, MetricsConfig)
            assert not result.concrete and not result.patterns

    def test_load_metrics_skips_invalid_items(self):
        """缺少 symbol 或非法 symbol 的项被跳过"""
        raw = [
            {"domain": "D"},
            {"symbol": "module.path:ClassName.method_name", "domain": "Valid"},
        ]
        with patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config", return_value=raw):
            with patch("ms_service_profiler.patcher.core.config_loader.ConfigHooker") as MockDH:
                MockDH.return_value = MagicMock()
                result = self.loader.load_metrics()
        assert len(result.concrete) == 1
        assert "module.path:ClassName.method_name" in result.concrete

    def test_load_metrics_with_pattern_symbol_returns_patterns(self):
        """含模式 symbol 的 metrics 配置应解析出 patterns"""
        raw = [
            {"symbol": "vllm.models.*:*.some_method", "domain": "D"},
        ]
        with patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config", return_value=raw):
            with patch("ms_service_profiler.patcher.core.config_loader.wrap_handler_with_metrics") as mock_wrap:
                mock_wrap.side_effect = lambda h, _: h
                result = self.loader.load_metrics()
        assert isinstance(result, MetricsConfig)
        assert len(result.patterns) == 1
        assert result.patterns[0].module_pattern == "vllm.models.*"
        assert result.patterns[0].method_name == "some_method"
