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
"""SGLang metric adapter."""

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

try:
    from setproctitle import getproctitle
except ImportError:
    getproctitle = None


class SGLangMetricAdapter:
    """Initialize ms_service_metric hooks for SGLang."""

    def __init__(self):
        self._manager: Optional[SymbolHandlerManager] = None
        self._version: Optional[str] = None
        self._initialized: bool = False

    def initialize(self):
        """Initialize the adapter and load SGLang metric symbols."""
        if self._initialized:
            logger.debug("SGLangMetricAdapter already initialized")
            return

        logger.info("Initializing SGLangMetricAdapter")
        self._version = self._detect_sglang_version()
        logger.info("Detected SGLang version: %s", self._version)

        from ms_service_metric.adapters.sglang.metrics_init import setup_sglang_metrics

        setup_sglang_metrics()
        self._setup_ranks()
        self._setup_role()

        self._manager = SymbolHandlerManager(
            current_version=self._version,
            provider_registry=ProviderRegistry(),
        )

        config_path, default_config_path, config_is_user_owned = self._get_config_path()
        self._manager.initialize(
            config_path,
            default_config_path,
            framework_config_is_user=config_is_user_owned,
        )

        self._initialized = True
        logger.info("SGLangMetricAdapter initialized successfully")

    def shutdown(self):
        """Shutdown metric hooks and watchers."""
        if not self._initialized and self._manager is None:
            return

        logger.info("Shutting down SGLangMetricAdapter")
        manager = self._manager
        self._manager = None
        self._initialized = False
        if manager:
            manager.shutdown()
        logger.info("SGLangMetricAdapter shutdown complete")

    def _detect_sglang_version(self) -> Optional[str]:
        """Detect the installed SGLang version."""
        version = get_package_version("sglang")
        if version:
            logger.debug("SGLang version: %s", version)
            return version
        logger.warning("SGLang not installed")
        return None

    def _setup_ranks(self):
        """Set process rank labels used by MetricsManager."""
        rank_sources = self._get_rank_source_names()
        dp_rank = self._get_int_env("SGLANG_DP_RANK")
        if dp_rank < 0:
            dp_rank = self._parse_rank_from_names(rank_sources, "DP")
        if dp_rank < 0:
            logger.warning("Could not resolve SGLang dp_rank from env or process title: %s", rank_sources)
        set_dp_rank(dp_rank)

        tp_rank = self._get_int_env("SGLANG_TP_RANK")
        if tp_rank < 0:
            tp_rank = self._parse_rank_from_names(rank_sources, "TP")
        if tp_rank < 0:
            logger.warning("Could not resolve SGLang tp_rank from env or process title: %s", rank_sources)
        get_meta_state().set("tp_rank", tp_rank)
        logger.debug("Setup SGLang dp_rank=%s, tp_rank=%s", dp_rank, tp_rank)

    @staticmethod
    def _get_int_env(name: str) -> int:
        value = os.getenv(name)
        if not value:
            return -1
        try:
            return int(value)
        except ValueError:
            logger.debug("Invalid %s value: %r", name, value)
            return -1

    @staticmethod
    def _parse_rank_from_process_name(process_name: str, prefix: str) -> int:
        match = re.search(rf"(?:^|[^A-Za-z0-9]){prefix}(\d+)(?:$|[^A-Za-z0-9])", process_name, re.IGNORECASE)
        if not match:
            return -1
        return int(match.group(1))

    @classmethod
    def _parse_rank_from_names(cls, process_names: Tuple[str, ...], prefix: str) -> int:
        for process_name in process_names:
            rank = cls._parse_rank_from_process_name(process_name, prefix)
            if rank >= 0:
                return rank
        return -1

    @staticmethod
    def _get_rank_source_names() -> Tuple[str, ...]:
        names = [multiprocessing.current_process().name]
        if getproctitle is not None:
            try:
                process_title = getproctitle()
            except Exception as err:
                logger.debug("Failed to get SGLang process title: %s", err)
            else:
                if process_title and process_title not in names:
                    names.append(process_title)
        return tuple(names)

    def _setup_role(self):
        role = os.getenv("SGLANG_PD_ROLE", "mixed").lower()
        get_meta_state().set("pd_role", role)
        get_meta_state().set("role", role)
        get_meta_state().set("phase", role if role in {"prefill", "decode"} else "mixed")

    def _get_config_path(self) -> Tuple[Optional[str], Optional[str], bool]:
        """Return framework config, built-in default config and ownership flag."""
        adapter_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(adapter_dir, "config")
        default_config = os.path.join(config_dir, "default.yaml")

        env_config = os.getenv("MS_SERVICE_METRIC_SGLANG_CONFIG")
        if env_config and os.path.exists(env_config):
            logger.debug("Using config from environment: %s", env_config)
            return env_config, default_config, True

        if os.path.exists(default_config):
            logger.debug("Using default config: %s", default_config)
            return None, default_config, False

        logger.warning("No config file found for SGLang adapter")
        return None, default_config, False

    def get_manager(self) -> Optional[SymbolHandlerManager]:
        """Return the symbol handler manager."""
        return self._manager

    def is_initialized(self) -> bool:
        """Return whether the adapter is initialized."""
        return self._initialized


_sglang_adapter_instance: Optional[SGLangMetricAdapter] = None


def get_sglang_adapter() -> SGLangMetricAdapter:
    """Return the global SGLang metric adapter."""
    global _sglang_adapter_instance
    if _sglang_adapter_instance is None:
        _sglang_adapter_instance = SGLangMetricAdapter()
    return _sglang_adapter_instance


def initialize_sglang_metric():
    """Initialize optional SGLang metric collection."""
    adapter = None
    try:
        adapter = get_sglang_adapter()
        adapter.initialize()
    except Exception:
        logger.exception(
            "Failed to initialize optional SGLang metrics; metrics are disabled and SGLang startup will continue"
        )
        if adapter is not None:
            try:
                adapter.shutdown()
            except Exception:
                logger.exception("Failed to clean up partially initialized SGLang metrics")
