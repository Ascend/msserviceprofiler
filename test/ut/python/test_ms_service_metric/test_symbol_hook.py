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
# pylint: disable=disallowed-name

import types
from unittest.mock import patch

from ms_service_metric.core.handler import MetricHandler, HandlerType
from ms_service_metric.core.symbol import Symbol


class DummyWatcher:
    def watch_module(self, _module_name, _callback):
        # tests trigger module-loaded callback manually
        return

    def unwatch_module(self, _module_name, _callback):
        return


class DummyManager:
    def is_updating(self):
        return False


class DummyTarget:
    def foo(self, x):
        return x * 2


def test_given_wrap_handler_when_module_loaded_then_wrapped_result_unhook_restores():
    module_path = __name__
    symbol_path = f"{module_path}:DummyTarget.foo"

    watcher = DummyWatcher()
    manager = DummyManager()
    symbol = Symbol(symbol_path, watcher=watcher, manager=manager)

    def wrap_handler(ori, *args, **kwargs):
        return ori(*args, **kwargs) + 1

    handler = MetricHandler(
        name="h1",
        symbol_info={"symbol_path": symbol_path},
        hook_func=wrap_handler,
        min_version=None,
        max_version=None,
        metrics_config=[],
    )
    # Make sure it is classified as WRAP.
    hook_type, _ = handler.get_hook_func(DummyTarget.foo)
    assert hook_type == HandlerType.WRAP

    symbol.add_handler(handler)

    # Simulate module loaded event -> should apply hook.
    event = types.SimpleNamespace(module_name=module_path)
    with patch("ms_service_metric.core.symbol.is_allowed_symbol_module", return_value=True):
        symbol._on_module_loaded(event)

    assert DummyTarget().foo(5) == 11  # (5*2)+1

    # Unhook should restore original behavior.
    symbol.unhook()
    assert DummyTarget().foo(5) == 10
