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
"""Load explicitly configured user Handlers without changing ``sys.path``."""

import hashlib
import importlib.util
import sys
import threading
from pathlib import Path
from types import ModuleType
from typing import Optional

from ms_service_metric.utils.exceptions import HandlerError

_MODULE_LOAD_LOCK = threading.RLock()


def resolve_external_handler_root(
    environment_path: Optional[str],
    framework_path: Optional[str],
    framework_config_is_user: bool,
) -> Optional[str]:
    """Resolve the user-owned configuration directory, if one is active."""
    candidate = environment_path if _path_exists(environment_path) else None
    if candidate is None and framework_config_is_user and _path_exists(framework_path):
        candidate = framework_path
    if candidate is None:
        return None

    resolved = Path(candidate).expanduser().resolve(strict=True)
    return str(resolved if resolved.is_dir() else resolved.parent)


def _path_exists(path: Optional[str]) -> bool:
    return bool(path and Path(path).expanduser().exists())


def load_external_handler_module(module_path: str, handler_root: str) -> ModuleType:
    """Load ``module_path`` from a trusted user configuration directory."""
    module_parts = module_path.split(".")
    if not module_path or any(not part.isidentifier() for part in module_parts):
        raise HandlerError(f"Invalid external Handler module path: {module_path!r}")

    try:
        root = Path(handler_root).expanduser().resolve(strict=True)
    except (FileNotFoundError, RuntimeError) as error:
        raise HandlerError(f"External Handler root does not exist: {handler_root}") from error
    if not root.is_dir():
        raise HandlerError(f"External Handler root is not a directory: {handler_root}")

    module_file = root.joinpath(*module_parts).with_suffix(".py")
    try:
        resolved_file = module_file.resolve(strict=True)
        resolved_file.relative_to(root)
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        raise HandlerError(f"External Handler module not found under configured root: {module_path}") from error

    if not resolved_file.is_file():
        raise HandlerError(f"External Handler module is not a file: {resolved_file}")

    module_key = hashlib.sha256(str(resolved_file).encode("utf-8")).hexdigest()
    synthetic_name = f"_ms_service_metric_external_handler_{module_key}"
    with _MODULE_LOAD_LOCK:
        loaded_module = sys.modules.get(synthetic_name)
        if loaded_module is not None:
            return loaded_module

        spec = importlib.util.spec_from_file_location(synthetic_name, resolved_file)
        if spec is None or spec.loader is None:
            raise HandlerError(f"Cannot create module spec for external Handler: {resolved_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[synthetic_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as error:
            sys.modules.pop(synthetic_name, None)
            raise HandlerError(f"Failed to load external Handler module: {resolved_file}") from error
        return module
