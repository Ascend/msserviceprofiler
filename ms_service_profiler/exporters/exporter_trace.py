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

import os
import time
import multiprocessing as mp
import json
from typing import Optional, NamedTuple
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from ms_service_profiler.exporters.base import TaskExporterBase
from ms_service_profiler.utils.file_open_check import ms_open, safe_json_dump, OpenException
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.exporters.utils import get_db_connection, create_sqlite_tables
from ms_service_profiler.utils.trace_to_db import (
    TRACE_TABLE_DEFINITIONS,
    trans_trace_meta_event,
    trans_trace_slice_data,
    trans_trace_counter_data,
    trans_trace_flow_data,
    write_to_process_thread_table,
    reset_track_id_manager,
    reset_process_table_manager,
    clear_data_cache,
    calculate_smart_process_config,
    write_all_data_smart,
)

# 常量定义
LARGE_EVENTS_THRESHOLD = 5000000  # 当事件数量超过500万时，启用大数据量处理模式
MAX_PROCESSES_LARGE = 8  # 大数据量处理时的最大进程数限制，避免过多进程导致系统资源耗尽
MIN_CHUNK_SIZE_LARGE = 200000  # 大数据量处理时每个数据块的最小事件数量，确保每个进程有足够的工作量
PROGRESS_REPORT_INTERVAL = 10  # 进度报告间隔，每处理10个数据块报告一次进度（仅限debug模式）

# 全局变量用于worker进程共享数据
_worker_track_id_map = None


def _init_worker_shared(track_id_map):
    """初始化worker进程，共享track_id映射"""
    global _worker_track_id_map
    _worker_track_id_map = track_id_map


class ExporterTrace(TaskExporterBase):
    name = "trace"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def depends(cls):
        return ["pipeline:service", "pipeline:mspti", "data_source:torch_profiler"]

    @classmethod
    @timer(logger.debug)
    def export(cls, data, mspti, torch_profiler) -> None:
        if 'db' not in cls.args.format and 'json' not in cls.args.format:
            return

        output = cls.args.output_path

        torch_profiler_prof_list = []
        torch_profiler_pid_domain_map = {}
        torch_profiler_pid_list = set()

        if torch_profiler:
            for index, prof_path in enumerate(torch_profiler):
                torch_profiler_prof, pid_list = load_single_prof(prof_path, index)
                torch_profiler_prof_list.extend(torch_profiler_prof.get("traceEvents"))
                torch_profiler_pid_list.update(pid_list)
                for event in torch_profiler_prof.get("traceEvents", []):
                    if event.get("name") == "process_name":
                        pid = event.get("pid")
                        process_name = event.get("args", {}).get("name", "")
                        if pid is not None and process_name:
                            torch_profiler_pid_domain_map[pid] = process_name

        if data is not None:
            all_data_df = data.get('tx_data_df', pd.DataFrame(columns=["name", "domain"])).copy()

            pid_domain_map = get_pid_primary_domain(all_data_df) if not all_data_df.empty else None
            prepare_domain_for_process(all_data_df)

            if 'pid_label_map' in data:
                pid_label_map = data['pid_label_map']
            else:
                pid_label_map = None

            msprof_data_df = data.get('msprof_data', pd.DataFrame())

            cann_data = []
            pid_ppid_map = []
            for index, pf in enumerate(msprof_data_df):
                msprof_data_ppid = pf.get("pid")
                msprof_data_pids = set()
                for prof_path in pf.get("msprof_files"):
                    cann_prof_data, msprof_data_pids = load_single_prof(prof_path, index)
                    cann_data.append(cann_prof_data)
                for msprof_data_pid in msprof_data_pids:
                    pid_ppid_map.append((msprof_data_pid, msprof_data_ppid, 'msprof'))

            if "ppid" in all_data_df and "pid" in all_data_df:
                for pid, ppid in set(zip(all_data_df['pid'], all_data_df['ppid'])):
                    pid_ppid_map.append((pid, ppid, 'service'))

            service_pid_str_map = {}
            for item in pid_ppid_map:
                if item[2] == 'service':
                    service_pid_str_map[int(item[0])] = item[1]

            python_pids = {}
            for pid in torch_profiler_pid_list:
                process_name = torch_profiler_pid_domain_map.get(pid, '')
                if process_name == 'Python':
                    service_pid_str = service_pid_str_map.get(int(pid))
                    if service_pid_str:
                        pid_ppid_map.append((pid, service_pid_str, 'torch'))
                        python_pids[int(pid)] = pid
                    else:
                        pid_ppid_map.append((pid, None, 'torch'))

            for pid in torch_profiler_pid_list:
                process_name = torch_profiler_pid_domain_map.get(pid, '')
                if process_name != 'Python':
                    for python_int_pid, python_pid in python_pids.items():
                        pid_ppid_map.append((pid, python_pid, 'torch'))
                        break

            pid_ppid_map = [(str(pid), ppid, pid, source) for pid, ppid, source in pid_ppid_map]

            logger.info(
                f"Total pid_ppid_map count: {len(pid_ppid_map)}, torch_profiler added: {len(torch_profiler_pid_list)}"
            )

            trace_data = create_trace_events(
                all_data_df, pid_label_map, pid_ppid_map, torch_profiler_pid_domain_map, pid_domain_map
            )
            merged_data = merge_json_data(trace_data, cann_data)
        else:
            merged_data = {"traceEvents": []}

        api_df = pd.DataFrame()
        kernel_df = pd.DataFrame()

        if mspti is not None:
            api_df = mspti.get('api_df', pd.DataFrame())
            kernel_df = mspti.get('kernel_df', pd.DataFrame())

        if not api_df.empty or not kernel_df.empty:
            tarce_events_list = []

            api_events = export_event_from_df(api_df, "Api", "Api")
            tarce_events_list.extend(api_events)

            kernel_events = export_event_from_df(kernel_df, "Kernel", "Kernel")
            tarce_events_list.extend(kernel_events)

            mspti_data = {"traceEvents": tarce_events_list}
            merged_data = merge_json_data(merged_data, [mspti_data])

        if 'db' in cls.args.format:
            logger.info('Start write trace data to db')
            create_sqlite_tables(TRACE_TABLE_DEFINITIONS)
            db_data = merged_data
            if torch_profiler:
                chrome_events = merged_data.get('traceEvents', [])
                db_events = torch_profiler_prof_list + chrome_events
                db_data = {'traceEvents': db_events}
            save_trace_data_into_db(db_data)
            logger.info('Write trace data to db success')

        if 'json' in cls.args.format:
            if torch_profiler:
                chrome_events = merged_data.get('traceEvents', [])
                merged_events = torch_profiler_prof_list + chrome_events
                merged_data = {'traceEvents': merged_events}
            save_trace_data_into_json(merged_data, output)

    def do_export(self):
        data, mspti, torch_profiler = (
            self.get_depends_result("pipeline:service", None),
            self.get_depends_result("pipeline:mspti", None),
            self.get_depends_result("data_source:torch_profiler", None),
        )
        torch_profiler = torch_profiler.get("torch_profiler") if torch_profiler is not None else None

        has_any_data = data is not None or mspti is not None or torch_profiler is not None
        if self.task_index == 0 and has_any_data:
            data_list = self.gather((None, None, None), dst=0)
        else:
            data_list = self.gather((data, mspti, torch_profiler), dst=0)

        if data_list is None:
            return None

        if self.task_index == 0 and has_any_data:
            data_list[0] = (data, mspti, torch_profiler)

        # 使用列表推导式过滤并提取非None值
        all_data = [item[0] for item in data_list if item is not None and item[0] is not None]
        all_mspti = [item[1] for item in data_list if item is not None and item[1] is not None]
        all_profilers = [item[2] for item in data_list if item is not None and item[2] is not None]

        # 获取第一个非None的值
        valid_data = all_data[0] if all_data else None
        valid_mspti = all_mspti[0] if all_mspti else None

        self.export(valid_data, valid_mspti, all_profilers)
        return None


