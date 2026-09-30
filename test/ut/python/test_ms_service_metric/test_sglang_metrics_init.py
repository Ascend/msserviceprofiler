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

"""Tests for SGLang metrics initialization."""

import ms_service_metric.adapters.sglang.metrics_init as mi
from ms_service_metric.metrics.metrics_manager import get_metrics_manager


def test_setup_sglang_metrics_sets_prefix(monkeypatch):
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    client = get_metrics_manager()
    client.metric_prefix = ""

    mi.setup_sglang_metrics()

    assert client.metric_prefix == mi.SGLANG_METRICS_PREFIX


def test_setup_sglang_metrics_sets_prometheus_registry(monkeypatch):
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    client = get_metrics_manager()
    client.set_registry(None)

    mi.setup_sglang_metrics()

    assert client.get_registry() is mi.REGISTRY


def test_setup_sglang_metrics_uses_multiprocess_registry(monkeypatch):
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", "/tmp/sglang_metrics")
    client = get_metrics_manager()
    client.set_registry(None)
    registry = object()
    monkeypatch.setattr(client, "_get_appropriate_registry", lambda: registry)

    mi.setup_sglang_metrics()

    assert client.get_registry() is registry
