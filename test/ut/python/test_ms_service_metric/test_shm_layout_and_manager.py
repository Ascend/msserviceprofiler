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

"""SharedMemoryLayout / SharedMemoryManager tests (posix_ipc stub from conftest)."""

# pylint: disable=redefined-outer-name

import uuid

import pytest

from ms_service_metric.utils.shm_manager import (
    IPC_OBJECT_MODE,
    MAGIC_NUMBER,
    HEADER_END_MARKER,
    CURRENT_VERSION,
    SharedMemoryLayout,
    SharedMemoryManager,
    STATE_OFF,
    STATE_ON,
)


@pytest.fixture
def unique_shm_prefix(monkeypatch):
    prefix = f"/ut_ms_metric_{uuid.uuid4().hex[:12]}"
    monkeypatch.setenv("MS_SERVICE_METRIC_SHM_PREFIX", prefix)
    monkeypatch.setenv("MS_SERVICE_METRIC_MAX_PROCS", "8")
    yield prefix


def test_shared_memory_layout_names_and_size():
    assert SharedMemoryLayout.get_shm_name("/p") == "/p_control"
    assert SharedMemoryLayout.get_sem_name("/p") == "/p_semaphore"
    size8 = SharedMemoryLayout.calc_memory_size(8)
    assert size8 == (
        SharedMemoryLayout.HEADER_SIZE
        + SharedMemoryLayout.PROC_LIST_HEADER_SIZE
        + 8 * SharedMemoryLayout.PROC_ENTRY_SIZE
    )


def test_manager_connect_create_write_state(unique_shm_prefix):
    mgr = SharedMemoryManager()
    assert mgr.connect(create=True) is True
    try:
        assert mgr._shm.mode == IPC_OBJECT_MODE
        assert mgr._sem.mode == IPC_OBJECT_MODE
        assert mgr.get_state() == STATE_OFF
        mgr.set_state(STATE_ON)
        assert mgr.get_state() == STATE_ON
        mgr.set_timestamp(42)
        assert mgr.get_timestamp() == 42
    finally:
        mgr.destroy()


def test_manager_connect_false_when_missing(unique_shm_prefix):
    mgr = SharedMemoryManager()
    assert mgr.connect(create=False) is False
    mgr.disconnect()


def test_manager_second_client_sees_same_state(unique_shm_prefix):
    a = SharedMemoryManager()
    assert a.connect(create=True) is True
    try:
        a.set_state(STATE_ON)
        a.set_timestamp(99)
        b = SharedMemoryManager()
        assert b.connect(create=False) is True
        try:
            assert b.get_state() == STATE_ON
            assert b.get_timestamp() == 99
        finally:
            b.disconnect()
    finally:
        a.destroy()


def test_control_state_validation_rejects_bad_header_and_state(unique_shm_prefix):
    mgr = SharedMemoryManager()
    assert mgr.connect(create=True) is True
    try:
        assert mgr.is_control_state_valid() is True

        mgr.write_int(SharedMemoryLayout.OFFSET_STATE, 42)
        assert mgr.is_control_state_valid() is False

        mgr.write_int(SharedMemoryLayout.OFFSET_STATE, STATE_ON)
        mgr.write_int(SharedMemoryLayout.OFFSET_MAGIC, 0)
        assert mgr.is_control_state_valid() is False

        mgr.write_int(SharedMemoryLayout.OFFSET_MAGIC, MAGIC_NUMBER)
        mgr.write_int(SharedMemoryLayout.OFFSET_VERSION, CURRENT_VERSION)
        mgr.write_int(SharedMemoryLayout.OFFSET_HEADER_END, HEADER_END_MARKER)
        assert mgr.is_control_state_valid() is True
    finally:
        mgr.destroy()
