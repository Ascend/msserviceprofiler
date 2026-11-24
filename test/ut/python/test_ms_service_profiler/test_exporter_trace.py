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

from unittest import mock
from unittest.mock import patch, mock_open, MagicMock
import unittest
import json
import tempfile
import sqlite3

import os
import math

import pytest
import pandas as pd

from ms_service_profiler.utils.file_open_check import OpenException
from ms_service_profiler.exporters.exporter_trace import (
    ExporterTrace,
    write_trace_data_to_file,
    save_trace_data_into_json,
    create_trace_events,
    sort_trace_events_by_tid,
    add_mem_events,
    load_single_prof,
    find_cann_pid,
    merge_json_data,
    add_npu_events,
    add_kvcache_events,
    add_cpu_events,
    add_pull_kvcache_events,
    _prepare_data_smart_parallel,
    save_trace_data_into_db,
    _build_track_id_mapping_smart,
    _setup_database_optimizations,
    _collect_pid_tid_and_meta_events,
    _get_tid_from_event,
    _process_meta_events_batch,
    _find_thread_sort_index,
    _process_chunk_smart,
    _process_single_event,
    _is_slice_event,
    _is_counter_event,
    _is_flow_event,
    _prepare_slice_data_smart,
    _prepare_counter_data_smart,
    _prepare_flow_data_smart,
    sort_trace_events_by_pid,
)


# Mock 数据
@pytest.fixture
def mock_data():
    base_path = '/home/raonaxin/cheps/0211-1226/'

    profiles = [
        'PROF_000001_20250211122640832_MOAFENMIAMARIKCA',
        'PROF_000001_20250211122717318_QCFMCMCCQNJJGQCC',
        'PROF_000001_20250211122717318_FRPOJKFFIHHERIIA',
    ]
    date_times = ['20250211122801', '20250211122756', '20250211122800']

    msprof_data = []
    for profile, date_time in zip(profiles, date_times):
        file_path = f'{base_path}{profile}/mindstudio_profiler_output/msprof_{date_time}.json'
        msprof_data.append(dict(msprof_files=[file_path], pid=12))

    # 模拟输入的 DataFrame 数据
    return {
        'tx_data_df': pd.DataFrame(
            {
                'name': ['task1', 'task2'],
                'domain': ['domain1', 'domain2'],
                'start_time': [12345, 12346],
                'end_time': [12355, 12356],
                'during_time': [10, 10],
                'start_datetime': [12345, 12346],
                'end_datetime': [12345, 12346],
                'batch_type': ['batch1', 'batch2'],
                'batch_size': [5, 10],
                'deviceBlock=': [5, 10],
                'res_list': [['res1'], ['res2']],
                'rid': [[0], [1]],
                'pid': [0, 1],
                'tid': [0, 1],
                'message': [
                    {'rid': 0, 'PENDING+': 1, 'RUNNING+': -1, 'name': 'ReqState', 'type': 0},
                    {'rid': 1, 'PENDING+': 1, 'RUNNING+': -1, 'name': 'ReqState', 'type': 0},
                ],
            }
        ),
        'cpu_data_df': pd.DataFrame(
            {'start_time': [12345, 12346], 'start_datetime': [12345, 12346], 'usage': [30.5, 35.0]}
        ),
        'memory_data_df': pd.DataFrame(
            {'start_time': [12345, 12346], 'start_datetime': [12345, 12346], 'usage': [200, 250]}
        ),
        'msprof_data': msprof_data,
    }


@pytest.fixture
def mock_mspti():
    return {
        'api_df': pd.DataFrame(
            {
                'name': ['aclnnInplaceCopy_SliceAiCore_Slice', 'aclnnEmbedding_GatherV2AiCore_GatherV2'],
                'start': [12345, 12346],
                'end': [12355, 12356],
                'processId': [409726, 409726],
                'threadId': [409895, 409895],
                'correlationId': [1268, 1273],
                'db_id': [409726, 409726],
            }
        ),
        'kernel_df': pd.DataFrame(
            {
                'name': ['aclnnInplaceCopy_SliceAiCore_Slice', 'aclnnEmbedding_GatherV2AiCore_GatherV2'],
                'type': ['KERNEL_AIVEC', 'KERNEL_AIVEC'],
                'start': [12345, 12346],
                'end': [12355, 12356],
                'deviceId': [0, 0],
                'streamId': [2, 2],
                'correlationId': [1268, 1273],
                'db_id': [409726, 409726],
            }
        ),
    }


def test_find_cann_pid():
    # 测试找到 CANN PID 的情况
    trace_events = [
        {"name": "process_name", "args": {"name": "CANN"}, "pid": 123},
        {"name": "other_event", "args": {}, "pid": 456},
    ]
    assert find_cann_pid(trace_events) == 123

    # 测试未找到 CANN PID 的情况
    trace_events = [
        {"name": "process_name", "args": {"name": "OTHER"}, "pid": 123},
        {"name": "other_event", "args": {}, "pid": 456},
    ]
    assert find_cann_pid(trace_events) is None


def test_load_single_prof_file_not_found():
    # 模拟 ms_open 在文件不存在时抛出 OpenException
    with patch(
        "ms_service_profiler.exporters.exporter_trace.ms_open", side_effect=OpenException("No such file or directory")
    ):
        result, _ = load_single_prof("nonexistent_path.json", [])
        assert result == {"traceEvents": []}


def test_load_single_prof_invalid_json():
    mock_file = mock_open(read_data="invalid json").return_value
    mock_file.read.return_value = "invalid json"

    with patch("ms_service_profiler.exporters.exporter_trace.ms_open", return_value=mock_file) as mock_ms_open:
        result, _ = load_single_prof("invalid_path.json", [])
        assert result == {"traceEvents": []}
        mock_ms_open.assert_called_once_with("invalid_path.json", "r", encoding='utf-8')


def test_merge_json_data():
    # 测试合并 JSON 数据
    trace_data = {"traceEvents": [{"name": "event1", "pid": 123}]}
    msprof_data_df = [
        {"traceEvents": [{"name": "event2", "pid": 123}]},
        {"traceEvents": [{"name": "event3", "pid": 456}]},
    ]
    result = merge_json_data(trace_data, msprof_data_df)
    assert result == {
        "traceEvents": [{"name": "event1", "pid": 123}, {"name": "event2", "pid": 123}, {"name": "event3", "pid": 456}]
    }


