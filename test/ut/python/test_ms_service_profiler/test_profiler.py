# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of the Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------

import unittest
from unittest.mock import patch, MagicMock
import json
from ms_service_profiler.profiler import Profiler, MarkType, Level


class TestMarkType(unittest.TestCase):
    def test_mark_type_values(self):
        """测试MarkType枚举值"""
        self.assertEqual(MarkType.TYPE_EVENT.value, 0)
        self.assertEqual(MarkType.TYPE_METRIC.value, 1)
        self.assertEqual(MarkType.TYPE_SPAN.value, 2)
        self.assertEqual(MarkType.TYPE_LINK.value, 3)


class TestLevel(unittest.TestCase):
    def test_level_values(self):
        """测试Level枚举值"""
        self.assertEqual(Level.ERROR.value, 10)
        self.assertEqual(Level.INFO.value, 20)
        self.assertEqual(Level.DETAILED.value, 30)
        self.assertEqual(Level.VERBOSE.value, 40)
        self.assertEqual(Level.LEVEL_CORE_TRACE.value, 10)
        self.assertEqual(Level.LEVEL_NORMAL_TRACE.value, 20)
        self.assertEqual(Level.LEVEL_DETAILED_TRACE.value, 30)
        self.assertEqual(Level.L0.value, 10)
        self.assertEqual(Level.L1.value, 20)
        self.assertEqual(Level.L2.value, 30)


