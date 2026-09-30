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
from ms_service_profiler.pipeline.pipeline_base import PipelineBase
from ms_service_profiler.utils.error import ParseError


class TestPipelineBase(unittest.TestCase):
    """测试 PipelineBase 类的功能"""

    def setUp(self):
        """设置测试环境"""
        self.mock_args = MagicMock()
        self.pipeline = PipelineBase(self.mock_args)

    def test_pipeline_base_initialization(self):
        """测试 PipelineBase 初始化"""
        self.assertEqual(self.pipeline._args, self.mock_args)
        self.assertEqual(self.pipeline.cur_step_id, 0)

    @patch('ms_service_profiler.pipeline.pipeline_base.Timer')
    @patch('ms_service_profiler.pipeline.pipeline_base.logger')
    def test_run_step_success(self, mock_logger, mock_timer):
        """测试 run_step 方法成功执行"""
        mock_processor = MagicMock()
        mock_processor.parse.return_value = "processed_data"
        mock_timer_instance = MagicMock()
        mock_timer.return_value.__enter__.return_value = mock_timer_instance
        mock_timer.return_value.__exit__.return_value = None

        result = self.pipeline.run_step(mock_processor, "test_processor", "input_data", is_key_step=True)

        self.assertEqual(result, "processed_data")
        self.assertEqual(self.pipeline.cur_step_id, 1)
        mock_processor.parse.assert_called_once_with("input_data")
        mock_timer_instance.set_done_state.assert_called_once_with("success")

    @patch('ms_service_profiler.pipeline.pipeline_base.Timer')
    @patch('ms_service_profiler.pipeline.pipeline_base.logger')
    def test_run_step_with_additional_params(self, mock_logger, mock_timer):
        """测试 run_step 方法带额外参数"""
        mock_processor = MagicMock()
        mock_processor.parse.return_value = "processed_data"
        mock_timer_instance = MagicMock()
        mock_timer.return_value.__enter__.return_value = mock_timer_instance
        mock_timer.return_value.__exit__.return_value = None

        result = self.pipeline.run_step(
            mock_processor, "test_processor", "input_data", "param1", "param2", is_key_step=True
        )

        self.assertEqual(result, "processed_data")
        mock_processor.parse.assert_called_once_with("input_data", "param1", "param2")

    @patch('ms_service_profiler.pipeline.pipeline_base.Timer')
    @patch('ms_service_profiler.pipeline.pipeline_base.logger')
    def test_run_step_key_step_failure(self, mock_logger, mock_timer):
        """测试 run_step 方法关键步骤失败"""
        mock_processor = MagicMock()
        mock_processor.parse.side_effect = Exception("Test error")
        mock_timer_instance = MagicMock()
        mock_timer.return_value.__enter__.return_value = mock_timer_instance
        mock_timer.return_value.__exit__.return_value = None

        with self.assertRaises(ParseError) as context:
            self.pipeline.run_step(mock_processor, "test_processor", "input_data", is_key_step=True)

        self.assertIn("test_processor", str(context.exception))
        self.assertIn("failure", str(context.exception))
        mock_timer_instance.set_done_state.assert_called_once_with("failure")

    @patch('ms_service_profiler.pipeline.pipeline_base.Timer')
    @patch('ms_service_profiler.pipeline.pipeline_base.logger')
    def test_run_step_non_key_step_failure(self, mock_logger, mock_timer):
        """测试 run_step 方法非关键步骤失败"""
        mock_processor = MagicMock()
        mock_processor.parse.side_effect = Exception("Test error")
        mock_timer_instance = MagicMock()
        mock_timer.return_value.__enter__.return_value = mock_timer_instance
        mock_timer.return_value.__exit__.return_value = None

        result = self.pipeline.run_step(mock_processor, "test_processor", "input_data", is_key_step=False)

        self.assertEqual(result, "input_data")
        mock_logger.exception.assert_called_once()
        mock_timer_instance.set_done_state.assert_called_once_with("failure")

    @patch('ms_service_profiler.pipeline.pipeline_base.Timer')
    @patch('ms_service_profiler.pipeline.pipeline_base.logger')
    def test_run_step_multiple_calls(self, mock_logger, mock_timer):
        """测试多次调用 run_step 方法"""
        mock_processor = MagicMock()
        mock_processor.parse.return_value = "processed_data"
        mock_timer_instance = MagicMock()
        mock_timer.return_value.__enter__.return_value = mock_timer_instance
        mock_timer.return_value.__exit__.return_value = None

        result1 = self.pipeline.run_step(mock_processor, "processor1", "data1", is_key_step=True)
        result2 = self.pipeline.run_step(mock_processor, "processor2", "data2", is_key_step=True)
        result3 = self.pipeline.run_step(mock_processor, "processor3", "data3", is_key_step=True)

        self.assertEqual(result1, "processed_data")
        self.assertEqual(result2, "processed_data")
        self.assertEqual(result3, "processed_data")
        self.assertEqual(self.pipeline.cur_step_id, 3)

    @patch('ms_service_profiler.pipeline.pipeline_base.Timer')
    @patch('ms_service_profiler.pipeline.pipeline_base.logger')
    def test_run_step_none_data(self, mock_logger, mock_timer):
        """测试 run_step 方法处理 None 数据"""
        mock_processor = MagicMock()
        mock_processor.parse.return_value = None
        mock_timer_instance = MagicMock()
        mock_timer.return_value.__enter__.return_value = mock_timer_instance
        mock_timer.return_value.__exit__.return_value = None

        result = self.pipeline.run_step(mock_processor, "test_processor", None, is_key_step=True)

        self.assertIsNone(result)
        mock_processor.parse.assert_called_once_with(None)

    @patch('ms_service_profiler.pipeline.pipeline_base.Timer')
    @patch('ms_service_profiler.pipeline.pipeline_base.logger')
    def test_run_step_complex_data(self, mock_logger, mock_timer):
        """测试 run_step 方法处理复杂数据"""
        mock_processor = MagicMock()
        complex_data = {"key1": "value1", "key2": ["item1", "item2"]}
        mock_processor.parse.return_value = complex_data
        mock_timer_instance = MagicMock()
        mock_timer.return_value.__enter__.return_value = mock_timer_instance
        mock_timer.return_value.__exit__.return_value = None

        result = self.pipeline.run_step(mock_processor, "test_processor", complex_data, is_key_step=True)

        self.assertEqual(result, complex_data)
        mock_processor.parse.assert_called_once_with(complex_data)

    @patch('ms_service_profiler.pipeline.pipeline_base.Timer')
    @patch('ms_service_profiler.pipeline.pipeline_base.logger')
    def test_run_step_exception_with_message(self, mock_logger, mock_timer):
        """测试 run_step 方法异常包含原始错误消息"""
        mock_processor = MagicMock()
        error_message = "Custom error message"
        mock_processor.parse.side_effect = ValueError(error_message)
        mock_timer_instance = MagicMock()
        mock_timer.return_value.__enter__.return_value = mock_timer_instance
        mock_timer.return_value.__exit__.return_value = None

        with self.assertRaises(ParseError) as context:
            self.pipeline.run_step(mock_processor, "test_processor", "input_data", is_key_step=True)

        self.assertIn(error_message, str(context.exception))
        self.assertIn("test_processor", str(context.exception))


if __name__ == '__main__':
    unittest.main()