def get_track_name(domain):
    if pd.notna(domain) and isinstance(domain, str):
        if 'Engine' in domain or 'Request' in domain:
            return "schedule"
        elif 'Execute' in domain:
            return "forward"
    return None


def get_pid_primary_domain(all_data_df):
    """获取每个PID的主要domain类型，用于生成进程名称"""
    if all_data_df is None or all_data_df.empty:
        return {}

    domain_col = all_data_df['domain']
    pid_col = all_data_df['pid']

    track_names = domain_col.apply(get_track_name)

    valid_mask = track_names.notna() & pid_col.notna()
    if not valid_mask.any():
        return {}

    valid_pids = pid_col[valid_mask].astype(int)
    valid_tracks = track_names[valid_mask]

    pid_tracks_df = pd.DataFrame({'pid': valid_pids, 'track': valid_tracks})

    return pid_tracks_df.drop_duplicates('pid').set_index('pid')['track'].to_dict()


def prepare_domain_for_process(all_data_df):
    # 如果只采集到了python数据而没有采集到cpp数据，则直接认为name为domain，确保domain列存在
    if 'domain' not in all_data_df.columns:
        all_data_df['domain'] = all_data_df['name']  # 直接添加新列

    # 过滤显示数据, Meta不显示
    meta_mask = all_data_df['domain'].isin(['Meta'])
    all_data_df.drop(all_data_df[meta_mask].index, inplace=True)

    # 适配vllm解析特殊打点字段
    if (all_data_df['name'] == 'outputSync').any():
        all_data_df = all_data_df[~all_data_df['name'].isin(['httpReq', 'httpRes', "getOutputAsync"])]

    # 对于非Request, RequestState, KVCache泳道区分tid显示
    mask = ~all_data_df['domain'].isin(['Request', 'RequestState', 'Schedule.KVCache', 'KVCache'])
    all_data_df.loc[mask, 'domain'] = (
        all_data_df.loc[mask, 'domain'].astype(str) + '(' + all_data_df.loc[mask, 'tid'].astype(str) + ')'
    )

    all_data_df['domain'] = all_data_df['domain'].replace('PDSplit', 'PDCommunication')


def process_prof_trace_events(events, index):
    pid_list = set()
    for event in events:
        pid_list.add(event.get('pid'))
        event_id = event.get('id')
        event_ph = event.get('ph')
        if event_id is not None and event_ph in ['s', 'f']:
            # 将 event_id 和 index 转换为字符串并拼接，保证不会重复
            event['id'] = str(event_id) + '_' + str(index)

    pid_list.discard(None)
    return [x for x in events if x.get("name") != 'process_sort_index'], pid_list


def load_single_prof(pf, prof_id):
    try:
        with ms_open(pf, 'r', encoding='utf-8') as file:
            trace_events = json.load(file)
    except OpenException as oe:
        logger.warning(f"cannot read file %r occurred {oe}", pf)
        return {"traceEvents": []}, set()
    except FileNotFoundError:
        logger.warning("The %r file was not found. Please check the file path.", pf)
        return {"traceEvents": []}, set()
    except json.JSONDecodeError:
        logger.warning("%r is not in a valid JSON format, which might be normal.", pf)
        return {"traceEvents": []}, set()

    trace_events, pid_list = process_prof_trace_events(trace_events, prof_id)

    return {"traceEvents": trace_events}, pid_list


def find_cann_pid(trace_events):
    for event in trace_events:
        if event.get("name") == "process_name":
            args = event.get("args", {})
            if args.get("name") == "CANN":
                return event.get("pid")
    return None


def merge_json_data(trace_data, msprof_data_df):
    for item in msprof_data_df:
        events = item.get("traceEvents", [])
        trace_data["traceEvents"].extend(events)
    return trace_data


@timer(logger.debug)
def write_trace_data_to_file(trace_data, output):
    def write_trace_data(range_index):
        start_index, end_index = range_index
        trace_data_list = trace_data[start_index:end_index]
        return safe_json_dump(trace_data_list, ensure_ascii=False)

    gourp_count = 100000
    data_count = len(trace_data)
    group_range_list = [(x, min(x + gourp_count, data_count)) for x in range(0, data_count, gourp_count)]
    results = []
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(write_trace_data, x) for x in group_range_list]
        for future in futures:
            try:
                results.append(future.result())
            except Exception as e:
                logger.error(f"Error raise from exporter trace, json dump failed. message: {e}")

    with ms_open(output, "w") as f:
        f.write('[')
        for index, content2 in enumerate(results):
            if len(content2) < 2:  # 确保至少有 2 个字符
                continue
            f.write(content2[1:-1])  # 去除首字符和尾字符
            if index != len(results) - 1:
                f.write(',')

        f.write("]")

    logger.info(f"Written trace data successfully. at {output}")


