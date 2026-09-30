# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2026 Huawei Technologies Co.,Ltd.
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

import unittest
from unittest.mock import MagicMock, patch
from ms_service_profiler.data_source.torch_profiler_data_source import TorchProfilerDataSource


class TestTorchProfilerDataSource(unittest.TestCase):
    """测试 TorchProfilerDataSource 类的功能"""

    def setUp(self):
        """设置测试环境"""
        self.data_source = TorchProfilerDataSource(None)

    def test_outputs(self):
        """测试 outputs 方法"""
        self.assertEqual(TorchProfilerDataSource.outputs(), ["data_source:torch_profiler"])

    @patch('ms_service_profiler.data_source.torch_profiler_data_source.Path')
    def test_get_prof_paths(self, mock_path):
        """测试 get_prof_paths 方法"""
        # 模拟 Path 对象
        mock_dp1 = MagicMock()
        mock_dp1.is_dir.return_value = True
        mock_dp2 = MagicMock()
        mock_dp2.is_dir.return_value = True
        mock_rglob = MagicMock(return_value=[mock_dp1, mock_dp2])
        mock_path_instance = MagicMock()
        mock_path_instance.rglob = mock_rglob
        mock_path.return_value = mock_path_instance

        result = TorchProfilerDataSource.get_prof_paths("test_path")

        self.assertEqual(len(result), 2)
        mock_path.assert_called_once_with("test_path")
        mock_rglob.assert_called_once_with("**/*_ascend_pt")

    @patch('os.path.isdir')
    def test_is_need_torchprofiler_true(self, mock_isdir):
        """测试 is_need_torchprofiler 方法（需要 torch profiler）"""
        mock_isdir.return_value = False
        result = TorchProfilerDataSource.is_need_torchprofiler("test_path")
        self.assertTrue(result)

    @patch('os.path.isdir')
    def test_is_need_torchprofiler_false(self, mock_isdir):
        """测试 is_need_torchprofiler 方法（不需要 torch profiler）"""
        mock_isdir.return_value = True
        result = TorchProfilerDataSource.is_need_torchprofiler("test_path")
        self.assertFalse(result)

    @patch('ms_service_profiler.data_source.torch_profiler_data_source.logger')
    @patch.dict('sys.modules', {'torch': None, 'torch_npu': None})
    def test_run_torch_profiler_parse_import_error(self, mock_logger):
        """测试 run_torch_profiler_parse 方法（导入错误）"""
        result = TorchProfilerDataSource.run_torch_profiler_parse("test_path")
        self.assertIsNone(result)
        mock_logger.warning.assert_called_once()

    @patch('ms_service_profiler.data_source.torch_profiler_data_source.logger')
    def test_run_torch_profiler_parse_success(self, mock_logger):
        """测试 run_torch_profiler_parse 方法（成功）"""
        # 模拟导入成功
        mock_torch = MagicMock()
        mock_torch_npu = MagicMock()
        mock_analyse = MagicMock(return_value="test_result")
        mock_torch_npu.profiler.profiler.analyse = mock_analyse
        mock_modules = {
            'torch': mock_torch,
            'torch_npu': mock_torch_npu,
            'torch_npu.profiler': mock_torch_npu.profiler,
            'torch_npu.profiler.profiler': mock_torch_npu.profiler.profiler,
        }

        with patch.dict('sys.modules', mock_modules):
            # 临时修改模块的导入逻辑
            original_import = __builtins__['__import__']

            def mock_import(name, *args, **kwargs):
                if name in mock_modules:
                    return mock_modules[name]
                return original_import(name, *args, **kwargs)

            __builtins__['__import__'] = mock_import

            try:
                result = TorchProfilerDataSource.run_torch_profiler_parse("test_path")
            finally:
                __builtins__['__import__'] = original_import

        self.assertEqual(result, "test_result")
        mock_analyse.assert_called_once_with(profiler_path="test_path")
        mock_logger.info.assert_called_once()

    @patch('ms_service_profiler.data_source.torch_profiler_data_source.logger')
    def test_run_torch_profiler_parse_exception(self, mock_logger):
        """测试 run_torch_profiler_parse 方法（异常）"""
        # 模拟导入成功但分析失败
        mock_torch = MagicMock()
        mock_torch_npu = MagicMock()
        mock_analyse = MagicMock(side_effect=Exception("Test error"))
        mock_torch_npu.profiler.profiler.analyse = mock_analyse
        mock_modules = {
            'torch': mock_torch,
            'torch_npu': mock_torch_npu,
            'torch_npu.profiler': mock_torch_npu.profiler,
            'torch_npu.profiler.profiler': mock_torch_npu.profiler.profiler,
        }

        with patch.dict('sys.modules', mock_modules):
            # 临时修改模块的导入逻辑
            original_import = __builtins__['__import__']

            def mock_import(name, *args, **kwargs):
                if name in mock_modules:
                    return mock_modules[name]
                return original_import(name, *args, **kwargs)

            __builtins__['__import__'] = mock_import

            try:
                result = TorchProfilerDataSource.run_torch_profiler_parse("test_path")
            finally:
                __builtins__['__import__'] = original_import

        self.assertIsNone(result)
        mock_analyse.assert_called_once_with(profiler_path="test_path")
        mock_logger.error.assert_called_once()

    @patch('ms_service_profiler.data_source.torch_profiler_data_source.TorchProfilerDataSource.is_need_torchprofiler')
    @patch(
        'ms_service_profiler.data_source.torch_profiler_data_source.TorchProfilerDataSource.run_torch_profiler_parse'
    )
    @patch('ms_service_profiler.data_source.torch_profiler_data_source.BaseDataSource.get_filepaths')
    def test_load_with_torchprofiler(
        self, mock_get_filepaths, mock_run_torch_profiler_parse, mock_is_need_torchprofiler
    ):
        """测试 load 方法（需要 torch profiler）"""
        mock_is_need_torchprofiler.return_value = True
        mock_run_torch_profiler_parse.return_value = "test_result"
        mock_get_filepaths.return_value = {"test": "path"}

        result = self.data_source.load("test_path")

        self.assertEqual(result["test"], "path")
        self.assertIsNone(result["tx_data_df"])
        mock_is_need_torchprofiler.assert_called_once_with("test_path")
        mock_run_torch_profiler_parse.assert_called_once_with("test_path")
        mock_get_filepaths.assert_called_once()

    @patch('ms_service_profiler.data_source.torch_profiler_data_source.TorchProfilerDataSource.is_need_torchprofiler')
    @patch(
        'ms_service_profiler.data_source.torch_profiler_data_source.TorchProfilerDataSource.run_torch_profiler_parse'
    )
    @patch('ms_service_profiler.data_source.torch_profiler_data_source.BaseDataSource.get_filepaths')
    def test_load_without_torchprofiler(
        self, mock_get_filepaths, mock_run_torch_profiler_parse, mock_is_need_torchprofiler
    ):
        """测试 load 方法（不需要 torch profiler）"""
        mock_is_need_torchprofiler.return_value = False
        mock_get_filepaths.return_value = {"test": "path"}

        result = self.data_source.load("test_path")

        self.assertEqual(result["test"], "path")
        self.assertIsNone(result["tx_data_df"])
        mock_is_need_torchprofiler.assert_called_once_with("test_path")
        mock_run_torch_profiler_parse.assert_not_called()
        mock_get_filepaths.assert_called_once()

    def test_class_inheritance(self):
        """测试类继承关系"""
        from ms_service_profiler.data_source.base_data_source import BaseDataSource

        self.assertTrue(issubclass(TorchProfilerDataSource, BaseDataSource))

    def test_task_registration(self):
        """测试任务注册"""
        import inspect

        source_code = inspect.getsource(TorchProfilerDataSource)
        self.assertIn('@Task.register("data_source:torch_profiler")', source_code)


if __name__ == '__main__':
    unittest.main()
