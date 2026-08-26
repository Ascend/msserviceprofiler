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
from ms_service_profiler.exporters.utils import write_result_to_csv, write_result_to_db, check_domain_valid, TableConfig
from ms_service_profiler.constant import US_PER_MS
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer


REQUIED_NAME = set(["forward"])
FORWARD_REMAME_COLUMNS = {
    "start_time": "start_time(ms)",
    "end_time": "end_time(ms)",
    "during_time": "during_time(ms)",
    "relative_start_time": "relative_start_time(ms)",
    "bubble_time": "bubble_time(ms)",
}
DELETE_COLUMNS = ["rid", "rid_list", "pid", "tid"]


class ExporterForwardData(ExporterBase):  # pylint: disable=abstract-method
    name = "forward_data"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    @timer(logger.debug)
    def export(cls, data) -> None:
        if "csv" not in cls.args.format and "db" not in cls.args.format:
            return

        df = data.get("tx_data_df")
        if df is None:
            logger.warning("There is no service prof data, froward data will not be generated. please check")
            return
        output = cls.args.output_path

        if not check_domain_valid(df, ["ModelExecute", "BatchSchedule", "Schedule"], "forward"):
            return
        # 取出 forward 和 batch_start_name
        batch_name = get_batch_name(df)
        REQUIED_NAME.add(batch_name)
        check_all = all(element in df["name"].unique() for element in REQUIED_NAME)
        if not check_all:
            warning_msg = (
                f"The data is not complete, froward data will not be generated. please check. "
                f"The required data for forward.csv is {REQUIED_NAME}"
            )
            logger.warning(warning_msg)
            return

        forward_df = get_filter_forward_df(REQUIED_NAME, df)

        # 获取batch_type 和 batch_size
        forward_df = get_batch_info(forward_df, batch_name)

        # 计算 relative_time, bubble_time
        if forward_df.empty:
            logger.warning(
                "Skip forward export because no rows remain after batch/rid matching. "
                "This is currently an expected/known limitation in vllm scenarios and can be ignored."
            )
            return
        forward_df = get_relative_and_bubble(forward_df)

        forward_df = forward_df.drop(columns=DELETE_COLUMNS)
        forward_df["forward_iter"] = forward_df.groupby("prof_id").cumcount() + 1
        forward_df = forward_df.sort_values(by=["start_time"]).reset_index(drop=True)

        if 'start_time' in forward_df.columns and 'end_time' in forward_df.columns:
            forward_df['start_time'] = forward_df['start_time']
            forward_df['end_time'] = forward_df['end_time']

        data_link_df = pd.DataFrame({'source_name': ['rid'], 'target_table': ['request'], 'target_name': ['http_rid']})

        if 'db' in cls.args.format:
            write_result_to_db(CREATE_FORWARD_TABLE_CONFIG, forward_df)
            write_result_to_db(TableConfig(table_name="data_link"), data_link_df)

        if 'csv' in cls.args.format:
            write_result_to_csv(forward_df, output, "forward", FORWARD_REMAME_COLUMNS)


# 按 hostname 分组，并计算每个分组的相对时间
def calculate_relative_times(group):
    base_time = group["start_time"].min()  # 以每个分组中的最小 start_time 为基准时间
    group["relative_start_time"] = (group["start_time"] - base_time).round(2)
    return group


def calculate_bubble_time(group):
    group["bubble_time"] = (group["start_time"].shift(-1) - group["end_time"]).round(2)
    return group


def get_batch_name(dataframe):
    if (dataframe["name"] == "BatchSchedule").any():
        return "BatchSchedule"
    return "batchFrameworkProcessing"


def get_filter_forward_df(required_name, forward_df):
    mask = forward_df["name"].isin(required_name)

    ori_columns = [
        "name",
        "relative_start_time",
        "start_datetime",
        "end_datetime",
        "during_time",
        "bubble_time",
        "batch_size",
        "batch_type",
        "forward_iter",
        "rid",
        "rid_list",
        "dp_rank",
        "prof_id",
        "hostname",
        "pid",
        "tid",
        "start_time",
        "end_time",
    ]

    missing_columns = set(ori_columns) - set(forward_df.columns)
    for col in missing_columns:
        forward_df.loc[mask, col] = None
    convert_time_cols = ["during_time", "start_time", "end_time"]
    forward_df[convert_time_cols] = forward_df[convert_time_cols].astype(float)
    forward_df.loc[mask, convert_time_cols] = forward_df.loc[mask, convert_time_cols].div(US_PER_MS)

    forward_df = forward_df.reindex(columns=ori_columns)

    return forward_df[mask]


def get_batch_info(forward_df, batch_name):
    if forward_df[["batch_type", "batch_size"]].notna().all().all():
        return forward_df[forward_df["name"] != batch_name]
    # 按rid分组forward_df
    forward_df_grouped = forward_df.groupby("rid")

    result = []

    # 遍历每组rid
    for _, group in forward_df_grouped:
        temp_result = group.copy()
        batch_name_indices = group[group["name"] == batch_name].index
        if len(batch_name_indices) == 0:
            continue

        for idx in batch_name_indices:
            temp_result.loc[(temp_result.index > idx), "batch_type"] = group.loc[idx, "batch_type"]

        # 将处理后的组添加到最终结果中
        result.append(temp_result)

    merged = pd.concat(result, ignore_index=True)
    mask = merged["name"] != batch_name
    merged = merged[mask].sort_values(by=["start_time"]).reset_index(drop=True)

    return merged


def get_relative_and_bubble(forward_df):
    forward_df = forward_df.copy()
    forward_df["relative_start_time"] = (
        forward_df["start_time"] - forward_df.groupby("hostname")["start_time"].transform("min")
    ).round(2)
    # 计算 bubble_time
    forward_df["bubble_time"] = (forward_df.groupby("prof_id")["start_time"].shift(-1) - forward_df["end_time"]).round(
        2
    )
    mask = forward_df.groupby("prof_id").cumcount(ascending=False) == 0
    forward_df.loc[mask, "bubble_time"] = pd.NA

    return forward_df


CREATE_FORWARD_TABLE_CONFIG = TableConfig(
    table_name="forward",
    create_view=True,
    view_name="forward_info",
    view_rename_cols=FORWARD_REMAME_COLUMNS,
    description={
        "en": "Detailed data for the forward execution during servitized inference",
        "zh": "服务化推理模型前向执行过程的详细数据",
    },
)
