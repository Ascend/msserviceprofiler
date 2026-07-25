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

import ctypes
import os
import sys
import threading
import types

import pytest


def _memfd_create(name, flags=0):
    """Create an anonymous file - fallback to ctypes when os.memfd_create is not available."""
    if hasattr(os, 'memfd_create'):
        return os.memfd_create(name, flags)
    libc = ctypes.CDLL(None)
    return libc.memfd_create(name.encode() if isinstance(name, str) else name, flags)


_shm_registry = {}
_sem_registry = {}


def _clear_ipc_registry():
    """Clear IPC registries for test isolation."""
    for _name, entry in list(_shm_registry.items()):
        try:
            os.close(entry["fd"])
        except OSError:
            pass
    _shm_registry.clear()
    _sem_registry.clear()


def _install_posix_ipc_dummy():
    """Minimal `posix_ipc` stub so `shm_manager` / `MetricControlWatch` can import on CI.

    Uses Linux `memfd_create` + `mmap` compatible fds; keeps per-name registry like real IPC.
    """
    if "posix_ipc" in sys.modules:
        return

    class ExistentialError(Exception):
        pass

    O_CREX = 0x1000

    class SharedMemory:
        def __init__(self, name, flags=0, size=None):
            self._name = name
            if name in _shm_registry:
                if flags & O_CREX:
                    raise ExistentialError("shm exists")
                entry = _shm_registry[name]
                entry["refcount"] += 1
                self._entry = entry
                self.fd = entry["fd"]
                self.size = entry["size"]
                return
            if flags & O_CREX:
                if size is None:
                    raise ValueError("size required for O_CREX")
                fd = _memfd_create("ms_metric_ut_shm", 0)
                os.ftruncate(fd, size)
                entry = {"fd": fd, "size": size, "refcount": 1}
                _shm_registry[name] = entry
                self._entry = entry
                self.fd = fd
                self.size = size
            else:
                raise ExistentialError("shm missing")

        def close_fd(self):
            entry = getattr(self, "_entry", None)
            if not entry:
                return
            entry["refcount"] -= 1
            if entry["refcount"] <= 0:
                try:
                    os.close(entry["fd"])
                except OSError:
                    pass
                _shm_registry.pop(self._name, None)

    class Semaphore:
        def __init__(self, name, flags=0, initial_value=1):
            self._name = name
            if name in _sem_registry:
                if flags & O_CREX:
                    raise ExistentialError("sem exists")
                self._sem = _sem_registry[name]
                return
            if flags & O_CREX:
                sem = threading.Semaphore(initial_value)
                _sem_registry[name] = sem
                self._sem = sem
            else:
                raise ExistentialError("sem missing")

        def acquire(self, *args, **kwargs):
            return self._sem.acquire(*args, **kwargs)

        def release(self):
            self._sem.release()

        def close(self):
            # Unlink clears IPC name; disconnect only drops local handle (matches real ipc).
            pass

    def unlink_shared_memory(name):
        entry = _shm_registry.pop(name, None)
        if entry:
            try:
                os.close(entry["fd"])
            except OSError:
                pass

    def unlink_semaphore(name):
        _sem_registry.pop(name, None)

    mod = types.ModuleType("posix_ipc")
    mod.ExistentialError = ExistentialError
    mod.O_CREX = O_CREX
    mod.SharedMemory = SharedMemory
    mod.Semaphore = Semaphore
    mod.unlink_shared_memory = unlink_shared_memory
    mod.unlink_semaphore = unlink_semaphore
    sys.modules["posix_ipc"] = mod


def _find_repo_root() -> str:
    """Locate repository root by project marker files."""
    current = os.path.dirname(os.path.abspath(__file__))
    while current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, "pyproject.toml")) or os.path.exists(os.path.join(current, "setup.py")):
            return current
        current = os.path.dirname(current)
    # Fallback for CI/runtime layouts where marker files are unavailable in parent chain.
    fallback = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    if os.path.exists(os.path.join(fallback, "ms_service_metric")) and os.path.exists(
        os.path.join(fallback, "test", "ut", "python")
    ):
        return fallback
    raise RuntimeError("Cannot find project root from conftest.py")


