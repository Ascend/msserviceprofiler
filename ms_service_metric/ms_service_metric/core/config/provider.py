# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------
"""Provider discovery for framework-owned metric configurations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from typing import Any

from ms_service_metric.utils.logger import get_logger

logger = get_logger("metric_provider")

PROVIDER_ENTRY_POINT_GROUP = "ms_service_metric.providers"
PROVIDER_OWNERSHIP_OVERLAY = "overlay"
PROVIDER_OWNERSHIP_EXCLUSIVE = "exclusive"
SUPPORTED_OWNERSHIP_MODES = {
    PROVIDER_OWNERSHIP_OVERLAY,
    PROVIDER_OWNERSHIP_EXCLUSIVE,
}


@dataclass(frozen=True)
class MetricProvider:
    """A framework package's metric configuration contribution.

    Overlay providers replace only the symbols they contribute. Exclusive
    providers additionally remove fallback symbols in their owned prefixes.
    """

    name: str
    config_paths: Sequence[str]
    priority: int = 100
    framework_package: str | None = None
    owned_symbol_prefixes: Sequence[str] = ()
    handler_module_prefixes: Sequence[str] = ()
    ownership_mode: str = PROVIDER_OWNERSHIP_OVERLAY


class ProviderRegistry:
    """Discover and validate providers without coupling Core to a framework."""

    def __init__(self, entry_point_group: str = PROVIDER_ENTRY_POINT_GROUP):
        self._entry_point_group = entry_point_group

    def discover(self) -> list[MetricProvider]:
        providers = []
        for entry_point in self._entry_points():
            try:
                provider = self._normalize(entry_point.name, entry_point.load())
                if self._is_valid(provider):
                    providers.append(provider)
            except Exception as error:  # noqa: BLE001 - isolate third-party plugins
                logger.warning(
                    "Skipping metric provider %s: %s",
                    entry_point.name,
                    error,
                )

        providers.sort(key=lambda provider: (provider.priority, provider.name))
        return self._reject_duplicate_names(providers)

    def _entry_points(self) -> Iterable[Any]:
        discovered = metadata.entry_points()
        if hasattr(discovered, "select"):
            return discovered.select(group=self._entry_point_group)
        if isinstance(discovered, Mapping):
            return discovered.get(self._entry_point_group, [])
        return []

    @staticmethod
    def _normalize(entry_point_name: str, loaded: Any) -> MetricProvider:
        candidate = loaded() if callable(loaded) and not isinstance(loaded, type) else loaded
        if isinstance(candidate, MetricProvider):
            return candidate
        if isinstance(candidate, Mapping):
            return MetricProvider(**candidate)

        if all(hasattr(candidate, field) for field in ("name", "config_paths")):
            return MetricProvider(
                name=candidate.name,
                config_paths=candidate.config_paths,
                priority=getattr(candidate, "priority", 100),
                framework_package=getattr(candidate, "framework_package", None),
                owned_symbol_prefixes=getattr(candidate, "owned_symbol_prefixes", ()),
                handler_module_prefixes=getattr(
                    candidate,
                    "handler_module_prefixes",
                    (),
                ),
                ownership_mode=getattr(
                    candidate,
                    "ownership_mode",
                    PROVIDER_OWNERSHIP_OVERLAY,
                ),
            )
        raise TypeError(f"entry point {entry_point_name!r} did not return a metric provider")

    @staticmethod
    def _is_valid(provider: MetricProvider) -> bool:
        if not isinstance(provider.name, str) or not provider.name:
            raise ValueError("provider name must not be empty")
        if not isinstance(provider.priority, int) or isinstance(provider.priority, bool):
            raise TypeError(f"provider {provider.name!r} priority must be an integer")
        if not provider.config_paths:
            raise ValueError(f"provider {provider.name!r} has no config paths")
        if isinstance(provider.config_paths, (str, bytes)):
            raise TypeError(f"provider {provider.name!r} config_paths must be a sequence")
        if any(not isinstance(path, str) or not path for path in provider.config_paths):
            raise ValueError(f"provider {provider.name!r} config_paths must contain non-empty strings")
        if isinstance(provider.owned_symbol_prefixes, (str, bytes)):
            raise TypeError(f"provider {provider.name!r} owned_symbol_prefixes must be a sequence")
        if not provider.owned_symbol_prefixes:
            raise ValueError(f"provider {provider.name!r} must declare owned_symbol_prefixes")
        ProviderRegistry._validate_module_prefixes(
            provider.name,
            "owned_symbol_prefixes",
            provider.owned_symbol_prefixes,
        )
        if isinstance(provider.handler_module_prefixes, (str, bytes)):
            raise TypeError(f"provider {provider.name!r} handler_module_prefixes must be a sequence")
        ProviderRegistry._validate_module_prefixes(
            provider.name,
            "handler_module_prefixes",
            provider.handler_module_prefixes,
        )
        if provider.ownership_mode not in SUPPORTED_OWNERSHIP_MODES:
            raise ValueError(
                f"provider {provider.name!r} ownership_mode must be one of {sorted(SUPPORTED_OWNERSHIP_MODES)}"
            )
        return True

    @staticmethod
    def resolve_ownership_conflicts(
        providers: list[MetricProvider],
    ) -> list[MetricProvider]:
        """Reject ambiguous ownership while allowing overlay providers to compose."""
        conflicting_indexes = set()
        for index, provider in enumerate(providers):
            for other_index in range(index + 1, len(providers)):
                other = providers[other_index]
                if (
                    provider.ownership_mode == PROVIDER_OWNERSHIP_OVERLAY
                    and other.ownership_mode == PROVIDER_OWNERSHIP_OVERLAY
                ):
                    continue
                conflict = next(
                    (
                        (prefix, other_prefix)
                        for prefix in provider.owned_symbol_prefixes
                        for other_prefix in other.owned_symbol_prefixes
                        if prefix.startswith(other_prefix) or other_prefix.startswith(prefix)
                    ),
                    None,
                )
                if conflict is None:
                    continue
                prefix, other_prefix = conflict
                conflicting_indexes.update((index, other_index))
                logger.warning(
                    "Skipping conflicting metric providers %s and %s: owned prefixes %s and %s overlap",
                    provider.name,
                    other.name,
                    prefix,
                    other_prefix,
                )

        return [provider for index, provider in enumerate(providers) if index not in conflicting_indexes]

    @staticmethod
    def _reject_duplicate_names(
        providers: list[MetricProvider],
    ) -> list[MetricProvider]:
        counts = {}
        for provider in providers:
            counts[provider.name] = counts.get(provider.name, 0) + 1

        duplicate_names = {name for name, count in counts.items() if count > 1}
        for name in sorted(duplicate_names):
            logger.warning(
                "Skipping all metric providers named %s because the name is ambiguous",
                name,
            )
        return [provider for provider in providers if provider.name not in duplicate_names]

    @staticmethod
    def _validate_module_prefixes(
        provider_name: str,
        field_name: str,
        prefixes: Sequence[str],
    ) -> None:
        for prefix in prefixes:
            if not isinstance(prefix, str) or not prefix or not prefix.endswith("."):
                raise ValueError(
                    f"provider {provider_name!r} {field_name} entries must be non-empty module prefixes ending with '.'"
                )
