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

import pandas as pd

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.constant import US_PER_MS
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.error import key_except
from ms_service_profiler.exporters.utils import TableConfig, write_result_to_csv, write_result_to_db, check_domain_valid


def is_invalid_rid(rid):
    return ',' in rid or '{' in rid or ':' in rid


def get_req_base_info(df):
    # 原有分组逻辑
    req_group_df = df.groupby('rid')
    req_base_info = []
    for rid, pre_req_data in req_group_df:
        rid = str(rid)
        if rid == "" or is_invalid_rid(rid):
            continue

        # 构造请求信息
        new_req = {
            'rid': rid,
            'start_time': '',
            'start_datetime': '',
            'end_time': '',
            'recvTokenSize=': '',
            'replyTokenSize=': '',
            'execution_time': '',
            'cache_hit_rate': '',
        }

        # 获取httpReq
        http_req_df = pre_req_data[pre_req_data['name'] == 'httpReq']
        if not http_req_df.empty:
            first_row = http_req_df.iloc[0]
            new_req['start_time'] = first_row.get("start_time", 0)
            new_req['start_datetime'] = first_row.get("start_datetime", 0)

        # 获取 httpRes
        # 由于存在httpRes提前被调用，导致请求结束时间过早的情况，所以当前取httpRes和DecodeEnd中最晚一个点作为请求结束时间
        # mindIE重构后，取最后一个sendResponse的结束时间
        http_res_df = pre_req_data[pre_req_data['name'].isin(['httpRes', 'DecodeEnd', 'sendResponse', 'outputSync'])]
        if not http_res_df.empty:
            last_row = http_res_df.iloc[-1]
            new_req['end_time'] = last_row.get("end_time", 0)

        # 获取replyTokenSize
        if 'replyTokenSize=' in pre_req_data.columns and pre_req_data['replyTokenSize='].notna().any():
            # 获取当replyTokenSize列中值不为空时，获取其中的第一个值
            new_req['replyTokenSize='] = pre_req_data['replyTokenSize='].dropna().iloc[0]

        # 获取 recvTokenSize=
        if 'recvTokenSize=' in pre_req_data.columns and pre_req_data['recvTokenSize='].notna().any():
            # 获取当replyTokenSize列中值不为空时，获取其中的第一个值
            new_req['recvTokenSize='] = pre_req_data['recvTokenSize='].dropna().iloc[0]

        # 特殊字段，从outputSync获取输出长度
        output_sync_count = http_res_df[http_res_df['name'] == 'outputSync'].shape[0]
        if output_sync_count > 0:
            new_req['replyTokenSize='] = output_sync_count

        # 计算缓存命中率
        cache_hit_df = pre_req_data[pre_req_data['name'] == 'CacheHitRate']
        if not cache_hit_df.empty:
            hit_cache_value = cache_hit_df.iloc[0].get("hitCache")
            new_req['cache_hit_rate'] = hit_cache_value if hit_cache_value is not None else 0

        # 计算 execution_time
        if new_req['start_time'] != '' and new_req['end_time'] != '':
            new_req['end_time'] = new_req['end_time'] // US_PER_MS
            new_req['start_time'] = new_req['start_time'] // US_PER_MS
            new_req['execution_time'] = new_req['end_time'] - new_req['start_time']

            new_req['start_datetime'] = new_req['start_datetime']

        req_base_info.append(new_req)
    return pd.DataFrame(req_base_info)


def safe_merge_ttft_que(req_base_info: pd.DataFrame, ttft_df: pd.DataFrame, que_df: pd.DataFrame) -> pd.DataFrame:
    """
    无 copy 合并 rid、ttft、que_wait_time
    """
    # 1.ttft
    if 'rid' not in req_base_info.columns:
        req_base_info['rid'] = 'unknown'

    ttft_part = (
        ttft_df[['rid', 'ttft']].drop_duplicates('rid')
        if not ttft_df.empty and 'ttft' in ttft_df.columns
        else pd.DataFrame(columns=['rid', 'ttft'])
    )

    # 2.que_wait_time
    que_part = (
        que_df[['rid', 'que_wait_time']].drop_duplicates('rid')
        if not que_df.empty and 'que_wait_time' in que_df.columns
        else pd.DataFrame(columns=['rid', 'que_wait_time'])
    )

    # 3.合并ttft+que
    metrics = ttft_part.merge(que_part, on='rid', how='outer')

    # 4.与req_base_info合并
    return (
        req_base_info.assign(rid=lambda d: d['rid'].astype(str))
        .merge(metrics, on='rid', how='left')
        .assign(ttft=lambda d: d['ttft'].fillna(0), que_wait_time=lambda d: d['que_wait_time'].fillna(0))
        .infer_objects()
    )