def test_integration(mock_data):
    # 集成测试：模拟多个文件的加载和合并
    mock_json_content = json.dumps(
        [
            {"name": "process_name", "args": {"name": "CANN"}, "pid": 123},
            {"name": "event1", "pid": 123, "tid": 123},
            {"name": "event2", "pid": 456},
        ]
    )

    # 模拟 ms_open 的行为，使其返回预设的 JSON 内容
    mock_file = mock_open(read_data=mock_json_content).return_value
    mock_file.read.return_value = mock_json_content

    with patch("ms_service_profiler.exporters.exporter_trace.ms_open", return_value=mock_file) as mock_ms_open:
        trace_data = {"traceEvents": []}
        for pf in mock_data["msprof_data"]:
            for prof_path in pf.get("msprof_files"):
                result, _ = load_single_prof(prof_path, ["123"])
                trace_data = merge_json_data(trace_data, [result])

        # 验证 ms_open 被正确调用
        mock_ms_open.assert_called()
        assert len(trace_data["traceEvents"]) == 9


# 测试 ExporterTrace 初始化
def test_exporter_initialize():
    mock_args = mock.Mock()
    ExporterTrace.initialize(mock_args)
    assert ExporterTrace.args == mock_args


# 测试 ExporterTrace 的 export 方法
@mock.patch('ms_service_profiler.exporters.exporter_trace.create_trace_events')
@mock.patch('ms_service_profiler.exporters.exporter_trace.save_trace_data_into_json')
def test_exporter_export(mock_save, mock_create, mock_data, mock_mspti):
    # 模拟 create_trace_events 返回值
    mock_create.return_value = {"traceEvents": []}
    mock_save.return_value = None  # 模拟保存行为

    ExporterTrace.initialize(mock.Mock(output_path='/tmp', format=['json']))
    ExporterTrace.export(mock_data, mock_mspti, mock_data)

    # 验证 create_trace_events 被调用一次
    mock_create.assert_called_once()

    # 获取调用参数
    called_args, called_kwargs = mock_create.call_args

    # 手动验证参数中的 DataFrame 内容
    called_args_domain = called_args[0].pop('domain')
    mock_data_without_domain = mock_data['tx_data_df'].drop(columns=['domain'], errors='ignore')
    # 非domain列相等
    pd.testing.assert_frame_equal(called_args[0], mock_data_without_domain)
    # domain列为domain+tid
    custom_domain = pd.Series(["domain1(0)", "domain2(1)"])
    pd.testing.assert_series_equal(called_args_domain, custom_domain, check_names=False)


def test_write_trace_data_to_file():
    trace_data = {'traceEvents': []}

    with tempfile.TemporaryDirectory() as temp_dir:
        output = os.path.join(temp_dir, 'trace.json')

        write_trace_data_to_file(trace_data, output)
        assert os.path.exists(output)  # 验证文件是否存在


def test_create_trace_events(mock_data):
    result = create_trace_events(mock_data['tx_data_df'])

    assert 'traceEvents' in result
    assert len(result['traceEvents']) > 0
    assert all('name' in event for event in result['traceEvents'])


# 测试 sort_trace_events_by_tid
def test_sort_trace_events_by_tid():
    trace_events = [
        {'tid': 'KVCache', 'name': 'event1'},
        {'tid': 'BatchSchedule', 'name': 'event2'},
        {'tid': 'Api', 'name': 'event3'},
        {'tid': 'Kernel', 'name': 'event4'},
    ]
    sorted_trace_events = sort_trace_events_by_tid(trace_events)

    # 验证事件是否按正确顺序排序
    assert sorted_trace_events[0]['tid'] == 'KVCache'
    assert sorted_trace_events[1]['tid'] == 'Api'
    assert sorted_trace_events[2]['tid'] == 'Kernel'
    assert sorted_trace_events[3]['tid'] == 'BatchSchedule'


def test_add_mem_events_valid_data():
    data = {
        'start_time': [1000, 2000, 3000],
        'usage': [0.5, 0.75, 0.25],
    }
    df = pd.DataFrame(data)

    result = add_mem_events(df)

    assert len(result) == 3
    assert result[0]['name'] == 'Memory Usage'
    assert result[0]['args'] == {'Memory Usage': 0.5}
    assert result[1]['args'] == {'Memory Usage': 0.75}
    assert result[2]['args'] == {'Memory Usage': 0.25}


def test_add_mem_events_empty_df():
    # 空 DataFrame
    df = pd.DataFrame(columns=['start_time', 'usage'])  # 没有数据的 DataFrame

    result = add_mem_events(df)

    assert not result  # 应该返回空列表


def test_add_mem_events_none_input():
    # 输入为 None
    result = add_mem_events(None)

    assert not result  # 应该返回空列表


def test_add_mem_events_with_missing_data():
    # DataFrame 中的 usage 列存在缺失值
    data = {
        'start_time': [1000, 2000, 3000],
        'usage': [0.5, None, 0.25],  # 包含 None
    }
    df = pd.DataFrame(data)

    result = add_mem_events(df)

    assert len(result) == 3
    assert math.isnan(result[1]['args']['Memory Usage'])


def test_add_mem_events_with_nan_data():
    #  DataFrame 中的 usage 列包含 NaN
    data = {
        'start_time': [1000, 2000, 3000],
        'usage': [0.5, float('nan'), 0.25],  # 包含 NaN
    }
    df = pd.DataFrame(data)

    result = add_mem_events(df)

    assert len(result) == 3  # 应该有 3 个事件
    assert math.isnan(result[1]['args']['Memory Usage'])


def test_add_npu_events_valid_data():
    data = {
        'start_time': [1000, 2000, 3000],
        'usage=': [0.5, 0.75, 0.25],
    }
    df = pd.DataFrame(data)

    result = add_npu_events(df)

    assert len(result) == 3
    assert result[0]['name'] == 'NPU Usage'
    assert result[0]["ph"] == "C"
    assert result[0]['args'] == {'Usage': 0.5}
    assert result[1]['args'] == {'Usage': 0.75}
    assert result[2]['args'] == {'Usage': 0.25}