def save_trace_data_into_json(trace_data, output):
    file_path = os.path.join(output, 'chrome_tracing.json')
    write_trace_data_to_file(trace_data.get("traceEvents", []), file_path)


def add_flow_event(flow_event_df):
    flow_event_df = flow_event_df.copy()
    flow_event_df['rid'] = flow_event_df['rid'].astype(object)
    flow_event_df.loc[:, 'rid'] = flow_event_df['rid'].str.split(',')
    exploded_df = flow_event_df.explode('rid')
    exploded_df['tid'] = exploded_df['domain']

    # 初始化 ph 列为默认值
    exploded_df['ph'] = 't'

    # 如果某个 rid 只有一行，根据during_time是否为0区分，为0就是ph=i，否则ph=x
    single_occurrences = exploded_df['rid'].value_counts()
    single_rids = single_occurrences[single_occurrences == 1].index
    single_mask = exploded_df['rid'].isin(single_rids)

    # 根据 during_time 的值来设置 ph（优先处理）
    during_time_zero_mask = exploded_df['during_time'] == 0
    exploded_df.loc[single_mask & during_time_zero_mask, 'ph'] = 'i'  # 瞬时事件
    exploded_df.loc[single_mask & ~during_time_zero_mask, 'ph'] = 'X'  # 完整事件

    # 找出每个 rid 的第一次和最后一次出现的位置（排除单次出现的）
    multi_mask = ~single_mask  # 多次出现的记录
    first_occurrences = exploded_df[multi_mask].groupby('rid').head(1).index
    last_occurrences = exploded_df[multi_mask].groupby('rid').tail(1).index

    # 设置第一次出现为 's'
    exploded_df.loc[first_occurrences, 'ph'] = 's'

    # 设置最后一次出现为 'f'
    exploded_df.loc[last_occurrences, 'ph'] = 'f'

    exploded_df['bp'] = ['b' if ph == 'f' else '' for ph in exploded_df['ph']]
    exploded_df['name'] = 'flow_' + exploded_df['rid']
    exploded_df['ts'] = exploded_df['start_time']
    exploded_df['id'] = exploded_df['rid']
    exploded_df['cat'] = exploded_df['rid']
    exploded_df['pid'] = exploded_df['pid']
    flow_trace_events = exploded_df[['name', 'ph', 'ts', 'id', 'cat', 'pid', 'tid']].to_dict(orient='records')
    return flow_trace_events


def create_trace_events(
    all_data_df, pid_label_map=None, pid_ppid_map=None, torch_profiler_pid_domain_map=None, pid_domain_map=None
):
    metric_event = ['npu', 'Schedule.KVCache', 'KVCache', 'PullKVCache', 'Queue']

    # name 非空
    name_notna_condition = all_data_df['name'].notna()

    # 非metric数据
    domain_not_in_metric_condition = ~all_data_df['domain'].isin(metric_event)

    # 筛选掉domain为expert_hot开头的数据，不写入trace图
    prefix_to_exclude = 'expert_hot'
    domain_not_startswith_condition = ~all_data_df['domain'].str.startswith(prefix_to_exclude)

    # 普通事件
    valid_name_df = all_data_df[name_notna_condition & domain_not_in_metric_condition & domain_not_startswith_condition]
    trace_events = add_trace_events(valid_name_df)

    if not all_data_df.empty and "name" in all_data_df:
        npu_trace_events = add_npu_events(all_data_df[all_data_df['name'] == 'npu'])
        trace_events.extend(npu_trace_events)

        kv_trace_events = add_kvcache_events(
            all_data_df[all_data_df['domain'].isin(['Schedule.KVCache', 'KVCache'])], pid_label_map
        )
        trace_events.extend(kv_trace_events)

        queue_trace_events = add_queue_events(all_data_df[all_data_df['name'] == 'Queue'])
        trace_events.extend(queue_trace_events)

        pull_kvcache_events = add_pull_kvcache_events(all_data_df[all_data_df['domain'] == 'PullKVCache'])
        trace_events.extend(pull_kvcache_events)

        # flow事件
        flow_event_df = valid_name_df[valid_name_df['rid'].notna()]
        flow_trace_events = add_flow_event(flow_event_df)

        trace_events.extend(flow_trace_events)

    trace_events = sort_trace_events_by_tid(trace_events)

    coordinator_pid = None
    for event in trace_events:
        tid = event.get("tid", "")
        if isinstance(tid, str) and "Coordinator" in tid:
            coordinator_pid = event["pid"]
            break  # 找到第一个就退出

    pid_domain_map = (
        get_pid_primary_domain(all_data_df) if all_data_df is not None and pid_domain_map is None else pid_domain_map
    )

    if torch_profiler_pid_domain_map:
        if pid_domain_map is None:
            pid_domain_map = {}
        for pid, domain in torch_profiler_pid_domain_map.items():
            if pid not in pid_domain_map:
                pid_domain_map[pid] = domain

    trace_events = [e for e in trace_events if e.get('name') != 'process_name']

    if pid_label_map is not None or pid_ppid_map is not None:
        trace_events.extend(
            sort_trace_events_by_pid(
                pid_label_map, pid_ppid_map, coordinator_pid, pid_domain_map, torch_profiler_pid_domain_map
            )
        )

    trace_data = {"traceEvents": trace_events}
    return trace_data


