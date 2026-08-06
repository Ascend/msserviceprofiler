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

import sys
from types import ModuleType

import ms_service_metric.core.config.symbol_config as symbol_config_module
import pytest
from ms_service_metric.core.config.provider import MetricProvider
from ms_service_metric.core.config.symbol_config import SymbolConfig
from ms_service_metric.core.handler import MetricHandler


def test_given_array_yaml_when_load_then_converted_to_symbol_map(tmp_path):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        "- symbol: a.b:Cls.fn\n"
        "  handler: ms_service_metric.handlers:default_handler\n"
        "  metrics:\n"
        "    - name: m1\n"
        "      type: counter\n",
        encoding="utf-8",
    )

    c = SymbolConfig(user_config_path=str(cfg))
    out = c.load()
    assert "a.b:Cls.fn" in out
    assert isinstance(out["a.b:Cls.fn"], list)
    assert out["a.b:Cls.fn"][0]["handler"] == "ms_service_metric.handlers:default_handler"


def test_given_env_user_config_when_load_then_env_path_takes_precedence(tmp_path, monkeypatch):
    env_cfg = tmp_path / "env.yaml"
    env_cfg.write_text("- symbol: m.n:o\n  handler: ms_service_metric.handlers:default_handler\n", encoding="utf-8")

    fallback_cfg = tmp_path / "fallback.yaml"
    fallback_cfg.write_text(
        "- symbol: x.y:z\n  handler: ms_service_metric.handlers:default_handler\n", encoding="utf-8"
    )

    monkeypatch.setenv(SymbolConfig.ENV_CONFIG_PATH, str(env_cfg))
    c = SymbolConfig(user_config_path=str(fallback_cfg))
    out = c.load()
    assert "m.n:o" in out
    assert "x.y:z" not in out


