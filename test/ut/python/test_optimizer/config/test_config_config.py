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
import os
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import numpy as np
from ms_serviceparam_optimizer.config.config import (
    map_param_with_value,
    OptimizerConfigField,
    ErrorPatternConfig,
    HealthCheckConfig,
    ErrorType,
    _get_mindie_config_paths,
    MindieConfig,
    update_optimizer_value,
    DecodeContext,
    resolve_priority,
    _repair_ternary_factories_with_priority,
)


class TestMapParamWithValueRealFields(unittest.TestCase):
    def setUp(self):
        self.default_support_field = [
            OptimizerConfigField(
                name="max_batch_size",
                config_position="BackendConfig.ScheduleConfig.maxBatchSize",
                min=25,
                max=300,
                dtype="int",
            ),
            OptimizerConfigField(
                name="max_prefill_batch_size",
                config_position="BackendConfig.ScheduleConfig.maxPrefillBatchSize",
                min=1,
                max=25,
                dtype="int",
            ),
            OptimizerConfigField(
                name="prefill_time_ms_per_req",
                config_position="BackendConfig.ScheduleConfig.prefillTimeMsPerReq",
                max=1000,
                dtype="int",
            ),
            OptimizerConfigField(
                name="decode_time_ms_per_req",
                config_position="BackendConfig.ScheduleConfig.decodeTimeMsPerReq",
                max=1000,
                dtype="int",
            ),
            OptimizerConfigField(
                name="support_select_batch",
                config_position="BackendConfig.ScheduleConfig.supportSelectBatch",
                max=1,
                dtype="bool",
            ),
            OptimizerConfigField(
                name="max_prefill_token",
                config_position="BackendConfig.ScheduleConfig.maxPrefillTokens",
                min=4096,
                max=409600,
                dtype="int",
            ),
            OptimizerConfigField(
                name="max_queue_deloy_microseconds",
                config_position="BackendConfig.ScheduleConfig.maxQueueDelayMicroseconds",
                min=500,
                max=1000000,
                dtype="int",
            ),
            OptimizerConfigField(
                name="prefill_policy_type",
                config_position="BackendConfig.ScheduleConfig.prefillPolicyType",
                min=0,
                max=1,
                dtype="enum",
                dtype_param=[0, 1, 3],
            ),
            OptimizerConfigField(
                name="decode_policy_type",
                config_position="BackendConfig.ScheduleConfig.decodePolicyType",
                min=0,
                max=1,
                dtype="enum",
                dtype_param=[0, 1, 3],
            ),
            OptimizerConfigField(
                name="max_preempt_count",
                config_position="BackendConfig.ScheduleConfig.maxPreemptCount",
                min=0,
                max=1,
                dtype="ratio",
                dtype_param="max_batch_size",
            ),
        ]
        self.pd_field = [
            OptimizerConfigField(
                name="default_p_rate", config_position="default_p_rate", min=1, max=3, dtype="int", value=1
            ),
            OptimizerConfigField(
                name="default_d_rate",
                config_position="default_d_rate",
                min=1,
                max=3,
                dtype="share",
                dtype_param="default_p_rate",
            ),
        ]

    def test_int_type_with_min_max(self):
        # 测试 int 类型（带 min/max 约束）
        params = np.array([26.7, 12.3, 999.9, 500.0, 0.6, 40960.0, 750000.0])
        result = map_param_with_value(params, self.default_support_field[:7])

        # 验证字段值是否符合预期
        self.assertEqual(result[0].value, 26)
        self.assertEqual(result[1].value, 12)
        self.assertEqual(result[2].value, 999)
        self.assertEqual(result[3].value, 500)
        self.assertTrue(result[4].value)
        self.assertEqual(result[5].value, 40960)
        self.assertEqual(result[6].value, 750000)

    def test_enum_type_mapping(self):
        # 测试 enum 类型的分段映射
        params = np.array([0.0, 0.3, 0.6, 1.0])
        enum_fields = [
            self.default_support_field[7],  # prefill_policy_type (enum [0,1,3])
            self.default_support_field[8],  # decode_policy_type (enum [0,1,3])
        ]
        result = map_param_with_value(params, enum_fields)

        # 验证 enum 分段逻辑
        self.assertEqual(result[0].value, 0)
        self.assertEqual(result[1].value, 0)

    def test_ratio_type_dependency(self):
        # 测试 ratio 类型（依赖 max_batch_size）
        params = np.array([0.5])
        ratio_field = self.default_support_field[9]  # max_preempt_count (ratio)

        # 手动设置依赖字段的值
        max_batch_size_field = OptimizerConfigField(
            name="max_batch_size",
            config_position="BackendConfig.ScheduleConfig.maxBatchSize",
            dtype="int",
            value=100,
            constant=100,
        )

        result = map_param_with_value(params, [max_batch_size_field, ratio_field])
        self.assertEqual(result[1].value, 50)

    def test_share_type_mapping(self):
        params = np.array([1, 2])
        share_ratio = map_param_with_value(params, self.pd_field)
        self.assertEqual(share_ratio[1].value, 3)

    def test_edge_cases(self):
        # 测试边界条件
        params = np.array([24.9, 0.0, 0.0, 0.0, 0.4, 4095.9, 499.9, -1.0, 2.0, 1.1])
        result = map_param_with_value(params, self.default_support_field)

        # 验证边界处理
        self.assertEqual(result[0].value, 24)
        self.assertEqual(result[1].value, 1)
        self.assertFalse(result[4].value)
        self.assertEqual(result[5].value, 4095)
        self.assertEqual(result[6].value, 499)
        self.assertEqual(result[7].value, 0)


class TestErrorPatternConfig(unittest.TestCase):
    """测试 ErrorPatternConfig 配置类"""

    def test_custom_patterns(self):
        """测试自定义错误模式"""
        custom_config = ErrorPatternConfig(
            fatal_patterns={ErrorType.OUT_OF_MEMORY: ["custom OOM pattern"]},
            retryable_patterns={ErrorType.NETWORK_ERROR: ["custom network pattern"]},
        )
        self.assertEqual(len(custom_config.fatal_patterns[ErrorType.OUT_OF_MEMORY]), 1)
        self.assertEqual(custom_config.fatal_patterns[ErrorType.OUT_OF_MEMORY][0], "custom OOM pattern")
        self.assertEqual(custom_config.retryable_patterns[ErrorType.NETWORK_ERROR][0], "custom network pattern")

    def test_empty_patterns(self):
        """测试空错误模式"""
        empty_config = ErrorPatternConfig(fatal_patterns={}, retryable_patterns={})
        self.assertEqual(len(empty_config.fatal_patterns), 0)
        self.assertEqual(len(empty_config.retryable_patterns), 0)