def sort_trace_events_by_pid(
    pid_label_map, pid_ppid_map, coordinator_pid=None, pid_domain_map=None, torch_profiler_pid_domain_map=None
):
    if not pid_ppid_map:
        return []

    process_tree = {str(pid): str(ppid) for pid, ppid, _, _ in pid_ppid_map}

    def find_schedule_parent(start_pid):
        group_pid = 0
        current_pid = start_pid
        visited = set()
        while current_pid is not None:
            current_key = str(current_pid)
            if current_key in visited:
                break
            visited.add(current_key)
            parent = process_tree.get(current_key)
            if parent is None:
                break
            parent_int = int(parent) if str(parent).isdigit() else parent
            if pid_domain_map and parent_int in pid_domain_map:
                if pid_domain_map[parent_int].lower() == "schedule":
                    group_pid = parent_int
                    break
            current_pid = parent_int
        return group_pid

    def build_prcess_prefix(pid):
        pid_key = str(pid)
        if pid_key in process_prefix:
            return process_prefix[pid_key]
        ppid = process_tree.get(pid_key)
        if ppid is None:
            return ""

        ppid_prefix = build_prcess_prefix(ppid)
        pid_prefix = f"{ppid_prefix}.{pid}"
        process_prefix[pid_key] = pid_prefix
        return pid_prefix

    process_prefix = {}

    child_to_parent = {str(pid): str(ppid) for pid, ppid, _, _ in pid_ppid_map if str(pid) != str(ppid)}

    service_pid_to_group_pid = {}
    for str_pid, ppid, ori_pid, source in pid_ppid_map:
        if source == 'service' and pid_domain_map:
            pid_int = int(ori_pid) if not isinstance(ori_pid, int) else ori_pid
            group_pid = find_schedule_parent(ori_pid)
            if group_pid == 0 and pid_int in pid_domain_map:
                if pid_domain_map[pid_int].lower() == "schedule":
                    group_pid = pid_int
            if group_pid != 0:
                service_pid_to_group_pid[pid_int] = group_pid

    def sort_key(item):
        pid, prefix, source = item
        if pid == coordinator_pid:
            return (-1, -1, -1, '')

        source_rank = 0 if source == 'service' else 1

        process_type = None
        parent_type_rank = None
        parent_dp_rank = None

        pid_str = str(pid)
        pid_in_child = pid_str in child_to_parent
        parent_pid = None

        if pid_domain_map and pid in pid_domain_map:
            domain = pid_domain_map[pid]
            if domain.lower() == "schedule":
                process_type = 'schedule'
            elif domain.lower() == "forward":
                process_type = 'forward'
        elif pid_in_child:
            parent_pid_str = str(child_to_parent[pid_str])
            parent_pid = int(parent_pid_str) if parent_pid_str.isdigit() else parent_pid_str

            if pid_domain_map and parent_pid in pid_domain_map:
                parent_domain = pid_domain_map[parent_pid]
                if parent_domain.lower() == "schedule":
                    parent_type_rank = 0
                    parent_dp_rank = None
                elif parent_domain.lower() == "forward":
                    parent_type_rank = 1
                    if pid_label_map and parent_pid in pid_label_map:
                        parent_dp_rank = pid_label_map[parent_pid].get('dp_rank')
                        if parent_dp_rank is None:
                            parent_dp_rank = pid_label_map[parent_pid].get('dp')

        type_priority = {'schedule': 0, 'forward': 1}
        type_rank = type_priority.get(process_type, parent_type_rank if parent_type_rank is not None else 3)

        dp_rank = None
        if process_type == 'forward':
            if pid_label_map and pid in pid_label_map:
                dp_rank = pid_label_map[pid].get('dp_rank')
                if dp_rank is None:
                    dp_rank = pid_label_map[pid].get('dp')

        if parent_type_rank is not None and parent_dp_rank is not None:
            dp_rank = parent_dp_rank

        group_pid = 0
        if process_type == 'schedule':
            group_pid = pid
        else:
            group_pid = find_schedule_parent(pid)

        if group_pid == 0 and source in ('torch', 'msprof'):
            pid_int = int(pid) if not isinstance(pid, int) else pid
            for service_pid, service_group_pid in service_pid_to_group_pid.items():
                if service_pid == pid_int:
                    group_pid = service_group_pid
                    break

        if group_pid == 0 and source in ('torch', 'msprof'):
            group_pid = float('inf')

        parent_pid_for_sort = 0
        if source in ('torch', 'msprof'):
            ppid = process_tree.get(str(pid))
            if ppid:
                parent_pid_for_sort = int(ppid) if ppid.isdigit() else ppid
        elif process_type == 'forward':
            parent_pid_for_sort = int(pid) if not isinstance(pid, int) else pid
        if dp_rank is not None:
            return (group_pid, parent_pid_for_sort, source_rank, type_rank, int(dp_rank), prefix)
        else:
            return (group_pid, parent_pid_for_sort, source_rank, type_rank, 0, prefix)

    process_prefix_list = [(ori_pid, build_prcess_prefix(pid), source) for pid, _, ori_pid, source in pid_ppid_map]

    process_prefix_list.sort(key=sort_key)

    pid_sorting_meta = []

    for index, item in enumerate(process_prefix_list):
        pid, _, source = item
        pid_sorting_meta.append(dict(name="process_sort_index", ph="M", pid=pid, args=dict(sort_index=index)))

        primary_domain = None
        if pid_domain_map:
            if pid in pid_domain_map:
                primary_domain = pid_domain_map[pid]
            else:
                pid_int = int(pid) if not isinstance(pid, str) else None
                if pid_int and pid_int in pid_domain_map:
                    primary_domain = pid_domain_map[pid_int]

        display_name = primary_domain if primary_domain else str(pid)

        if source in ('torch', 'msprof') and torch_profiler_pid_domain_map:
            for key in torch_profiler_pid_domain_map:
                if key == pid and type(key) is type(pid):
                    display_name = torch_profiler_pid_domain_map[key]
                    break

        pid_sorting_meta.append(dict(name="process_name", ph="M", pid=pid, args=dict(name=display_name)))

        labels = []
        if pid_label_map is not None and "hostname" in pid_label_map.get(pid, []):
            labels.append(pid_label_map.get(pid).get("hostname"))
        if pid_label_map is not None and "dp" in pid_label_map.get(pid, []):
            labels.append(f"dp{pid_label_map.get(pid).get('dp')}")
        elif pid_label_map is not None and "dp_rank" in pid_label_map.get(pid, []):
            labels.append(f"dp{pid_label_map.get(pid).get('dp_rank')}")

        if labels:
            pid_sorting_meta.append(dict(name="process_labels", ph="M", pid=pid, args=dict(labels=','.join(labels))))

    return pid_sorting_meta