def _ensure_import_paths():
    # Allow `import ms_service_metric` from workspace without installing wheels.
    repo_root = _find_repo_root()
    metric_pkg_root = os.path.join(repo_root, "ms_service_metric")
    if metric_pkg_root not in sys.path:
        sys.path.insert(0, metric_pkg_root)

    # Allow `import test_ms_service_metric.*` (needed for Symbol tests via importlib).
    test_python_root = os.path.join(repo_root, "test", "ut", "python")
    if test_python_root not in sys.path:
        sys.path.insert(0, test_python_root)


def _install_prometheus_client_dummy():
    """Install a minimal `prometheus_client` dummy.

    Repo runtime (and CI containers) often lack `prometheus_client`.
    `ms_service_metric.metrics.metrics_manager` requires real classes for `isinstance`.
    """
    if "prometheus_client" in sys.modules:
        return

    prom = types.ModuleType("prometheus_client")

    class DummyRegistry:
        def __init__(self):
            self._metrics = {}
            self._collector_to_names = {}

        def clear(self):
            self._metrics.clear()
            self._collector_to_names.clear()

        def unregister(self, _collector):
            return

    class CollectorRegistry(DummyRegistry):
        pass

    # Keep type semantics consistent with real prometheus_client.
    REGISTRY = CollectorRegistry()

    multiprocess_mod = types.ModuleType("prometheus_client.multiprocess")

    class MultiProcessCollector:
        def __init__(self, registry):
            self.registry = registry

    multiprocess_mod.MultiProcessCollector = MultiProcessCollector

    class _BaseMetric:
        def __init__(
            self,
            name,
            documentation=None,
            labelnames=None,
            registry=None,
        ):
            self.name = name
            self.documentation = documentation
            self.labelnames = labelnames or []
            self._registry = registry

            self._last_labels = None
            self._values = []
            self._last_inc = None
            self._last_set = None
            self._last_observe = None

            # mimic duplicate registration behavior
            if registry is not None and hasattr(registry, "_metrics"):
                if name in registry._metrics:
                    raise ValueError(f"Duplicated metric name: {name}")
                registry._metrics[name] = self

        def labels(self, **labels):
            self._last_labels = labels
            return self

    class Counter(_BaseMetric):
        def inc(self, value):
            self._values.append(value)
            self._last_inc = value

    class Gauge(_BaseMetric):
        def __init__(
            self,
            name,
            documentation=None,
            labelnames=None,
            registry=None,
            multiprocess_mode=None,
        ):
            super().__init__(name, documentation, labelnames, registry)
            self.multiprocess_mode = multiprocess_mode

        def set(self, value):
            self._values.append(value)
            self._last_set = value

    class Histogram(_BaseMetric):
        def __init__(
            self,
            name,
            documentation=None,
            labelnames=None,
            registry=None,
            buckets=None,
        ):
            super().__init__(name, documentation, labelnames, registry)
            self.buckets = buckets

        def observe(self, value):
            self._values.append(value)
            self._last_observe = value

    class Summary(_BaseMetric):
        def observe(self, value):
            self._values.append(value)
            self._last_observe = value

    prom.Counter = Counter
    prom.Gauge = Gauge
    prom.Histogram = Histogram
    prom.Summary = Summary
    prom.REGISTRY = REGISTRY
    prom.CollectorRegistry = CollectorRegistry
    prom.multiprocess = multiprocess_mod

    sys.modules["prometheus_client"] = prom
    sys.modules["prometheus_client.multiprocess"] = multiprocess_mod


_ensure_import_paths()

_install_posix_ipc_dummy()

_install_prometheus_client_dummy()


@pytest.fixture(autouse=True)
def _ensure_prometheus_client_dummy():
    _install_prometheus_client_dummy()
    yield


@pytest.fixture(autouse=True)
def _reset_global_state(_ensure_prometheus_client_dummy):
    # Import after dummy installed.
    from ms_service_metric.metrics.meta_state import reset_meta_state  # pylint: disable=no-name-in-module
    from ms_service_metric.metrics.metrics_manager import reset_metrics_manager  # pylint: disable=no-name-in-module
    from prometheus_client import REGISTRY

    _clear_ipc_registry()
    reset_meta_state()
    reset_metrics_manager()

    if hasattr(REGISTRY, "clear"):
        REGISTRY.clear()
    else:
        try:
            REGISTRY._metrics.clear()
        except Exception:
            pass

    yield
    _clear_ipc_registry()