class TestProfiler(unittest.TestCase):
    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_init_enabled(self, mock_is_enable):
        """测试Profiler初始化（启用状态）"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        self.assertTrue(profiler.enable)

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_init_disabled(self, mock_is_enable):
        """测试Profiler初始化（禁用状态）"""
        mock_is_enable.return_value = False
        profiler = Profiler(Level.L0)
        self.assertFalse(profiler.enable)

    def test_profiler_context_manager(self):
        """测试Profiler上下文管理器"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            self.assertTrue(profiler.enable)

            result = profiler.__enter__()  # pylint: disable=unnecessary-dunder-call
            self.assertEqual(result, profiler)

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_exit_with_span_end(self, mock_is_enable):
        """测试Profiler退出时调用span_end"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        profiler._span_handle = MagicMock()

        with patch.object(profiler, 'span_end') as mock_span_end:
            profiler.__exit__(None, None, None)
            mock_span_end.assert_called_once()

    def test_profiler_attr(self):
        """测试attr方法"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            result = profiler.attr('key1', 'value1')
            self.assertEqual(profiler._attr['key1'], 'value1')
            self.assertEqual(result, profiler)

    def test_profiler_attr_multiple(self):
        """测试多个attr调用"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            profiler.attr('key1', 'value1').attr('key2', 'value2')
            self.assertEqual(profiler._attr['key1'], 'value1')
            self.assertEqual(profiler._attr['key2'], 'value2')

    @patch('ms_service_profiler.profiler.service_profiler.is_domain_enable')
    def test_profiler_domain(self, mock_is_domain_enable):
        """测试domain方法"""
        mock_is_domain_enable.return_value = True
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            result = profiler.domain('TestDomain')
            self.assertEqual(profiler._domain, 'TestDomain')
            self.assertTrue(profiler._enable)
            self.assertEqual(result, profiler)

    @patch('ms_service_profiler.profiler.service_profiler.is_domain_enable')
    def test_profiler_domain_disabled(self, mock_is_domain_enable):
        """测试domain方法（域禁用）"""
        mock_is_domain_enable.return_value = False
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            profiler.domain('TestDomain')
            self.assertFalse(profiler._enable)

    def test_profiler_res(self):
        """测试res方法"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            result = profiler.res('request_id_123')
            self.assertEqual(profiler._attr['rid'], 'request_id_123')
            self.assertEqual(result, profiler)

    def test_profiler_metric(self):
        """测试metric方法"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            result = profiler.metric('response_time', 100)
            self.assertEqual(profiler._attr['response_time='], 100)
            self.assertEqual(result, profiler)

    def test_profiler_metric_inc(self):
        """测试metric_inc方法"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            result = profiler.metric_inc('counter', 1)
            self.assertEqual(profiler._attr['counter+'], 1)
            self.assertEqual(result, profiler)

    def test_profiler_metric_scope(self):
        """测试metric_scope方法"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            result = profiler.metric_scope('request_count', 5)
            self.assertEqual(profiler._attr['scope#request_count'], 5)
            self.assertEqual(result, profiler)

    def test_profiler_metric_scope_as_req_id(self):
        """测试metric_scope_as_req_id方法"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            result = profiler.metric_scope_as_req_id()
            self.assertEqual(profiler._attr['scope#'], 'req')
            self.assertEqual(result, profiler)

    def test_profiler_get_attrs_json_empty(self):
        """测试_get_attrs_json方法（空属性）"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            result = profiler._get_attrs_json()
            self.assertEqual(result, "")

    def test_profiler_get_attrs_json_with_data(self):
        """测试_get_attrs_json方法（有数据）"""
        with patch('ms_service_profiler.profiler.service_profiler.is_enable', return_value=True):
            profiler = Profiler(Level.L0)
            profiler._attr = {'key1': 'value1', 'key2': 'value2'}
            result = profiler._get_attrs_json()
            expected = json.dumps({'key1': 'value1', 'key2': 'value2'})
            self.assertEqual(result, expected)

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_launch_disabled(self, mock_is_enable):
        """测试launch方法（禁用状态）"""
        mock_is_enable.return_value = False
        profiler = Profiler(Level.L0)
        profiler.launch()
        self.assertIsNone(profiler._name)

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    @patch('ms_service_profiler.profiler.service_profiler.mark_event_ex')
    def test_profiler_launch_enabled(self, mock_mark, mock_is_enable):
        """测试launch方法（启用状态）"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        profiler.launch()
        self.assertEqual(profiler._name, "Launch")
        self.assertEqual(profiler._attr["type"], MarkType.TYPE_EVENT)
        mock_mark.assert_called_once()

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_link_disabled(self, mock_is_enable):
        """测试link方法（禁用状态）"""
        mock_is_enable.return_value = False
        profiler = Profiler(Level.L0)
        profiler.link('from_rid', 'to_rid')
        self.assertIsNone(profiler._name)

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    @patch('ms_service_profiler.profiler.service_profiler.mark_event_ex')
    def test_profiler_link_enabled(self, mock_mark, mock_is_enable):
        """测试link方法（启用状态）"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        profiler.link('from_rid', 'to_rid')
        self.assertEqual(profiler._name, "Link")
        self.assertEqual(profiler._attr["type"], MarkType.TYPE_LINK)
        self.assertEqual(profiler._attr["from"], "from_rid")
        self.assertEqual(profiler._attr["to"], "to_rid")
        mock_mark.assert_called_once()

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_event_disabled(self, mock_is_enable):
        """测试event方法（禁用状态）"""
        mock_is_enable.return_value = False
        profiler = Profiler(Level.L0)
        profiler.event('test_event')
        self.assertIsNone(profiler._name)

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    @patch('ms_service_profiler.profiler.service_profiler.mark_event_ex')
    def test_profiler_event_enabled(self, mock_mark, mock_is_enable):
        """测试event方法（启用状态）"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        profiler.event('test_event')
        self.assertEqual(profiler._name, 'test_event')
        self.assertEqual(profiler._attr["type"], MarkType.TYPE_EVENT)
        mock_mark.assert_called_once()

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_span_start_disabled(self, mock_is_enable):
        """测试span_start方法（禁用状态）"""
        mock_is_enable.return_value = False
        profiler = Profiler(Level.L0)
        result = profiler.span_start('test_span')
        self.assertEqual(result, profiler)

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    @patch('ms_service_profiler.profiler.service_profiler.start_span')
    def test_profiler_span_start_enabled(self, mock_start_span, mock_is_enable):
        """测试span_start方法（启用状态）"""
        mock_is_enable.return_value = True
        mock_start_span.return_value = 'span_handle_123'
        profiler = Profiler(Level.L0)
        result = profiler.span_start('test_span')
        self.assertEqual(profiler._name, 'test_span')
        self.assertEqual(profiler._attr["type"], MarkType.TYPE_SPAN)
        self.assertEqual(profiler._span_handle, 'span_handle_123')
        self.assertEqual(result, profiler)

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_span_end_disabled(self, mock_is_enable):
        """测试span_end方法（禁用状态）"""
        mock_is_enable.return_value = False
        profiler = Profiler(Level.L0)
        profiler.span_end()

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_span_end_no_handle(self, mock_is_enable):
        """测试span_end方法（无span handle）"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        profiler._span_handle = None
        profiler.span_end()

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    @patch('ms_service_profiler.profiler.service_profiler.span_end_ex')
    def test_profiler_span_end_with_handle(self, mock_span_end, mock_is_enable):
        """测试span_end方法（有span handle）"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        profiler._name = 'test_span'
        profiler._domain = 'TestDomain'
        profiler._attr = {'key': 'value'}
        profiler._span_handle = 'handle_123'

        with patch.object(profiler, '_get_attrs_json', return_value='{"key": "value"}'):
            profiler.span_end()
            mock_span_end.assert_called_once_with('test_span', 'TestDomain', '{"key": "value"}', 'handle_123')

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_mark_event_ex_disabled(self, mock_is_enable):
        """测试_mark_event_ex方法（禁用状态）"""
        mock_is_enable.return_value = False
        profiler = Profiler(Level.L0)
        profiler._name = 'test_event'
        profiler._domain = 'TestDomain'
        profiler._mark_event_ex()

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    @patch('ms_service_profiler.profiler.service_profiler.mark_event_ex')
    def test_profiler_mark_event_ex_enabled(self, mock_mark, mock_is_enable):
        """测试_mark_event_ex方法（启用状态）"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        profiler._name = 'test_event'
        profiler._domain = 'TestDomain'
        profiler._attr = {'key': 'value'}

        with patch.object(profiler, '_get_attrs_json', return_value='{"key": "value"}'):
            profiler._mark_event_ex()
            mock_mark.assert_called_once_with('test_event', 'TestDomain', '{"key": "value"}')

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    def test_profiler_add_meta_info_disabled(self, mock_is_enable):
        """测试add_meta_info方法（禁用状态）"""
        mock_is_enable.return_value = False
        profiler = Profiler(Level.L0)
        profiler.add_meta_info('meta_key', 'meta_data')

    @patch('ms_service_profiler.profiler.service_profiler.is_enable')
    @patch('ms_service_profiler.profiler.service_profiler.add_meta_info')
    def test_profiler_add_meta_info_enabled(self, mock_add_meta, mock_is_enable):
        """测试add_meta_info方法（启用状态）"""
        mock_is_enable.return_value = True
        profiler = Profiler(Level.L0)
        profiler.add_meta_info('meta_key', 'meta_data')
        mock_add_meta.assert_called_once_with('meta_key', 'meta_data')


class TestInitializeProfiler(unittest.TestCase):
    @patch.dict('ms_service_profiler.profiler.__dict__', {'torch': MagicMock()})
    @patch('ms_service_profiler.profiler.torch_prof_total_steps', 0)
    @patch('ms_service_profiler.profiler.service_profiler.get_acl_task_time_level')
    @patch('ms_service_profiler.profiler.service_profiler.get_acl_prof_aicore_metrics')
    @patch('ms_service_profiler.profiler.service_profiler.get_prof_path')
    @patch('ms_service_profiler.profiler.service_profiler.is_torch_prof_stack')
    @patch('ms_service_profiler.profiler.service_profiler.is_torch_prof_modules')
    @patch('ms_service_profiler.profiler.service_profiler.get_torch_prof_step_num')
    @patch('ms_service_profiler.profiler.logger')
    def test_initialize_profiler_no_steps(
        self,
        mock_logger,
        mock_get_steps,
        mock_is_stack,
        mock_is_modules,
        mock_get_path,
        mock_get_aicore,
        mock_get_task_level,
    ):
        """测试initialize_profiler（无步骤限制）"""
        mock_get_task_level.return_value = 'L1'
        mock_get_aicore.return_value = 1
        mock_get_path.return_value = '/tmp/prof'
        mock_is_stack.return_value = False
        mock_is_modules.return_value = False
        mock_get_steps.return_value = 0

        import sys

        mock_torch = MagicMock()
        mock_torch_npu = MagicMock()
        mock_torch.npu = mock_torch_npu
        type(mock_torch_npu).profiler = MagicMock()

        with patch.dict(sys.modules, {'torch': mock_torch, 'torch_npu': mock_torch_npu}):
            from ms_service_profiler import profiler as profiler_module

            profiler_module.torch_prof = None
            profiler_module.torch_prof_total_steps = 0
            profiler_module.initialize_profiler()


class TestProfStepFunction(unittest.TestCase):
    """针对 prof_step 函数的专项测试"""

    def setUp(self):
        """每个测试前重置全局状态"""
        # 导入被测模块
        from ms_service_profiler import profiler as pm

        # 重置全局变量到初始状态
        pm.torch_prof = None
        pm.torch_prof_total_steps = 0
        pm.torch_prof_current_step = 0
        pm.prof_current_step = 0

        self.pm = pm

    @patch('ms_service_profiler.profiler.service_profiler')
    @patch('ms_service_profiler.profiler.logger')
    def test_prof_step_stop_check_early_return(self, mock_logger, mock_service):
        """场景 1: stop_check=True，直接返回，不执行后续逻辑"""
        # 预设一些值，验证它们是否被改变
        self.pm.prof_current_step = 10

        self.pm.prof_step(stop_check=True)

        # 验证 prof_current_step 没有增加 (因为第一行就 return 了)
        self.assertEqual(self.pm.prof_current_step, 10)

        # 验证 service_profiler 的方法未被调用
        mock_service.set_profiler_current_step.assert_not_called()

    @patch('ms_service_profiler.profiler.service_profiler')
    @patch('ms_service_profiler.profiler.logger')
    def test_prof_step_switch_disabled_stop_existing(self, mock_logger, mock_service):
        """场景 2: 开关关闭，且存在 torch_prof，执行停止逻辑"""
        # 构造已存在的 torch_prof
        mock_torch_prof = MagicMock()
        self.pm.torch_prof = mock_torch_prof
        self.pm.prof_current_step = 5

        # Mock 开关返回 False
        mock_service.is_torch_profiler_enable.return_value = False

        self.pm.prof_step(stop_check=False)

        # 验证全局步数已增加 (代码逻辑：先 +1 再检查开关)
        self.assertEqual(self.pm.prof_current_step, 6)
        mock_service.set_profiler_current_step.assert_called_once_with(6)

        # 验证停止逻辑
        mock_torch_prof.stop.assert_called_once()
        self.assertIsNone(self.pm.torch_prof)
        mock_logger.info.assert_any_call("Torch Profiler has stopped")

    @patch('ms_service_profiler.profiler.initialize_profiler')
    @patch('ms_service_profiler.profiler.Profiler')
    @patch('ms_service_profiler.profiler.service_profiler')
    @patch('ms_service_profiler.profiler.logger')
    def test_prof_step_initialize_and_run_limited(self, mock_logger, mock_service, mock_profiler_cls, mock_init):
        """场景 3: torch_prof 为空 -> 初始化 -> 限制模式下运行一步 (未超限)"""
        # 初始状态
        self.pm.torch_prof = None
        self.pm.torch_prof_total_steps = 5
        self.pm.torch_prof_current_step = 2
        self.pm.prof_current_step = 10

        # Mock 开关返回 True
        mock_service.is_torch_profiler_enable.return_value = True

        # Mock 初始化行为：设置全局 torch_prof
        mock_torch_instance = MagicMock()

        def side_effect_init():
            self.pm.torch_prof = mock_torch_instance

        mock_init.side_effect = side_effect_init

        # Mock Profiler 上下文管理器
        mock_prof_ctx = MagicMock()
        mock_profiler_cls.return_value.__enter__.return_value = mock_prof_ctx
        mock_profiler_cls.return_value.__exit__.return_value = None

        self.pm.prof_step(stop_check=False)

        # 验证全局步数
        self.assertEqual(self.pm.prof_current_step, 11)
        mock_service.set_profiler_current_step.assert_called_once_with(11)

        # 验证初始化被调用
        mock_init.assert_called_once()

        # 验证限制计数器增加 (2 -> 3)
        self.assertEqual(self.pm.torch_prof_current_step, 3)

        # 验证日志打印 (3/5)
        mock_logger.info.assert_any_call("Torch Profiler is running step 3/5")

        # 验证 torch_prof.step() 被调用
        mock_torch_instance.step.assert_called_once()
        mock_profiler_cls.assert_called_once_with(self.pm.Level.L0)

    @patch('ms_service_profiler.profiler.initialize_profiler')
    @patch('ms_service_profiler.profiler.Profiler')
    @patch('ms_service_profiler.profiler.service_profiler')
    @patch('ms_service_profiler.profiler.logger')
    def test_prof_step_limited_exceed_no_log(self, mock_logger, mock_service, mock_profiler_cls, mock_init):
        """场景 4: 限制模式下，步数已超过限制，不打印运行日志，但仍执行 step"""
        mock_torch_instance = MagicMock()
        self.pm.torch_prof = mock_torch_instance
        self.pm.torch_prof_total_steps = 5
        self.pm.torch_prof_current_step = 5  # 下一步变成 6，超过 5

        mock_service.is_torch_profiler_enable.return_value = True

        mock_prof_ctx = MagicMock()
        mock_profiler_cls.return_value.__enter__.return_value = mock_prof_ctx

        self.pm.prof_step(stop_check=False)

        # 验证计数器增加
        self.assertEqual(self.pm.torch_prof_current_step, 6)

        # 验证 "running step..." 日志没有被打印 (因为 6 <= 5 为假)
        # 检查所有 info 调用，确保不包含特定的 step 日志
        for call_arg in mock_logger.info.call_args_list:
            msg = str(call_arg)
            self.assertNotIn("Torch Profiler is running step 6/5", msg)

        # 验证 step 依然被执行 (根据当前代码逻辑)
        mock_torch_instance.step.assert_called_once()

    @patch('ms_service_profiler.profiler.initialize_profiler')
    @patch('ms_service_profiler.profiler.Profiler')
    @patch('ms_service_profiler.profiler.service_profiler')
    @patch('ms_service_profiler.profiler.logger')
    def test_prof_step_switch_disabled_after_init(self, mock_logger, mock_service, mock_profiler_cls, mock_init):
        """场景 6: 初始化后，但在执行 step 前发现开关关闭 (模拟动态关闭)"""
        # 这个场景主要测试代码中 'if not service_profiler.is_torch_profiler_enable' 在 init 之后的逻辑
        # 但根据你的代码结构，开关检查在 init 之前。
        # 这里测试的是：如果 init 成功，但 torch_prof 最终仍为 None (初始化失败) 的情况

        self.pm.torch_prof = None
        self.pm.torch_prof_total_steps = 5
        mock_service.is_torch_profiler_enable.return_value = True

        # 模拟 initialize_profiler 执行了但 torch_prof 仍然是 None (失败)
        def side_effect_init_fail():
            pass  # 不设置 self.pm.torch_prof

        mock_init.side_effect = side_effect_init_fail

        self.pm.prof_step(stop_check=False)

        # 验证全局步数增加了
        self.assertEqual(self.pm.prof_current_step, 1)
        mock_service.set_profiler_current_step.assert_called_once()

        # 验证初始化被调用
        mock_init.assert_called_once()

        # 因为 torch_prof 仍为 None，后续的 if torch_prof: 块不应执行
        mock_profiler_cls.assert_not_called()


if __name__ == '__main__':
    unittest.main()