def sort_trace_events_by_tid(trace_events):
    tid_sorting_order = [
        'Execute',
        'Schedule',
        'Communication',
        'KVCache',
        'Schedule.KVCache',
        'Engine',
        'Api',
        'Kernel',
    ]
    main_pid = 0
    for event_info in trace_events:
        if event_info.get("tid") in tid_sorting_order:
            main_pid = event_info.get("pid")
            break
    tid_sorting_meta = [
        dict(name="thread_sort_index", ph="M", pid=main_pid, tid=tid, args=dict(sort_index=index))
        for index, tid in enumerate(tid_sorting_order)
    ]

    def get_tid_sorting_key(event):
        if 'tid' in event and event['tid'] in tid_sorting_order:
            return tid_sorting_order.index(event['tid'])
        else:
            return len(tid_sorting_order)

    sorted_trace_events = sorted(trace_events, key=get_tid_sorting_key)

    sorted_trace_events.extend(tid_sorting_meta)
    return sorted_trace_events


def add_trace_events(valid_name_df):
    """将有效名称数据转换为跟踪事件列表"""
    # 添加基本跟踪事件字段
    trace_event_df = _add_basic_trace_fields(valid_name_df)

    # 确保所有必需的列都存在
    valid_name_df = _ensure_required_columns(valid_name_df)

    # 构建参数列表
    args_list = _build_args_list(valid_name_df)

    # 安全地获取所有字段的值
    names = trace_event_df.get('name', pd.Series([''] * len(trace_event_df))).tolist()
    phs = trace_event_df.get('ph', pd.Series(['X'] * len(trace_event_df))).tolist()
    tss = trace_event_df.get('ts', pd.Series([None] * len(trace_event_df))).tolist()
    durs = trace_event_df.get('dur', pd.Series([0.0] * len(trace_event_df))).tolist()
    pids = trace_event_df.get('pid', pd.Series([0] * len(trace_event_df))).tolist()
    tids = trace_event_df.get('tid', pd.Series([0] * len(trace_event_df))).tolist()

    trace_events = []
    for i in range(len(trace_event_df)):
        # 只有当ts有有效值时才添加这条记录
        if tss[i] is not None:
            trace_events.append(
                {
                    'name': names[i],
                    'ph': phs[i],
                    'ts': tss[i],
                    'dur': durs[i],
                    'pid': pids[i],
                    'tid': tids[i],
                    'args': args_list[i] if i < len(args_list) else {},
                }
            )

    return trace_events


def _add_basic_trace_fields(df):
    """添加基本跟踪事件字段到DataFrame"""
    trace_df = df.copy()
    trace_df['ph'] = ['I' if during_time == 0 else 'X' for during_time in df['during_time']]
    trace_df['ts'] = df['start_time']
    trace_df['tid'] = df['domain']
    trace_df['dur'] = df['during_time']
    return trace_df


def _ensure_required_columns(df):
    """确保DataFrame包含所有必需的列，缺失的列使用默认值填充"""
    required_columns = ['start_datetime', 'end_datetime', 'batch_size', 'res_list', 'rid', 'message', 'tid']

    column_defaults = {
        'start_datetime': pd.NaT,
        'end_datetime': pd.NaT,
        'batch_size': 0,
        'res_list': [],
        'rid': '',
        'message': {},
        'tid': 0,
    }

    missing_columns = []
    for col in required_columns:
        if col not in df.columns:
            missing_columns.append(col)
            default_value = column_defaults.get(col, [])
            if default_value == []:
                df[col] = df.apply(lambda _: [], axis=1)
            else:
                df[col] = default_value

    if missing_columns:
        logger.warning(f"Missing columns in trace event data, using defaults: {missing_columns}")

    return df


def _build_args_list(df):
    """从DataFrame构建参数列表"""
    required_columns = [
        'start_datetime',
        'end_datetime',
        'batch_type',
        'batch_size',
        'res_list',
        'rid',
        'message',
        'tid',
    ]

    args_list = []
    try:
        selected_df = df[required_columns]

        for row in selected_df.itertuples(index=False, name='TraceRow'):
            args_dict = _process_row_to_args(row)
            args_list.append(args_dict)

    except Exception as e:
        logger.error(f"Error during trace event generation: {e}")
        return []

    return args_list


def _process_row_to_args(row):
    """处理单行数据并转换为参数字典"""
    start, end, batch_type, batch_size, res_list, rid, message, tid = row

    # 从message中排除特定键
    args_dict = {k: v for k, v in message.items() if k not in ["domain", "name", "type", "rid"]}

    # 添加基本字段
    args_dict.update({'start_datetime': start, 'end_datetime': end, 'tid': tid})

    # 条件添加可选字段
    if batch_size is not None and is_valid_value(batch_size):
        args_dict.update({'batch_size': batch_size})

    if batch_type is not None and is_valid_value(batch_type):
        args_dict.update({'batch_type': batch_type})

    if res_list is not None and is_valid_value(res_list):
        args_dict.update({"res_list": res_list})

    if batch_size is None and rid != res_list:
        args_dict.update({"rid": rid})

    return args_dict


def is_valid_value(x):
    """
    判断是否一个值是否非空、非Nan值等
    涉及到多种数据格式
    """
    if x is None:
        return False
    if isinstance(x, (list, tuple)) and len(x) == 0:
        return False
    if isinstance(x, str) and x.strip() == "":
        return False
    if isinstance(x, (list, tuple)):
        # 对于列表，检查是否全为 None/空/NaN
        return not all(item is None or (isinstance(item, str) and item.strip() == "") for item in x)
    if isinstance(x, (np.ndarray, pd.Series)):
        return len(x) > 0 and not pd.isna(x).all()
    # 其他情况：数字、非空字符串等都算有效
    return not pd.isna(x)


def add_cpu_events(cpu_data_df):
    if cpu_data_df is None or cpu_data_df.shape[0] == 0:
        return []
    cpu_trace_df = cpu_data_df.copy()
    cpu_trace_df['name'] = 'CPU Usage'
    cpu_trace_df['ph'] = 'C'
    cpu_trace_df['ts'] = cpu_data_df['start_time']
    cpu_trace_df['pid'] = 1
    cpu_trace_df['tid'] = 'CPU Usage'
    cpu_trace_df['args'] = [{'CPU Usage': usage} for usage in cpu_data_df['usage']]
    cpu_trace_events = cpu_trace_df[['name', 'ph', 'ts', 'pid', 'tid', 'args']].to_dict(orient='records')
    return cpu_trace_events