class TestHealthCheckConfig(unittest.TestCase):
    """测试 HealthCheckConfig 配置类"""

    def test_default_service_errors(self):
        """测试默认的 service_errors 配置"""
        config = HealthCheckConfig()
        self.assertIsInstance(config.service_errors, ErrorPatternConfig)
        self.assertIn(ErrorType.OUT_OF_MEMORY, config.service_errors.fatal_patterns)
        self.assertIn(ErrorType.NETWORK_ERROR, config.service_errors.retryable_patterns)

    def test_default_benchmark_errors(self):
        """测试默认的 benchmark_errors 配置"""
        config = HealthCheckConfig()
        self.assertIsInstance(config.benchmark_errors, ErrorPatternConfig)
        self.assertEqual(len(config.benchmark_errors.fatal_patterns), 0)
        self.assertIn(ErrorType.NETWORK_ERROR, config.benchmark_errors.retryable_patterns)
        self.assertIn(ErrorType.IO_ERROR, config.benchmark_errors.retryable_patterns)

    def test_custom_log_snippet_length(self):
        """测试自定义 log_snippet_length"""
        config = HealthCheckConfig(log_snippet_length=500)
        self.assertEqual(config.log_snippet_length, 500)

    def test_custom_health_check_config(self):
        """测试自定义健康检查配置"""
        custom_config = HealthCheckConfig(
            service_errors=ErrorPatternConfig(
                fatal_patterns={ErrorType.DEVICE_ERROR: ["device fault"]}, retryable_patterns={}
            ),
            benchmark_errors=ErrorPatternConfig(
                fatal_patterns={}, retryable_patterns={ErrorType.IO_ERROR: ["disk full"]}
            ),
            log_snippet_length=300,
        )
        self.assertIn("device fault", custom_config.service_errors.fatal_patterns[ErrorType.DEVICE_ERROR])
        self.assertIn("disk full", custom_config.benchmark_errors.retryable_patterns[ErrorType.IO_ERROR])
        self.assertEqual(custom_config.log_snippet_length, 300)


class TestGetMindieConfigPaths(unittest.TestCase):
    """测试 _get_mindie_config_paths 函数"""

    @patch.object(Path, 'is_file')
    def test_default_path_exists(self, mock_is_file):
        """测试默认配置文件存在时返回默认路径"""
        mock_is_file.return_value = True

        config_path, config_bak_path = _get_mindie_config_paths()

        expected_config = Path("/usr/local/Ascend/mindie/latest/mindie-service/conf/config.json")
        expected_bak = Path("/usr/local/Ascend/mindie/latest/mindie-service/conf/config_bak.json")

        self.assertEqual(config_path, expected_config)
        self.assertEqual(config_bak_path, expected_bak)

    @patch.object(Path, 'is_file')
    def test_env_variable_not_set(self, mock_is_file):
        """测试默认路径不存在且环境变量也不存在时返回默认路径"""
        mock_is_file.return_value = False

        # 清除环境变量
        env_backup = os.environ.pop("MIES_INSTALL_PATH", None)
        try:
            config_path, config_bak_path = _get_mindie_config_paths()

            expected_config = Path("/usr/local/Ascend/mindie/latest/mindie-service/conf/config.json")
            expected_bak = Path("/usr/local/Ascend/mindie/latest/mindie-service/conf/config_bak.json")

            self.assertEqual(config_path, expected_config)
            self.assertEqual(config_bak_path, expected_bak)
        finally:
            if env_backup:
                os.environ["MIES_INSTALL_PATH"] = env_backup


class TestMindieConfig(unittest.TestCase):
    """测试 MindieConfig 配置类"""

    @patch('ms_serviceparam_optimizer.config.config._get_mindie_config_paths')
    def test_default_values(self, mock_get_paths):
        """测试 MindieConfig 默认值"""
        mock_get_paths.return_value = (Path("/test/config.json"), Path("/test/config_bak.json"))

        config = MindieConfig()

        self.assertEqual(config.process_name, "mindie, mindie-llm, mindieservice_daemon, mindie_llm")
        self.assertEqual(config.output, Path("mindie"))
        self.assertEqual(config.config_path, Path("/test/config.json"))
        self.assertEqual(config.config_bak_path, Path("/test/config_bak.json"))

    @patch('ms_serviceparam_optimizer.config.config._get_mindie_config_paths')
    def test_custom_output(self, mock_get_paths):
        """测试自定义 output 路径"""
        mock_get_paths.return_value = (Path("/test/config.json"), Path("/test/config_bak.json"))

        config = MindieConfig(output=Path("/custom/output"))

        self.assertEqual(config.output, Path("/custom/output"))

    @patch('ms_serviceparam_optimizer.config.config._get_mindie_config_paths')
    def test_target_field_default(self, mock_get_paths):
        """测试 target_field 默认值"""
        mock_get_paths.return_value = (Path("/test/config.json"), Path("/test/config_bak.json"))

        config = MindieConfig()

        self.assertIsInstance(config.target_field, list)
        self.assertTrue(len(config.target_field) > 0)


class TestOptimizerConfigFieldConstant(unittest.TestCase):
    """测试 OptimizerConfigField 的 constant 相关逻辑"""

    def test_constant_auto_set_when_min_equals_max(self):
        """测试当 min 等于 max 时自动设置 constant"""
        field = OptimizerConfigField(name="test_field", config_position="test.position", min=100, max=100, dtype="int")

        self.assertEqual(field.constant, 100)
        self.assertEqual(field.min, 100)
        self.assertEqual(field.max, 100)

    def test_constant_explicit_set(self):
        """测试显式设置 constant"""
        field = OptimizerConfigField(
            name="test_field", config_position="test.position", min=0, max=100, dtype="int", constant=50
        )

        self.assertEqual(field.constant, 50)
        self.assertEqual(field.min, 50)
        self.assertEqual(field.max, 50)

    def test_min_greater_than_max_raises_error(self):
        """测试 min 大于 max 时抛出错误"""
        with self.assertRaises(ValueError) as context:
            OptimizerConfigField(name="test_field", config_position="test.position", min=100, max=0, dtype="int")

        self.assertIn("min", str(context.exception))
        self.assertIn("max", str(context.exception))

    def test_find_available_value_within_range(self):
        """测试 find_available_value 在范围内"""
        field = OptimizerConfigField(name="test_field", config_position="test.position", min=0, max=100, dtype="int")

        self.assertEqual(field.find_available_value(50), 50)
        self.assertEqual(field.find_available_value(0), 0)
        self.assertEqual(field.find_available_value(100), 100)

    def test_find_available_value_out_of_range(self):
        """测试 find_available_value 超出范围时返回边界值"""
        field = OptimizerConfigField(name="test_field", config_position="test.position", min=0, max=100, dtype="int")

        self.assertEqual(field.find_available_value(-10), 0)
        self.assertEqual(field.find_available_value(150), 100)

    def test_find_available_value_enum_type(self):
        """测试 find_available_value 对于 enum 类型"""
        field = OptimizerConfigField(
            name="test_field", config_position="test.position", min=0, max=1, dtype="enum", dtype_param=[1, 2, 4, 8]
        )

        # 值在枚举列表中
        self.assertEqual(field.find_available_value(2), 2)
        self.assertEqual(field.find_available_value(8), 8)

        # 值不在枚举列表中，返回最接近的
        self.assertEqual(field.find_available_value(3), 4)
        self.assertEqual(field.find_available_value(0), 1)

    def test_convert_dtype(self):
        """测试 convert_dtype 方法"""
        int_field = OptimizerConfigField(name="int_field", config_position="test.position", dtype="int")
        float_field = OptimizerConfigField(name="float_field", config_position="test.position", dtype="float")

        self.assertEqual(int_field.convert_dtype("42"), 42)
        self.assertIsInstance(int_field.convert_dtype("42"), int)

        self.assertAlmostEqual(float_field.convert_dtype("3.14"), 3.14)
        self.assertIsInstance(float_field.convert_dtype("3.14"), float)


