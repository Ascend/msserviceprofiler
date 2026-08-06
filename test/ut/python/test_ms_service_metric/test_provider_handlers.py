# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------

from types import SimpleNamespace
from unittest.mock import Mock

from ms_service_metric.metrics.metrics_manager import get_metrics_manager
from ms_service_metric.provider_api import get_metric_recorder

from ms_service_metric import provider_handlers


def test_provider_handler_exports_match_lazy_targets():
    assert set(provider_handlers.__all__) == set(provider_handlers._HANDLER_TARGETS)


def test_provider_handler_facade_resolves_direct_handler_lazily(monkeypatch):
    target_handler = Mock(return_value="result")
    module = SimpleNamespace(scheduler_scheduler_hooker=target_handler)
    module_loader = Mock(return_value=module)
    monkeypatch.setattr(provider_handlers, "import_module", module_loader)

    assert module_loader.call_count == 0
    original = Mock()
    result = provider_handlers.scheduler_scheduler_hooker(
        original,
        "scheduler",
        request_id="request",
    )

    assert result == "result"
    module_loader.assert_called_once_with("ms_service_metric.adapters.vllm.handlers.metric_handlers")
    target_handler.assert_called_once_with(
        original,
        "scheduler",
        request_id="request",
    )


def test_provider_handler_facade_forwards_factory_arguments(monkeypatch):
    target_factory = Mock(return_value="wrapped")
    module = SimpleNamespace(phase_all_handler=target_factory)
    monkeypatch.setattr(
        provider_handlers,
        "import_module",
        Mock(return_value=module),
    )
    metrics_config = [SimpleNamespace(name="duration")]

    result = provider_handlers.phase_all_handler(
        metrics_config,
        is_async=True,
        context="test",
    )

    assert result == "wrapped"
    target_factory.assert_called_once_with(
        metrics_config,
        is_async=True,
        context="test",
    )


def test_provider_api_exposes_the_core_metric_recorder():
    assert get_metric_recorder() is get_metrics_manager()
