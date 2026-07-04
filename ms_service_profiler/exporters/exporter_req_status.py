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
import numpy as np

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.plugins.plugin_req_status import ReqStatus
from ms_service_profiler.exporters.utils import (
    write_result_to_db,
    check_domain_valid,
    TableConfig,
    CurveViewConfig,
    check_columns_valid,
    save_dataframe_to_csv,
    ColumnConst,
)
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.error import key_except


class ExporterReqStatus(ExporterBase):
    name = "req_status"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    @timer(logger.debug)
    @key_except(
        ColumnConst.DOMAIN_COLUMN,
        ColumnConst.NAME_COLUMN,
        ignore=True,
        msg="ignoring current exporter by default.",
    )
    def export(cls, data) -> None:
        if 'db' not in cls.args.format and 'csv' not in cls.args.format:
            return

        if 'csv' in cls.args.format and cls.valid_for_csv_output(data) and not cls._is_sglang_profile_data(data):
            df = data.get('tx_data_df')
            if ColumnConst.STATUS_COLUMN in df.columns:
                state_col = ColumnConst.STATUS_COLUMN
                state_values = ['waiting', 'running', 'swapped']
            else:
                state_col = ColumnConst.SCOPE_QUEUE_NAME_COLUMN
                state_values = ['WAITING', 'RUNNING', 'SWAPPED']

            queue_name_mask = (
                df[ColumnConst.SCOPE_QUEUE_NAME_COLUMN].isin(['WAITING', 'RUNNING', 'SWAPPED', 'PENDING'])
                if ColumnConst.SCOPE_QUEUE_NAME_COLUMN in df.columns
                else False
            )
            queue_mask = (df[ColumnConst.DOMAIN_COLUMN] == 'Schedule') & (
                (df[ColumnConst.NAME_COLUMN] == 'Queue') | queue_name_mask
            )
            need_columns = [
                ColumnConst.HOSTUID_COLUMN,
                ColumnConst.PID_COLUMN,
                ColumnConst.START_TIME_COLUMN,
                ColumnConst.DOMAIN_COLUMN,
                ColumnConst.NAME_COLUMN,
                state_col,
                ColumnConst.QUEUESIZE_COLUMN,
                ColumnConst.START_DATETIME_COLUMN,
            ]
            mask = queue_mask & (df[state_col].isin(state_values))
            df = df.loc[mask, need_columns]
            df['waiting'] = np.where(df[state_col] == state_values[0], df[ColumnConst.QUEUESIZE_COLUMN], None)
            df['running'] = np.where(df[state_col] == state_values[1], df[ColumnConst.QUEUESIZE_COLUMN], None)
            df['swapped'] = np.where(df[state_col] == state_values[2], df[ColumnConst.QUEUESIZE_COLUMN], None)

            # 增加timestamp(ms)列
            df[ColumnConst.TIMESTAMP_MS_COLUMN] = (df[ColumnConst.START_TIME_COLUMN] / 1000.0).round(2)

            # 改为使用真实时间
            df[ColumnConst.START_DATETIME_COLUMN] = df[ColumnConst.START_DATETIME_COLUMN]

            # 增加relative_timestamp(ms)列
            df[ColumnConst.RELATIVE_TIMESTAMP_MS_COLUMN] = df.groupby(ColumnConst.PID_COLUMN)[
                ColumnConst.TIMESTAMP_MS_COLUMN
            ].transform(lambda x: (x - x.min()).round(2))

            desired_columns = [
                ColumnConst.HOSTUID_COLUMN,
                ColumnConst.PID_COLUMN,
                ColumnConst.START_DATETIME_COLUMN,
                ColumnConst.RELATIVE_TIMESTAMP_MS_COLUMN,
                'waiting',
                'running',
                'swapped',
                ColumnConst.TIMESTAMP_MS_COLUMN,
            ]
            df = df[desired_columns]

            output = cls.args.output_path
            logger.info("Start save data to csv")
            save_dataframe_to_csv(df, output, "request_status.csv")
            logger.info('Write request status data to csv success')

        if 'db' in cls.args.format and cls.valid_for_db_output(data):
            df = data.get('tx_data_df')
            metrics = data.get('metric_data_df')

            # 处理 status 列的映射和编码
            tx_columns = df.columns.tolist() if isinstance(df, pd.DataFrame) else []
            metric_columns = metrics.columns.tolist() if isinstance(metrics, pd.DataFrame) else []
            df = cls._process_status_columns(df, metrics)
            if df.empty:
                logger.warning(
                    "request_status db output is empty after _process_status_columns, tx_columns=%s, metric_columns=%s",
                    tx_columns,
                    metric_columns,
                )

            if 'QueueSize=' not in df.columns and ColumnConst.QUEUESIZE_COLUMN in df.columns:
                df['QueueSize='] = df[ColumnConst.QUEUESIZE_COLUMN]

            write_result_to_db(TableConfig(table_name="request_status"), df, CREATE_REQUEST_STATE_CURVE_VIEW_CONFIG)

    @classmethod
    def valid_for_csv_output(cls, data):
        df = data.get("tx_data_df")
        if df is None:
            logger.warning("There is no service prof data, request status data will not be generated. please check")
            return False

        need_columns = [
            ColumnConst.HOSTUID_COLUMN,
            ColumnConst.PID_COLUMN,
            ColumnConst.START_TIME_COLUMN,
            ColumnConst.DOMAIN_COLUMN,
            ColumnConst.NAME_COLUMN,
            ColumnConst.QUEUESIZE_COLUMN,
            ColumnConst.START_DATETIME_COLUMN,
        ]
        if not check_columns_valid(df, need_columns, cls.name):
            return False
        if ColumnConst.STATUS_COLUMN not in df.columns and ColumnConst.SCOPE_QUEUE_NAME_COLUMN not in df.columns:
            return False
        if not check_domain_valid(df, ['Schedule'], cls.name):
            return False
        return True

    @classmethod
    def _is_sglang_profile_data(cls, data):
        """SGLang docs do not list request_status.csv as a delivered CSV artifact."""
        df = data.get("tx_data_df")
        if df is None or ColumnConst.NAME_COLUMN not in df.columns:
            return False
        return (df[ColumnConst.NAME_COLUMN] == "recvReq").any()

    @classmethod
    def valid_for_db_output(cls, data):
        df = data.get("tx_data_df")
        if df is None:
            logger.warning("There is no service prof data, request status data will not be generated. please check")
            return False

        if not check_domain_valid(df, ['Request', 'Schedule'], 'request_status'):
            return False

        metrics = data.get('metric_data_df')
        if metrics is None:
            logger.warning("The req status prof data is empty, no request status data will generated. please check")
            return False

        return True

    @classmethod
    def _process_queue_status(cls, df, metrics):
        """
        专门处理队列状态数据，确保QueueSize=字段正确保留
        """
        # 筛选出domain为'Schedule'，name为'Queue'的记录
        mask = (df[ColumnConst.DOMAIN_COLUMN] == 'Schedule') & (df[ColumnConst.NAME_COLUMN] == 'Queue')
        queue_df = df.loc[mask].copy()

        # 如果找不到符合条件的记录，返回空DataFrame
        if queue_df.empty or not check_columns_valid(
            queue_df,
            [ColumnConst.START_DATETIME_COLUMN, ColumnConst.QUEUESIZE_COLUMN, ColumnConst.STATUS_COLUMN],
            cls.name,
        ):
            return pd.DataFrame()

        # 创建结果DataFrame
        result_df = pd.DataFrame()

        # 添加timestamp列
        result_df['timestamp'] = queue_df[ColumnConst.START_DATETIME_COLUMN]

        # 添加QueueSize=列
        result_df['QueueSize='] = queue_df[ColumnConst.QUEUESIZE_COLUMN]

        # 添加status列，并映射状态值
        status_mapping = {'waiting': 'WAITING', 'running': 'RUNNING', 'swapped': 'SWAPPED'}
        result_df['status'] = queue_df[ColumnConst.STATUS_COLUMN].map(status_mapping)

        return result_df

    @classmethod
    def _process_queue_columns(cls, df):
        need_columns = [
            ColumnConst.NAME_COLUMN,
            ColumnConst.START_DATETIME_COLUMN,
            ColumnConst.SCOPE_QUEUE_NAME_COLUMN,
            ColumnConst.QUEUESIZE_COLUMN,
        ]
        if not check_columns_valid(df, need_columns, cls.name):
            return pd.DataFrame()

        queue_mask = (df[ColumnConst.DOMAIN_COLUMN] == 'Schedule') & (
            (df[ColumnConst.NAME_COLUMN] == 'Queue')
            | (df[ColumnConst.SCOPE_QUEUE_NAME_COLUMN].isin(['WAITING', 'RUNNING', 'SWAPPED', 'PENDING']))
        )
        queue_df = df[queue_mask]
        df = queue_df.pivot_table(
            index='start_datetime', columns='scope#QueueName', values='QueueSize=', aggfunc='first'
        ).reset_index()

        # 检查并创建所需的列，如果不存在则填充为0
        required_columns = ['start_datetime', 'WAITING', 'RUNNING', 'PENDING']
        for col in required_columns:
            if col not in df.columns:
                df[col] = 0

        df = df[required_columns].rename(columns={'start_datetime': 'timestamp'})
        value_columns = ['WAITING', 'RUNNING', 'PENDING']
        df[value_columns] = df[value_columns].apply(pd.to_numeric, errors='coerce')
        return df

    @classmethod
    def _process_status_columns(cls, df, metrics):
        # 首先尝试使用新的队列状态处理逻辑
        queue_status_df = cls._process_queue_status(df, metrics)
        if not queue_status_df.empty:
            logger.debug("request_status db path: using queue_status schema")
            return queue_status_df

        # 如果新的逻辑没有返回数据，回退到原有逻辑
        if ColumnConst.STATUS_COLUMN in df.columns:
            logger.debug("request_status db path: using status column schema")
            df = cls._map_and_encode_status(df, metrics)
        elif check_columns_valid(df, [ColumnConst.SCOPE_QUEUE_NAME_COLUMN, ColumnConst.QUEUESIZE_COLUMN], cls.name):
            # vllm 数据解析特有处理逻辑，当前只有vllm数据会走到
            logger.debug("request_status db path: using scope#QueueName + QueueSize= schema")
            df = cls._process_queue_columns(df)
        else:
            logger.debug("request_status db path: falling back to metric_data_df schema")
            df = cls._prepare_metrics_df(df, metrics)
        return df

    @classmethod
    def _map_and_encode_status(cls, df, metrics):
        old_status_mapping = {
            'waiting': 'WAITING',
            'running': 'RUNNING',
        }

        # 保留原始数据中的 QueueSize= 字段
        if ColumnConst.QUEUESIZE_COLUMN in df.columns:
            df['QueueSize='] = df[ColumnConst.QUEUESIZE_COLUMN]

        # 将status列的值映射到旧版状态值
        df[ColumnConst.STATUS_COLUMN] = df[ColumnConst.STATUS_COLUMN].map(old_status_mapping)

        # 将status列转换为one-hot编码
        status_dummies = pd.get_dummies(df[ColumnConst.STATUS_COLUMN], prefix='', prefix_sep='')

        # 将one-hot编码的结果与原始数据合并
        result_df = pd.concat([df, status_dummies], axis=1)

        # 添加timestamp列
        result_df.insert(0, 'timestamp', metrics['start_datetime'])

        # 补全缺失的状态列，值为0
        for status in old_status_mapping.values():
            if status not in result_df.columns:
                result_df[status] = 0

        if 'PENDING' not in result_df.columns:
            result_df['PENDING'] = 0

        # 确保列的顺序正确
        result_df = result_df[['timestamp', 'QueueSize='] + list(old_status_mapping.values()) + ['PENDING']]

        return result_df

    @classmethod
    def _prepare_metrics_df(cls, df, metrics):
        req_status_cols = [col for col in metrics.columns if col in ReqStatus.__members__]
        df = metrics[req_status_cols].fillna(0).astype(int)
        df.insert(0, 'timestamp', metrics['start_datetime'])

        # 默认会从db文件中筛选下述列进行展示，如不存在该列需要补齐
        show_columns = [status.name for status in ReqStatus]

        for column_name in show_columns:
            if column_name not in df.columns:
                df = df.assign(**{column_name: [None] * len(df)})
        return df