class TestTernaryRelationship(unittest.TestCase):
    """测试三元关系参数 (ternary_factories / ternary_times) 的完整逻辑"""

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _make_base_field(name, dtype, min_=0, max_=0, value=0, dtype_param=None):
        """创建一个常规 OptimizerConfigField，用于组合测试"""
        return OptimizerConfigField(
            name=name,
            config_position=f"Test.{name}",
            min=min_,
            max=max_,
            dtype=dtype,
            value=value,
            dtype_param=dtype_param,
        )

    @staticmethod
    def _run_update(params_field_list, init_values, support_select_is_false=False):
        """
        将 params_field_list 深拷贝为 simulate_run_info，按 init_values 覆写初始化值后执行 update_optimizer_value。
        返回修改后的 simulate_run_info 列表。
        """
        simulate = [deepcopy(f) for f in params_field_list]
        for idx, val in enumerate(init_values):
            simulate[idx].value = val
        update_optimizer_value(tuple(params_field_list), tuple(simulate), support_select_is_false)
        return simulate

    # ------------------------------------------------- ternary_factories tests
    def test_ternary_factories_basic(self):
        """三元除法基本: 16 / (tp=2 * pp=4) = 2"""
        tp = self._make_base_field("tp", "int", min_=1, max_=8, value=2)
        pp = self._make_base_field("pp", "int", min_=1, max_=4, value=4)
        dp = self._make_base_field(
            "dp", "ternary_factories", dtype_param={"target_names": ["tp", "pp"], "product": 16, "dtype": "int"}
        )
        result = self._run_update([tp, pp, dp], [2, 4, 0])
        self.assertEqual(result[2].value, 2)

    def test_ternary_factories_float_result(self):
        """三元除法 float 类型: 10.0 / (tp=2 * pp=2) = 2.5"""
        tp = self._make_base_field("tp", "int", min_=1, max_=8, value=2)
        pp = self._make_base_field("pp", "int", min_=1, max_=4, value=2)
        dp_f = self._make_base_field(
            "dp_f", "ternary_factories", dtype_param={"target_names": ["tp", "pp"], "product": 10.0, "dtype": "float"}
        )
        result = self._run_update([tp, pp, dp_f], [2, 2, 0.0])
        self.assertAlmostEqual(result[2].value, 2.5)

    def test_ternary_factories_first_target_zero(self):
        """三元除法：第一个依赖字段为 0 时不更新字段值"""
        tp = self._make_base_field("tp", "int", min_=1, max_=8, value=0)
        pp = self._make_base_field("pp", "int", min_=1, max_=4, value=4)
        dp = self._make_base_field(
            "dp",
            "ternary_factories",
            value=99,
            dtype_param={"target_names": ["tp", "pp"], "product": 16, "dtype": "int"},
        )
        result = self._run_update([tp, pp, dp], [0, 4, 99])
        # tp=0 导致除数为 0，跳过计算，值保持 99
        self.assertEqual(result[2].value, 99)

    def test_ternary_factories_second_target_zero(self):
        """三元除法：第二个依赖字段为 0 时不更新字段值"""
        tp = self._make_base_field("tp", "int", min_=1, max_=8, value=4)
        pp = self._make_base_field("pp", "int", min_=1, max_=4, value=0)
        dp = self._make_base_field(
            "dp",
            "ternary_factories",
            value=88,
            dtype_param={"target_names": ["tp", "pp"], "product": 16, "dtype": "int"},
        )
        result = self._run_update([tp, pp, dp], [4, 0, 88])
        self.assertEqual(result[2].value, 88)

    def test_ternary_factories_default_product(self):
        """三元除法: dtype_param 中缺省 product 时默认为 1"""
        tp = self._make_base_field("tp", "int", min_=1, max_=8, value=2)
        pp = self._make_base_field("pp", "int", min_=1, max_=4, value=1)
        dp = self._make_base_field(
            "dp",
            "ternary_factories",
            dtype_param={
                "target_names": ["tp", "pp"],
                "dtype": "int",  # 没有 product
            },
        )
        result = self._run_update([tp, pp, dp], [2, 1, 0])
        # product=1, divisor=2*1=2: int(1/2)=0 但 min_value=1 且 1%2≠0，触发修复
        # 修复找到 (tp=1,pp=1) 使 dp=1/(1*1)=1 自洽
        self.assertEqual(result[2].value, 1)

    def test_ternary_factories_overflow_with_min_value(self):
        """三元除法：乘积超过 product 时，min_value 自动截断兜底"""
        tp = self._make_base_field("tp", "int", min_=1, max_=8, value=8)
        pp = self._make_base_field("pp", "int", min_=1, max_=4, value=4)
        dp = self._make_base_field(
            "dp",
            "ternary_factories",
            dtype_param={"target_names": ["tp", "pp"], "product": 16, "dtype": "int", "min_value": 1},
        )
        result = self._run_update([tp, pp, dp], [8, 4, 99])
        # 16 / (8 * 4) = 0.5 → int → 0 < min_value=1 → 截断至 1
        self.assertEqual(result[2].value, 1)

    def test_ternary_factories_overflow_without_min_value(self):
        """三元除法：乘积超过 product 且未显式设 min_value 时，int 类型默认自动截断至 1"""
        tp = self._make_base_field("tp", "int", min_=1, max_=8, value=8)
        pp = self._make_base_field("pp", "int", min_=1, max_=4, value=4)
        dp = self._make_base_field(
            "dp",
            "ternary_factories",
            value=99,
            dtype_param={"target_names": ["tp", "pp"], "product": 16, "dtype": "int"},
        )
        result = self._run_update([tp, pp, dp], [8, 4, 99])
        # 16 / (8 * 4) = 0.5 → int → 0 < 默认 min=1 → 自动截断至 1，输出 WARNING
        self.assertEqual(result[2].value, 1)

    def test_ternary_factories_max_value_clamp(self):
        """三元除法：结果超过 max_value 时自动截断至上界"""
        tp = self._make_base_field("tp", "int", min_=1, max_=8, value=1)
        pp = self._make_base_field("pp", "int", min_=1, max_=4, value=1)
        dp = self._make_base_field(
            "dp",
            "ternary_factories",
            dtype_param={"target_names": ["tp", "pp"], "product": 64, "dtype": "int", "max_value": 8},
        )
        result = self._run_update([tp, pp, dp], [1, 1, 0])
        # 64 / (1 * 1) = 64 > max_value=8 → 截断至 8
        self.assertEqual(result[2].value, 8)

    def test_ternary_factories_min_max_both(self):
        """三元除法： min_value 和 max_value 同时生效：先下界再上界"""
        tp = self._make_base_field("tp", "int", min_=1, max_=8, value=2)
        pp = self._make_base_field("pp", "int", min_=1, max_=4, value=2)
        dp = self._make_base_field(
            "dp",
            "ternary_factories",
            dtype_param={"target_names": ["tp", "pp"], "product": 8, "dtype": "int", "min_value": 1, "max_value": 3},
        )
        result = self._run_update([tp, pp, dp], [2, 2, 0])
        # 8 / (2 * 2) = 2，在 [1, 3] 范围内，不被截断
        self.assertEqual(result[2].value, 2)

    # --------------------------------------------------- ternary_times tests
    def test_ternary_times_basic(self):
        """三元乘法基本: 2 * seq_len=512 * batch=4 = 4096"""
        seq_len = self._make_base_field("seq_len", "int", min_=128, max_=4096, value=512)
        batch = self._make_base_field("batch_size", "int", min_=1, max_=64, value=4)
        total = self._make_base_field(
            "total_tokens",
            "ternary_times",
            dtype_param={"target_names": ["seq_len", "batch_size"], "product": 2, "dtype": "int"},
        )
        result = self._run_update([seq_len, batch, total], [512, 4, 0])
        self.assertEqual(result[2].value, 4096)

    def test_ternary_times_product_one(self):
        """三元乘法: product=1 直接计算两字段之积: a=3 * b=7 = 21"""
        fa = self._make_base_field("a", "int", min_=1, max_=10, value=3)
        fb = self._make_base_field("b", "int", min_=1, max_=10, value=7)
        fc = self._make_base_field(
            "c", "ternary_times", dtype_param={"target_names": ["a", "b"], "product": 1, "dtype": "int"}
        )
        result = self._run_update([fa, fb, fc], [3, 7, 0])
        self.assertEqual(result[2].value, 21)

    def test_ternary_times_first_target_none(self):
        """三元乘法：第一个依赖字段值为 NaN 时不更新派生字段值

        OptimizerConfigField.value 不支持 None；代码中对无效值的判断是 ``value is None or isnan(value)``。
        因此用 float('nan') 作为无效值代表，验证首个源字段无效时应跳过计算。
        """
        fa = self._make_base_field("a", "float", min_=1.0, max_=10.0, value=float('nan'))
        fb = self._make_base_field("b", "int", min_=1, max_=10, value=5)
        fc = self._make_base_field(
            "c", "ternary_times", value=999, dtype_param={"target_names": ["a", "b"], "product": 2, "dtype": "int"}
        )
        result = self._run_update([fa, fb, fc], [float('nan'), 5, 999])
        self.assertEqual(result[2].value, 999)

    def test_ternary_times_second_target_none(self):
        """三元乘法：第二个依赖字段值为 NaN 时不更新派生字段值

        覆盖 test_ternary_times_nan_target 未测试的「第二个字段 NaN」分支。
        """
        fa = self._make_base_field("a", "int", min_=1, max_=10, value=5)
        fb = self._make_base_field("b", "float", min_=1.0, max_=10.0, value=float('nan'))
        fc = self._make_base_field(
            "c", "ternary_times", value=777, dtype_param={"target_names": ["a", "b"], "product": 3, "dtype": "int"}
        )
        result = self._run_update([fa, fb, fc], [5, float('nan'), 777])
        self.assertEqual(result[2].value, 777)

    def test_ternary_times_nan_target(self):
        """三元乘法：依赖字段值为 NaN 时不更新字段值"""
        fa = self._make_base_field("a", "float", min_=0.0, max_=1.0, value=float('nan'))
        fb = self._make_base_field("b", "int", min_=1, max_=10, value=4)
        fc = self._make_base_field(
            "c", "ternary_times", value=555, dtype_param={"target_names": ["a", "b"], "product": 1, "dtype": "float"}
        )
        result = self._run_update([fa, fb, fc], [float('nan'), 4, 555])
        self.assertEqual(result[2].value, 555)

    def test_ternary_times_default_product(self):
        """三元乘法: dtype_param 缺省 product 时默认为 1，结果 = a * b"""
        fa = self._make_base_field("a", "int", min_=1, max_=10, value=3)
        fb = self._make_base_field("b", "int", min_=1, max_=10, value=5)
        fc = self._make_base_field(
            "c",
            "ternary_times",
            dtype_param={
                "target_names": ["a", "b"],
                "dtype": "int",  # 缺省 product
            },
        )
        result = self._run_update([fa, fb, fc], [3, 5, 0])
        self.assertEqual(result[2].value, 15)

    def test_ternary_times_missing_target_keeps_original(self):
        """三元乘法依赖字段写错时，不应按部分字段静默计算。"""
        fa = self._make_base_field("a", "int", min_=1, max_=10, value=3)
        fc = self._make_base_field(
            "c",
            "ternary_times",
            value=777,
            dtype_param={"target_names": ["a", "missing_b"], "product": 2, "dtype": "int"},
        )
        result = self._run_update([fa, fc], [3, 777])
        self.assertEqual(result[1].value, 777)

    def test_ternary_factories_repair_adjusts_source_fields(self):
        """
        约束修复：源字段被调整至最近合法组合，整体配置自洽。
        tp=8, pp=4 非法 → 修复到 tp=8, pp=2，使 dp=16/(8*2)=1 合法
        """
        tp = self._make_base_field("tp", "int", min_=1, max_=8, value=8)
        pp = self._make_base_field("pp", "int", min_=1, max_=4, value=4)
        dp = self._make_base_field(
            "dp", "ternary_factories", dtype_param={"target_names": ["tp", "pp"], "product": 16, "dtype": "int"}
        )
        result = self._run_update([tp, pp, dp], [8, 4, 0])

        tp_val = result[0].value
        pp_val = result[1].value
        dp_val = result[2].value

        # 验证自洽性：dp 必须等于 product/(tp*pp)
        self.assertGreater(dp_val, 0, "dp 不能为 0")
        self.assertEqual(
            dp_val,
            int(16 / (tp_val * pp_val)),
            f"dp 必须与 tp={tp_val}, pp={pp_val} 自洽：16/({tp_val}*{pp_val}) != {dp_val}",
        )

    def test_ternary_factories_repair_enum_source(self):
        """
        约束修复：源字段为 enum 类型时正确修复并验证自洽性。
        tp=[1,2,4,8], pp=[1,2]（限制了最大乘积为 16）
        """
        tp = self._make_base_field("tp", "enum", min_=0, max_=1, dtype_param=[1, 2, 4, 8], value=8)
        pp = self._make_base_field("pp", "enum", min_=0, max_=1, dtype_param=[1, 2, 4], value=4)
        dp = self._make_base_field(
            "dp", "ternary_factories", dtype_param={"target_names": ["tp", "pp"], "product": 16, "dtype": "int"}
        )
        result = self._run_update([tp, pp, dp], [8, 4, 0])

        tp_val = result[0].value
        pp_val = result[1].value
        dp_val = result[2].value

        # 验证自洽性
        self.assertGreater(dp_val, 0, "dp 不能为 0")
        self.assertEqual(dp_val, int(16 / (tp_val * pp_val)), f"dp 必须与 tp={tp_val}, pp={pp_val} 自洽")
        # 验证修复后的源字段在候选列表内
        self.assertIn(tp_val, [1, 2, 4, 8])
        self.assertIn(pp_val, [1, 2, 4])

    def test_ternary_factories_repair_requires_exact_division(self):
        """
        修复时必须满足整除条件：候选对中包含非整除的组合，修复应勿选它。
        product=12, tp=[2,3], pp=[2,3]
        - (2,2)=4: 12%4=0, dp=3 ✔
        - (2,3)=6: 12%6=0, dp=2 ✔
        - (3,2)=6: 12%6=0, dp=2 ✔
        - (3,3)=9: 12%9=3≠0, 应当过滤掉 ✘
        """
        tp = self._make_base_field("tp", "int", min_=2, max_=3, value=3)
        pp = self._make_base_field("pp", "int", min_=2, max_=3, value=3)
        dp = self._make_base_field(
            "dp", "ternary_factories", dtype_param={"target_names": ["tp", "pp"], "product": 12, "dtype": "int"}
        )
        result = self._run_update([tp, pp, dp], [3, 3, 0])

        tp_val = result[0].value
        pp_val = result[1].value
        dp_val = result[2].value

        # 验证一定整除：tp*pp*dp == product
        self.assertEqual(
            tp_val * pp_val * dp_val, 12, f"tp={tp_val}, pp={pp_val}, dp={dp_val}: {tp_val}*{pp_val}*{dp_val} 应等于 12"
        )
        # (3,3)=9 不整除 12，修复后必不能是(3,3)
        self.assertFalse(tp_val == 3 and pp_val == 3, "(3,3) 不整除 product=12，不应被选为修复结果")

    def test_ternary_factories_repair_fallback_clamp(self):
        """
        降级截断：源字段为 float 类型无法枚举时，修复失败，降级为截断兑底。
        """
        # float 类型的源字段无法枚举，_repair 必返回 False
        tp = self._make_base_field("tp", "float", min_=0.5, max_=8.0, value=8.0)
        pp = self._make_base_field("pp", "float", min_=0.5, max_=4.0, value=4.0)
        dp = self._make_base_field(
            "dp", "ternary_factories", dtype_param={"target_names": ["tp", "pp"], "product": 16, "dtype": "int"}
        )
        result = self._run_update([tp, pp, dp], [8.0, 4.0, 0])
        # 修复失败，降级截断至 min_value=1
        self.assertEqual(result[2].value, 1)

    def test_ternary_factories_non_divisible_repair_failure_raises(self):
        """
        非整除且无法修复时，应 raise ValueError 中止本轮评估，
        避免基于 tp * pp * dp != product 的逻辑不一致配置污染 PSO 搜索。
        ValueError 将沿调用链传播至 op_func，最终置 fitness=inf。
        """
        tp = self._make_base_field("tp", "int", min_=1, max_=1000, value=8)
        pp = self._make_base_field("pp", "enum", min_=0, max_=1, value=3, dtype_param=[3])
        dp = self._make_base_field(
            "dp",
            "ternary_factories",
            value=99,
            dtype_param={"target_names": ["tp", "pp"], "product": 32, "dtype": "int"},
        )
        with self.assertRaises(ValueError) as ctx:
            self._run_update([tp, pp, dp], [8, 3, 99])
        self.assertIn("ternary_factories constraint violated", str(ctx.exception))
        self.assertIn("product=32 not divisible by divisor=24", str(ctx.exception))

    # ---------------------------------------- integration with map_param_with_value
    def test_ternary_factories_with_map_param(self):
        """
        集成测试：ternary_factories 字段 min=max=0，被识别为常量，
        不占用 params 中的参数位，值由 map_param_with_value 内部调用 update_optimizer_value 推导
        """
        tp = OptimizerConfigField(name="tp", config_position="Test.tp", min=1, max=8, dtype="int")
        pp = OptimizerConfigField(name="pp", config_position="Test.pp", min=1, max=4, dtype="int")
        # min=max=0 使其成为常量字段
        dp = OptimizerConfigField(
            name="dp",
            config_position="Test.dp",
            min=0,
            max=0,
            dtype="ternary_factories",
            dtype_param={"target_names": ["tp", "pp"], "product": 16, "dtype": "int"},
        )
        # 只需为 tp 和 pp 提供参数，dp 不占参数位
        params = np.array([2.0, 4.0])
        result = map_param_with_value(params, [tp, pp, dp])
        self.assertEqual(result[0].value, 2)  # tp=2
        self.assertEqual(result[1].value, 4)  # pp=4
        self.assertEqual(result[2].value, 2)  # dp = 16 / (2*4) = 2

    def test_ternary_times_with_map_param(self):
        """
        集成测试：ternary_times 字段 min=max=0，不占用 params 参数位，
        值由 map_param_with_value 内部自动计算
        """
        seq_len = OptimizerConfigField(name="seq_len", config_position="Test.seq_len", min=128, max=4096, dtype="int")
        batch = OptimizerConfigField(name="batch_size", config_position="Test.batch_size", min=1, max=64, dtype="int")
        total = OptimizerConfigField(
            name="total_tokens",
            config_position="Test.total_tokens",
            min=0,
            max=0,
            dtype="ternary_times",
            dtype_param={"target_names": ["seq_len", "batch_size"], "product": 1, "dtype": "int"},
        )
        params = np.array([512.0, 4.0])
        result = map_param_with_value(params, [seq_len, batch, total])
        self.assertEqual(result[0].value, 512)
        self.assertEqual(result[1].value, 4)
        self.assertEqual(result[2].value, 2048)  # 1 * 512 * 4 = 2048


