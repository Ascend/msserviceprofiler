# -------------------------------------------------------------------------
# pylint: disable=logging-fstring-interpolation
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

"""
vLLM 框架适配器。

职责：
- 框架特定的配置加载
- 版本检测
- 初始化 SymbolWatchFinder + HookController
- 对外暴露 enable_hooks/disable_hooks

依赖：
- HookController（控制层）
- SymbolWatchFinder（执行层）
"""

import os
import sys
from typing import Optional, Tuple, Callable

from ..core.utils import parse_version_tuple, check_profiling_enabled, install_symbol_watcher, get_package_version
from ..core.config_loader import ConfigLoader, ProfilingConfig, MetricsConfig
from ..core.symbol_watcher import SymbolWatchFinder
from ..core.hook_controller import HookController
from ..core.logger import logger
from ms_service_profiler.patcher.vllm.metrics.initialize import setup_vllm_metrics


def _is_registry_subprocess() -> bool:
    """当前进程是否以 python -m vllm.model_executor.models.registry 启动的子进程。
    该子进程内不应安装 SymbolWatchFinder，否则会破坏 import 顺序导致 RuntimeWarning/SIGSEGV。
    """
    if len(sys.argv) >= 3 and sys.argv[1] == "-m" and sys.argv[2] == "vllm.model_executor.models.registry":
        return True
    return False


def _clear_hook_trace_runtime() -> None:
    from ms_service_profiler.tracer.hook_runtime import get_hook_trace_runtime

    get_hook_trace_runtime().clear()


