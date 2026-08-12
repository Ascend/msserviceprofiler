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
"""
VLLM Metric Adapter - vLLM框架适配器

提供对vLLM推理框架的适配支持，包括：
- 加载V1版本的handlers
- 初始化SymbolHandlerManager
- 与vLLM的插件系统集成

使用示例:
    >>> from ms_service_metric.adapters.vllm import initialize_vllm_metric
    >>> initialize_vllm_metric()
"""

import multiprocessing
import os
import re
from typing import Optional, Tuple

from ms_service_metric.core.config.provider import ProviderRegistry
from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager
from ms_service_metric.metrics.meta_state import get_meta_state, set_dp_rank
from ms_service_metric.utils.logger import get_logger
from ms_service_metric.utils.version import get_package_version

logger = get_logger(__name__)


class VLLMMetricAdapter:
    """vLLM Metric适配器

    负责：
    1. 设置dp_rank到meta_state
    2. 加载V1版本的配置和handlers
    3. 初始化SymbolHandlerManager
    4. 提供与vLLM生命周期的集成点

    Attributes:
        _manager: SymbolHandlerManager实例
        _initialized: 是否已初始化
    """

    def __init__(self):
        """初始化适配器"""
        self._manager: Optional[SymbolHandlerManager] = None
        self._initialized = False
        self._version: Optional[str] = None

    def initialize(self):
        """初始化适配器

        设置vLLM metrics环境，设置dp_rank，加载配置，初始化管理器。
        """
        if self._initialized:
            logger.debug("VLLMMetricAdapter already initialized")
            return

        logger.info("Initializing VLLMMetricAdapter")

        # 检测vLLM版本
        self._version = self._detect_vllm_version()
        logger.info("Detected vLLM version: %s", self._version)

        # 设置vLLM metrics环境（多进程、registry、前缀等）
        from ms_service_metric.adapters.vllm.metrics_init import setup_vllm_metrics

        setup_vllm_metrics()

        # 设置meta_state的dp_rank
        self._setup_dp_rank()
        self._setup_pd_role()

        # 创建并初始化SymbolHandlerManager（传入版本信息）
        self._manager = SymbolHandlerManager(
            current_version=self._version,
            provider_registry=ProviderRegistry(),
        )

        # 加载vLLM V1版本的配置
        config_path, default_config_path, config_is_user_owned = self._get_config_path()
        self._manager.initialize(
            config_path,
            default_config_path,
            framework_config_is_user=config_is_user_owned,
        )

        self._initialized = True
        logger.info("VLLMMetricAdapter initialized successfully")

    def shutdown(self):
        """关闭适配器"""
        if not self._initialized and self._manager is None:
            return

        logger.info("Shutting down VLLMMetricAdapter")

        manager = self._manager
        self._manager = None
        self._initialized = False
        if manager:
            manager.shutdown()

        logger.info("VLLMMetricAdapter shutdown complete")

    def _setup_dp_rank(self):
        """设置dp_rank到meta_state

        尝试从vLLM的各种配置中获取dp_rank。
        """
        dp_rank = self._get_dp_rank_from_env()

        # Resolve dp_rank from explicit sources first, then fall back to vLLM's process name.
        if dp_rank < 0:
            dp_rank = self._get_dp_rank_from_vllm()
        if dp_rank < 0:
            dp_rank = self._get_dp_rank_from_process_name()

        # 设置到meta_state
        logger.debug("Final dp_rank before set_dp_rank: %r", dp_rank)
        set_dp_rank(dp_rank)
        logger.debug("Set dp_rank to meta_state: %s", dp_rank)

    def _get_dp_rank_from_env(self) -> int:
        env_dp_rank = os.getenv("VLLM_DP_RANK")
        logger.debug("Raw env VLLM_DP_RANK=%r", env_dp_rank)
        if not env_dp_rank:
            return -1

        try:
            dp_rank = int(env_dp_rank)
            logger.debug("Got dp_rank from environment: %s", dp_rank)
            return dp_rank
        except ValueError as e:
            logger.debug("Invalid VLLM_DP_RANK value %r: %s", env_dp_rank, e)
            return -1

    def _get_dp_rank_from_vllm(self) -> int:
        try:
            from vllm.distributed.parallel_state import get_data_parallel_rank

            raw_dp_rank = get_data_parallel_rank()
            logger.debug(
                "Raw get_data_parallel_rank() return value=%r, type=%s",
                raw_dp_rank,
                type(raw_dp_rank).__name__,
            )
            dp_rank = int(raw_dp_rank)
            logger.debug("Got dp_rank from vLLM: %s", dp_rank)
            return dp_rank
        except Exception as e:
            logger.debug("Failed to get dp_rank from vLLM distributed state: %s", e, exc_info=True)
            return -1

    def _get_dp_rank_from_process_name(self) -> int:
        process_name = multiprocessing.current_process().name
        logger.debug("Current process name for dp_rank fallback: %r", process_name)
        dp_rank = self._parse_dp_rank_from_process_name(process_name)
        if dp_rank >= 0:
            logger.debug("Got dp_rank from process name: %s", dp_rank)
        return dp_rank

    @staticmethod
    def _parse_dp_rank_from_process_name(process_name: str) -> int:
        match = re.search(r"(?:^|[^A-Za-z0-9])DP(\d+)(?:$|[^A-Za-z0-9])", process_name)
        if not match:
            return -1
        return int(match.group(1))

    def _setup_pd_role(self):
        """设置pd_role到meta_state"""
        pd_role = "mixed"

        try:
            from vllm.distributed.ec_transfer import get_ec_transfer, has_ec_transfer

            if has_ec_transfer():
                _ec = get_ec_transfer()
                pd_role = "prefill" if _ec.is_producer else "decode"
        except Exception:
            try:
                from vllm.distributed.kv_transfer import (
                    get_kv_transfer_group,
                    has_kv_transfer_group,
                )

                if has_kv_transfer_group():
                    _kv = get_kv_transfer_group()
                    pd_role = str(_kv.role)
            except Exception as e:
                logger.debug("Failed to get pd_role: %s", e)

        get_meta_state().set("pd_role", pd_role.lower())
        get_meta_state().set("role", pd_role.lower())
        logger.debug("Setup pd_role=%s", pd_role.lower())

    def _detect_vllm_version(self) -> Optional[str]:
        """检测vLLM版本

        使用 get_package_version 获取 vllm 包版本信息。

        Returns:
            vLLM版本字符串，如果检测失败返回None
        """
        version = get_package_version("vllm")
        if version:
            logger.debug("vLLM version: %s", version)
            return version
        return None

    def _get_config_path(self) -> Tuple[Optional[str], Optional[str], bool]:
        """获取配置文件路径

        优先使用环境变量指定的配置，否则使用默认V1配置。

        Returns:
            配置文件路径，如果没有合适的配置则返回None
        """
        # 获取适配器目录
        adapter_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(adapter_dir, "config")
        default_config_path = os.path.join(config_dir, "default.yaml")

        # 首先检查环境变量指定的配置
        env_config = os.getenv("MS_SERVICE_METRIC_VLLM_CONFIG")
        if env_config and os.path.exists(env_config):
            logger.debug("Using config from environment: %s", env_config)
            return env_config, default_config_path, True

        # 使用V1配置
        config_path = os.path.join(config_dir, "v1_metrics.yaml")
        if os.path.exists(config_path):
            logger.debug("Using V1 config: %s", config_path)
            return config_path, default_config_path, False

        logger.warning("No config file found for vLLM adapter")
        return None, default_config_path, False

    def get_manager(self) -> Optional[SymbolHandlerManager]:
        """获取SymbolHandlerManager实例

        Returns:
            SymbolHandlerManager实例或None
        """
        return self._manager

    def is_initialized(self) -> bool:
        """检查是否已初始化

        Returns:
            是否已初始化
        """
        return self._initialized


# 全局适配器实例
_vllm_adapter_instance: Optional[VLLMMetricAdapter] = None


def get_vllm_adapter() -> VLLMMetricAdapter:
    """获取全局VLLM适配器实例（单例模式）

    Returns:
        VLLMMetricAdapter单例实例
    """
    global _vllm_adapter_instance
    if _vllm_adapter_instance is None:
        _vllm_adapter_instance = VLLMMetricAdapter()
    return _vllm_adapter_instance


def initialize_vllm_metric():
    """初始化vLLM metric收集

    这是主要的初始化入口，应在vLLM启动时调用。

    Example:
        >>> from ms_service_metric.adapters.vllm import initialize_vllm_metric
        >>> initialize_vllm_metric()
    """
    adapter = None
    try:
        adapter = get_vllm_adapter()
        adapter.initialize()
    except Exception:
        logger.exception(
            "Failed to initialize optional vLLM metrics; metrics are disabled and vLLM startup will continue"
        )
        if adapter is not None:
            try:
                adapter.shutdown()
            except Exception:
                logger.exception("Failed to clean up partially initialized vLLM metrics")