def test_add_npu_events_none_input():
    # 输入为 None
    result = add_npu_events(None)

    assert not result  # 应该返回空列表


def test_add_npu_events_empty_df():
    # 空 DataFrame
    df = pd.DataFrame(columns=['start_time', 'usage='])  # 没有数据的 DataFrame

    result = add_npu_events(df)

    assert not result  # 应该返回空列表


def test_add_kvcache_events_valid_data():
    data = {
        'start_time': [1000, 2000, 3000],
        'deviceBlock=': [0, 1, 2],
        'domain': ['KVCache', 'KVCache', 'KVCache'],
        'pid': [1, 1, 1],
        "scope#dp": [0, 0, 0],
    }
    df = pd.DataFrame(data)

    result = add_kvcache_events(df)

    assert len(result) == 3
    assert result[0]['name'] == 'KVCache-dp0'
    assert result[0]['pid'] == 1
    assert result[0]["ph"] == "C"
    assert result[0]['args'] == {'Device Block': 0}
    assert result[1]['args'] == {'Device Block': 1}
    assert result[2]['args'] == {'Device Block': 2}


def test_add_cpu_events_valid_data():
    data = {
        'start_time': [1000, 2000, 3000],
        'usage': [0.5, 0.75, 0.25],
    }
    df = pd.DataFrame(data)

    result = add_cpu_events(df)

    assert len(result) == 3
    assert result[0]['name'] == 'CPU Usage'
    assert result[0]["ph"] == "C"
    assert result[0]['args'] == {'CPU Usage': 0.5}
    assert result[1]['args'] == {'CPU Usage': 0.75}
    assert result[2]['args'] == {'CPU Usage': 0.25}


def test_add_cpu_events_none_input():
    # 输入为 None
    result = add_cpu_events(None)

    assert not result  # 应该返回空列表


def test_add_cpu_events_empty_df():
    # 空 DataFrame
    df = pd.DataFrame(columns=['start_time', 'usage'])  # 没有数据的 DataFrame

    result = add_cpu_events(df)

    assert not result  # 应该返回空列表


def test_add_pull_kvcache_events_valid_data():
    data = {
        'start_time': [1000, 2000, 3000],
        'end_time': [1500, 2500, 3500],
        'rank': [0, 1, 2],
        'domain': ['PullKVCache', 'PullKVCache', 'PullKVCache'],
        'during_time': [500, 500, 500],
    }

    df = pd.DataFrame(data)

    result = add_pull_kvcache_events(df)

    assert len(result) == 3
    assert result[0]['name'] == 'PullKVCache'
    assert result[0]['pid'] == 'PullKVCache'
    assert result[0]["ph"] == "X"
    assert result[0]['dur'] == 500
    assert result[0]['args'] == {'rank': 0, 'during_time': 500, 'end_time': 1500, 'start_time': 1000}


def test_add_pull_kvcache_events_none_input():
    # 输入为 None
    result = add_pull_kvcache_events(None)

    assert not result  # 应该返回空列表


def test_add_pull_kvcache_events_empty_df():
    # 空 DataFrame
    df = pd.DataFrame(columns=['start_time', 'end_time', 'rank', 'domain', 'during_time'])  # 没有数据的 DataFrame

    result = add_pull_kvcache_events(df)

    assert not result  # 应该返回空列表


class MockFile:
    def __init__(self, file_content=""):
        self.file_content = file_content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def read(self):
        return self.file_content

    def write(self, str):
        self.file_content += str


@mock.patch('ms_service_profiler.exporters.exporter_trace.ms_open')
@mock.patch('ms_service_profiler.exporters.exporter_trace.logger')
def test_save_trace_data_into_json(mock_logger, mock_ms_open):
    fake_file = MockFile()
    mock_ms_open.return_value = fake_file
    save_trace_data_into_json({}, 'output')
    assert fake_file.read() == '[]'
    mock_logger.info.assert_called_once()


@mock.patch('ms_service_profiler.exporters.exporter_trace.ms_open')
@mock.patch('ms_service_profiler.exporters.exporter_trace.json.dumps')
@mock.patch('ms_service_profiler.exporters.exporter_trace.logger')
def test_save_trace_data_into_json_exception(mock_logger, mock_dumps, mock_ms_open):
    mock_dumps.side_effect = Exception('Test exception')
    fake_file = MockFile()
    mock_ms_open.return_value = fake_file
    save_trace_data_into_json({"traceEvents": [123]}, 'output')
    mock_dumps.assert_called_once()
    assert fake_file.read() == '[]'
    mock_logger.error.assert_called_once()