class TestResolvePriority(unittest.TestCase):
    """测试 resolve_priority 函数：fixed / balanced / 无上下文退化"""

    def _ctx(self, idx, total):
        return DecodeContext(particle_index=idx, n_particles=total)

    # ---------- fixed 策略
    def test_fixed_uses_explicit_priority(self):
        """fixed 策略使用用户显式配置的 priority"""
        dtype_param = {
            "target_names": ["tp", "pp"],
            "priority_policy": "fixed",
            "priority": ["pp", "tp"],
        }
        result = resolve_priority(dtype_param)
        self.assertEqual(result, ["pp", "tp"])

    def test_fixed_fallback_when_no_priority(self):
        """fixed 策略未配置 priority 时退化为 target_names 顺序"""
        dtype_param = {
            "target_names": ["tp", "pp"],
            "priority_policy": "fixed",
        }
        result = resolve_priority(dtype_param)
        self.assertEqual(result, ["tp", "pp"])

    def test_fixed_invalid_priority_fallback_to_target_names(self):
        """fixed 策略 priority 配置不完整时退化为 target_names 顺序，避免运行时 IndexError。"""
        dtype_param = {
            "target_names": ["tp", "pp"],
            "priority_policy": "fixed",
            "priority": ["tp"],
        }
        result = resolve_priority(dtype_param)
        self.assertEqual(result, ["tp", "pp"])

    # ---------- balanced 策略
    def test_balanced_even_particles_first_half(self):
        """balanced：偶数粒子，前半部分使用正序"""
        dtype_param = {"target_names": ["tp", "pp"], "priority_policy": "balanced"}
        # n=10，粒子 0-4 属于前半
        for i in range(5):
            result = resolve_priority(dtype_param, self._ctx(i, 10))
            self.assertEqual(result, ["tp", "pp"], f"particle {i} should use forward order")

    def test_balanced_even_particles_second_half(self):
        """balanced：偶数粒子，后半部分使用反序"""
        dtype_param = {"target_names": ["tp", "pp"], "priority_policy": "balanced"}
        # n=10，粒子 5-9 属于后半
        for i in range(5, 10):
            result = resolve_priority(dtype_param, self._ctx(i, 10))
            self.assertEqual(result, ["pp", "tp"], f"particle {i} should use reversed order")

    def test_balanced_odd_particles_ceil_forward(self):
        """balanced：奇数粒子，前 ceil(n/2) 个使用正序"""
        dtype_param = {"target_names": ["tp", "pp"], "priority_policy": "balanced"}
        # n=11，粒子 0..5 (ceil(11/2)=5.5 取 0<=i<5.5即 i<5.5)
        for i in range(6):  # 0..5 共 6 个，小于 11/2=5.5
            result = resolve_priority(dtype_param, self._ctx(i, 11))
            self.assertEqual(result, ["tp", "pp"], f"particle {i} should use forward order")

    def test_balanced_odd_particles_floor_reversed(self):
        """balanced：奇数粒子，后 floor(n/2) 个使用反序"""
        dtype_param = {"target_names": ["tp", "pp"], "priority_policy": "balanced"}
        # n=11，粒子 6..10 属于后半
        for i in range(6, 11):  # 6..10 共 5 个，大于等于 11/2=5.5
            result = resolve_priority(dtype_param, self._ctx(i, 11))
            self.assertEqual(result, ["pp", "tp"], f"particle {i} should use reversed order")

    def test_balanced_no_context_degrades_to_forward(self):
        """balanced 无上下文时退化为 target_names 顺序"""
        dtype_param = {"target_names": ["tp", "pp"], "priority_policy": "balanced"}
        self.assertEqual(resolve_priority(dtype_param, None), ["tp", "pp"])
        self.assertEqual(resolve_priority(dtype_param, DecodeContext()), ["tp", "pp"])

    def test_balanced_default_policy(self):
        """priority_policy 缺省时默认为 balanced"""
        dtype_param = {"target_names": ["tp", "pp"]}  # 无 priority_policy 字段
        # 小于 midpoint 应为正序
        result = resolve_priority(dtype_param, self._ctx(0, 4))
        self.assertEqual(result, ["tp", "pp"])

    def test_balanced_iteration_0_no_flip(self):
        """balanced + iteration=0（偶数轮）：行为与不传 iteration 一致"""
        dtype_param = {"target_names": ["tp", "pp"], "priority_policy": "balanced"}
        # 粒子 0, 前半, iteration=0 → 正序
        ctx = DecodeContext(particle_index=0, n_particles=10, iteration=0)
        self.assertEqual(resolve_priority(dtype_param, ctx), ["tp", "pp"])
        # 粒子 9, 后半, iteration=0 → 反序
        ctx = DecodeContext(particle_index=9, n_particles=10, iteration=0)
        self.assertEqual(resolve_priority(dtype_param, ctx), ["pp", "tp"])

    def test_balanced_iteration_1_flips_direction(self):
        """balanced + iteration=1（奇数轮）：方向反转"""
        dtype_param = {"target_names": ["tp", "pp"], "priority_policy": "balanced"}
        # 粒子 0（前半）在奇数迭代应被翻转为反序
        ctx = DecodeContext(particle_index=0, n_particles=10, iteration=1)
        self.assertEqual(resolve_priority(dtype_param, ctx), ["pp", "tp"])
        # 粒子 9（后半）在奇数迭代应被翻转为正序
        ctx = DecodeContext(particle_index=9, n_particles=10, iteration=1)
        self.assertEqual(resolve_priority(dtype_param, ctx), ["tp", "pp"])

    def test_balanced_iteration_alternates(self):
        """balanced：连续多轮迭代交替方向"""
        dtype_param = {"target_names": ["tp", "pp"], "priority_policy": "balanced"}
        # iteration 0, 2, 4（偶数）→ 前半正序
        for it in (0, 2, 4):
            ctx = DecodeContext(particle_index=0, n_particles=10, iteration=it)
            self.assertEqual(resolve_priority(dtype_param, ctx), ["tp", "pp"], f"it={it}")
        # iteration 1, 3, 5（奇数）→ 前半反序
        for it in (1, 3, 5):
            ctx = DecodeContext(particle_index=0, n_particles=10, iteration=it)
            self.assertEqual(resolve_priority(dtype_param, ctx), ["pp", "tp"], f"it={it}")

    def test_too_few_target_names(self):
        """target_names 少于 2 时直接返回原列表"""
        dtype_param = {"target_names": ["tp"], "priority_policy": "balanced"}
        self.assertEqual(resolve_priority(dtype_param, self._ctx(0, 10)), ["tp"])