class VLLMProfiler:
    """vLLM 框架适配器。

    该类只负责 vLLM 特定的逻辑：
    - 配置文件路径查找
    - vLLM 版本检测
    - handlers 导入

    hook 的启用/禁用由 HookController 统一管理。
    """

    def __init__(self):
        """初始化 vLLM Profiler。"""
        self._vllm_use_v1 = VLLMProfiler._detect_version()
        self._vllm_version = VLLMProfiler._get_vllm_version()
        self._controller: Optional[HookController] = None
        self._initialized = False
        self._profiling_requested = True
        self._profiling_active = True
        self._tracing_requested = False

    # -------------------------------------------------------------------------
    # 版本检测
    # -------------------------------------------------------------------------

    @staticmethod
    def _determine_v1_default() -> str:
        """根据已安装的 vLLM 版本自动决定默认 V1 使用情况。"""
        try:
            vllm_version = get_package_version("vllm")
            if vllm_version is None:
                raise ValueError("Could not get vllm version")
            major, minor, patch = parse_version_tuple(vllm_version)
            use_v1 = (major, minor, patch) >= (0, 9, 2)
            return "1" if use_v1 else "0"
        except Exception:
            return "0"

    @staticmethod
    def _detect_version() -> str:
        """检测 vLLM 版本。"""
        return VLLMProfiler._determine_v1_default()

    @staticmethod
    def _get_vllm_version() -> Optional[str]:
        """获取 vLLM 版本号。"""
        return get_package_version("vllm")

    # -------------------------------------------------------------------------
    # 配置加载
    # -------------------------------------------------------------------------

    @staticmethod
    def _find_default_config_path() -> Optional[str]:
        """查找默认配置文件路径（仅本地或用户目录，不含环境变量）。"""
        try:
            local_candidate = os.path.join(os.path.dirname(__file__), 'config', 'service_profiling_symbols.yaml')
            if os.path.isfile(local_candidate):
                logger.debug(f"Loading profiling symbols from local config file: {local_candidate}")
                return local_candidate
        except Exception as e:
            logger.warning(f"Failed to find profiling symbols from local project: {e}")
        try:
            try:
                import vllm  # type: ignore

                vllm_version = getattr(vllm, '__version__', None)
            except Exception as e:
                logger.debug(f"vllm not available for version detection: {e}")
                vllm_version = None
            try:
                from vllm_ascend import register_service_profiling  # type: ignore

                register_service_profiling()
            except Exception as e:
                logger.debug(f"Cannot using register_service_profiling to get default symbols config: {e}")
            if vllm_version:
                home_dir = os.path.expanduser('~')
                candidate = os.path.join(
                    home_dir,
                    '.config',
                    'vllm_ascend',
                    f"service_profiling_symbols.{vllm_version}.yaml",
                )
                if os.path.isfile(candidate):
                    logger.debug(f"Loading profiling symbols from user config: {candidate}")
                    return candidate
        except Exception as e:
            logger.warning(f"Failed to find profiling symbols from default path: {e}")
        return None

    @staticmethod
    def _get_default_metrics_config_path() -> str:
        """返回默认 Meta 配置路径（始终存在）。"""
        return os.path.join(os.path.dirname(__file__), "config", "service_metrics_symbols_default.yaml")

    @classmethod
    def _find_metrics_config_path(cls) -> Optional[str]:
        """查找用户 metrics 配置路径：环境变量 METRIC_SYMBOLS_PATH（.yaml/.yml）或本地 config/service_metrics_symbols.yaml。"""
        path = None
        env_path = os.environ.get("METRIC_SYMBOLS_PATH")
        if env_path and str(env_path).lower().endswith((".yaml", ".yml")) and os.path.isfile(env_path):
            path = env_path
        if path is None:
            local = os.path.join(os.path.dirname(__file__), "config", "service_metrics_symbols.yaml")
            if os.path.isfile(local):
                path = local
        if path:
            logger.info("Using metrics config path: %s", path)
        return path

    def _load_metrics_config(self, just_default: bool = False) -> Optional[MetricsConfig]:
        """加载 metrics 配置：始终加载默认 Meta 配置，再合并用户配置（除非 just_default=True）。"""
        default_cfg: Optional[MetricsConfig] = None
        default_path = self._get_default_metrics_config_path()
        if os.path.isfile(default_path):
            try:
                default_cfg = ConfigLoader(default_path, self._vllm_version).load_metrics()
                if default_cfg.concrete or default_cfg.patterns:
                    logger.info("Loaded default metrics config from: %s", default_path)
            except Exception as e:
                logger.warning("Failed to load default metrics config from %s: %s", default_path, e)
        if just_default:
            return default_cfg if (default_cfg and (default_cfg.concrete or default_cfg.patterns)) else None
        user_path = self._find_metrics_config_path()
        user_cfg: Optional[MetricsConfig] = None
        if user_path:
            try:
                user_cfg = ConfigLoader(user_path, self._vllm_version).load_metrics()
            except Exception as e:
                logger.warning("Failed to load metrics config from %s: %s", user_path, e)
        merged = MetricsConfig.merge(default_cfg, user_cfg)
        return merged if (merged and (merged.concrete or merged.patterns)) else None

    def _load_profiling_config(self) -> Optional[ProfilingConfig]:
        """加载 profiling 配置文件并返回 ProfilingConfig（concrete + patterns）。"""

        def _load_symbols(path: str) -> ProfilingConfig:
            return ConfigLoader(path, self._vllm_version).load_profiling(
                enable_profiling=self._profiling_active,
                enable_tracing=self._tracing_requested,
            )

        def _write_profiling_symbols(env_path: str, default_cfg: str) -> Optional[ProfilingConfig]:
            try:
                parent_dir = os.path.dirname(env_path) or '.'
                os.makedirs(parent_dir, exist_ok=True)
                with open(default_cfg, 'r', encoding='utf-8') as src, open(env_path, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
                logger.debug(f"Wrote profiling symbols to env path: {env_path}")
                logger.info("Loading vLLM profiling symbols from: %s", env_path)
                return _load_symbols(env_path)
            except Exception as e:
                logger.warning(f"Failed to write profiling symbols to env path {env_path}: {e}")
                return None

        default_cfg = self._find_default_config_path()
        env_path = os.environ.get('PROFILING_SYMBOLS_PATH')
        if env_path and str(env_path).lower().endswith(('.yaml', '.yml')):
            if os.path.isfile(env_path):
                logger.info("Loading vLLM profiling symbols from: %s", env_path)
                return _load_symbols(env_path)
            if default_cfg:
                return _write_profiling_symbols(env_path, default_cfg)
            logger.warning("No default config file found to populate PROFILING_SYMBOLS_PATH")
        elif env_path and not str(env_path).lower().endswith(('.yaml', '.yml')):
            logger.warning(f"PROFILING_SYMBOLS_PATH is not a yaml file: {env_path}")

        if default_cfg:
            logger.info("Loading vLLM profiling symbols from: %s", default_cfg)
            return _load_symbols(default_cfg)
        logger.warning("No config file found")
        return None

    def _load_metric_handlers_only(self, just_default: bool = False) -> Optional[MetricsConfig]:
        """仅加载 metric 的 yaml 配置，返回 MetricsConfig（不加载 profiling）。
        仅由 C++ 的 startMetricCallback/stop 触发时调用；just_default=True 时只返回默认配置（不合并用户配置）。
        """
        return self._load_metrics_config(just_default=just_default)

    def _load_config(self) -> Tuple[Optional[ProfilingConfig], Optional[MetricsConfig]]:
        """加载 profiling 配置并返回；metrics 由 C++ 通过 on_start_metric 回调单独控制，此处不读 JSON。"""
        profiling = self._load_profiling_config()
        metrics = None
        return (profiling, metrics)

    # -------------------------------------------------------------------------
    # 初始化
    # -------------------------------------------------------------------------

    def _import_handlers(self):
        """按版本导入内置 handlers。"""
        if self._vllm_use_v1 == "0":
            logger.debug("Initializing service profiler with vLLM V0 interface")
            from .handlers.v0 import batch_handlers, kvcache_handlers, model_handlers, request_handlers  # noqa: F401
        elif self._vllm_use_v1 == "1":
            logger.debug("Initializing service profiler with vLLM V1 interface")
            from .handlers.v1 import batch_handlers, kvcache_handlers, meta_handlers, model_handlers, request_handlers  # noqa: F401
        else:
            logger.error(
                f"unknown vLLM interface version: auto_detected={self._vllm_use_v1}, vllm_version={self._vllm_version}"
            )

    def initialize(self) -> bool:
        """初始化服务分析器。

        执行完整的初始化流程：
        1. 检查环境变量
        2. 初始化 metrics 模块
        3. 导入内置 handlers
        4. 创建 SymbolWatchFinder 和 HookController
        5. 非 registry 子进程内：与 enable_hooks() 相同流程（load_handlers + 对已有模块 apply + 打开 auto_apply）

        Returns:
            bool: 初始化是否成功
        """
        try:
            self._profiling_requested = check_profiling_enabled()
            self._profiling_active = self._profiling_requested
            self._tracing_requested = os.environ.get("MS_TRACE_ENABLE") == "1"
            if not self._profiling_requested and not self._tracing_requested:
                return False
            logger.debug("Initializing VLLM Service Profiler")

            # 初始化metrics模块逻辑，后续有metrics独立开关后从此处移出
            if self._profiling_requested:
                setup_vllm_metrics()

            # Trace-only startup consumes only YAML metadata and must not import
            # or execute the existing business profiling handlers.
            if self._profiling_requested:
                self._import_handlers()
            # 创建 SymbolWatchFinder（未加载配置）并安装；registry 子进程内不安装，避免破坏 import 顺序
            watcher = SymbolWatchFinder()
            if not _is_registry_subprocess():
                if install_symbol_watcher(watcher):
                    logger.debug("Symbol watcher installed")
            else:
                logger.debug("Skipping symbol watcher install (registry subprocess)")
            self._controller = HookController(watcher)
            if not _is_registry_subprocess():
                self.enable_hooks()
            self._initialized = True
            logger.debug("VLLM Service Profiler initialized successfully")
            return True

        except Exception as e:
            logger.exception("Failed to initialize VLLM Service Profiler: %s", str(e))
            self._initialized = False
            return False

    # -------------------------------------------------------------------------
    # Hooks 生命周期（委托给 HookController）
    # -------------------------------------------------------------------------

    @property
    def initialized(self) -> bool:
        """Profiler 是否已初始化。"""
        return self._initialized

    @property
    def hooks_enabled(self) -> bool:
        """hooks 是否已启用。"""
        if self._controller is None:
            return False
        return self._controller.enabled

    def enable_hooks(self) -> None:
        """启用所有 hooks（先加载 profiling/metrics 配置，再交给 controller.enable）。"""
        if self._controller is None:
            logger.warning("Profiler not initialized, cannot enable hooks")
            return

        profiling, metrics = self._load_config()
        self._controller.enable(profiling_handlers=profiling, metrics_handlers=metrics)

    def disable_hooks(self) -> None:
        """禁用所有 hooks。"""
        if self._controller is None:
            logger.warning("Profiler not initialized, cannot disable hooks")
            if self._tracing_requested:
                _clear_hook_trace_runtime()
            return
        self._controller.disable()
        if self._tracing_requested:
            _clear_hook_trace_runtime()

    # -------------------------------------------------------------------------
    # C++ 回调（委托给 HookController）
    # -------------------------------------------------------------------------

    def get_callbacks(self) -> Tuple[Callable[[], None], Callable[[], None]]:
        """返回可注册到 C++ 的回调函数对（start, stop）。

        Returns:
            (on_start_callback, on_stop_callback)
        """
        if self._controller is None:
            # 如果还没初始化，返回空操作的回调
            def noop():
                logger.warning("Profiler not initialized, callback ignored")

            return noop, noop
        if not self._tracing_requested:
            return self._controller.get_callbacks(self._load_config)

        def on_start():
            try:
                self._profiling_active = self._profiling_requested
                profiling, metrics = self._load_config()
                self._controller.enable(profiling_handlers=profiling, metrics_handlers=metrics)
            except Exception as exc:
                logger.exception("Failed to handle profiler start with tracing enabled: %s", exc)

        def on_stop():
            try:
                self._profiling_active = False
                tracing, metrics = self._load_config()
                self._controller.enable(profiling_handlers=tracing, metrics_handlers=metrics)
            except Exception as exc:
                logger.exception("Failed to keep tracing hooks after profiler stop: %s", exc)

        return on_start, on_stop

    def get_metric_callbacks(self) -> Tuple[Callable[[], None], Callable[[], None]]:
        """返回可注册到 C++ 的 metric 回调函数对（on_start_metric, on_stop_metric）。
        startMetricCallback 时仅加载 metric yaml 并 update_metrics_handlers；
        stopMetricCallback 时 update_metrics_handlers(None) 停止 metric 采集。
        """
        if self._controller is None:

            def noop():
                logger.warning("Profiler not initialized, metric callback ignored")

            return noop, noop

        def on_start_metric() -> None:
            try:
                logger.info("Received metric start signal from C++")
                metrics_handlers = self._load_metric_handlers_only()
                self._controller.update_metrics_handlers(metrics_handlers)
            except Exception as e:
                logger.exception("Failed to handle metric start: %s", e)

        def on_stop_metric() -> None:
            try:
                logger.info("Received metric stop signal from C++")
                metrics_handlers = self._load_metric_handlers_only(just_default=True)
                self._controller.update_metrics_handlers(metrics_handlers)
            except Exception as e:
                logger.exception("Failed to handle metric stop: %s", e)

        return on_start_metric, on_stop_metric

    @property
    def vllm_version(self) -> str:
        """获取 vLLM 版本标识。"""
        return self._vllm_use_v1