def test_given_env_handler_for_default_symbol_when_load_then_appends(tmp_path, monkeypatch):
    default_cfg = tmp_path / "default.yaml"
    default_cfg.write_text(
        "- symbol: framework.module:fn\n  metrics:\n    - name: core:duration\n",
        encoding="utf-8",
    )
    env_cfg = tmp_path / "env.yaml"
    env_cfg.write_text(
        "- symbol: framework.module:fn\n"
        "  handler: ms_service_metric.provider_handlers:phase_all_handler\n"
        "  metrics:\n"
        "    - name: user:duration\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(SymbolConfig.ENV_CONFIG_PATH, str(env_cfg))

    config = SymbolConfig(default_config_path=str(default_cfg)).load()

    assert [metric["name"] for handler in config["framework.module:fn"] for metric in handler["metrics"]] == [
        "core:duration",
        "user:duration",
    ]


def test_given_version_bounds_when_filter_then_non_matching_handlers_removed(tmp_path):
    cfg = tmp_path / "ver.yaml"
    cfg.write_text(
        "- symbol: p.q:r\n  handler: ms_service_metric.handlers:default_handler\n  min_version: '9.9.9'\n",
        encoding="utf-8",
    )
    c = SymbolConfig(user_config_path=str(cfg), current_version="1.0.0")
    out = c.load()
    assert out == {}


def test_given_handler_without_optional_fields_when_fill_defaults_then_defaults_present(tmp_path):
    cfg = tmp_path / "d.yaml"
    cfg.write_text(
        "- symbol: p.q:r\n  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )
    c = SymbolConfig(user_config_path=str(cfg))
    out = c.load()
    h = out["p.q:r"][0]
    assert h["type"] == "wrap"
    assert h["enabled"] is True
    assert h["need_locals"] is False
    assert h["lock_patch"] is False
    assert h["metrics"] == []


def test_given_bad_yaml_when_load_then_raises_config_error(tmp_path):
    cfg = tmp_path / "bad.yaml"
    cfg.write_text(":\n  - bad", encoding="utf-8")
    c = SymbolConfig(user_config_path=str(cfg))
    with pytest.raises(Exception):
        c.load()


def test_given_provider_and_environment_config_when_load_then_keeps_provider_and_replaces_framework(
    tmp_path, monkeypatch
):
    framework_cfg = tmp_path / "framework.yaml"
    framework_cfg.write_text(
        "- symbol: framework.module:fn\n  handler: framework.handlers:record\n",
        encoding="utf-8",
    )
    provider_cfg = tmp_path / "provider.yaml"
    provider_cfg.write_text(
        "- symbol: provider.module:fn\n  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )
    env_cfg = tmp_path / "env.yaml"
    env_cfg.write_text(
        "- symbol: operator.module:fn\n  handler: operator.handlers:record\n",
        encoding="utf-8",
    )
    registry = type(
        "Registry",
        (),
        {
            "discover": lambda self: [
                MetricProvider(
                    name="test-provider",
                    config_paths=[str(provider_cfg)],
                    owned_symbol_prefixes=("provider.",),
                )
            ]
        },
    )()
    monkeypatch.setenv(SymbolConfig.ENV_CONFIG_PATH, str(env_cfg))

    config = SymbolConfig(
        user_config_path=str(framework_cfg),
        provider_registry=registry,
    ).load()

    assert "framework.module:fn" not in config
    assert set(config) >= {"provider.module:fn", "operator.module:fn"}


def test_given_provider_changes_when_reload_then_discovers_again(tmp_path):
    first_cfg = tmp_path / "first.yaml"
    first_cfg.write_text(
        "- symbol: first.module:fn\n  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )
    second_cfg = tmp_path / "second.yaml"
    second_cfg.write_text(
        "- symbol: second.module:fn\n  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )

    class ReloadableRegistry:
        config_path = first_cfg
        calls = 0

        def discover(self):
            self.calls += 1
            return [
                MetricProvider(
                    name="reloadable",
                    config_paths=[str(self.config_path)],
                    owned_symbol_prefixes=(f"{self.config_path.stem}.",),
                )
            ]

    registry = ReloadableRegistry()
    symbol_config = SymbolConfig(provider_registry=registry)
    first = symbol_config.load()
    registry.config_path = second_cfg
    second = symbol_config.reload()

    assert "first.module:fn" in first
    assert "first.module:fn" not in second
    assert "second.module:fn" in second
    assert registry.calls == 2


def test_given_no_provider_when_load_then_keeps_all_core_symbols(tmp_path):
    fallback_cfg = tmp_path / "fallback.yaml"
    fallback_cfg.write_text(
        "- symbol: framework.module:fn\n  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )
    registry = type(
        "Registry",
        (),
        {"discover": lambda self: []},
    )()

    config = SymbolConfig(
        default_config_path=str(fallback_cfg),
        provider_registry=registry,
    ).load()

    assert "framework.module:fn" in config


def test_given_overlay_provider_when_load_then_replaces_only_contributed_symbols(
    tmp_path,
):
    fallback_cfg = tmp_path / "fallback.yaml"
    fallback_cfg.write_text(
        "- symbol: framework.migrated:fn\n"
        "  handler: ms_service_metric.handlers:default_handler\n"
        "- symbol: framework.pending:fn\n"
        "  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )
    provider_cfg = tmp_path / "provider.yaml"
    provider_cfg.write_text(
        "- symbol: framework.migrated:fn\n"
        "  handler: ms_service_metric.provider_handlers:phase_all_handler\n"
        "  metrics:\n"
        "    - name: provider:duration\n",
        encoding="utf-8",
    )
    registry = type(
        "Registry",
        (),
        {
            "discover": lambda self: [
                MetricProvider(
                    name="partial-migration",
                    config_paths=[str(provider_cfg)],
                    owned_symbol_prefixes=("framework.",),
                )
            ]
        },
    )()

    config = SymbolConfig(
        default_config_path=str(fallback_cfg),
        provider_registry=registry,
    ).load()

    assert [handler["handler"] for handler in config["framework.migrated:fn"]] == [
        "ms_service_metric.provider_handlers:phase_all_handler"
    ]
    assert config["framework.pending:fn"][0]["handler"] == ("ms_service_metric.handlers:default_handler")


def test_given_overlapping_overlay_providers_when_load_then_later_priority_wins(
    tmp_path,
):
    first_cfg = tmp_path / "first.yaml"
    first_cfg.write_text(
        "- symbol: framework.module:fn\n  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )
    second_cfg = tmp_path / "second.yaml"
    second_cfg.write_text(
        "- symbol: framework.module:fn\n"
        "  handler: ms_service_metric.provider_handlers:phase_all_handler\n"
        "  metrics:\n"
        "    - name: provider:duration\n",
        encoding="utf-8",
    )
    registry = type(
        "Registry",
        (),
        {
            "discover": lambda self: [
                MetricProvider(
                    name="first",
                    config_paths=[str(first_cfg)],
                    priority=100,
                    owned_symbol_prefixes=("framework.",),
                ),
                MetricProvider(
                    name="second",
                    config_paths=[str(second_cfg)],
                    priority=200,
                    owned_symbol_prefixes=("framework.",),
                ),
            ]
        },
    )()

    config = SymbolConfig(provider_registry=registry).load()

    assert [handler["handler"] for handler in config["framework.module:fn"]] == [
        "ms_service_metric.provider_handlers:phase_all_handler"
    ]


def test_given_exclusive_provider_when_load_then_filters_owned_bindings_from_all_core_configs(
    tmp_path,
):
    default_cfg = tmp_path / "default.yaml"
    default_cfg.write_text(
        "- symbol: framework.module:fn\n"
        "  handler: core.meta:record\n"
        "- symbol: core.module:fn\n"
        "  handler: core.meta:record\n",
        encoding="utf-8",
    )
    framework_cfg = tmp_path / "framework.yaml"
    framework_cfg.write_text(
        "- symbol: framework.module:fn\n"
        "  handler: old.handlers:record\n"
        "- symbol: other.module:fn\n"
        "  handler: other.handlers:record\n",
        encoding="utf-8",
    )
    provider_cfg = tmp_path / "provider.yaml"
    provider_cfg.write_text(
        "- symbol: framework.module:fn\n  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )
    registry = type(
        "Registry",
        (),
        {
            "discover": lambda self: [
                MetricProvider(
                    name="replacement",
                    config_paths=[str(provider_cfg)],
                    owned_symbol_prefixes=("framework.",),
                    ownership_mode="exclusive",
                )
            ]
        },
    )()

    config = SymbolConfig(
        user_config_path=str(framework_cfg),
        default_config_path=str(default_cfg),
        provider_registry=registry,
    ).load()

    handlers = config["framework.module:fn"]
    assert [handler["handler"] for handler in handlers] == ["ms_service_metric.handlers:default_handler"]
    assert config["core.module:fn"][0]["handler"] == "core.meta:record"
    assert config["other.module:fn"][0]["handler"] == "other.handlers:record"


@pytest.mark.parametrize("provider_content", [None, ":\n  - invalid"])
def test_given_provider_config_unavailable_when_load_then_keeps_core_fallback(
    tmp_path,
    provider_content,
):
    fallback_cfg = tmp_path / "fallback.yaml"
    fallback_cfg.write_text(
        "- symbol: framework.module:fn\n  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )
    provider_cfg = tmp_path / "provider.yaml"
    if provider_content is not None:
        provider_cfg.write_text(provider_content, encoding="utf-8")
    registry = type(
        "Registry",
        (),
        {
            "discover": lambda self: [
                MetricProvider(
                    name="broken",
                    config_paths=[str(provider_cfg)],
                    owned_symbol_prefixes=("framework.",),
                )
            ]
        },
    )()

    symbol_config = SymbolConfig(
        default_config_path=str(fallback_cfg),
        provider_registry=registry,
    )
    config = symbol_config.load()

    assert "framework.module:fn" in config
    assert symbol_config.get_active_provider_names() == ()


def test_given_provider_handler_prefix_when_load_then_external_handler_is_allowed(
    tmp_path,
    monkeypatch,
):
    provider_package = ModuleType("provider_ext")
    provider_package.__path__ = []
    provider_handlers = ModuleType("provider_ext.handlers")
    provider_handlers.record = lambda original, *args, **kwargs: original(
        *args,
        **kwargs,
    )
    monkeypatch.setitem(sys.modules, "provider_ext", provider_package)
    monkeypatch.setitem(sys.modules, "provider_ext.handlers", provider_handlers)

    provider_cfg = tmp_path / "provider.yaml"
    provider_cfg.write_text(
        "- symbol: framework.module:fn\n  handler: provider_ext.handlers:record\n",
        encoding="utf-8",
    )
    registry = type(
        "Registry",
        (),
        {
            "discover": lambda self: [
                MetricProvider(
                    name="external-handler",
                    config_paths=[str(provider_cfg)],
                    owned_symbol_prefixes=("framework.",),
                    handler_module_prefixes=("provider_ext.",),
                )
            ]
        },
    )()

    symbol_config = SymbolConfig(provider_registry=registry)
    config = symbol_config.load()
    handler_config = config["framework.module:fn"][0]
    handler = MetricHandler.from_config(
        handler_config,
        "framework.module:fn",
        symbol_config.get_allowed_handler_module_prefixes(),
    )

    assert handler is not None
    assert symbol_config.get_allowed_symbol_module_prefixes() == ("framework.",)
    assert symbol_config.get_active_provider_names() == ("external-handler",)


@pytest.mark.parametrize(
    "buckets",
    ["['not-a-number']", "[.nan]", "[1, 1]", "[2, 1]", "[true, 2]"],
)
def test_given_invalid_provider_buckets_when_load_then_keeps_fallback(
    tmp_path,
    buckets,
):
    fallback_cfg = tmp_path / "fallback.yaml"
    fallback_cfg.write_text(
        "- symbol: framework.module:fn\n  metrics:\n    - name: core:duration\n",
        encoding="utf-8",
    )
    provider_cfg = tmp_path / "provider.yaml"
    provider_cfg.write_text(
        "- symbol: framework.module:fn\n"
        "  metrics:\n"
        "    - name: provider:duration\n"
        "      type: histogram\n"
        f"      buckets: {buckets}\n",
        encoding="utf-8",
    )
    registry = type(
        "Registry",
        (),
        {
            "discover": lambda self: [
                MetricProvider(
                    name="invalid-buckets",
                    config_paths=[str(provider_cfg)],
                    owned_symbol_prefixes=("framework.",),
                )
            ]
        },
    )()
    symbol_config = SymbolConfig(
        default_config_path=str(fallback_cfg),
        provider_registry=registry,
    )

    config = symbol_config.load()

    assert config["framework.module:fn"][0]["metrics"][0]["name"] == "core:duration"
    assert symbol_config.get_active_provider_names() == ()


def test_given_invalid_provider_metric_name_when_load_then_keeps_fallback(tmp_path):
    fallback_cfg = tmp_path / "fallback.yaml"
    fallback_cfg.write_text(
        "- symbol: framework.module:fn\n  metrics:\n    - name: core:duration\n",
        encoding="utf-8",
    )
    provider_cfg = tmp_path / "provider.yaml"
    provider_cfg.write_text(
        "- symbol: framework.module:fn\n  metrics:\n    - name: 'bad metric name'\n",
        encoding="utf-8",
    )
    registry = type(
        "Registry",
        (),
        {
            "discover": lambda self: [
                MetricProvider(
                    name="invalid-name",
                    config_paths=[str(provider_cfg)],
                    owned_symbol_prefixes=("framework.",),
                )
            ]
        },
    )()
    symbol_config = SymbolConfig(
        default_config_path=str(fallback_cfg),
        provider_registry=registry,
    )

    config = symbol_config.load()

    assert config["framework.module:fn"][0]["metrics"][0]["name"] == "core:duration"
    assert symbol_config.get_active_provider_names() == ()


def test_given_provider_metric_schema_conflicts_with_core_when_load_then_keeps_fallback(
    tmp_path,
):
    fallback_cfg = tmp_path / "fallback.yaml"
    fallback_cfg.write_text(
        "- symbol: core.module:fn\n  metrics:\n    - name: shared:requests\n      type: counter\n",
        encoding="utf-8",
    )
    provider_cfg = tmp_path / "provider.yaml"
    provider_cfg.write_text(
        "- symbol: framework.module:fn\n  metrics:\n    - name: shared:requests\n      type: gauge\n",
        encoding="utf-8",
    )
    registry = type(
        "Registry",
        (),
        {
            "discover": lambda self: [
                MetricProvider(
                    name="schema-conflict",
                    config_paths=[str(provider_cfg)],
                    owned_symbol_prefixes=("framework.",),
                )
            ]
        },
    )()
    symbol_config = SymbolConfig(
        default_config_path=str(fallback_cfg),
        provider_registry=registry,
    )

    config = symbol_config.load()

    assert "core.module:fn" in config
    assert "framework.module:fn" not in config
    assert symbol_config.get_active_provider_names() == ()


def test_given_user_framework_config_when_provider_owns_symbol_then_user_overrides(
    tmp_path,
):
    provider_cfg = tmp_path / "provider.yaml"
    provider_cfg.write_text(
        "- symbol: framework.module:fn\n  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )
    user_cfg = tmp_path / "user.yaml"
    user_cfg.write_text(
        "- symbol: framework.module:fn\n"
        "  handler: ms_service_metric.provider_handlers:phase_all_handler\n"
        "  metrics:\n"
        "    - name: custom:duration\n",
        encoding="utf-8",
    )
    registry = type(
        "Registry",
        (),
        {
            "discover": lambda self: [
                MetricProvider(
                    name="framework-provider",
                    config_paths=[str(provider_cfg)],
                    owned_symbol_prefixes=("framework.",),
                )
            ]
        },
    )()

    config = SymbolConfig(
        user_config_path=str(user_cfg),
        provider_registry=registry,
        framework_config_is_user=True,
    ).load()

    assert [handler["handler"] for handler in config["framework.module:fn"]] == [
        "ms_service_metric.provider_handlers:phase_all_handler"
    ]


def test_given_provider_version_bounds_when_load_then_uses_provider_package_version(
    tmp_path,
    monkeypatch,
):
    provider_cfg = tmp_path / "provider.yaml"
    provider_cfg.write_text(
        "- symbol: framework.module:fn\n"
        "  handler: ms_service_metric.handlers:default_handler\n"
        "  max_version: '1.5.0'\n",
        encoding="utf-8",
    )
    registry = type(
        "Registry",
        (),
        {
            "discover": lambda self: [
                MetricProvider(
                    name="versioned",
                    config_paths=[str(provider_cfg)],
                    framework_package="framework_dist",
                    owned_symbol_prefixes=("framework.",),
                )
            ]
        },
    )()
    monkeypatch.setattr(
        symbol_config_module,
        "get_package_version",
        lambda package: "1.0.0" if package == "framework_dist" else None,
    )

    config = SymbolConfig(
        current_version="9.0.0",
        provider_registry=registry,
    ).load()

    assert "framework.module:fn" in config


def test_given_provider_uses_core_internal_handler_then_keeps_fallback(
    tmp_path,
):
    fallback_cfg = tmp_path / "fallback.yaml"
    fallback_cfg.write_text(
        "- symbol: framework.module:fn\n  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )
    provider_cfg = tmp_path / "provider.yaml"
    provider_cfg.write_text(
        "- symbol: framework.module:fn\n"
        "  handler: "
        "ms_service_metric.adapters.vllm.handlers.metric_handlers:"
        "phase_all_handler\n"
        "  metrics:\n"
        "    - name: internal:duration\n",
        encoding="utf-8",
    )
    registry = type(
        "Registry",
        (),
        {
            "discover": lambda self: [
                MetricProvider(
                    name="internal-handler",
                    config_paths=[str(provider_cfg)],
                    owned_symbol_prefixes=("framework.",),
                )
            ]
        },
    )()

    symbol_config = SymbolConfig(
        default_config_path=str(fallback_cfg),
        provider_registry=registry,
    )
    config = symbol_config.load()

    assert config["framework.module:fn"][0]["handler"] == ("ms_service_metric.handlers:default_handler")
    assert symbol_config.get_active_provider_names() == ()


def test_given_provider_uses_unknown_stable_handler_then_keeps_fallback(
    tmp_path,
):
    fallback_cfg = tmp_path / "fallback.yaml"
    fallback_cfg.write_text(
        "- symbol: framework.module:fn\n  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )
    provider_cfg = tmp_path / "provider.yaml"
    provider_cfg.write_text(
        "- symbol: framework.module:fn\n  handler: ms_service_metric.provider_handlers:not_exported\n",
        encoding="utf-8",
    )
    registry = type(
        "Registry",
        (),
        {
            "discover": lambda self: [
                MetricProvider(
                    name="unknown-stable-handler",
                    config_paths=[str(provider_cfg)],
                    owned_symbol_prefixes=("framework.",),
                )
            ]
        },
    )()

    symbol_config = SymbolConfig(
        default_config_path=str(fallback_cfg),
        provider_registry=registry,
    )
    config = symbol_config.load()

    assert config["framework.module:fn"][0]["handler"] == ("ms_service_metric.handlers:default_handler")
    assert symbol_config.get_active_provider_names() == ()


def test_given_duplicate_yaml_handlers_when_load_then_keeps_one(tmp_path):
    config_path = tmp_path / "duplicate.yaml"
    config_path.write_text(
        "- symbol: framework.module:fn\n"
        "  handler: ms_service_metric.handlers:default_handler\n"
        "- symbol: framework.module:fn\n"
        "  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )

    config = SymbolConfig(user_config_path=str(config_path)).load()

    assert len(config["framework.module:fn"]) == 1


def test_given_failed_replacement_load_then_keeps_last_committed_config(
    tmp_path,
):
    valid_path = tmp_path / "valid.yaml"
    valid_path.write_text(
        "- symbol: framework.module:fn\n  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )
    invalid_path = tmp_path / "invalid.yaml"
    invalid_path.write_text(":\n  - invalid", encoding="utf-8")
    symbol_config = SymbolConfig(user_config_path=str(valid_path))
    committed = symbol_config.load()

    with pytest.raises(Exception):
        symbol_config.load(config_path=str(invalid_path))

    assert symbol_config.get_config() == committed
    assert symbol_config._user_config_path == str(valid_path)


def test_given_semantically_equivalent_handlers_when_load_then_deduplicates(
    tmp_path,
):
    config_path = tmp_path / "semantic-duplicates.yaml"
    config_path.write_text(
        "- symbol: framework.module:fn\n"
        "  metrics:\n"
        "    - name: request:duration\n"
        "- symbol: framework.module:fn\n"
        "  handler: ms_service_metric.handlers:default_handler\n"
        "  lock_patch: false\n"
        "  metrics:\n"
        "    - name: request:duration\n"
        "      type: timer\n"
        "      expr: ignored-for-timer\n"
        "      labels: []\n",
        encoding="utf-8",
    )

    config = SymbolConfig(user_config_path=str(config_path)).load()

    assert len(config["framework.module:fn"]) == 1


def test_given_provider_split_files_with_semantic_duplicate_when_load_then_keeps_one(
    tmp_path,
):
    first_cfg = tmp_path / "first.yaml"
    first_cfg.write_text(
        "- symbol: framework.module:fn\n  metrics:\n    - name: request:duration\n",
        encoding="utf-8",
    )
    second_cfg = tmp_path / "second.yaml"
    second_cfg.write_text(
        "- symbol: framework.module:fn\n"
        "  handler: ms_service_metric.handlers:default_handler\n"
        "  lock_patch: false\n"
        "  metrics:\n"
        "    - name: request:duration\n"
        "      type: timer\n"
        "      labels: []\n",
        encoding="utf-8",
    )
    registry = type(
        "Registry",
        (),
        {
            "discover": lambda self: [
                MetricProvider(
                    name="split-provider",
                    config_paths=[str(first_cfg), str(second_cfg)],
                    owned_symbol_prefixes=("framework.",),
                )
            ]
        },
    )()

    config = SymbolConfig(provider_registry=registry).load()

    assert len(config["framework.module:fn"]) == 1


def test_given_malformed_provider_item_when_load_then_keeps_fallback(
    tmp_path,
):
    fallback_cfg = tmp_path / "fallback.yaml"
    fallback_cfg.write_text(
        "- symbol: framework.module:fn\n  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )
    provider_cfg = tmp_path / "provider.yaml"
    provider_cfg.write_text(
        "- symbol: framework.module:fn\n"
        "  handler: ms_service_metric.handlers:default_handler\n"
        "- symbol: framework.module:fn\n"
        "  handler: ms_service_metric.handlers:default_handler\n"
        "  metrics:\n"
        "    - malformed-metric\n",
        encoding="utf-8",
    )
    registry = type(
        "Registry",
        (),
        {
            "discover": lambda self: [
                MetricProvider(
                    name="strict-provider",
                    config_paths=[str(provider_cfg)],
                    owned_symbol_prefixes=("framework.",),
                )
            ]
        },
    )()

    symbol_config = SymbolConfig(
        default_config_path=str(fallback_cfg),
        provider_registry=registry,
    )
    config = symbol_config.load()

    assert config["framework.module:fn"][0]["handler"] == ("ms_service_metric.handlers:default_handler")
    assert symbol_config.get_active_provider_names() == ()


def test_given_empty_provider_split_file_when_load_then_keeps_fallback(
    tmp_path,
):
    fallback_cfg = tmp_path / "fallback.yaml"
    fallback_cfg.write_text(
        "- symbol: framework.module:fn\n  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )
    provider_cfg = tmp_path / "provider.yaml"
    provider_cfg.write_text(
        "- symbol: framework.module:fn\n  handler: ms_service_metric.handlers:default_handler\n",
        encoding="utf-8",
    )
    empty_cfg = tmp_path / "empty.yaml"
    empty_cfg.write_text("# no metric definitions\n", encoding="utf-8")
    registry = type(
        "Registry",
        (),
        {
            "discover": lambda self: [
                MetricProvider(
                    name="split-provider",
                    config_paths=[str(provider_cfg), str(empty_cfg)],
                    owned_symbol_prefixes=("framework.",),
                )
            ]
        },
    )()

    symbol_config = SymbolConfig(
        default_config_path=str(fallback_cfg),
        provider_registry=registry,
    )
    symbol_config.load()

    assert symbol_config.get_active_provider_names() == ()