def add_mem_events(df):
    if df is None or df.shape[0] == 0:
        return []
    df = df.copy()
    df['name'] = 'Memory Usage'
    df['ph'] = 'C'
    df['ts'] = df['start_time']
    df['pid'] = 1
    df['tid'] = 'Memory Usage'
    df['args'] = [{'Memory Usage': usage} for usage in df['usage']]
    events = df[['name', 'ph', 'ts', 'pid', 'tid', 'args']].to_dict(orient='records')
    return events


def add_npu_events(npu_data_df):
    if npu_data_df is None or npu_data_df.shape[0] == 0:
        return []
    npu_trace_df = npu_data_df.copy()
    npu_trace_df['name'] = 'NPU Usage'
    npu_trace_df['ph'] = 'C'
    npu_trace_df['ts'] = npu_data_df['start_time']
    npu_trace_df['pid'] = 1
    npu_trace_df['tid'] = 'NPU Usage'
    npu_trace_df['args'] = [{'Usage': usage} for usage in npu_data_df['usage=']]
    npu_trace_events = npu_trace_df[['name', 'ph', 'ts', 'pid', 'tid', 'args']].to_dict(orient='records')
    return npu_trace_events


def add_kvcache_events(kv_data_df, pid_label_map=None):
    # 检查是否包含所需的列
    has_free_blocks_cal = 'free_blocks' in kv_data_df.columns
    has_device_block = 'deviceBlock=' in kv_data_df.columns
    has_free_blocks = 'FreeBlocks=' in kv_data_df.columns

    if not has_free_blocks_cal and not has_free_blocks and not has_device_block:
        logger.warning('No KVCache related columns found')
        return []

    logger.debug('KVCache columns found, proceeding with event generation')

    # 预声明变量避免分支中重复检查
    has_pid_map = pid_label_map is not None and "pid" in kv_data_df.columns
    has_scope_dp = "scope#dp" in kv_data_df.columns

    # 向量化处理name列
    name = _build_name_column(kv_data_df, pid_label_map, has_pid_map, has_scope_dp)

    # 根据条件设置args值，优先使用FreeBlocks=，否则使用deviceBlock=
    args_values = []
    if has_free_blocks_cal:
        # 优先使用插件计算的新列 free_blocks
        logger.debug("Using free_blocks column for KVCache events")
        args_values = [{'Device Block': x} for x in kv_data_df['free_blocks']]
    elif has_free_blocks:
        # 其次使用vllm的采集落盘 FreeBlocks=
        logger.debug("Using FreeBlocks= column for KVCache events")
        args_values = [{'Device Block': x} for x in kv_data_df['FreeBlocks=']]
    else:
        # 兼容旧版 deviceBlock=
        logger.debug("Using deviceBlock= column for KVCache events")
        args_values = [{'Device Block': x} for x in kv_data_df['deviceBlock=']]

    # 构建结果DataFrame
    result_df = pd.DataFrame(
        {
            'name': name,
            'ph': 'C',
            'ts': kv_data_df['start_time'],
            'pid': kv_data_df['pid'] if 'pid' in kv_data_df else None,
            'tid': kv_data_df['domain'],
            'args': args_values,
        }
    )

    # 使用itertuples加速字典转换
    return [
        dict(name=r.name, ph=r.ph, ts=r.ts, pid=r.pid, tid=r.tid, args=r.args)
        for r in result_df.itertuples(index=False)
    ]


def add_queue_events(queue_data_df):
    if 'QueueSize=' not in queue_data_df or 'scope#QueueName' not in queue_data_df:
        return []
    queue_data_df.loc[queue_data_df['scope#QueueName'] == 'WAITING', ['name', 'domain']] = 'WaitingQueue'
    queue_data_df.loc[queue_data_df['scope#QueueName'] == 'RUNNING', ['name', 'domain']] = 'RunningQueue'

    queue_trace_df = queue_data_df.copy()
    queue_trace_df['ph'] = 'C'
    queue_trace_df['ts'] = queue_trace_df['start_time']
    queue_trace_df['tid'] = queue_trace_df['domain']
    queue_trace_df['args'] = [{'Queue Size': size} for size in queue_trace_df['QueueSize=']]
    queue_trace_events = queue_trace_df[['name', 'ph', 'ts', 'pid', 'tid', 'args']].to_dict(orient='records')
    return queue_trace_events


def _build_name_column(kv_data_df, pid_label_map, has_pid_map, has_scope_dp):
    """构建name列的逻辑"""
    if has_pid_map:
        return _build_name_with_pid_map(kv_data_df, pid_label_map, has_scope_dp)
    elif has_scope_dp:
        return kv_data_df['domain'] + '-dp' + kv_data_df['scope#dp'].astype(int, errors='ignore').astype(str)
    else:
        return kv_data_df['domain']


def _build_name_with_pid_map(kv_data_df, pid_label_map, has_scope_dp):
    """当有pid_map时构建name列"""
    # 构建pid到dp_rank的向量化映射
    dp_rank_map = {pid: info['dp_rank'] for pid, info in pid_label_map.items() if 'dp_rank' in info}

    dp_ranks = kv_data_df['pid'].map(dp_rank_map)
    has_dp_rank = dp_ranks.notna()
    name = kv_data_df['domain'].copy()

    # 处理有dp_rank的情况
    if has_dp_rank.any():
        name.loc[has_dp_rank] = (
            kv_data_df.loc[has_dp_rank, 'domain'] + '-dp' + dp_ranks[has_dp_rank].astype(int).astype(str)
        )

    # 处理scope#dp回退
    if has_scope_dp:
        scope_dp_mask = ~has_dp_rank & kv_data_df['scope#dp'].notna()
        if scope_dp_mask.any():
            name.loc[scope_dp_mask] = (
                kv_data_df.loc[scope_dp_mask, 'domain']
                + '-dp'
                + kv_data_df.loc[scope_dp_mask, 'scope#dp'].astype(int).astype(str)
            )
    return name