class TestTraceDataProcessing(unittest.TestCase):
    def setUp(self):
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor

    def test_save_trace_data_into_db_empty_events(self):
        """测试空事件列表"""
        trace_data = {"traceEvents": []}

        with (
            patch('ms_service_profiler.exporters.exporter_trace.logger') as mock_logger,
            patch('ms_service_profiler.exporters.exporter_trace.reset_track_id_manager'),
            patch('ms_service_profiler.exporters.exporter_trace.reset_process_table_manager'),
            patch('ms_service_profiler.exporters.exporter_trace.clear_data_cache'),
        ):
            save_trace_data_into_db(trace_data)

            mock_logger.warning.assert_called_with("no data to write")

    @patch('ms_service_profiler.exporters.exporter_trace.time.time')
    def test_save_trace_data_into_db_normal_case(self, mock_time):
        """测试正常情况下的数据处理"""
        mock_time.return_value = 100.0
        trace_data = {
            "traceEvents": [
                {'ph': 'X', 'pid': 1, 'tid': 1, 'ts': 100, 'dur': 50, 'name': 'slice1'},
                {'ph': 'C', 'pid': 1, 'name': 'counter1', 'ts': 200},
            ]
        }

        with (
            patch('ms_service_profiler.exporters.exporter_trace.reset_track_id_manager'),
            patch('ms_service_profiler.exporters.exporter_trace.reset_process_table_manager'),
            patch('ms_service_profiler.exporters.exporter_trace.clear_data_cache'),
            patch('ms_service_profiler.exporters.exporter_trace._build_track_id_mapping_smart', return_value={}),
            patch(
                'ms_service_profiler.exporters.exporter_trace._prepare_data_smart_parallel',
                return_value={'slice': [], 'counter': [], 'flow': []},
            ),
            patch('ms_service_profiler.exporters.exporter_trace.write_all_data_smart'),
            patch('ms_service_profiler.exporters.exporter_trace.logger') as mock_logger,
        ):
            save_trace_data_into_db(trace_data)

            # 验证日志记录
            self.assertTrue(mock_logger.debug.called)

    def test_save_trace_data_into_db_only_meta_events(self):
        """测试只有元事件的情况"""
        trace_data = {"traceEvents": [{'ph': 'M', 'name': 'process_name', 'pid': 1, 'args': {'name': 'test_process'}}]}

        with (
            patch('ms_service_profiler.exporters.exporter_trace.reset_track_id_manager'),
            patch('ms_service_profiler.exporters.exporter_trace.reset_process_table_manager'),
            patch('ms_service_profiler.exporters.exporter_trace.clear_data_cache'),
            patch('ms_service_profiler.exporters.exporter_trace._build_track_id_mapping_smart', return_value={}),
            patch('ms_service_profiler.exporters.exporter_trace.write_all_data_smart'),
            patch('ms_service_profiler.exporters.exporter_trace._prepare_data_smart_parallel') as mock_prepare,
        ):
            save_trace_data_into_db(trace_data)

            # 验证没有调用数据准备函数（因为other_events为空）
            mock_prepare.assert_not_called()

    def test_build_track_id_mapping_smart_connection_failure(self):
        """测试数据库连接失败"""
        with (
            patch('ms_service_profiler.exporters.exporter_trace.get_db_connection', return_value=None),
            patch('ms_service_profiler.exporters.exporter_trace.logger') as mock_logger,
        ):
            result = _build_track_id_mapping_smart([])

            self.assertEqual(result, {})
            mock_logger.warning.assert_called_with("Failed to get database connection for track_id mapping")

    def test_build_track_id_mapping_smart_database_error(self):
        """测试数据库操作错误"""
        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = sqlite3.Error("Database error")

        with (
            patch('ms_service_profiler.exporters.exporter_trace.get_db_connection', return_value=mock_conn),
            patch('ms_service_profiler.exporters.exporter_trace.logger') as mock_logger,
        ):
            result = _build_track_id_mapping_smart([])

            self.assertEqual(result, {})
            mock_logger.warning.assert_called()
            mock_conn.close.assert_called()

    def test_build_track_id_mapping_smart_general_error(self):
        """测试一般错误"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("General error")

        with (
            patch('ms_service_profiler.exporters.exporter_trace.get_db_connection', return_value=mock_conn),
            patch('ms_service_profiler.exporters.exporter_trace.logger') as mock_logger,
        ):
            result = _build_track_id_mapping_smart([])

            self.assertEqual(result, {})
            mock_logger.warning.assert_called()
            mock_conn.rollback.assert_called()
            mock_conn.close.assert_called()

    def test_setup_database_optimizations(self):
        """测试数据库优化设置"""
        mock_cursor = MagicMock()

        _setup_database_optimizations(mock_cursor)

        expected_calls = [
            unittest.mock.call("PRAGMA journal_mode = WAL"),
            unittest.mock.call("PRAGMA cache_size = 10000"),
            unittest.mock.call("PRAGMA synchronous = NORMAL"),
        ]
        mock_cursor.execute.assert_has_calls(expected_calls)

    def test_collect_pid_tid_and_meta_events_empty(self):
        """测试空事件列表"""
        unique_pid_tid, meta_events = _collect_pid_tid_and_meta_events([])
        self.assertEqual(unique_pid_tid, set())
        self.assertEqual(meta_events, [])

    def test_collect_pid_tid_and_meta_events_with_different_ph_types(self):
        """测试不同ph类型事件的收集"""
        events = [
            {'ph': 'M', 'name': 'process_name', 'pid': 1, 'args': {'name': 'test'}},
            {'ph': 'X', 'pid': 1, 'tid': 1, 'ts': 100, 'dur': 50},
            {'ph': 'C', 'pid': 2, 'name': 'counter1', 'ts': 200},
            {'ph': 's', 'pid': 1, 'tid': 2, 'ts': 300},
        ]

        unique_pid_tid, meta_events = _collect_pid_tid_and_meta_events(events)

        self.assertEqual(len(meta_events), 1)
        self.assertEqual(meta_events[0]['name'], 'process_name')
        self.assertEqual(unique_pid_tid, {(1, 1), (2, 'counter1'), (1, 2)})

    def test_get_tid_from_event_counter(self):
        """测试获取counter事件的tid"""
        event = {'name': 'counter_name'}
        tid = _get_tid_from_event(event, 'C')
        self.assertEqual(tid, 'counter_name')

    def test_get_tid_from_event_non_counter(self):
        """测试获取非counter事件的tid"""
        event = {'tid': 'thread1'}
        tid = _get_tid_from_event(event, 'X')
        self.assertEqual(tid, 'thread1')

    def test_process_meta_events_batch(self):
        """测试批量处理meta事件"""
        meta_events = [
            {'name': 'process_name', 'pid': 1, 'args': {'name': 'test_process'}},
            {'name': 'thread_name', 'pid': 1, 'tid': 1, 'args': {'name': 'test_thread'}},
        ]
        mock_cursor = MagicMock()

        with patch('ms_service_profiler.exporters.exporter_trace.trans_trace_meta_event') as mock_trans:
            _process_meta_events_batch(meta_events, mock_cursor)

            self.assertEqual(mock_trans.call_count, 2)

    def test_find_thread_sort_index_found(self):
        """测试找到thread_sort_index"""
        events = [
            {'pid': 1, 'tid': 1, 'name': 'thread_sort_index', 'ph': 'M', 'args': {'sort_index': 5}},
            {'pid': 1, 'tid': 2, 'name': 'thread_sort_index', 'ph': 'M', 'args': {'sort_index': 10}},
        ]

        sort_index = _find_thread_sort_index(events, 1, 1)
        self.assertEqual(sort_index, 5)

    def test_find_thread_sort_index_not_found(self):
        """测试未找到thread_sort_index"""
        events = [{'pid': 1, 'tid': 2, 'name': 'thread_sort_index', 'ph': 'M', 'args': {'sort_index': 5}}]

        sort_index = _find_thread_sort_index(events, 1, 1)
        self.assertEqual(sort_index, 0)

    def test_find_thread_sort_index_wrong_ph(self):
        """测试ph类型不匹配"""
        events = [{'pid': 1, 'tid': 1, 'name': 'thread_sort_index', 'ph': 'X', 'args': {'sort_index': 5}}]

        sort_index = _find_thread_sort_index(events, 1, 1)
        self.assertEqual(sort_index, 0)

    def test_process_chunk_smart_empty(self):
        """测试空数据块处理"""
        result = _process_chunk_smart([])
        self.assertEqual(result, {'slice': [], 'counter': [], 'flow': []})

    def test_process_chunk_smart_mixed_events(self):
        """测试混合事件处理"""
        events = [
            {'ph': 'X', 'pid': 1, 'tid': 1, 'ts': 100, 'dur': 50, 'name': 'slice1'},
            {'ph': 'C', 'pid': 1, 'name': 'counter1', 'ts': 200},
            {'ph': 's', 'pid': 1, 'tid': 1, 'ts': 300, 'id': 'flow1'},
        ]

        with patch('ms_service_profiler.exporters.exporter_trace._process_single_event') as mock_process:
            _process_chunk_smart(events)

            self.assertEqual(mock_process.call_count, 3)

    def test_process_single_event_slice(self):
        """测试处理切片事件"""
        event = {'ph': 'X', 'ts': 100, 'dur': 50, 'name': 'slice1', 'pid': 1, 'tid': 1}
        slice_data = []
        counter_data = []
        flow_data = []

        with (
            patch('ms_service_profiler.exporters.exporter_trace._is_slice_event', return_value=True),
            patch('ms_service_profiler.exporters.exporter_trace._prepare_slice_data_smart', return_value=MagicMock()),
            patch('ms_service_profiler.exporters.exporter_trace._is_counter_event', return_value=False),
            patch('ms_service_profiler.exporters.exporter_trace._is_flow_event', return_value=False),
        ):
            _process_single_event(event, slice_data, counter_data, flow_data)

            self.assertEqual(len(slice_data), 1)
            self.assertEqual(len(counter_data), 0)
            self.assertEqual(len(flow_data), 0)

    def test_process_single_event_counter(self):
        """测试处理计数器事件"""
        event = {'ph': 'C', 'ts': 200, 'name': 'counter1', 'pid': 1}
        slice_data = []
        counter_data = []
        flow_data = []

        with (
            patch('ms_service_profiler.exporters.exporter_trace._is_slice_event', return_value=False),
            patch('ms_service_profiler.exporters.exporter_trace._is_counter_event', return_value=True),
            patch('ms_service_profiler.exporters.exporter_trace._prepare_counter_data_smart', return_value=MagicMock()),
        ):
            _process_single_event(event, slice_data, counter_data, flow_data)

            self.assertEqual(len(slice_data), 0)
            self.assertEqual(len(counter_data), 1)
            self.assertEqual(len(flow_data), 0)

    def test_process_single_event_flow(self):
        """测试处理流事件"""
        event = {'ph': 's', 'ts': 300, 'name': 'flow1', 'pid': 1, 'tid': 1}
        slice_data = []
        counter_data = []
        flow_data = []

        with (
            patch('ms_service_profiler.exporters.exporter_trace._is_slice_event', return_value=False),
            patch('ms_service_profiler.exporters.exporter_trace._is_counter_event', return_value=False),
            patch('ms_service_profiler.exporters.exporter_trace._is_flow_event', return_value=True),
            patch('ms_service_profiler.exporters.exporter_trace._prepare_flow_data_smart', return_value=MagicMock()),
        ):
            _process_single_event(event, slice_data, counter_data, flow_data)

            self.assertEqual(len(slice_data), 0)
            self.assertEqual(len(counter_data), 0)
            self.assertEqual(len(flow_data), 1)

    def test_process_single_event_exception(self):
        """测试处理事件时发生异常"""
        event = {'ph': 'X', 'name': 'test'}
        slice_data = []

        with (
            patch('ms_service_profiler.exporters.exporter_trace._is_slice_event', side_effect=Exception("Test error")),
            patch('ms_service_profiler.exporters.exporter_trace.logger') as mock_logger,
        ):
            _process_single_event(event, slice_data, [], [])

            mock_logger.error.assert_called()

    def test_is_slice_event_valid(self):
        """测试有效的切片事件"""
        event = {'ts': 100, 'dur': 50}
        self.assertTrue(_is_slice_event('X', event))
        self.assertTrue(_is_slice_event('I', event))

    def test_is_slice_event_invalid_ph(self):
        """测试无效的ph类型"""
        event = {'ts': 100, 'dur': 50}
        self.assertFalse(_is_slice_event('C', event))

    def test_is_slice_event_missing_fields(self):
        """测试缺失字段的事件"""
        event = {'ts': 100}  # 缺少dur
        self.assertFalse(_is_slice_event('X', event))

        event = {'dur': 50}  # 缺少ts
        self.assertFalse(_is_slice_event('X', event))

    def test_is_counter_event_valid(self):
        """测试有效的计数器事件"""
        event = {'ts': 100}
        self.assertTrue(_is_counter_event('C', event))

    def test_is_counter_event_invalid_ph(self):
        """测试无效的ph类型"""
        event = {'ts': 100}
        self.assertFalse(_is_counter_event('X', event))

    def test_is_counter_event_missing_ts(self):
        """测试缺失时间戳的计数器事件"""
        event = {}
        self.assertFalse(_is_counter_event('C', event))

    def test_is_flow_event_valid(self):
        """测试有效的流事件"""
        event = {'ts': 100}
        self.assertTrue(_is_flow_event('s', event))
        self.assertTrue(_is_flow_event('t', event))
        self.assertTrue(_is_flow_event('f', event))

    def test_is_flow_event_invalid_ph(self):
        """测试无效的ph类型"""
        event = {'ts': 100}
        self.assertFalse(_is_flow_event('X', event))

    def test_is_flow_event_missing_ts(self):
        """测试缺失时间戳的流事件"""
        event = {}
        self.assertFalse(_is_flow_event('s', event))

    def test_prepare_slice_data_smart_valid(self):
        """测试有效的slice数据准备"""
        event = {'ph': 'X', 'pid': 1, 'tid': 1, 'ts': 100, 'dur': 50, 'name': 'slice1'}

        # 模拟worker track_id映射
        with patch('ms_service_profiler.exporters.exporter_trace._worker_track_id_map', {(1, 1): 100}):
            with patch(
                'ms_service_profiler.exporters.exporter_trace.trans_trace_slice_data',
                return_value={'ts': 100, 'dur': 50, 'name': 'slice1', 'args': {}},
            ):
                result = _prepare_slice_data_smart(event)

                self.assertIsNotNone(result)
                self.assertEqual(result.track_id, 100)
                self.assertEqual(result.timestamp, 100)
                self.assertEqual(result.duration, 50)

    def test_prepare_slice_data_smart_no_track_id(self):
        """测试没有track_id的slice数据"""
        event = {'ph': 'X', 'pid': 1, 'tid': 1, 'ts': 100, 'dur': 50, 'name': 'slice1'}

        # 模拟worker track_id映射中没有对应项
        with patch('ms_service_profiler.exporters.exporter_trace._worker_track_id_map', {}):
            result = _prepare_slice_data_smart(event)

            self.assertIsNone(result)

    def test_prepare_counter_data_smart_valid(self):
        """测试有效的counter数据准备"""
        event = {'ph': 'C', 'pid': 1, 'name': 'counter1', 'ts': 100}

        with patch(
            'ms_service_profiler.exporters.exporter_trace.trans_trace_counter_data',
            return_value={'ts': 100, 'name': 'counter1', 'pid': 1, 'args': {}},
        ):
            result = _prepare_counter_data_smart(event)

            self.assertIsNotNone(result)
            self.assertEqual(result.timestamp, 100)
            self.assertEqual(result.name, 'counter1')
            self.assertEqual(result.process_id, 1)

    def test_prepare_counter_data_smart_zero_timestamp(self):
        """测试时间戳为0的counter数据"""
        event = {'ph': 'C', 'pid': 1, 'name': 'counter1', 'ts': 0}

        with patch(
            'ms_service_profiler.exporters.exporter_trace.trans_trace_counter_data',
            return_value={'ts': 0, 'name': 'counter1', 'pid': 1},
        ):
            result = _prepare_counter_data_smart(event)

            self.assertIsNone(result)

    def test_prepare_flow_data_smart_valid(self):
        """测试有效的flow数据准备"""
        event = {'ph': 's', 'pid': 1, 'tid': 1, 'ts': 100, 'name': 'flow1', 'id': 'flow1'}

        # 模拟worker track_id映射
        with patch('ms_service_profiler.exporters.exporter_trace._worker_track_id_map', {(1, 1): 100}):
            with patch(
                'ms_service_profiler.exporters.exporter_trace.trans_trace_flow_data',
                return_value={'ts': 100, 'name': 'flow1', 'flow_id': 'flow1'},
            ):
                result = _prepare_flow_data_smart(event, 's')

                self.assertIsNotNone(result)
                self.assertEqual(result.track_id, 100)
                self.assertEqual(result.timestamp, 100)
                self.assertEqual(result.name, 'flow1')
                self.assertEqual(result.phase_type, 's')

    def test_prepare_flow_data_smart_no_track_id(self):
        """测试没有track_id的flow数据"""
        event = {'ph': 's', 'pid': 1, 'tid': 1, 'ts': 100, 'name': 'flow1'}

        # 模拟worker track_id映射中没有对应项
        with patch('ms_service_profiler.exporters.exporter_trace._worker_track_id_map', {}):
            result = _prepare_flow_data_smart(event, 's')

            self.assertIsNone(result)


class TestTraceDataProcessingParallel(unittest.TestCase):
    def test_prepare_data_smart_parallel_empty_events(self):
        """测试空事件列表的数据准备"""
        result = _prepare_data_smart_parallel([], {})
        self.assertEqual(result, {'slice': [], 'counter': [], 'flow': []})

    @patch('ms_service_profiler.exporters.exporter_trace.mp.Pool')
    @patch('ms_service_profiler.exporters.exporter_trace.calculate_smart_process_config', return_value=(2, 100))
    def test_prepare_data_smart_parallel_normal_case(self, mock_calc_config, mock_pool):
        """测试正常情况下的并行数据准备"""
        events = [{'ph': 'X', 'pid': 1, 'tid': 1, 'ts': 100, 'dur': 50}] * 10
        mock_pool_instance = MagicMock()
        mock_pool.return_value.__enter__.return_value = mock_pool_instance
        mock_pool_instance.imap_unordered.return_value = [
            {'slice': [MagicMock()], 'counter': [], 'flow': []},
            {'slice': [], 'counter': [MagicMock()], 'flow': []},
        ]

        result = _prepare_data_smart_parallel(events, {})

        self.assertEqual(len(result['slice']), 1)


# ======================================================================
# sort_trace_events_by_pid 测试用例
# ======================================================================


class TestSortTraceEventsByPid(unittest.TestCase):
    """测试 sort_trace_events_by_pid 函数"""

    def test_sort_trace_events_by_pid_empty_input(self):
        """测试空输入"""
        result = sort_trace_events_by_pid(None, [])
        assert result == []

    def test_sort_trace_events_by_pid_empty_pid_ppid_map(self):
        """测试空的 pid_ppid_map"""
        pid_label_map = {}
        pid_ppid_map = []
        result = sort_trace_events_by_pid(pid_label_map, pid_ppid_map)
        assert result == []

    def test_sort_trace_events_by_pid_single_process(self):
        """测试单个进程"""
        pid_label_map = {}
        pid_ppid_map = [('12345', 0, 12345, 'service')]  # (pid, ppid, ori_pid, source) - pid为字符串
        result = sort_trace_events_by_pid(pid_label_map, pid_ppid_map)

        assert len(result) == 2  # process_sort_index + process_name
        assert result[0]['name'] == 'process_sort_index'
        assert result[0]['pid'] == 12345
        assert result[0]['args']['sort_index'] == 0
        assert result[1]['name'] == 'process_name'

    def test_sort_trace_events_by_pid_schedule_forward_order(self):
        """测试 schedule 和 forward 的排序"""
        pid_label_map = {}
        pid_ppid_map = [
            ('12307', 12166, 12307, 'service'),  # forward
            ('12166', 2930, 12166, 'service'),  # schedule
        ]

        result = sort_trace_events_by_pid(pid_label_map, pid_ppid_map)

        # 应该返回 4 个事件: 2个进程 * (process_sort_index + process_name)
        assert len(result) == 4

        # 按顺序检查 sort_index
        schedule_event = next(e for e in result if e['name'] == 'process_sort_index' and e['pid'] == 12166)
        forward_event = next(e for e in result if e['name'] == 'process_sort_index' and e['pid'] == 12307)

        assert schedule_event['args']['sort_index'] == 0  # schedule 排第1
        assert forward_event['args']['sort_index'] == 1  # forward 排第2

    def test_sort_trace_events_by_pid_forward_with_dp(self):
        """测试 forward 进程按 dp 排序"""
        pid_label_map = {
            12307: {'dp_rank': '1', 'hostname': 'host1'},
            12308: {'dp_rank': '0', 'hostname': 'host1'},
        }
        pid_ppid_map = [
            ('12166', 2930, 12166, 'service'),  # schedule
            ('12307', 12166, 12307, 'service'),  # forward dp=1
            ('12308', 12166, 12308, 'service'),  # forward dp=0
        ]
        pid_domain_map = {
            12166: 'schedule',
            12307: 'forward',
            12308: 'forward',
        }

        result = sort_trace_events_by_pid(pid_label_map, pid_ppid_map, pid_domain_map=pid_domain_map)

        # schedule: 2 events (sort_index + name), forward: 3 events each (sort_index + name + labels)
        # Total: 2 + 3 + 3 = 8 events
        assert len(result) == 8

    def test_sort_trace_events_by_pid_with_operator_inheritance(self):
        """测试算子继承父进程的类型和 dp"""
        pid_label_map = {
            12307: {'dp_rank': '0', 'hostname': 'host1'},
            12602784: {'hostname': 'host1'},  # 算子进程
        }
        pid_ppid_map = [
            ('12602784', 12307, 12602784, 'service'),  # 算子，父进程是 forward dp=0
            ('12307', 12166, 12307, 'service'),  # forward dp=0
            ('12166', 2930, 12166, 'service'),  # schedule
        ]

        result = sort_trace_events_by_pid(pid_label_map, pid_ppid_map)

        # 应该有 3 个进程
        schedule_event = next(e for e in result if e['name'] == 'process_sort_index' and e['pid'] == 12166)
        forward_event = next(e for e in result if e['name'] == 'process_sort_index' and e['pid'] == 12307)
        operator_event = next(e for e in result if e['name'] == 'process_sort_index' and e['pid'] == 12602784)

        assert schedule_event['args']['sort_index'] == 0  # schedule 排第1
        assert forward_event['args']['sort_index'] == 1  # forward 排第2
        assert operator_event['args']['sort_index'] == 2  # 算子继承 forward，排第3

    def test_sort_trace_events_by_pid_coordinator_priority(self):
        """测试 coordinator 进程优先级"""
        pid_label_map = {}
        pid_ppid_map = [
            ('12307', 12166, 12307, 'service'),  # forward
            ('12166', 2930, 12166, 'service'),  # schedule
            ('100', 200, 100, 'service'),  # coordinator
        ]

        result = sort_trace_events_by_pid(pid_label_map, pid_ppid_map, coordinator_pid=100)

        # coordinator 应该在最前面
        coordinator_event = next(e for e in result if e['name'] == 'process_sort_index' and e['pid'] == 100)
        schedule_event = next(e for e in result if e['name'] == 'process_sort_index' and e['pid'] == 12166)
        forward_event = next(e for e in result if e['name'] == 'process_sort_index' and e['pid'] == 12307)

        assert coordinator_event['args']['sort_index'] == 0  # coordinator 排第1
        assert schedule_event['args']['sort_index'] == 1  # schedule 排第2
        assert forward_event['args']['sort_index'] == 2  # forward 排第3

    def test_sort_trace_events_by_pid_process_name_generation(self):
        """测试 process_name 事件生成"""
        pid_label_map = {
            12166: {'hostname': 'host1'},
            12307: {'dp_rank': '0', 'hostname': 'host1'},
        }
        pid_ppid_map = [
            ('12307', 12166, 12307, 'service'),
            ('12166', 2930, 12166, 'service'),
        ]
        pid_domain_map = {
            12166: 'Schedule',
            12307: 'forward',
        }

        result = sort_trace_events_by_pid(pid_label_map, pid_ppid_map, pid_domain_map=pid_domain_map)

        # 检查 process_name 事件
        schedule_name_event = next((e for e in result if e['name'] == 'process_name' and e['pid'] == 12166), None)
        forward_name_event = next((e for e in result if e['name'] == 'process_name' and e['pid'] == 12307), None)

        assert schedule_name_event is not None
        assert schedule_name_event['args']['name'] == 'Schedule'
        assert forward_name_event is not None
        assert forward_name_event['args']['name'] == 'forward'

    def test_sort_trace_events_by_pid_process_labels_generation(self):
        """测试 process_labels 事件生成"""
        pid_label_map = {
            12307: {'dp_rank': '0', 'hostname': 'host1'},
            12166: {'hostname': 'host1'},
        }
        pid_ppid_map = [
            ('12307', 12166, 12307, 'service'),
            ('12166', 2930, 12166, 'service'),
        ]

        result = sort_trace_events_by_pid(pid_label_map, pid_ppid_map)

        # 检查 process_labels 事件
        forward_labels_event = next((e for e in result if e['name'] == 'process_labels' and e['pid'] == 12307), None)
        schedule_labels_event = next((e for e in result if e['name'] == 'process_labels' and e['pid'] == 12166), None)

        assert forward_labels_event is not None
        assert 'dp0' in forward_labels_event['args']['labels']
        assert 'host1' in forward_labels_event['args']['labels']

        assert schedule_labels_event is not None
        assert 'host1' in schedule_labels_event['args']['labels']

    def test_sort_trace_events_by_pid_type_conversion_bug(self):
        """测试类型转换 bug 修复（child_to_parent key 是字符串，pid 是整数）"""
        pid_label_map = {
            12307: {'dp_rank': '0', 'hostname': 'host1'},
        }
        pid_ppid_map = [
            ('12602784', 12307, 12602784, 'service'),  # 算子，父进程是 forward
            ('12307', 12166, 12307, 'service'),  # forward
            ('12166', 2930, 12166, 'service'),  # schedule
        ]
        pid_domain_map = {
            12166: 'schedule',
            12307: 'forward',
        }

        result = sort_trace_events_by_pid(pid_label_map, pid_ppid_map, pid_domain_map=pid_domain_map)

        assert len(result) >= 6  # 至少有 3 个进程 * 2 events each

        # 验证 schedule 排在最前面
        schedule_event = next(e for e in result if e['name'] == 'process_sort_index' and e['pid'] == 12166)
        forward_event = next(e for e in result if e['name'] == 'process_sort_index' and e['pid'] == 12307)
        operator_event = next(e for e in result if e['name'] == 'process_sort_index' and e['pid'] == 12602784)

        assert schedule_event['args']['sort_index'] == 0  # schedule 排第1

        # 算子进程（没有 domain）的 parent_pid_for_sort=0，forward 的 parent_pid_for_sort=pid
        # 所以算子排在 forward 前面
        assert operator_event['args']['sort_index'] < forward_event['args']['sort_index']

    def test_sort_trace_events_by_pid_complex_hierarchy(self):
        """测试复杂层级结构（多个 schedule 和 forward）"""
        pid_label_map = {
            12307: {'dp_rank': '0', 'hostname': 'host1'},
            12308: {'dp_rank': '1', 'hostname': 'host1'},
            12309: {'dp_rank': '0', 'hostname': 'host2'},
            12310: {'dp_rank': '1', 'hostname': 'host2'},
        }
        pid_ppid_map = [
            # Schedule 1 的子进程
            ('12307', 12166, 12307, 'service'),  # forward dp=0
            ('12308', 12166, 12308, 'service'),  # forward dp=1
            # Schedule 2 的子进程
            ('12309', 12167, 12309, 'service'),  # forward dp=0
            ('12310', 12167, 12310, 'service'),  # forward dp=1
            # 算子进程
            ('12602784', 12307, 12602784, 'service'),  # 属于 forward dp=0 (host1)
            ('12602816', 12308, 12602816, 'service'),  # 属于 forward dp=1 (host1)
            # Schedule 进程
            ('12166', 2930, 12166, 'service'),  # schedule host1
            ('12167', 2931, 12167, 'service'),  # schedule host2
        ]
        pid_domain_map = {
            12166: 'schedule',
            12167: 'schedule',
            12307: 'forward',
            12308: 'forward',
            12309: 'forward',
            12310: 'forward',
        }

        result = sort_trace_events_by_pid(pid_label_map, pid_ppid_map, pid_domain_map=pid_domain_map)

        # 验证排序结果
        events_by_pid = {e['pid']: e for e in result if e['name'] == 'process_sort_index'}

        # schedule 进程
        schedule1_index = events_by_pid[12166]['args']['sort_index']
        schedule2_index = events_by_pid[12167]['args']['sort_index']

        # host1 的 forward 进程
        forward1_0_index = events_by_pid[12307]['args']['sort_index']  # dp=0
        forward1_1_index = events_by_pid[12308]['args']['sort_index']  # dp=1

        # host2 的 forward 进程
        forward2_0_index = events_by_pid[12309]['args']['sort_index']  # dp=0
        forward2_1_index = events_by_pid[12310]['args']['sort_index']  # dp=1

        # 算子进程
        operator1_index = events_by_pid[12602784]['args']['sort_index']
        operator2_index = events_by_pid[12602816]['args']['sort_index']

        # 验证排序规则
        assert schedule1_index < schedule2_index  # schedule 按 PID 排序

        # 同 host 的 forward 按 dp 排序
        assert forward1_0_index < forward1_1_index  # host1: dp=0 < dp=1
        assert forward2_0_index < forward2_1_index  # host2: dp=0 < dp=1

        # schedule 排在 forward 前面
        assert schedule1_index < forward1_0_index
        assert schedule1_index < forward1_1_index
        assert schedule2_index < forward2_0_index
        assert schedule2_index < forward2_1_index

        # 算子进程的 parent_pid_for_sort=0，forward 的 parent_pid_for_sort=pid
        # 所以算子排在 forward 前面（同一个 group_pid 下）
        assert operator1_index < forward1_0_index
        assert operator2_index < forward1_1_index

    @patch('ms_service_profiler.exporters.exporter_trace.mp.Pool')
    @patch('ms_service_profiler.exporters.exporter_trace.LARGE_EVENTS_THRESHOLD', 1000)
    @patch('ms_service_profiler.exporters.exporter_trace.MAX_PROCESSES_LARGE', 4)
    @patch('ms_service_profiler.exporters.exporter_trace.MIN_CHUNK_SIZE_LARGE', 500)
    def test_prepare_data_smart_parallel_large_events(self, mock_pool):
        """测试大数据量的并行数据准备"""
        events = [{'ph': 'X', 'pid': 1, 'tid': 1, 'ts': 100, 'dur': 50}] * 2000
        mock_pool_instance = MagicMock()
        mock_pool.return_value.__enter__.return_value = mock_pool_instance
        mock_pool_instance.imap_unordered.return_value = [{'slice': [MagicMock()], 'counter': [], 'flow': []}]

        result = _prepare_data_smart_parallel(events, {})

        self.assertEqual(len(result['slice']), 1)
