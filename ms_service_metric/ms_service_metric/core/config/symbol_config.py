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
SymbolConfig: 配置管理类

职责：
- 读取YAML配置文件
- 读取用户配置、默认配置
- 配置合并、自动赋默认值
- 所有配置相关的功能

配置格式示例（数组格式，与原始配置兼容）：
    - symbol: module.path:ClassName.method_name
      handler: module.path:function_name
      min_version: "0.1.0"
      max_version: "1.0.0"
      need_locals: false
      metrics:
        - name: metric_name
          type: timer
          expr: "duration"
          buckets: [0.1, 0.5, 1.0]

    - symbol: module.path:ClassName.method_name
      metrics:
        - name: metric_name
          type: timer
          labels:
            - name: label_name
              expr: "expression"
"""

import copy
import importlib
import math
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import yaml

from ms_service_metric.core.config.provider import (
    PROVIDER_OWNERSHIP_EXCLUSIVE,
    MetricProvider,
    ProviderRegistry,
)
from ms_service_metric.core.handler import MetricHandler
from ms_service_metric.core.external_handler_loader import resolve_external_handler_root
from ms_service_metric.utils.exceptions import ConfigError
from ms_service_metric.utils.import_security import is_allowed_handler_module
from ms_service_metric.utils.logger import get_logger
from ms_service_metric.utils.version import check_version_match, get_package_version

logger = get_logger("symbol_config")

_STABLE_PROVIDER_HANDLER_MODULES = (
    "ms_service_metric.handlers",
    "ms_service_metric.provider_handlers",
)
_VALID_PROVIDER_METRIC_TYPES = {
    "timer",
    "counter",
    "gauge",
    "histogram",
    "summary",
}
_PROMETHEUS_METRIC_NAME_PATTERN = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")
_PROMETHEUS_LABEL_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@dataclass(frozen=True)
class SymbolConfigState:
    """Committed configuration state used to roll back a failed reload."""

    config: Dict[str, List[dict]]
    current_version: Optional[str]
    user_config_path: Optional[str]
    default_config_path: Optional[str]
    framework_config_is_user: bool
    user_handler_root: Optional[str]
    allowed_handler_module_prefixes: Tuple[str, ...]
    allowed_symbol_module_prefixes: Tuple[str, ...]
    active_provider_names: Tuple[str, ...]


class SymbolConfig:
    """Symbol配置管理类

    负责加载和合并用户配置与默认配置，提供统一的配置访问接口。
    """

    # 环境变量名称
    ENV_CONFIG_PATH = "MS_SERVICE_METRIC_CONFIG_PATH"

    def __init__(
        self,
        user_config_path: Optional[str] = None,
        default_config_path: Optional[str] = None,
        current_version: Optional[str] = None,
        provider_registry: Optional[ProviderRegistry] = None,
        framework_config_is_user: bool = False,
    ):
        """
        初始化配置管理器

        Args:
            user_config_path: 用户配置文件路径
            default_config_path: 默认配置文件路径
            current_version: 当前框架版本，用于版本控制
        """
        self._user_config_path = user_config_path
        self._default_config_path = default_config_path or os.path.join(os.path.dirname(__file__), "config.yaml")
        self._config: Dict[str, List[dict]] = {}
        self._current_version = current_version
        self._provider_registry = provider_registry
        self._framework_config_is_user = framework_config_is_user
        self._user_handler_root: Optional[str] = None
        self._allowed_handler_module_prefixes: Tuple[str, ...] = ()
        self._allowed_symbol_module_prefixes: Tuple[str, ...] = ()
        self._active_provider_names: Tuple[str, ...] = ()

        logger.debug(
            "SymbolConfig initialized: user=%s, default=%s, version=%s",
            user_config_path,
            default_config_path,
            current_version,
        )

    def load(
        self,
        config_path: Optional[str] = None,
        default_config_path: Optional[str] = None,
        current_version: Optional[str] = None,
        framework_config_is_user: Optional[bool] = None,
    ) -> Dict[str, List[dict]]:
        """
        加载并合并配置

        加载顺序：
        1. 加载默认配置
        2. 加载用户配置（优先使用传入的config_path，其次使用构造函数传入的路径）
        3. 合并配置（用户配置覆盖默认配置）
        4. 根据版本过滤配置
        5. 填充默认值

        Args:
            config_path: 可选的配置文件路径，如果提供则作为用户配置加载
            current_version: 当前框架版本，如果提供则覆盖构造函数传入的版本

        Returns:
            合并后的配置字典，key为symbol_path，value为handler配置列表
        """
        logger.info("Loading configuration...")

        effective_version = current_version if current_version is not None else self._current_version
        effective_framework_config_is_user = (
            framework_config_is_user if framework_config_is_user is not None else self._framework_config_is_user
        )
        effective_default_path = default_config_path if default_config_path is not None else self._default_config_path
        effective_framework_path = config_path if config_path is not None else self._user_config_path

        # Resolve a candidate snapshot without mutating the committed state.
        logger.info("Default config path: %s", effective_default_path)
        logger.info(
            "Framework config path: %s",
            effective_framework_path or "Not set",
        )

        # Paths and version are committed only after all sources validate.
        default_config = self._filter_config_by_version(
            self._load_config_path(effective_default_path, "default"),
            effective_version,
            "default",
        )
        logger.debug("Default config loaded: %s symbols", len(default_config))

        # 2. Preserve the existing contract: an environment config replaces
        # the adapter config path instead of being appended to it.
        environment_path = os.environ.get(self.ENV_CONFIG_PATH)
        if environment_path:
            environment_path = os.path.expanduser(environment_path)
        framework_path = None if self._path_exists(environment_path) else effective_framework_path
        user_handler_root = resolve_external_handler_root(
            environment_path,
            effective_framework_path,
            effective_framework_config_is_user,
        )
        framework_config = self._filter_config_by_version(
            self._load_config_path(framework_path, "framework"),
            effective_version,
            "framework",
        )
        user_config = self._filter_config_by_version(
            self._load_config_path(environment_path, "environment"),
            effective_version,
            "environment",
        )

        candidate_providers = self._activate_providers(self._discover_providers())
        merged_config = self._merge_configs(default_config, framework_config)
        active_providers = []
        for provider, provider_config in candidate_providers:
            # A Provider migrates one complete symbol at a time. Overlay mode
            # replaces only symbols it contributes; symbols not yet migrated
            # continue to use the Core/Adapter fallback.
            candidate_base = merged_config
            if provider.ownership_mode == PROVIDER_OWNERSHIP_EXCLUSIVE:
                candidate_base = self._filter_provider_owned_symbols(
                    candidate_base,
                    [provider],
                )
            try:
                self._validate_metric_schema_compatibility(
                    provider.name,
                    candidate_base,
                    provider_config,
                )
            except ConfigError as error:
                logger.warning(
                    "Skipping metric provider %s before activation: %s",
                    provider.name,
                    error,
                )
                continue
            merged_config = self._override_configs(
                candidate_base,
                provider_config,
            )
            active_providers.append((provider, provider_config))
            logger.info(
                "Loaded active metric provider %s in %s mode with %s symbols",
                provider.name,
                provider.ownership_mode,
                len(provider_config),
            )

        if effective_framework_config_is_user:
            merged_config = self._override_configs(
                merged_config,
                framework_config,
            )
        merged_config = self._merge_configs(merged_config, user_config)

        merged_config = self._fill_defaults(merged_config)
        active_descriptors = [provider for provider, _ in active_providers]
        allowed_handler_module_prefixes = tuple(
            dict.fromkeys(prefix for provider in active_descriptors for prefix in provider.handler_module_prefixes)
        )
        allowed_symbol_module_prefixes = tuple(
            dict.fromkeys(prefix for provider in active_descriptors for prefix in provider.owned_symbol_prefixes)
        )
        active_provider_names = tuple(provider.name for provider in active_descriptors)

        self._current_version = effective_version
        self._framework_config_is_user = effective_framework_config_is_user
        self._default_config_path = effective_default_path
        self._user_config_path = effective_framework_path
        self._user_handler_root = user_handler_root
        self._config = merged_config
        self._allowed_handler_module_prefixes = allowed_handler_module_prefixes
        self._allowed_symbol_module_prefixes = allowed_symbol_module_prefixes
        self._active_provider_names = active_provider_names

        logger.info("Configuration loaded successfully: %s symbols", len(self._config))
        return self._config

    def reload(self) -> Dict[str, List[dict]]:
        """Reload and replace the committed snapshot only after validation."""
        logger.info("Reloading configuration...")
        return self.load()

    def _discover_providers(self):
        if self._provider_registry is None:
            return []
        return self._provider_registry.discover()

    def _activate_providers(
        self,
        providers: Sequence[MetricProvider],
    ) -> List[Tuple[MetricProvider, dict]]:
        """Load and validate providers before allowing namespace ownership."""
        loaded = []
        for provider in providers:
            try:
                provider_config = self._load_provider_config(provider)
                provider_version = self._get_provider_config_version(
                    provider,
                    provider_config,
                )
                provider_config = self._filter_config_by_version(
                    provider_config,
                    provider_version,
                    f"provider {provider.name}",
                    strict=True,
                )
                self._validate_provider_config(provider, provider_config)
                loaded.append((provider, provider_config))
            except Exception as error:
                logger.warning(
                    "Skipping metric provider %s before activation: %s",
                    provider.name,
                    error,
                )

        active_descriptors = ProviderRegistry.resolve_ownership_conflicts([provider for provider, _ in loaded])
        return [
            (provider, config)
            for provider, config in loaded
            if any(provider is active for active in active_descriptors)
        ]

    def _load_provider_config(self, provider: MetricProvider) -> dict:
        merged = {}
        for path in provider.config_paths:
            if not os.path.isfile(path):
                raise ConfigError(f"Metric provider {provider.name!r} config is not a file: {path}")
            config = self._load_yaml(path, strict=True)
            if not config:
                raise ConfigError(f"Metric provider {provider.name!r} config is empty: {path}")
            merged = self._merge_configs(merged, config)
        if not merged:
            raise ConfigError(f"Metric provider {provider.name!r} has no active configuration")
        return merged

    @staticmethod
    def _get_provider_config_version(
        provider: MetricProvider,
        config: dict,
    ) -> Optional[str]:
        has_version_bounds = any(
            handler.get("min_version") or handler.get("max_version")
            for handlers in config.values()
            for handler in (handlers if isinstance(handlers, list) else [handlers])
            if isinstance(handler, dict)
        )
        if not has_version_bounds:
            return None
        if not provider.framework_package:
            raise ConfigError(f"Metric provider {provider.name!r} uses version bounds without framework_package")
        framework_version = get_package_version(provider.framework_package)
        if framework_version is None:
            raise ConfigError(f"Cannot determine version of provider package {provider.framework_package!r}")
        return framework_version

    @staticmethod
    def _validate_provider_config(
        provider: MetricProvider,
        config: dict,
    ) -> None:
        symbols = tuple(config)
        for symbol_path, handlers in config.items():
            if not isinstance(symbol_path, str) or ":" not in symbol_path:
                raise ConfigError(f"Metric provider {provider.name!r} has invalid symbol {symbol_path!r}")
            if provider.owned_symbol_prefixes and not symbol_path.startswith(tuple(provider.owned_symbol_prefixes)):
                raise ConfigError(
                    f"Metric provider {provider.name!r} config symbol {symbol_path!r} is outside its owned namespaces"
                )

            handler_configs = handlers if isinstance(handlers, list) else [handlers]
            if not handler_configs:
                raise ConfigError(f"Metric provider {provider.name!r} symbol {symbol_path!r} has no handlers")
            for handler_config in handler_configs:
                if not isinstance(handler_config, dict):
                    raise ConfigError(
                        f"Metric provider {provider.name!r} has a non-mapping handler for {symbol_path!r}"
                    )
                handler_path = handler_config.get("handler")
                metrics = handler_config.get("metrics")
                if not handler_path and not metrics:
                    raise ConfigError(
                        f"Metric provider {provider.name!r} handler for "
                        f"{symbol_path!r} defines neither handler nor metrics"
                    )
                if handler_path:
                    if not isinstance(handler_path, str) or ":" not in handler_path:
                        raise ConfigError(
                            f"Metric provider {provider.name!r} has invalid handler path {handler_path!r}"
                        )
                    module_path, _ = handler_path.rsplit(":", 1)
                    if not is_allowed_handler_module(
                        module_path,
                        provider.handler_module_prefixes,
                    ):
                        raise ConfigError(
                            f"Metric provider {provider.name!r} handler module {module_path!r} is not allowed"
                        )
                    is_provider_handler = module_path.startswith(tuple(provider.handler_module_prefixes))
                    is_stable_core_handler = module_path in _STABLE_PROVIDER_HANDLER_MODULES
                    if not is_provider_handler and not is_stable_core_handler:
                        raise ConfigError(
                            f"Metric provider {provider.name!r} handler module "
                            f"{module_path!r} is a Core internal module; use "
                            "ms_service_metric.provider_handlers or a "
                            "Provider-owned handler"
                        )
                    if module_path == "ms_service_metric.provider_handlers":
                        _, handler_name = handler_path.rsplit(":", 1)
                        stable_module = importlib.import_module(module_path)
                        if handler_name not in stable_module.__all__:
                            raise ConfigError(
                                f"Metric provider {provider.name!r} references unknown stable handler {handler_path!r}"
                            )
                    else:
                        MetricHandler._import_handler(
                            handler_path,
                            provider.handler_module_prefixes,
                        )
                SymbolConfig._validate_provider_metrics(
                    provider.name,
                    symbol_path,
                    metrics,
                )

        for prefix in provider.owned_symbol_prefixes:
            if not any(symbol.startswith(prefix) for symbol in symbols):
                raise ConfigError(f"Metric provider {provider.name!r} owns {prefix!r} but provides no matching symbols")

    @staticmethod
    def _validate_provider_metrics(
        provider_name: str,
        symbol_path: str,
        metrics,
    ) -> None:
        if metrics is None:
            return
        metric_configs = metrics if isinstance(metrics, list) else [metrics]
        for metric in metric_configs:
            if not isinstance(metric, dict):
                raise ConfigError(f"Metric provider {provider_name!r} has a non-mapping metric for {symbol_path!r}")
            metric_name = metric.get("name")
            if not isinstance(metric_name, str) or not metric_name:
                raise ConfigError(f"Metric provider {provider_name!r} has an unnamed metric for {symbol_path!r}")
            normalized_name = SymbolConfig._normalize_metric_name(metric_name)
            if not _PROMETHEUS_METRIC_NAME_PATTERN.fullmatch(normalized_name):
                raise ConfigError(
                    f"Metric provider {provider_name!r} metric {metric_name!r} has an invalid Prometheus name"
                )
            metric_type = metric.get("type", "timer")
            if metric_type not in _VALID_PROVIDER_METRIC_TYPES:
                raise ConfigError(
                    f"Metric provider {provider_name!r} metric {metric_name!r} has invalid type {metric_type!r}"
                )
            if "expr" in metric and not isinstance(metric["expr"], str):
                raise ConfigError(f"Metric provider {provider_name!r} metric {metric_name!r} has a non-string expr")
            if "buckets" in metric and not isinstance(metric["buckets"], list):
                raise ConfigError(f"Metric provider {provider_name!r} metric {metric_name!r} has non-list buckets")
            buckets = metric.get("buckets") or []
            if any(
                isinstance(bucket, bool) or not isinstance(bucket, (int, float)) or not math.isfinite(bucket)
                for bucket in buckets
            ):
                raise ConfigError(
                    f"Metric provider {provider_name!r} metric {metric_name!r} has a non-finite numeric bucket"
                )
            if any(current >= following for current, following in zip(buckets, buckets[1:])):
                raise ConfigError(
                    f"Metric provider {provider_name!r} metric {metric_name!r} buckets must be strictly increasing"
                )
            labels = metric.get("labels", [])
            if not isinstance(labels, list):
                raise ConfigError(f"Metric provider {provider_name!r} metric {metric_name!r} has non-list labels")
            if any(
                not isinstance(label, dict)
                or not isinstance(label.get("name"), str)
                or not label.get("name")
                or not isinstance(label.get("expr"), str)
                for label in labels
            ):
                raise ConfigError(
                    f"Metric provider {provider_name!r} metric {metric_name!r} has an invalid label definition"
                )
            label_names = [label["name"] for label in labels]
            if len(label_names) != len(set(label_names)) or any(
                not _PROMETHEUS_LABEL_NAME_PATTERN.fullmatch(label_name) for label_name in label_names
            ):
                raise ConfigError(
                    f"Metric provider {provider_name!r} metric {metric_name!r} has invalid Prometheus labels"
                )

    @staticmethod
    def _normalize_metric_name(metric_name: str) -> str:
        normalized = metric_name.replace("-", "_")
        if normalized and normalized[0].isdigit():
            normalized = f"fn_{normalized}"
        return normalized

    @classmethod
    def _validate_metric_schema_compatibility(
        cls,
        provider_name: str,
        base_config: dict,
        provider_config: dict,
    ) -> None:
        base_schemas = cls._collect_metric_schemas(base_config, "Core", reject_conflicts=False)
        provider_schemas = cls._collect_metric_schemas(
            provider_config,
            f"provider {provider_name!r}",
            reject_conflicts=True,
        )
        for metric_name, provider_schema in provider_schemas.items():
            base_schema = base_schemas.get(metric_name)
            if base_schema is not None and base_schema != provider_schema:
                raise ConfigError(
                    f"Metric provider {provider_name!r} metric {metric_name!r} conflicts with "
                    f"the existing schema {base_schema!r}; provider schema is {provider_schema!r}"
                )

    @classmethod
    def _collect_metric_schemas(
        cls,
        config: dict,
        source: str,
        reject_conflicts: bool,
    ) -> dict:
        schemas = {}
        for handlers in config.values():
            for handler in handlers if isinstance(handlers, list) else [handlers]:
                if not isinstance(handler, dict):
                    continue
                metrics = handler.get("metrics", [])
                for metric in metrics if isinstance(metrics, list) else [metrics]:
                    if not isinstance(metric, dict) or not isinstance(metric.get("name"), str):
                        continue
                    metric_name = cls._normalize_metric_name(metric["name"])
                    metric_type = metric.get("type", "timer")
                    labels = metric.get("labels", [])
                    label_names = tuple(
                        sorted(
                            label["name"]
                            for label in labels
                            if isinstance(label, dict) and isinstance(label.get("name"), str)
                        )
                    )
                    buckets = metric.get("buckets") or []
                    bucket_schema = tuple(buckets) if metric_type in {"timer", "histogram"} else ()
                    schema = (metric_type, label_names, bucket_schema)
                    existing = schemas.get(metric_name)
                    if existing is not None and existing != schema and reject_conflicts:
                        raise ConfigError(
                            f"{source} declares conflicting schemas for metric {metric_name!r}: "
                            f"{existing!r} and {schema!r}"
                        )
                    schemas.setdefault(metric_name, schema)
        return schemas

    @staticmethod
    def _filter_provider_owned_symbols(config: dict, providers) -> dict:
        """Remove fallback symbols owned by active exclusive Providers."""
        owned_prefixes = tuple(prefix for provider in providers for prefix in provider.owned_symbol_prefixes)
        if not owned_prefixes:
            return config

        filtered = {}
        for symbol_path, handlers in config.items():
            if symbol_path.startswith(owned_prefixes):
                logger.info(
                    "Skipping adapter metric %s because its namespace is provider-owned",
                    symbol_path,
                )
                continue
            filtered[symbol_path] = handlers
        return filtered

    def _load_config_path(self, path: Optional[str], source: str) -> dict:
        if not path:
            return {}
        if not os.path.exists(path):
            logger.warning("Metric config from %s does not exist: %s", source, path)
            return {}
        if os.path.isfile(path):
            return self._load_yaml(path)
        if not os.path.isdir(path):
            logger.warning("Metric config from %s is neither a file nor directory: %s", source, path)
            return {}

        config = {}
        try:
            with os.scandir(path) as entries:
                yaml_paths = sorted(
                    (
                        entry.path
                        for entry in entries
                        if entry.is_file() and os.path.splitext(entry.name)[1].lower() in {".yaml", ".yml"}
                    ),
                    key=lambda item: (
                        os.path.basename(item).casefold(),
                        os.path.basename(item),
                    ),
                )
        except OSError as error:
            raise ConfigError(f"Failed to scan metric config directory {path}: {error}") from error
        for yaml_path in yaml_paths:
            config = self._merge_configs(config, self._load_yaml(yaml_path))
        logger.info(
            "Loaded %s metric YAML file(s) from %s directory: %s",
            len(yaml_paths),
            source,
            path,
        )
        return config

    @staticmethod
    def _path_exists(path: Optional[str]) -> bool:
        return bool(path and os.path.exists(path))

    def _load_yaml(self, path: str, strict: bool = False) -> dict:
        """
        加载YAML文件

        支持两种格式：
        1. 数组格式（原始格式）: [{symbol: ..., handler: ...}, ...]
        2. 字典格式: {symbol_path: [handlers...], ...}

        统一转换为字典格式返回。

        Args:
            path: YAML文件路径

        Returns:
            解析后的字典，格式为 {symbol_path: [handler_configs...]}

        Raises:
            ConfigError: 文件读取或解析失败
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)

            if not content:
                return {}

            # 如果是列表格式（原始配置格式），转换为字典格式
            if isinstance(content, list):
                config = self._convert_array_config(content, strict=strict)
                if strict:
                    self._validate_strict_config_shape(path, config)
                return config

            # 如果是字典格式，直接返回
            if isinstance(content, dict):
                if strict:
                    self._validate_strict_config_shape(path, content)
                return content

            message = f"Unexpected config format in {path}: {type(content)}"
            if strict:
                raise ConfigError(message)
            logger.warning(message)
            return {}

        except FileNotFoundError:
            logger.error("Config file not found: %s", path)
            raise ConfigError(f"Config file not found: {path}")
        except yaml.YAMLError as e:
            logger.error("Failed to parse YAML file %s: %s", path, e)
            raise ConfigError(f"Failed to parse YAML file {path}: {e}")
        except Exception as e:
            logger.error("Failed to load config file %s: %s", path, e)
            raise ConfigError(f"Failed to load config file {path}: {e}")

    @staticmethod
    def _validate_strict_config_shape(source: str, config: dict) -> None:
        """Validate every raw entry before semantic deduplication can hide it."""
        for symbol_path, handlers in config.items():
            if not isinstance(symbol_path, str) or ":" not in symbol_path:
                raise ConfigError(f"Strict metric config {source!r} has invalid symbol {symbol_path!r}")
            handler_configs = handlers if isinstance(handlers, list) else [handlers]
            if not handler_configs:
                raise ConfigError(f"Strict metric config {source!r} symbol {symbol_path!r} has no handlers")
            for handler_config in handler_configs:
                if not isinstance(handler_config, dict):
                    raise ConfigError(f"Strict metric config {source!r} has a non-mapping handler for {symbol_path!r}")
                handler_path = handler_config.get("handler")
                metrics = handler_config.get("metrics")
                if not handler_path and not metrics:
                    raise ConfigError(
                        f"Strict metric config {source!r} handler for "
                        f"{symbol_path!r} defines neither handler nor metrics"
                    )
                if handler_path and (not isinstance(handler_path, str) or ":" not in handler_path):
                    raise ConfigError(f"Strict metric config {source!r} has invalid handler path {handler_path!r}")
                SymbolConfig._validate_provider_metrics(
                    f"config {source}",
                    symbol_path,
                    metrics,
                )

    def _convert_array_config(
        self,
        config_list: list,
        strict: bool = False,
    ) -> dict:
        """
        将数组格式的配置转换为字典格式

        原始格式: [{symbol: ..., handler: ..., metrics: ...}, ...]
        目标格式: {symbol_path: [{handler: ..., metrics: ...}], ...}

        与原项目配置格式保持一致：
        - 有handler字段：使用指定的handler
        - 无handler字段但有metrics字段：使用默认handler（在Handler.from_config中处理）

        Args:
            config_list: 数组格式的配置列表

        Returns:
            字典格式的配置
        """
        result = {}

        for item in config_list:
            if not isinstance(item, dict):
                message = f"Invalid config item: {item}"
                if strict:
                    raise ConfigError(message)
                logger.warning(message)
                continue

            # 获取symbol路径
            symbol_path = item.get('symbol')
            if not isinstance(symbol_path, str) or not symbol_path:
                message = f"Config item has invalid 'symbol' field: {item}"
                if strict:
                    raise ConfigError(message)
                logger.warning(message)
                continue

            # 构建handler配置（排除symbol字段）
            handler_config = {k: v for k, v in item.items() if k != 'symbol'}

            # 注意：不自动添加handler字段
            # 如果没有handler但有metrics，Handler.from_config会使用默认handler

            # 添加到结果
            if symbol_path not in result:
                result[symbol_path] = []
            result[symbol_path].append(handler_config)

            logger.debug("Converted config for symbol: %s", symbol_path)

        return result

    def _merge_configs(self, default: dict, user: dict) -> dict:
        """
        合并配置

        合并策略：
        - 对于同一个symbol，用户配置的handlers追加到默认配置后面
        - 对于新的symbol，直接添加

        Args:
            default: 默认配置
            user: 用户配置

        Returns:
            合并后的配置
        """
        # 深拷贝默认配置
        merged = {
            symbol_path: copy.deepcopy(self._deduplicate_handlers(symbol_path, handlers))
            for symbol_path, handlers in default.items()
        }

        for symbol_path, handlers in user.items():
            incoming_handlers = handlers if isinstance(handlers, list) else [handlers]
            incoming_handlers = self._deduplicate_handlers(
                symbol_path,
                incoming_handlers,
            )
            if symbol_path in merged:
                existing_handlers = merged[symbol_path]
                if not isinstance(existing_handlers, list):
                    existing_handlers = [existing_handlers]
                    merged[symbol_path] = existing_handlers
                fingerprints = {self._handler_fingerprint(handler) for handler in existing_handlers}
                for handler in incoming_handlers:
                    fingerprint = self._handler_fingerprint(handler)
                    if fingerprint in fingerprints:
                        logger.warning(
                            "Skipping duplicate metric handler for symbol %s",
                            symbol_path,
                        )
                        continue
                    existing_handlers.append(copy.deepcopy(handler))
                    fingerprints.add(fingerprint)
                logger.debug("Merged handlers for symbol: %s", symbol_path)
            else:
                merged[symbol_path] = copy.deepcopy(incoming_handlers)
                logger.debug("Added new symbol: %s", symbol_path)

        return merged

    @staticmethod
    def _handler_fingerprint(handler) -> str:
        if isinstance(handler, dict):
            return MetricHandler._fingerprint_config(handler)
        return yaml.safe_dump(handler, sort_keys=True)

    def _deduplicate_handlers(self, symbol_path: str, handlers) -> list:
        unique_handlers = []
        fingerprints = set()
        for handler in handlers if isinstance(handlers, list) else [handlers]:
            fingerprint = self._handler_fingerprint(handler)
            if fingerprint in fingerprints:
                logger.warning(
                    "Skipping duplicate metric handler for symbol %s",
                    symbol_path,
                )
                continue
            fingerprints.add(fingerprint)
            unique_handlers.append(handler)
        return unique_handlers

    def _override_configs(self, base: dict, override: dict) -> dict:
        """Replace lower-priority handlers for symbols explicitly configured."""
        merged = copy.deepcopy(base)
        for symbol_path, handlers in override.items():
            merged[symbol_path] = copy.deepcopy(self._deduplicate_handlers(symbol_path, handlers))
            logger.info("Overrode metric handlers for symbol %s", symbol_path)
        return merged

    @staticmethod
    def _filter_config_by_version(
        config: dict,
        current_version: Optional[str],
        source: str,
        strict: bool = False,
    ) -> dict:
        """根据版本过滤配置

        检查每个handler的min_version和max_version，
        如果当前版本不符合要求，则过滤掉该handler。
        """
        if not current_version:
            logger.debug(
                "No current version specified, skipping version filter for %s",
                source,
            )
            return config

        logger.info("Filtering %s configs by version: %s", source, current_version)

        filtered_config: Dict[str, List[dict]] = {}

        for symbol_path, handlers in config.items():
            if not isinstance(handlers, list):
                handlers = [handlers]

            filtered_handlers = []
            for handler in handlers:
                if not isinstance(handler, dict):
                    if strict:
                        raise ConfigError(f"Invalid handler config for {symbol_path!r} in {source}: expected mapping")
                    continue

                min_version = handler.get('min_version')
                max_version = handler.get('max_version')

                # 检查版本是否匹配
                if check_version_match(current_version, min_version, max_version):
                    filtered_handlers.append(handler)
                    logger.debug(
                        "Handler for %s matches version requirements",
                        symbol_path,
                    )
                else:
                    logger.info(
                        "Handler for %s filtered out: current=%s, min=%s, max=%s",
                        symbol_path,
                        current_version,
                        min_version,
                        max_version,
                    )

            # 只保留有handler的symbol
            if filtered_handlers:
                filtered_config[symbol_path] = filtered_handlers
            else:
                logger.debug(
                    "Symbol %s has no handlers after version filter",
                    symbol_path,
                )

        return filtered_config

    @staticmethod
    def _fill_defaults(config: dict) -> dict:
        """
        为配置填充默认值

        为每个handler填充默认配置项。
        """
        for symbol_path, handlers in config.items():
            if not isinstance(handlers, list):
                handlers = [handlers]
                config[symbol_path] = handlers

            for handler in handlers:
                if not isinstance(handler, dict):
                    logger.warning(
                        "Invalid handler config for %s: %s",
                        symbol_path,
                        handler,
                    )
                    continue

                # 填充默认值
                handler.setdefault('type', 'wrap')
                handler.setdefault('enabled', True)
                handler.setdefault('need_locals', False)
                handler.setdefault('lock_patch', False)
                handler.setdefault('metrics', [])

                # 确保metrics是列表
                if not isinstance(handler.get('metrics'), list):
                    handler['metrics'] = [handler['metrics']] if handler['metrics'] else []

        return config

    def get_config(self) -> Dict[str, List[dict]]:
        """
        获取当前配置

        Returns:
            当前配置字典
        """
        return self._config

    def get_allowed_handler_module_prefixes(self) -> Tuple[str, ...]:
        """Return handler module prefixes contributed by active providers."""
        return self._allowed_handler_module_prefixes

    def get_user_handler_root(self) -> Optional[str]:
        """Return the committed root for user-owned external Handler files."""
        return self._user_handler_root

    def get_allowed_symbol_module_prefixes(self) -> Tuple[str, ...]:
        """Return Symbol module prefixes contributed by active providers."""
        return self._allowed_symbol_module_prefixes

    def get_active_provider_names(self) -> Tuple[str, ...]:
        """Return providers that completed activation for this configuration."""
        return self._active_provider_names

    def snapshot_state(self) -> SymbolConfigState:
        """Capture the current immutable-by-replacement configuration state."""
        return SymbolConfigState(
            config=self._config,
            current_version=self._current_version,
            user_config_path=self._user_config_path,
            default_config_path=self._default_config_path,
            framework_config_is_user=self._framework_config_is_user,
            user_handler_root=self._user_handler_root,
            allowed_handler_module_prefixes=self._allowed_handler_module_prefixes,
            allowed_symbol_module_prefixes=self._allowed_symbol_module_prefixes,
            active_provider_names=self._active_provider_names,
        )

    def restore_state(self, state: SymbolConfigState) -> None:
        """Restore a state captured before a failed Handler build."""
        self._config = state.config
        self._current_version = state.current_version
        self._user_config_path = state.user_config_path
        self._default_config_path = state.default_config_path
        self._framework_config_is_user = state.framework_config_is_user
        self._user_handler_root = state.user_handler_root
        self._allowed_handler_module_prefixes = state.allowed_handler_module_prefixes
        self._allowed_symbol_module_prefixes = state.allowed_symbol_module_prefixes
        self._active_provider_names = state.active_provider_names

    def get_symbol_config(self, symbol_path: str) -> List[dict]:
        """
        获取指定symbol的配置

        Args:
            symbol_path: symbol路径

        Returns:
            symbol的handler配置列表，如果不存在返回空列表
        """
        return self._config.get(symbol_path, [])