REQUEST_STATE_VIEW_NAME = "Request_Status_curve"
CREATE_REQUEST_STATE_VIEW_SQL = """
    CREATE VIEW Request_Status_curve AS
    SELECT
        substr(timestamp, 1, 10) || ' ' || substr(timestamp, 12, 8) || '.' || substr(timestamp, 21, 6) AS time,
        CASE WHEN status = 'WAITING' THEN CAST("QueueSize=" AS REAL) ELSE CAST(0 AS REAL) END as waiting,
        CASE WHEN status = 'SWAPPED' THEN CAST("QueueSize=" AS REAL) ELSE CAST(0 AS REAL) END as swapped,
        CASE WHEN status = 'RUNNING' THEN CAST("QueueSize=" AS REAL) ELSE CAST(0 AS REAL) END as running
    FROM
        request_status
    WHERE
        "QueueSize=" IS NOT NULL
        AND (
            (status = 'WAITING' AND "QueueSize=" != 0.0) OR
            (status = 'SWAPPED' AND "QueueSize=" != 0.0) OR
            (status = 'RUNNING' AND "QueueSize=" != 0.0)
        )
    ORDER BY
        time ASC
"""
CREATE_REQUEST_STATE_CURVE_VIEW_CONFIG = CurveViewConfig(
    view_name=REQUEST_STATE_VIEW_NAME,
    sql=CREATE_REQUEST_STATE_VIEW_SQL,
    description={
        "en": "Queue Size Over Time by Status",
        "zh": "不同状态下队列大小随时间变化的折线图",
    },
)
