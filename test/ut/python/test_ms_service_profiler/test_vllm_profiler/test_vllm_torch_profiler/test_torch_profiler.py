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

# pylint: disable=redefined-outer-name

"""ms_service_profiler.patcher.vllm.handlers.torch_profiler 单元测试

独立于 test_vllm_profiler 目录，避免 conftest 触发 module_hook/inject/bytecode 导入链。

用例信息表：
| 序号 | 测试类 | 用例名称 | 测试目标 | 前置条件 | 预期结果 |
|------|--------|----------|----------|----------|----------|
| 1 | TestRegisterTorchProfiler | test_register_torch_profiler_given_normal_call_when_invoked_then_calls_register_and_enable_patch_functions | register_torch_profiler | 模块已加载 | 依次调用 patch_model_runner_with_torch_profiler_register、patch_model_runner_with_torch_profiler_enable |
| 2 | TestPatchModelRunnerWithTorchProfilerEnable | test_patch_model_runner_with_torch_profiler_enable_given_npu_worker_exists_when_invoked_then_replaces_npu_worker_profile_method | patch_model_runner_with_torch_profiler_enable | vllm_ascend 可导入 | NPUWorker.profile 被替换为新实现 |
| 3 | TestPatchModelRunnerWithTorchProfilerEnable | test_new_profile_given_is_start_true_when_invoked_then_calls_prof_build_and_prof_start | new_profile (is_start=True) | 已执行 patch | 调用 prof_build、prof_start 各一次 |
| 4 | TestPatchModelRunnerWithTorchProfilerEnable | test_new_profile_given_is_start_false_when_invoked_then_calls_prof_stop | new_profile (is_start=False) | 已执行 patch | 调用 prof_stop 一次 |
| 5 | TestPatchModelRunnerWithTorchProfilerRegister | test_patch_model_runner_with_torch_profiler_register_given_engine_core_exists_when_invoked_then_replaces_initialize_kv_caches_and_preserves_original_behavior | patch_model_runner_with_torch_profiler_register | vllm 可导入，profiler 未启用 | EngineCore._initialize_kv_caches 被替换，原逻辑仍可执行 |
| 6 | TestPatchModelRunnerWithTorchProfilerRegister | test_new_init_kv_caches_given_profiler_enabled_and_step_num_zero_when_initialize_invoked_then_calls_torch_profiler_register | new_init（内部逻辑） | profiler 启用、step_num=0 | 调用 torch_profiler_register 一次 |
| 7 | TestProfStartExecProfStopExec | test_prof_start_exec_given_pointer_with_model_executor_when_invoked_then_calls_model_executor_profile_true | prof_start_exec | pointer 有效且含 model_executor | 调用 model_executor.profile(True) |
| 8 | TestProfStartExecProfStopExec | test_prof_stop_exec_given_pointer_with_model_executor_when_invoked_then_calls_model_executor_profile_false | prof_stop_exec | pointer 有效且含 model_executor | 调用 model_executor.profile(False) |
| 9 | TestProfStartExecProfStopExec | test_prof_start_exec_given_pointer_none_when_invoked_then_raises_attribute_error | prof_start_exec | pointer 为 None | 抛出 AttributeError |
| 10 | TestTorchProfilerRegister | test_torch_profiler_register_given_service_profiler_available_when_invoked_then_registers_prof_start_exec_and_prof_stop_exec_as_callbacks | torch_profiler_register | service_profiler 可用 | 注册 prof_start_exec 为 start 回调、prof_stop_exec 为 stop 回调 |
| 11 | TestProfBuild | test_prof_build_given_service_profiler_configured_when_invoked_then_sets_torch_prof_in_shared_state_under_lock | prof_build | get_shared_state、service_profiler 可 mock | 在 state._lock 下设置 state.torch_prof |
| 12 | TestProfStartProfStop | test_prof_start_given_state_has_torch_prof_when_invoked_then_calls_torch_prof_start | prof_start | state 含 torch_prof | 调用 torch_prof.start() |
| 13 | TestProfStartProfStop | test_prof_start_given_state_without_torch_prof_when_invoked_then_completes_without_error | prof_start | state 无 torch_prof | 不报错、不调用 start |
| 14 | TestProfStartProfStop | test_prof_stop_given_state_has_torch_prof_when_invoked_then_calls_torch_prof_stop | prof_stop | state 含 torch_prof | 调用 torch_prof.stop() |
| 15 | TestRegisterTorchProfiler | test_register_torch_profiler_given_torch_npu_none_when_invoked_then_returns_without_patching | register_torch_profiler | torch_npu 为 None | 直接返回，不调用 patch 函数 |
| 16 | TestProfBuild | test_prof_build_given_torch_npu_none_when_invoked_then_returns_without_building | prof_build | torch_npu 为 None | 直接返回，不构建 profiler |
| 17 | TestProfStartProfStop | test_prof_start_given_torch_npu_none_when_invoked_then_returns_without_error | prof_start | torch_npu 为 None | 直接返回不报错 |
| 18 | TestProfStartProfStop | test_prof_stop_given_torch_npu_none_when_invoked_then_returns_without_error | prof_stop | torch_npu 为 None | 直接返回不报错 |
"""