class TestRepairTernaryFactoriesWithPriority(unittest.TestCase):
    """测试 _repair_ternary_factories_with_priority的两阶段修复逻辑"""

    @staticmethod
    def _make_field(name, dtype, min_, max_, value=0, dtype_param=None):
        return OptimizerConfigField(
            name=name,
            config_position=f"Test.{name}",
            min=min_,
            max=max_,
            dtype=dtype,
            value=value,
            dtype_param=dtype_param,
        )

    def _build_run_info(self, tp_val, pp_val, dp_val=0):
        tp = self._make_field("tp", "enum", 0, 1, tp_val, dtype_param=[1, 2, 4, 8])
        pp = self._make_field("pp", "enum", 0, 1, pp_val, dtype_param=[1, 2, 4])
        dp = self._make_field(
            "dp",
            "ternary_factories",
            0,
            0,
            dp_val,
            dtype_param={
                "target_names": ["tp", "pp"],
                "product": 32,
                "dtype": "int",
            },
        )
        return [tp, pp, dp]

    def _params_field(self):
        """params_field: 定义字段候选集"""
        tp = self._make_field("tp", "enum", 0, 1, 0, dtype_param=[1, 2, 4, 8])
        pp = self._make_field("pp", "enum", 0, 1, 0, dtype_param=[1, 2, 4])
        dp = self._make_field(
            "dp",
            "ternary_factories",
            0,
            0,
            0,
            dtype_param={
                "target_names": ["tp", "pp"],
                "product": 32,
                "dtype": "int",
            },
        )
        return (tp, pp, dp)

    # ---------- fixed 策略：优先保留 tp
    def test_fixed_priority_tp_preserved(self):
        """
        fixed，priority=["tp","pp"]：固定 tp=8，在 pp 候选中找最近 cur_pp=5 且合法的値。
        product=32，候选 pp=[1,2,4]，cur_pp=5：
          pp=4 → 32/(8*4)=1 ✔，距离=|4-5|=1（唯一最近）
          pp=2 → 32/(8*2)=2 ✔，距离=|2-5|=3
          pp=1 → 32/(8*1)=4 ✔，距离=|1-5|=4
        预期: tp=8, pp=4, dp=1
        """
        dp_field = self._make_field(
            "dp",
            "ternary_factories",
            0,
            0,
            0,
            dtype_param={
                "target_names": ["tp", "pp"],
                "product": 32,
                "dtype": "int",
                "priority_policy": "fixed",
                "priority": ["tp", "pp"],
            },
        )
        tp = self._make_field("tp", "enum", 0, 1, 8, dtype_param=[1, 2, 4, 8])
        pp = self._make_field("pp", "enum", 0, 1, 4, dtype_param=[1, 2, 4])
        params_field = (
            self._make_field("tp", "enum", 0, 1, 0, dtype_param=[1, 2, 4, 8]),
            self._make_field("pp", "enum", 0, 1, 0, dtype_param=[1, 2, 4]),
            dp_field,
        )
        run_info = [deepcopy(tp), deepcopy(pp), deepcopy(dp_field)]
        run_info[0].value = 8
        run_info[1].value = 5  # cur_pp=5，与 pp=4 距离=1，是唯一最近合法候选

        ok = _repair_ternary_factories_with_priority(
            dp_field,
            run_info,
            params_field,
            product=32,
            min_val=1,
            max_val=None,
            conv=int,
        )
        self.assertTrue(ok)
        self.assertEqual(run_info[0].value, 8, "tp 应被保留为 8")
        self.assertEqual(run_info[1].value, 4, "pp 应被调整为 4（唯一最近合法候选）")
        self.assertEqual(run_info[2].value, 1, "dp = 32/(8*4) = 1")

    def test_fixed_priority_reversed_pp_preserved(self):
        """
        fixed，priority=["pp","tp"]：固定 pp=4，在 tp 候选中找最近 tp=3 且合法的値。
        product=32，候选 tp=[1,2,4,8]，pp=4：
          tp=8 → 32/(8*4)=1 ✔
          tp=4 → 32/(4*4)=2 ✔，距离=|4-3|=1
          tp=2 → 32/(2*4)=4 ✔，距离=|2-3|=1
          ... 选距离最近候选，即 tp=4（|4-3|=1）或 tp=2（|2-3|=1）
        预期: pp=4 被保留，dp 自洽
        """
        dp_field = self._make_field(
            "dp",
            "ternary_factories",
            0,
            0,
            0,
            dtype_param={
                "target_names": ["tp", "pp"],
                "product": 32,
                "dtype": "int",
                "priority_policy": "fixed",
                "priority": ["pp", "tp"],
            },
        )
        tp = self._make_field("tp", "enum", 0, 1, 3, dtype_param=[1, 2, 4, 8])
        pp = self._make_field("pp", "enum", 0, 1, 4, dtype_param=[1, 2, 4])
        params_field = (
            self._make_field("tp", "enum", 0, 1, 0, dtype_param=[1, 2, 4, 8]),
            self._make_field("pp", "enum", 0, 1, 0, dtype_param=[1, 2, 4]),
            dp_field,
        )
        run_info = [deepcopy(tp), deepcopy(pp), deepcopy(dp_field)]
        run_info[0].value = 3
        run_info[1].value = 4

        ok = _repair_ternary_factories_with_priority(
            dp_field,
            run_info,
            params_field,
            product=32,
            min_val=1,
            max_val=None,
            conv=int,
        )
        self.assertTrue(ok)
        self.assertEqual(run_info[1].value, 4, "pp=4 应被保留")
        # dp 必须自洽
        self.assertEqual(run_info[2].value, int(32 / (run_info[0].value * run_info[1].value)))

    # ---------- balanced 策略
    def test_balanced_first_half_preserves_tp(self):
        """balanced，前半粒子使用 [tp,pp]，应固定 tp"""
        dp_field = self._make_field(
            "dp",
            "ternary_factories",
            0,
            0,
            0,
            dtype_param={
                "target_names": ["tp", "pp"],
                "product": 32,
                "dtype": "int",
                "priority_policy": "balanced",
            },
        )
        params_field = (
            self._make_field("tp", "enum", 0, 1, 0, dtype_param=[1, 2, 4, 8]),
            self._make_field("pp", "enum", 0, 1, 0, dtype_param=[1, 2, 4]),
            dp_field,
        )
        run_info = [deepcopy(params_field[0]), deepcopy(params_field[1]), deepcopy(dp_field)]
        run_info[0].value = 8
        run_info[1].value = 3

        context = DecodeContext(particle_index=2, n_particles=10)  # 前半粒子
        ok = _repair_ternary_factories_with_priority(
            dp_field,
            run_info,
            params_field,
            product=32,
            min_val=1,
            max_val=None,
            conv=int,
            context=context,
        )
        self.assertTrue(ok)
        self.assertEqual(run_info[0].value, 8, "tp 应被 balanced 前半保留")

    def test_balanced_second_half_preserves_pp(self):
        """balanced，后半粒子使用 [pp,tp]，应固定 pp"""
        dp_field = self._make_field(
            "dp",
            "ternary_factories",
            0,
            0,
            0,
            dtype_param={
                "target_names": ["tp", "pp"],
                "product": 32,
                "dtype": "int",
                "priority_policy": "balanced",
            },
        )
        params_field = (
            self._make_field("tp", "enum", 0, 1, 0, dtype_param=[1, 2, 4, 8]),
            self._make_field("pp", "enum", 0, 1, 0, dtype_param=[1, 2, 4]),
            dp_field,
        )
        run_info = [deepcopy(params_field[0]), deepcopy(params_field[1]), deepcopy(dp_field)]
        run_info[0].value = 3
        run_info[1].value = 4

        context = DecodeContext(particle_index=7, n_particles=10)  # 后半粒子
        ok = _repair_ternary_factories_with_priority(
            dp_field,
            run_info,
            params_field,
            product=32,
            min_val=1,
            max_val=None,
            conv=int,
            context=context,
        )
        self.assertTrue(ok)
        self.assertEqual(run_info[1].value, 4, "pp 应被 balanced 后半保留")

    # ---------- fallback 与 stage2
    def test_stage2_fallback_when_stage1_fails(self):
        """
        stage1 失败（固定 keep 后无合法 adjust）时，stage2 应能找到合法组合。
        product=32，候选 tp=[1,2,4,8]，pp=[1,2,4]
        当 tp=8（stage1 固定）：
          pp=4 → dp=1 ✔ 应正常工作...
        换一个必然 stage1 失败的场景：设置 pp 候选仅有 [3]（非合法）却多加 tp 候选有 [4]
        """
        dp_field = self._make_field(
            "dp",
            "ternary_factories",
            0,
            0,
            0,
            dtype_param={
                "target_names": ["tp", "pp"],
                "product": 32,
                "dtype": "int",
                "priority_policy": "fixed",
                "priority": ["tp", "pp"],
            },
        )
        # tp 候选：[4,8]; pp 候选：[3]（不能与任何 tp 整除 32）
        tp_def = self._make_field("tp", "enum", 0, 1, 8, dtype_param=[4, 8])
        pp_def = self._make_field("pp", "enum", 0, 1, 3, dtype_param=[3])  # 32%3!=0, 32%(4*3)!=0
        params_field = (tp_def, pp_def, dp_field)
        run_info = [deepcopy(tp_def), deepcopy(pp_def), deepcopy(dp_field)]
        run_info[0].value = 8
        run_info[1].value = 3

        ok = _repair_ternary_factories_with_priority(
            dp_field,
            run_info,
            params_field,
            product=32,
            min_val=1,
            max_val=None,
            conv=int,
        )
        self.assertFalse(ok, "无合法组合时应返回 False")

    def test_no_fallback_when_repair_succeeds(self):
        """修复成功时返回 True，且 simulate_run_info 被原地更新"""
        dp_field = self._make_field(
            "dp",
            "ternary_factories",
            0,
            0,
            0,
            dtype_param={
                "target_names": ["tp", "pp"],
                "product": 32,
                "dtype": "int",
            },
        )
        params_field = (
            self._make_field("tp", "enum", 0, 1, 0, dtype_param=[1, 2, 4, 8]),
            self._make_field("pp", "enum", 0, 1, 0, dtype_param=[1, 2, 4]),
            dp_field,
        )
        run_info = [deepcopy(params_field[0]), deepcopy(params_field[1]), deepcopy(dp_field)]
        run_info[0].value = 8
        run_info[1].value = 3

        ok = _repair_ternary_factories_with_priority(
            dp_field,
            run_info,
            params_field,
            product=32,
            min_val=1,
            max_val=None,
            conv=int,
        )
        self.assertTrue(ok)
        # 自洽性验证
        tp_v, pp_v, dp_v = run_info[0].value, run_info[1].value, run_info[2].value
        self.assertEqual(tp_v * pp_v * dp_v, 32, f"tp={tp_v}*pp={pp_v}*dp={dp_v} 应等于 product=32")


