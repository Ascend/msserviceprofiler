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

"""MetricControlWatch start/stop and control-side helpers."""

# Pytest injects fixtures by matching argument names.
# pylint: disable=redefined-outer-name

import uuid
from unittest.mock import patch

import pytest
from ms_service_metric.core.config.metric_control_watch import MetricControlWatch
from ms_service_metric.utils import shm_manager as shm_mod
from ms_service_metric.utils.shm_manager import (
    STATE_OFF,
    STATE_ON,
    SharedMemoryManager,
)


@pytest.fixture
def shm_prefix(monkeypatch):
    p = f"/ut_mcw_lc_{uuid.uuid4().hex[:12]}"
    monkeypatch.setenv("MS_SERVICE_METRIC_SHM_PREFIX", p)
    monkeypatch.setenv("MS_SERVICE_METRIC_MAX_PROCS", "8")
    return p


def test_start_stop_restores_handler(shm_prefix):
    w = MetricControlWatch()
    with patch.object(w, "_register_signal_handler", lambda: None):
        w.start()
        try:
            assert w._running is True
            assert w._manager is not None
        finally:
            w.stop()
    assert w._running is False
    assert w._manager is None


def test_start_idempotent(shm_prefix):
    w = MetricControlWatch()
    with patch.object(w, "_register_signal_handler", lambda: None):
        w.start()
        try:
            w.start()
            assert w._manager is not None
        finally:
            w.stop()


def test_stop_idempotent(shm_prefix):
    w = MetricControlWatch()
    w.stop()


def test_set_control_state_connects_and_updates(shm_prefix):
    mgr = SharedMemoryManager(shm_prefix=shm_prefix)
    assert mgr.connect(create=True) is True
    try:
        mgr.set_state(STATE_OFF)
        with patch.object(shm_mod.os, "kill", return_value=None):
            mgr.add_current_process()
        with patch("ms_service_metric.utils.shm_manager.os.kill", return_value=None) as mock_kill:
            MetricControlWatch.set_control_state(True, shm_prefix=shm_prefix)
            mock_kill.assert_called()
        mgr2 = SharedMemoryManager(shm_prefix=shm_prefix)
        assert mgr2.connect(create=False) is True
        try:
            assert mgr2.get_state() == STATE_ON
        finally:
            mgr2.disconnect()
    finally:
        mgr.destroy()


def test_set_control_state_raises_when_no_shm(shm_prefix):
    from ms_service_metric.utils.exceptions import SharedMemoryError

    missing = f"{shm_prefix}_no_such_segment_xxx"
    with pytest.raises(SharedMemoryError):
        MetricControlWatch.set_control_state(True, shm_prefix=missing)


def test_register_unregister_via_signal_handler_chain(shm_prefix):
    w = MetricControlWatch()
    with patch.object(w, "_register_signal_handler", lambda: None):
        w.start()
        try:
            w._check_control_state()
            w._read_control_state()
        finally:
            w.stop()


def test_notify_callbacks_given_error_then_reports_failure(shm_prefix):
    w = MetricControlWatch()

    def bad(_a, _b):
        raise RuntimeError("cb")

    with patch("ms_service_metric.core.config.metric_control_watch.logger") as log_mock:
        w.register_callback(bad)
        succeeded = w._notify_callbacks(True, 1)

    assert succeeded is False
    assert bad in w._callbacks
    log_mock.error.assert_called_once()
    msg = log_mock.error.call_args[0][0]
    assert "Error in callback" in msg
    assert "cb" in msg
