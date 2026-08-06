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
ms_service_metric.core.config - 配置管理模块

提供 Symbol 配置和 Metric 控制热更新功能。
"""

from ms_service_metric.core.config.metric_control_watch import MetricControlWatch
from ms_service_metric.core.config.provider import MetricProvider, ProviderRegistry
from ms_service_metric.core.config.symbol_config import SymbolConfig

__all__ = [
    "SymbolConfig",
    "MetricControlWatch",
    "MetricProvider",
    "ProviderRegistry",
]
