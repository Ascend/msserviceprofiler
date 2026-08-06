# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------

from unittest.mock import Mock

import ms_service_metric.core.config.provider as provider_module
from ms_service_metric.core.config.provider import MetricProvider, ProviderRegistry


class _EntryPoints(list):
    def select(self, **kwargs):
        assert kwargs == {"group": "ms_service_metric.providers"}
        return self


def _entry_point(name, value=None, error=None):
    entry_point = Mock(name=name)
    entry_point.name = name
    if error:
        entry_point.load.side_effect = error
    else:
        entry_point.load.return_value = value
    return entry_point


def test_discover_given_legacy_entry_point_mapping_then_loads_provider(monkeypatch):
    entry_point = _entry_point(
        "legacy",
        MetricProvider(
            name="legacy",
            config_paths=["legacy.yaml"],
            owned_symbol_prefixes=("legacy.",),
        ),
    )
    discovered = {"ms_service_metric.providers": [entry_point]}
    monkeypatch.setattr(provider_module.metadata, "entry_points", lambda: discovered)

    providers = ProviderRegistry().discover()

    assert [provider.name for provider in providers] == ["legacy"]


def test_discover_given_multiple_providers_then_returns_priority_order(monkeypatch):
    entry_points = _EntryPoints(
        [
            _entry_point(
                "late",
                lambda: {
                    "name": "late",
                    "config_paths": ["late.yaml"],
                    "priority": 20,
                    "owned_symbol_prefixes": ("late.",),
                },
            ),
            _entry_point(
                "early",
                MetricProvider(
                    name="early",
                    config_paths=["early.yaml"],
                    priority=10,
                    owned_symbol_prefixes=("early.",),
                ),
            ),
        ]
    )
    monkeypatch.setattr(provider_module.metadata, "entry_points", lambda: entry_points)

    providers = ProviderRegistry().discover()

    assert [provider.name for provider in providers] == ["early", "late"]


def test_discover_given_broken_and_invalid_providers_then_skips_them(monkeypatch):
    entry_points = _EntryPoints(
        [
            _entry_point("broken", error=RuntimeError("load failed")),
            _entry_point(
                "future",
                MetricProvider(
                    name="future",
                    config_paths=["future.yaml"],
                    owned_symbol_prefixes=("future.",),
                    ownership_mode="future",
                ),
            ),
            _entry_point(
                "valid",
                MetricProvider(
                    name="valid",
                    config_paths=["valid.yaml"],
                    owned_symbol_prefixes=("valid.",),
                ),
            ),
        ]
    )
    monkeypatch.setattr(provider_module.metadata, "entry_points", lambda: entry_points)

    providers = ProviderRegistry().discover()

    assert [provider.name for provider in providers] == ["valid"]


def test_discover_given_unspecified_ownership_mode_then_defaults_to_overlay(
    monkeypatch,
):
    entry_points = _EntryPoints(
        [
            _entry_point(
                "vllm-ascend",
                MetricProvider(
                    name="vllm-ascend",
                    config_paths=["ascend.yaml"],
                    framework_package="vllm-ascend",
                    owned_symbol_prefixes=("vllm_ascend.",),
                ),
            )
        ]
    )
    monkeypatch.setattr(provider_module.metadata, "entry_points", lambda: entry_points)

    providers = ProviderRegistry().discover()

    assert len(providers) == 1
    assert providers[0].ownership_mode == "overlay"


def test_resolve_given_overlapping_ownership_then_rejects_all_conflicting_providers(
    monkeypatch,
):
    entry_points = _EntryPoints(
        [
            _entry_point(
                "generic",
                MetricProvider(
                    name="generic",
                    config_paths=["generic.yaml"],
                    priority=100,
                    owned_symbol_prefixes=("framework.",),
                    ownership_mode="exclusive",
                ),
            ),
            _entry_point(
                "specific",
                MetricProvider(
                    name="specific",
                    config_paths=["specific.yaml"],
                    priority=200,
                    owned_symbol_prefixes=("framework.special.",),
                ),
            ),
        ]
    )
    monkeypatch.setattr(provider_module.metadata, "entry_points", lambda: entry_points)

    providers = ProviderRegistry().discover()
    resolved = ProviderRegistry.resolve_ownership_conflicts(providers)

    assert [provider.name for provider in providers] == ["generic", "specific"]
    assert resolved == []


def test_resolve_given_overlapping_overlay_providers_then_keeps_priority_order(
    monkeypatch,
):
    entry_points = _EntryPoints(
        [
            _entry_point(
                "generic",
                MetricProvider(
                    name="generic",
                    config_paths=["generic.yaml"],
                    priority=100,
                    owned_symbol_prefixes=("framework.",),
                ),
            ),
            _entry_point(
                "specific",
                MetricProvider(
                    name="specific",
                    config_paths=["specific.yaml"],
                    priority=200,
                    owned_symbol_prefixes=("framework.special.",),
                ),
            ),
        ]
    )
    monkeypatch.setattr(provider_module.metadata, "entry_points", lambda: entry_points)

    providers = ProviderRegistry().discover()

    assert ProviderRegistry.resolve_ownership_conflicts(providers) == providers


def test_discover_given_invalid_handler_prefix_then_skips_provider(monkeypatch):
    entry_points = _EntryPoints(
        [
            _entry_point(
                "invalid-prefix",
                MetricProvider(
                    name="invalid-prefix",
                    config_paths=["config.yaml"],
                    owned_symbol_prefixes=("framework.",),
                    handler_module_prefixes=("framework.handlers",),
                ),
            )
        ]
    )
    monkeypatch.setattr(provider_module.metadata, "entry_points", lambda: entry_points)

    assert ProviderRegistry().discover() == []


def test_discover_given_duplicate_provider_names_then_rejects_all(monkeypatch):
    entry_points = _EntryPoints(
        [
            _entry_point(
                "first",
                MetricProvider(
                    name="duplicate",
                    config_paths=["one.yaml"],
                    owned_symbol_prefixes=("one.",),
                ),
            ),
            _entry_point(
                "second",
                MetricProvider(
                    name="duplicate",
                    config_paths=["two.yaml"],
                    owned_symbol_prefixes=("two.",),
                ),
            ),
        ]
    )
    monkeypatch.setattr(provider_module.metadata, "entry_points", lambda: entry_points)

    assert ProviderRegistry().discover() == []


def test_discover_given_non_integer_priority_then_skips_provider(monkeypatch):
    entry_points = _EntryPoints(
        [
            _entry_point(
                "bad-priority",
                MetricProvider(
                    name="bad-priority",
                    config_paths=["config.yaml"],
                    priority="high",
                    owned_symbol_prefixes=("framework.",),
                ),
            )
        ]
    )
    monkeypatch.setattr(provider_module.metadata, "entry_points", lambda: entry_points)

    assert ProviderRegistry().discover() == []


def test_discover_given_missing_ownership_then_skips_provider(monkeypatch):
    entry_points = _EntryPoints(
        [
            _entry_point(
                "ownerless",
                MetricProvider(name="ownerless", config_paths=["config.yaml"]),
            )
        ]
    )
    monkeypatch.setattr(provider_module.metadata, "entry_points", lambda: entry_points)

    assert ProviderRegistry().discover() == []