def add_pull_kvcache_events(df):
    if df is None or df.shape[0] == 0:
        return []
    df_all_device = df.copy()
    all_events = []

    for rank in df_all_device['rank'].unique():
        try:
            rank = int(rank)
        except Exception as e:
            logger.warning(f"Unexpected error processing rank {rank}: {str(e)}, skipping this rank")
            continue
        df = df_all_device[df_all_device['rank'] == rank].copy().reset_index(drop=True)
        df['pid'] = "PullKVCache"
        df['name'] = df['domain']
        df['ph'] = 'X'
        df['ts'] = df['start_time']
        df['tid'] = f"Decode Device rank_{rank}"
        df['dur'] = df['during_time']
        args = [
            'rank',
            'rid',
            'block_tables',
            'seq_len',
            'during_time',
            'start_datetime',
            'end_datetime',
            'start_time',
            'end_time',
        ]
        df['args'] = df[[arg for arg in args if arg in df.columns]].to_dict(orient='records')
        events = df[['name', 'ph', 'ts', 'pid', 'tid', 'args', 'dur']].to_dict(orient='records')
        all_events.extend(events)

    return all_events


def export_event_from_df(df, channel_name, tid):
    tarce_events_list = []

    name_arr = df["name"].values
    start_arr = df["start"].values
    end_arr = df["end"].values
    process_arr = df["db_id"].values

    for i in range(len(df)):
        name = name_arr[i]
        start = start_arr[i] // 1000
        end = end_arr[i] // 1000
        process_id = process_arr[i]

        trace_event = {
            "name": name,
            "ph": "X",
            "ts": int(start),
            "dur": int(end - start),
            "pid": int(process_id),
            "tid": tid,
            "args": {},
        }

        tarce_events_list.append(trace_event)

    process_ids = list(set(list(process_arr)))
    for process_id in process_ids:
        channel_event = {
            "ph": "M",
            "pid": int(process_id),
            "tid": tid,
            "name": "thread_name",
            "args": {"name": channel_name},
        }
        tarce_events_list.append(channel_event)

    return tarce_events_list


def save_trace_data_into_db(trace_data):
    """
    使用智能进程数设置的多进程优化方案 - 性能优化版
    """
    events = trace_data.get("traceEvents", [])
    total = len(events)
    if total == 0:
        logger.warning("no data to write")
        return

    start_time = time.time()
    logger.debug(f"=== SMART MULTI-PROCESS: PROCESSING {total} EVENTS ===")

    # 重置状态
    reset_track_id_manager()
    reset_process_table_manager()
    clear_data_cache()

    # 第一步：单进程构建track_id映射
    logger.debug("=== STEP 1: BUILDING TRACK_ID MAPPING ===")
    track_id_map = _build_track_id_mapping_smart(events)

    # 第二步：智能多进程数据准备
    logger.debug("=== STEP 2: SMART MULTI-PROCESS DATA PREPARATION ===")
    other_events = [e for e in events if e.get('ph') != 'M']

    if other_events:
        data_results = _prepare_data_smart_parallel(other_events, track_id_map)
    else:
        data_results = {'slice': [], 'counter': [], 'flow': []}

    # 第三步：单进程批量写入
    logger.debug("=== STEP 3: BATCH WRITE ===")
    write_all_data_smart(data_results)

    elapsed = time.time() - start_time
    logger.debug(f"Smart multi-process completed in {elapsed:.3f}s")


def _build_track_id_mapping_smart(events):
    """
    优化的track_id映射构建
    """
    track_id_map = {}

    conn = get_db_connection()
    if not conn:
        logger.warning("Failed to get database connection for track_id mapping")
        return track_id_map

    cursor = None
    try:
        cursor = conn.cursor()
        _setup_database_optimizations(cursor)

        unique_pid_tid, meta_events = _collect_pid_tid_and_meta_events(events)
        _process_meta_events_batch(meta_events, cursor)
        _process_pid_tid_batch(events, unique_pid_tid, track_id_map, cursor)

        conn.commit()
        logger.debug(f"Built track_id mapping with {len(track_id_map)} entries")

    except sqlite3.Error as e:
        logger.warning(f"Database error during track_id mapping: {e}")
        conn.rollback()
    except Exception as e:
        logger.warning(f"Unexpected error during track_id mapping: {e}")
        conn.rollback()
    finally:
        # 确保游标和连接都被关闭
        if cursor:
            try:
                cursor.close()
            except sqlite3.Error:
                pass
        try:
            conn.close()
        except sqlite3.Error:
            pass

    return track_id_map


def _setup_database_optimizations(cursor):
    """设置数据库优化参数"""
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA cache_size = 10000")
    cursor.execute("PRAGMA synchronous = NORMAL")


def _collect_pid_tid_and_meta_events(events):
    """收集所有需要的pid,tid对和meta事件"""
    unique_pid_tid = set()
    meta_events = []

    for event in events:
        ph_type = event.get('ph')
        if ph_type == 'M':
            meta_events.append(event)
        else:
            pid = event.get('pid')
            tid = _get_tid_from_event(event, ph_type)
            if pid is not None and tid is not None:
                unique_pid_tid.add((pid, tid))

    return unique_pid_tid, meta_events


def _get_tid_from_event(event, ph_type):
    """从事件中提取tid"""
    if ph_type == 'C':
        return event.get('name')
    return event.get('tid')


def _process_meta_events_batch(meta_events, cursor):
    """批量处理meta事件"""
    for event in meta_events:
        trans_trace_meta_event(event, cursor)


def _process_pid_tid_batch(events, unique_pid_tid, track_id_map, cursor):
    """批量处理pid,tid对"""
    for pid, tid in unique_pid_tid:
        thread_sort_index = _find_thread_sort_index(events, pid, tid)
        track_id = write_to_process_thread_table({'pid': pid, 'tid': tid}, thread_sort_index, cursor)
        track_id_map[(pid, tid)] = track_id


def _find_thread_sort_index(events, pid, tid):
    """查找线程排序索引"""

    for event in events:
        # 精确匹配：必须是thread_sort_index的M事件，且pid和tid匹配
        # 先检查是否是元事件(M事件)
        if event.get('ph') != 'M':
            continue

        # 检查事件名称
        if event.get('name') != 'thread_sort_index':
            continue

        # 检查进程和线程ID匹配
        if event.get('pid') == pid and event.get('tid') == tid:
            args = event.get('args', {})
            return args.get('sort_index', 0)

    return 0


