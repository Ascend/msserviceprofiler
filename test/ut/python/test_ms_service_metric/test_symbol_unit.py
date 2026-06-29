# -------------------------------------------------------------------------
# pylint: disable=no-name-in-module,redefined-outer-name
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

"""Lightweight Symbol tests with mocked watcher / manager."""

from unittest.mock import MagicMock, patch

import pytest

from ms_service_metric.core.handler import MetricHandler
from ms_service_metric.core.symbol import Symbol
from ms_service_metric.utils.exceptions import SymbolError


@pytest.fixture
def no_watch_symbol():
    """Avoid real SymbolWatcher registration during __init__."""
    with patch.object(Symbol, "_start_watching", lambda self: None):
        w = MagicMock()
        mgr = MagicMock()
        sym = Symbol("my.mod:MyClass.run", w, mgr)
        try:
            yield sym, w, mgr
        finally:
            sym.stop()


def test_given_path_without_colon_when_construct_symbol_then_raises_symbol_error():
    w = MagicMock()
    m = MagicMock()
    with pytest.raises(SymbolError):
        Symbol("no_colon", w, m)


def test_given_same_handler_twice_when_add_handler_then_single_entry(no_watch_symbol):
    sym, _, _ = no_watch_symbol
    h = MetricHandler.from_config({"handler": "ms_service_metric.handlers:default_handler"}, "my.mod:MyClass.run")
    sym.add_handler(h)
    sym.add_handler(h)
    assert len(sym.get_all_handlers()) == 1


def test_given_unknown_handler_id_when_remove_handler_then_noop(no_watch_symbol):
    sym, _, _ = no_watch_symbol
    sym.remove_handler("missing-id")


def test_given_handler_added_when_remove_then_get_returns_none(no_watch_symbol):
    sym, _, _ = no_watch_symbol
    h = MetricHandler.from_config({"handler": "ms_service_metric.handlers:default_handler"}, "my.mod:MyClass.run")
    sym.add_handler(h)
    hid = h.id
    assert sym.get_handler(hid) is h
    sym.remove_handler(hid)
    assert sym.get_handler(hid) is None


def test_given_no_handlers_when_is_empty_and_has_handler_then_expected(no_watch_symbol):
    sym, _, _ = no_watch_symbol
    assert sym.is_empty() is True
    assert sym.has_handler("nope") is False


def test_given_target_module_not_loaded_when_hook_then_no_apply(no_watch_symbol):
    sym, _, _ = no_watch_symbol
    sym.hook()


def test_given_hook_not_applied_when_unhook_then_noop(no_watch_symbol):
    sym, _, _ = no_watch_symbol
    sym.unhook()