import os
import sys
import importlib
import importlib.util
from unittest.mock import patch, MagicMock

import pytest


def _load_torch_profiler_from_file():
    """从文件直接加载 torch_profiler，绕过 vllm/__init__.py，避免触发 inject→bytecode 导入链。"""
    # 兼容从项目根或 test/ 目录运行：向上定位包含 ms_service_profiler 的项目根
    test_dir = os.path.dirname(os.path.abspath(__file__))
    proj_root = test_dir
    torch_profiler_path = os.path.join(
        proj_root, "ms_service_profiler", "patcher", "vllm", "handlers", "torch_profiler.py"
    )
    while proj_root and not os.path.isfile(torch_profiler_path):
        parent = os.path.dirname(proj_root)
        if parent == proj_root:
            raise FileNotFoundError(
                f"Cannot find torch_profiler.py from {test_dir}. Run pytest from project root or test/ directory."
            )
        proj_root = parent
        torch_profiler_path = os.path.join(
            proj_root, "ms_service_profiler", "patcher", "vllm", "handlers", "torch_profiler.py"
        )
    # 确保项目根在 sys.path，使 ms_service_profiler 可导入（支持从 test/ 运行）
    if proj_root and proj_root not in sys.path:
        sys.path.insert(0, proj_root)
    spec = importlib.util.spec_from_file_location(
        "ms_service_profiler.patcher.vllm.handlers.torch_profiler",
        torch_profiler_path,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["ms_service_profiler.patcher.vllm.handlers.torch_profiler"] = module
    spec.loader.exec_module(module)
    return module


# 在导入 torch_profiler 之前注入 mock 模块，避免 torch_npu/vllm_ascend/vllm 导入失败
@pytest.fixture(scope="module")
def mock_torch_profiler_deps():
    """为 torch_profiler 提供 mock 依赖（torch_npu、vllm_ascend、vllm）。"""
    mock_torch_npu = MagicMock()
    mock_torch_npu.profiler = MagicMock()
    mock_torch_npu.profiler.ProfilerLevel = MagicMock()
    mock_torch_npu.profiler.ProfilerLevel.Level0 = "L0"
    mock_torch_npu.profiler.ProfilerLevel.Level1 = "L1"
    mock_torch_npu.profiler.ProfilerLevel.Level2 = "L2"
    mock_torch_npu.profiler.ProfilerLevel.Level_none = "none"
    mock_torch_npu.profiler.AiCMetrics = MagicMock()
    mock_torch_npu.profiler.AiCMetrics.ArithmeticUtilization = 0
    mock_torch_npu.profiler.AiCMetrics.PipeUtilization = 1
    mock_torch_npu.profiler.AiCMetrics.Memory = 2
    mock_torch_npu.profiler.AiCMetrics.MemoryL0 = 3
    mock_torch_npu.profiler.AiCMetrics.ResourceConflictRatio = 4
    mock_torch_npu.profiler.AiCMetrics.MemoryUB = 5
    mock_torch_npu.profiler.AiCMetrics.L2Cache = 6
    mock_torch_npu.profiler.AiCMetrics.MemoryAccess = 8
    mock_torch_npu.profiler.AiCMetrics.AiCoreNone = -1
    mock_torch_npu.profiler._ExperimentalConfig = MagicMock(return_value=MagicMock())
    mock_torch_npu.profiler.ProfilerActivity = MagicMock()
    mock_torch_npu.profiler.ProfilerActivity.CPU = "cpu"
    mock_torch_npu.profiler.ProfilerActivity.NPU = "npu"
    mock_torch_npu.profiler.profile = MagicMock(return_value=MagicMock())
    mock_torch_npu.profiler.tensorboard_trace_handler = MagicMock(return_value=MagicMock())
    mock_torch_npu.profiler.ExportType = MagicMock()
    mock_torch_npu.profiler.ExportType.Text = "text"

    mock_npu_worker = MagicMock()
    mock_npu_worker.profile = MagicMock()

    mock_engine_core = MagicMock()

    mock_vllm_ascend = MagicMock()
    mock_vllm_ascend.worker = MagicMock()
    mock_vllm_ascend.worker.worker = MagicMock()
    mock_vllm_ascend.worker.worker.NPUWorker = mock_npu_worker

    mock_vllm = MagicMock()
    mock_vllm.v1 = MagicMock()
    mock_vllm.v1.engine = MagicMock()
    mock_vllm.v1.engine.core = MagicMock()
    mock_vllm.v1.engine.core.EngineCore = mock_engine_core

    mock_vllm_worker = MagicMock()
    mock_vllm_worker.NPUWorker = mock_npu_worker
    mock_vllm_ascend.worker.worker = mock_vllm_worker

    mock_vllm_core = MagicMock()
    mock_vllm_core.EngineCore = mock_engine_core
    mock_vllm.v1.engine.core = mock_vllm_core

    mock_torch = MagicMock()
    with patch.dict(
        "sys.modules",
        {
            "torch": mock_torch,
            "torch_npu": mock_torch_npu,
            "vllm_ascend": mock_vllm_ascend,
            "vllm_ascend.worker": mock_vllm_ascend.worker,
            "vllm_ascend.worker.worker": mock_vllm_worker,
            "vllm": mock_vllm,
            "vllm.v1": mock_vllm.v1,
            "vllm.v1.engine": mock_vllm.v1.engine,
            "vllm.v1.engine.core": mock_vllm_core,
        },
    ):
        yield {
            "torch_npu": mock_torch_npu,
            "NPUWorker": mock_npu_worker,
            "EngineCore": mock_engine_core,
        }


@pytest.fixture
def torch_profiler_module(mock_torch_profiler_deps):
    """从文件直接加载 torch_profiler，绕过 vllm 包初始化（避免 bytecode 依赖）。"""
    mod_name = "ms_service_profiler.patcher.vllm.handlers.torch_profiler"
    mod = sys.modules.get(mod_name)
    if mod is None:
        mod = _load_torch_profiler_from_file()
    return mod


@pytest.fixture
def torch_profiler_module_without_torch_npu():
    """加载 torch_profiler 且 torch_npu 为 None（不注入 torch_npu，import 失败后设为 None）。"""
    mod_name = "ms_service_profiler.patcher.vllm.handlers.torch_profiler"
    # 先从 sys.modules 移除，确保重新加载
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    mock_torch = MagicMock()
    mock_vllm_ascend = MagicMock()
    mock_vllm_ascend.worker = MagicMock()
    mock_vllm_ascend.worker.worker = MagicMock()
    mock_npu_worker = MagicMock()
    mock_vllm_ascend.worker.worker.NPUWorker = mock_npu_worker
    mock_vllm = MagicMock()
    mock_vllm.v1 = MagicMock()
    mock_vllm.v1.engine = MagicMock()
    mock_vllm_core = MagicMock()
    mock_engine_core = MagicMock()
    mock_vllm_core.EngineCore = mock_engine_core
    mock_vllm.v1.engine.core = mock_vllm_core
    # 将 torch_npu 设为 None，使 import torch_npu 稳定触发 ImportError，
    # 模拟未安装 torch_npu 的环境。
    with patch.dict(
        "sys.modules",
        {
            "torch": mock_torch,
            "torch_npu": None,
            "vllm_ascend": mock_vllm_ascend,
            "vllm_ascend.worker": mock_vllm_ascend.worker,
            "vllm_ascend.worker.worker": mock_vllm_ascend.worker,
            "vllm": mock_vllm,
            "vllm.v1": mock_vllm.v1,
            "vllm.v1.engine": mock_vllm.v1.engine,
            "vllm.v1.engine.core": mock_vllm_core,
        },
        clear=False,
    ):
        mod = _load_torch_profiler_from_file()
    return mod


@pytest.fixture(autouse=True)
def reset_torch_profiler_state(torch_profiler_module):
    """每用例执行前重置 pointer 等全局状态。"""
    torch_profiler_module.pointer = None
    yield


class TestRegisterTorchProfiler:
    """测试 register_torch_profiler：注册 torch profiler 时调用的入口函数"""

    def test_register_torch_profiler_given_torch_npu_none_when_invoked_then_returns_without_patching(
        self, torch_profiler_module_without_torch_npu
    ):
        """用例15：torch_npu 为 None 时，直接返回不调用 patch 函数"""
        mod = torch_profiler_module_without_torch_npu
        assert mod.torch_npu is None
        with (
            patch.object(mod, "patch_model_runner_with_torch_profiler_register") as mock_register,
            patch.object(mod, "patch_model_runner_with_torch_profiler_enable") as mock_enable,
        ):
            mod.register_torch_profiler()
            mock_register.assert_not_called()
            mock_enable.assert_not_called()


class TestPatchModelRunnerWithTorchProfilerEnable:
    """测试 patch_model_runner_with_torch_profiler_enable：对 NPUWorker.profile 打补丁"""

    def test_patch_model_runner_with_torch_profiler_enable_given_npu_worker_exists_when_invoked_then_replaces_npu_worker_profile_method(
        self, torch_profiler_module, mock_torch_profiler_deps
    ):
        """用例2：NPUWorker 存在时，调用后将 NPUWorker.profile 替换为新实现"""
        NPUWorker = mock_torch_profiler_deps["NPUWorker"]
        orig_profile = NPUWorker.profile

        torch_profiler_module.patch_model_runner_with_torch_profiler_enable()

        assert NPUWorker.profile != orig_profile
        assert callable(NPUWorker.profile)

    def test_new_profile_given_is_start_true_when_invoked_then_calls_prof_build_and_prof_start(
        self, torch_profiler_module, mock_torch_profiler_deps
    ):
        """用例3：is_start=True 时，new_profile 应调用 prof_build 和 prof_start"""
        with (
            patch.object(torch_profiler_module, "prof_build") as mock_prof_build,
            patch.object(torch_profiler_module, "prof_start") as mock_prof_start,
        ):
            torch_profiler_module.patch_model_runner_with_torch_profiler_enable()
            NPUWorker = mock_torch_profiler_deps["NPUWorker"]
            instance = MagicMock()
            NPUWorker.profile(instance, True)
            mock_prof_build.assert_called_once()
            mock_prof_start.assert_called_once()

    def test_new_profile_given_is_start_false_when_invoked_then_calls_prof_stop(
        self, torch_profiler_module, mock_torch_profiler_deps
    ):
        """用例4：is_start=False 时，new_profile 应调用 prof_stop"""
        with patch.object(torch_profiler_module, "prof_stop") as mock_prof_stop:
            torch_profiler_module.patch_model_runner_with_torch_profiler_enable()
            NPUWorker = mock_torch_profiler_deps["NPUWorker"]
            instance = MagicMock()
            NPUWorker.profile(instance, False)
            mock_prof_stop.assert_called_once()


class TestPatchModelRunnerWithTorchProfilerRegister:
    """测试 patch_model_runner_with_torch_profiler_register：对 EngineCore._initialize_kv_caches 打补丁"""

    def test_patch_model_runner_with_torch_profiler_register_given_engine_core_exists_when_invoked_then_replaces_initialize_kv_caches_and_preserves_original_behavior(
        self, torch_profiler_module, mock_torch_profiler_deps
    ):
        """用例5：EngineCore 存在且 profiler 未启用时，替换 _initialize_kv_caches 并保留原逻辑"""
        EngineCore = mock_torch_profiler_deps["EngineCore"]
        orig_init = MagicMock(return_value="result")
        EngineCore._initialize_kv_caches = orig_init

        with patch.object(torch_profiler_module, "service_profiler") as mock_sp:
            mock_sp.get_torch_prof_step_num.return_value = 0
            mock_sp.is_torch_profiler_enable.return_value = False  # 避免触发 register
            torch_profiler_module.patch_model_runner_with_torch_profiler_register()

            instance = MagicMock()
            result = EngineCore._initialize_kv_caches(instance)
            assert result == "result"
            orig_init.assert_called_once_with(instance)

    def test_new_init_kv_caches_given_profiler_enabled_and_step_num_zero_when_initialize_invoked_then_calls_torch_profiler_register(
        self, torch_profiler_module, mock_torch_profiler_deps
    ):
        """用例6：profiler 启用且 step_num=0 时，_initialize_kv_caches 执行后应调用 torch_profiler_register"""
        EngineCore = mock_torch_profiler_deps["EngineCore"]
        orig_init = MagicMock(return_value="ok")

        with (
            patch.object(torch_profiler_module, "service_profiler") as mock_sp,
            patch.object(torch_profiler_module, "Level", MagicMock(L0=10)),
            patch.object(torch_profiler_module, "torch_profiler_register") as mock_register,
        ):
            mock_sp.get_torch_prof_step_num.return_value = 0
            mock_sp.is_torch_profiler_enable.return_value = True
            EngineCore._initialize_kv_caches = orig_init
            torch_profiler_module.patch_model_runner_with_torch_profiler_register()

            instance = MagicMock()
            EngineCore._initialize_kv_caches(instance)
            mock_register.assert_called_once()


class TestProfStartExecProfStopExec:
    """测试 prof_start_exec、prof_stop_exec：通过 pointer 调用 model_executor.profile"""

    def test_prof_start_exec_given_pointer_with_model_executor_when_invoked_then_calls_model_executor_profile_true(
        self, torch_profiler_module
    ):
        """用例7：pointer 含 model_executor 时，应调用 model_executor.profile(True)"""
        mock_executor = MagicMock()
        torch_profiler_module.pointer = MagicMock(model_executor=mock_executor)

        torch_profiler_module.prof_start_exec()
        mock_executor.profile.assert_called_once_with(True)

    def test_prof_stop_exec_given_pointer_with_model_executor_when_invoked_then_calls_model_executor_profile_false(
        self, torch_profiler_module
    ):
        """用例8：pointer 含 model_executor 时，应调用 model_executor.profile(False)"""
        mock_executor = MagicMock()
        torch_profiler_module.pointer = MagicMock(model_executor=mock_executor)

        torch_profiler_module.prof_stop_exec()
        mock_executor.profile.assert_called_once_with(False)

    def test_prof_start_exec_given_pointer_none_when_invoked_then_raises_attribute_error(self, torch_profiler_module):
        """用例9：pointer 为 None 时，调用应抛出 AttributeError"""
        torch_profiler_module.pointer = None
        with pytest.raises(AttributeError):
            torch_profiler_module.prof_start_exec()


class TestTorchProfilerRegister:
    """测试 torch_profiler_register：向 service_profiler 注册 start/stop 回调"""

    def test_torch_profiler_register_given_service_profiler_available_when_invoked_then_registers_prof_start_exec_and_prof_stop_exec_as_callbacks(
        self, torch_profiler_module
    ):
        """用例10：service_profiler 可用时，应注册 prof_start_exec 和 prof_stop_exec 为回调"""
        with patch.object(torch_profiler_module, "service_profiler") as mock_sp:
            mock_sp.register_profiler_start_callback = MagicMock()
            mock_sp.register_profiler_stop_callback = MagicMock()

            torch_profiler_module.torch_profiler_register()

            mock_sp.register_profiler_start_callback.assert_called_once()
            mock_sp.register_profiler_stop_callback.assert_called_once()
            # 校验注册的回调函数名
            cb_start = mock_sp.register_profiler_start_callback.call_args[0][0]
            cb_stop = mock_sp.register_profiler_stop_callback.call_args[0][0]
            assert cb_start.__name__ == "prof_start_exec"
            assert cb_stop.__name__ == "prof_stop_exec"


class TestProfBuild:
    """测试 prof_build：创建 torch_npu profiler 并存入 shared state"""

    def test_prof_build_given_service_profiler_configured_when_invoked_then_sets_torch_prof_in_shared_state_under_lock(
        self, torch_profiler_module, mock_torch_profiler_deps
    ):
        """用例11：service_profiler 已配置时，应在 state._lock 下设置 state.torch_prof"""
        mock_state = MagicMock()
        mock_state._lock = MagicMock()
        mock_state._lock.__enter__ = MagicMock(return_value=None)
        mock_state._lock.__exit__ = MagicMock(return_value=None)

        with (
            patch.object(torch_profiler_module, "get_shared_state", return_value=mock_state),
            patch.object(torch_profiler_module, "service_profiler") as mock_sp,
        ):
            mock_sp.get_acl_task_time_level.return_value = "L0"
            mock_sp.get_acl_prof_aicore_metrics.return_value = 0
            mock_sp.get_prof_path.return_value = "/tmp/prof"
            mock_sp.is_torch_prof_stack.return_value = False
            mock_sp.is_torch_prof_modules.return_value = False

            torch_profiler_module.prof_build()

            mock_state._lock.__enter__.assert_called_once()
            mock_state._lock.__exit__.assert_called_once()
            assert mock_state.torch_prof is not None

    def test_prof_build_given_torch_npu_none_when_invoked_then_returns_without_building(
        self, torch_profiler_module_without_torch_npu
    ):
        """用例16：torch_npu 为 None 时，直接返回不构建 profiler"""
        mod = torch_profiler_module_without_torch_npu
        assert mod.torch_npu is None
        mod.prof_build()  # 应直接返回，不报错
        # 未调用 get_shared_state 等
        with patch.object(mod, "get_shared_state") as mock_get_state:
            mod.prof_build()
            mock_get_state.assert_not_called()


class TestProfStartProfStop:
    """测试 prof_start、prof_stop：启动/停止 state 中的 torch_prof"""

    def test_prof_start_given_state_has_torch_prof_when_invoked_then_calls_torch_prof_start(
        self, torch_profiler_module
    ):
        """用例12：state 含 torch_prof 时，prof_start 应调用 torch_prof.start()"""
        mock_prof = MagicMock()
        mock_state = MagicMock(torch_prof=mock_prof)

        with patch.object(torch_profiler_module, "get_shared_state", return_value=mock_state):
            torch_profiler_module.prof_start()
            mock_prof.start.assert_called_once()

    def test_prof_start_given_state_without_torch_prof_when_invoked_then_completes_without_error(
        self, torch_profiler_module
    ):
        """用例13：state 无 torch_prof 时，prof_start 应正常返回不报错"""

        # 使用简单对象，无 torch_prof 属性
        class StateWithoutTorchProf:
            _lock = MagicMock()

        mock_state = StateWithoutTorchProf()

        with patch.object(torch_profiler_module, "get_shared_state", return_value=mock_state):
            torch_profiler_module.prof_start()  # 不应抛错

    def test_prof_stop_given_state_has_torch_prof_when_invoked_then_calls_torch_prof_stop(self, torch_profiler_module):
        """用例14：state 含 torch_prof 时，prof_stop 应调用 torch_prof.stop()"""
        mock_prof = MagicMock()
        mock_state = MagicMock(torch_prof=mock_prof)

        with patch.object(torch_profiler_module, "get_shared_state", return_value=mock_state):
            torch_profiler_module.prof_stop()
            mock_prof.stop.assert_called_once()

    def test_prof_start_given_torch_npu_none_when_invoked_then_returns_without_error(
        self, torch_profiler_module_without_torch_npu
    ):
        """用例17：torch_npu 为 None 时，prof_start 直接返回不报错"""
        mod = torch_profiler_module_without_torch_npu
        mod.prof_start()  # 应直接返回

    def test_prof_stop_given_torch_npu_none_when_invoked_then_returns_without_error(
        self, torch_profiler_module_without_torch_npu
    ):
        """用例18：torch_npu 为 None 时，prof_stop 直接返回不报错"""
        mod = torch_profiler_module_without_torch_npu
        mod.prof_stop()  # 应直接返回