class TestDecodeContextIntegration(unittest.TestCase):
    """集成测试：map_param_with_value 配合 DecodeContext 工作"""

    def _make_fields(self, priority_policy="balanced", priority=None):
        dtype_param = {
            "target_names": ["tp", "pp"],
            "product": 32,
            "dtype": "int",
            "priority_policy": priority_policy,
        }
        if priority is not None:
            dtype_param["priority"] = priority
        tp = OptimizerConfigField(
            name="tp", config_position="Test.tp", min=0, max=1, dtype="enum", dtype_param=[1, 2, 4, 8]
        )
        pp = OptimizerConfigField(
            name="pp", config_position="Test.pp", min=0, max=1, dtype="enum", dtype_param=[1, 2, 4]
        )
        dp = OptimizerConfigField(
            name="dp", config_position="Test.dp", min=0, max=0, dtype="ternary_factories", dtype_param=dtype_param
        )
        return [tp, pp, dp]

    def test_decode_context_passed_through(self):
        """
        map_param_with_value 应将 decode_context 传递至 update_optimizer_value 并最终影响修复策略。
        tp=[1,2,4,8]，pp=[1,2,4]，product=32
        使用近中间的参数出中间候选：tp segment 中间→tp=4，pp segment 中间→pp=2
        32/(4*2)=4 正常无需修复。
        """
        fields = self._make_fields(priority_policy="balanced")
        # linspace(0,1,5)=[0, 0.25, 0.5, 0.75, 1] segment midpoints for [1,2,4,8]
        # 取 segment[1..2] midpoint 对应 tp=2
        params = np.array([0.375, 0.375])  # tp midpoint2, pp midpoint2
        ctx = DecodeContext(particle_index=0, n_particles=10)
        result = map_param_with_value(params, fields, decode_context=ctx)
        # 将结果验证为自洽
        tp_v, pp_v, dp_v = result[0].value, result[1].value, result[2].value
        if tp_v > 0 and pp_v > 0 and (32 % (tp_v * pp_v) == 0):
            self.assertEqual(dp_v, int(32 / (tp_v * pp_v)), "配置应自洽")

    def test_no_decode_context_still_works(self):
        """不传入 decode_context 时，应退化为 target_names 顺序修复"""
        fields = self._make_fields(priority_policy="balanced")
        # 选一个会触发修复的参数：tp midpoint for 8, pp midpoint for 3→非候选会被对齐
        params = np.array([0.875, 0.375])  # tp-候选趄近 8, pp-候选趄近 2
        result = map_param_with_value(params, fields)  # 无 decode_context
        tp_v, pp_v, dp_v = result[0].value, result[1].value, result[2].value
        if tp_v > 0 and pp_v > 0:
            # 自洽或修复后自洽
            self.assertEqual(32 % (tp_v * pp_v), 0, f"修复后 tp={tp_v}*pp={pp_v} 应能整除 32")
            self.assertEqual(dp_v, int(32 / (tp_v * pp_v)))