def _prepare_data_smart_parallel(events, track_id_map):
    """
    智能多进程数据准备 - 优化进程配置
    """
    total_events = len(events)
    if total_events == 0:
        return {'slice': [], 'counter': [], 'flow': []}

    # 优化的进程数和分块大小配置 - 针对大数据量
    if total_events > LARGE_EVENTS_THRESHOLD:  # 超过500万事件
        optimal_processes = min(mp.cpu_count() - 1, MAX_PROCESSES_LARGE)  # 限制最大8个进程
        chunk_size = max(MIN_CHUNK_SIZE_LARGE, total_events // optimal_processes)
    else:
        num_processes, chunk_size = calculate_smart_process_config(total_events)
        optimal_processes = num_processes

    # 创建分块
    chunks = [events[i : i + chunk_size] for i in range(0, total_events, chunk_size)]

    logger.debug(f"Smart config: {optimal_processes} processes, {chunk_size} chunk size for {total_events} events")

    with mp.Pool(processes=optimal_processes, initializer=_init_worker_shared, initargs=(track_id_map,)) as pool:
        results = []
        completed = 0

        # 使用imap_unordered提高效率
        for result in pool.imap_unordered(_process_chunk_smart, chunks, chunksize=1):
            results.append(result)
            completed += 1

            # 进度报告
            if completed % PROGRESS_REPORT_INTERVAL == 0 or completed == len(chunks):
                logger.debug(f"Processed {completed}/{len(chunks)} chunks")

    # 合并结果
    final_result = {'slice': [], 'counter': [], 'flow': []}
    for result in results:
        final_result['slice'].extend(result['slice'])
        final_result['counter'].extend(result['counter'])
        final_result['flow'].extend(result['flow'])

    logger.debug(
        f"Data preparation completed: {len(final_result['slice'])} slices, "
        f"{len(final_result['counter'])} counters, {len(final_result['flow'])} flows"
    )
    return final_result


def _process_chunk_smart(events_chunk):
    """
    智能处理数据块

    Args:
        events_chunk: 事件数据块

    Returns:
        dict: 包含三种类型数据的字典
    """
    slice_data = []
    counter_data = []
    flow_data = []

    for event in events_chunk:
        _process_single_event(event, slice_data, counter_data, flow_data)

    return {'slice': slice_data, 'counter': counter_data, 'flow': flow_data}


def _process_single_event(event, slice_data, counter_data, flow_data):
    """处理单个事件"""
    try:
        ph_type = event.get('ph')

        if _is_slice_event(ph_type, event):
            data = _prepare_slice_data_smart(event)
            if data:
                slice_data.append(data)

        elif _is_counter_event(ph_type, event):
            data = _prepare_counter_data_smart(event)
            if data:
                counter_data.append(data)

        elif _is_flow_event(ph_type, event):
            data = _prepare_flow_data_smart(event, ph_type)
            if data:
                flow_data.append(data)

    except (ValueError, KeyError, TypeError) as e:
        logger.debug(f"error when _process_single_event: {e}, event: {event.get('name', 'unknown')}")

    except Exception as e:
        logger.error(f"unexpect error when _process_single_event: {e}, 事件: {event.get('name', 'unknown')}")


def _is_slice_event(ph_type, event):
    """判断是否为切片事件"""
    return ph_type in ('X', 'I') and event.get('ts') is not None and event.get('dur') is not None


def _is_counter_event(ph_type, event):
    """判断是否为计数器事件"""
    return ph_type == 'C' and event.get('ts') is not None


def _is_flow_event(ph_type, event):
    """判断是否为流事件"""
    return ph_type in ('s', 't', 'f') and event.get('ts') is not None


class SliceData(NamedTuple):
    """slice数据的命名元组"""

    timestamp: float
    duration: float
    name: str
    track_id: int
    category: Optional[str]
    args: Optional[dict]
    color_name: Optional[str]
    end_timestamp: float
    flag_id: Optional[int]


class CounterData(NamedTuple):
    """counter数据的命名元组"""

    name: str
    process_id: int
    timestamp: float
    category: Optional[str]
    args: Optional[dict]


class FlowData(NamedTuple):
    """flow数据的命名元组"""

    flow_id: str
    name: str
    track_id: int
    timestamp: float
    category: Optional[str]
    phase_type: str


def _prepare_slice_data_smart(event: dict) -> Optional[SliceData]:
    """智能slice数据处理

    Args:
        event: 原始事件数据

    Returns:
        Optional[SliceData]: 切片数据对象，如果track_id无效则返回None
    """
    event_data = trans_trace_slice_data(event)

    pid = event.get('pid')
    tid = event.get('tid')
    track_id = _worker_track_id_map.get((pid, tid), 0)

    if track_id == 0:
        return None

    end_timestamp = event_data['ts'] + event_data['dur']

    return SliceData(
        timestamp=event_data.get('ts'),
        duration=event_data.get('dur'),
        name=event_data.get('name'),
        track_id=track_id,
        category=event.get('cat'),
        args=event_data.get('args'),
        color_name=event.get('cname'),
        end_timestamp=end_timestamp,
        flag_id=event.get('flag_id'),
    )


def _prepare_counter_data_smart(event: dict) -> Optional[CounterData]:
    """智能counter数据处理

    Args:
        event: 原始事件数据

    Returns:
        Optional[CounterData]: 计数器数据对象，如果时间戳为0则返回None
    """
    event_data = trans_trace_counter_data(event)

    if event_data.get('ts') == 0:
        return None

    return CounterData(
        name=event_data.get('name'),
        process_id=event_data.get('pid'),
        timestamp=event_data.get('ts'),
        category=event.get('cat'),
        args=event_data.get('args'),
    )


def _prepare_flow_data_smart(event: dict, ph_type: str) -> Optional[FlowData]:
    """智能flow数据处理

    Args:
        event: 原始事件数据
        ph_type: 事件阶段类型 ('s', 't', 'f')

    Returns:
        Optional[FlowData]: 流数据对象，如果track_id无效则返回None
    """
    event_data = trans_trace_flow_data(event)

    pid = event.get('pid')
    tid = event.get('tid')
    track_id = _worker_track_id_map.get((pid, tid), 0)

    if track_id == 0:
        return None

    return FlowData(
        flow_id=event_data.get('flow_id'),
        name=event_data.get('name'),
        track_id=track_id,
        timestamp=event_data.get('ts'),
        category=event.get('cat'),
        phase_type=ph_type,
    )