class ExporterReqData(ExporterBase):  # pylint: disable=abstract-method
    name = "req_data"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    @timer(logger.debug)
    @key_except('domain', 'name', ignore=True, msg="ignoring current exporter by default.")
    def export(cls, data) -> None:
        if 'csv' not in cls.args.format and 'db' not in cls.args.format:
            return
        df = data.get('tx_data_df')
        if df is None:
            logger.error("cannot find service prof data, please check")
            return

        if 'rid' not in df.columns:
            logger.warning("Exporter request will skip, the columns rid is missing")
            return

        if check_domain_valid(df, ['Request', 'Engine'], 'request') is False:
            return

        output = cls.args.output_path

        df = df[~df['domain'].isin(['KVCache', 'PullKVCache'])]
        df = df[~df['name'].isin(['forward'])]
        ttft_df = data.get("req_ttft_df", pd.DataFrame())  # ttft的单位是微秒，需要转换为毫秒
        ttft_df['ttft'] = ttft_df['ttft'].div(US_PER_MS)

        que_wait_df = data.get("req_que_wait_df", pd.DataFrame())  # que_wait_df的单位是微秒，需要转换为毫秒
        que_wait_df['que_wait_time'] = que_wait_df['que_wait_time'].div(US_PER_MS)

        req_base = get_req_base_info(df)
        req_base_info = safe_merge_ttft_que(req_base, ttft_df, que_wait_df)

        if 'cache_hit_rate' in req_base_info.columns:
            # 将空字符串或NaN替换为 'N/A'
            req_base_info['cache_hit_rate'] = req_base_info['cache_hit_rate'].replace('', 'N/A').fillna('N/A')

        required_colunms = [
            'rid',
            'start_datetime',
            'recvTokenSize=',
            'replyTokenSize=',
            'execution_time',
            'que_wait_time',
            'ttft',
            'cache_hit_rate',
            'start_time',
        ]
        filtered_df = req_base_info.reindex(columns=required_colunms)

        # 将可能混有 '' 与数值的列转为数值，避免 sort_values / .eq(0) 时 Float64 与 Str 比较触发 ufunc 错误
        numeric_cols = ['start_time', 'recvTokenSize=', 'replyTokenSize=', 'execution_time']
        for col in numeric_cols:
            if col in filtered_df.columns:
                filtered_df[col] = pd.to_numeric(filtered_df[col], errors='coerce')

        check_columns = ['recvTokenSize=', 'replyTokenSize=', 'execution_time']

        if filtered_df[check_columns].eq(0).all().all() or filtered_df[check_columns].isna().all().all():
            logger.warning(
                "The data is not complete for request.csv, "
                "prof data recv request or reply request was not captured. please check."
            )
            return

        # 数据完整性检查之后，重命名之前添加排序逻辑
        start_time_sort_key = pd.to_numeric(filtered_df['start_time'], errors='coerce')
        invalid_start_time_count = start_time_sort_key.isna().sum()
        if invalid_start_time_count > 0:
            logger.debug(
                "ExporterReqData: %s rows have invalid start_time values and will be sorted last.",
                invalid_start_time_count,
            )

        filtered_df = (
            filtered_df.assign(_start_time_sort_key=start_time_sort_key)
            .sort_values(by='_start_time_sort_key', na_position='last', kind='stable')
            .drop(columns=['_start_time_sort_key'])
            .reset_index(drop=True)
        )

        filtered_df = filtered_df.rename(
            columns={
                'rid': 'http_rid',
                'start_time': 'start_time(ms)',
                'recvTokenSize=': 'recv_token_size',
                'replyTokenSize=': 'reply_token_size',
                'ttft': 'first_token_latency',
                'que_wait_time': 'queue_wait_time',
            }
        )

        if 'db' in cls.args.format:
            db_cache_hit = filtered_df['cache_hit_rate'].replace('N/A', None)
            write_result_to_db(CREATE_REQUEST_TABLE_CONFIG, filtered_df.assign(cache_hit_rate=db_cache_hit))

        if 'csv' in cls.args.format:
            write_result_to_csv(filtered_df, output, "request", REQUEST_DATA_RENAME_COLS)


REQUEST_DATA_RENAME_COLS = {
    'start_datetime': 'start_datetime',
    'execution_time': 'execution_time(ms)',
    'queue_wait_time': 'queue_wait_time(ms)',
    'first_token_latency': 'first_token_latency(ms)',  # nosec B105
    'cache_hit_rate': 'cache_hit_rate',
}

CREATE_REQUEST_TABLE_CONFIG = TableConfig(
    table_name="request",
    create_view=True,
    view_name="request_data",
    view_rename_cols=REQUEST_DATA_RENAME_COLS,
    description={
        "en": "Servitized Inference Request-Level Metrics: Time to First Token (TTFT), Input/Output Length, etc",
        "zh": "以服务化推理请求为粒度的详细数据指标，包括TTFT，请求的输入输出长度等信息",
    },
)
