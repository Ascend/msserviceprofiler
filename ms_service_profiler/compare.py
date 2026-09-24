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
import re
import argparse
import shlex
import subprocess  # nosec B404
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple

from ms_service_profiler.data_source.db_data_source import DBDataSource
from ms_service_profiler.exporters.utils import save_dataframe_to_csv, check_input_dir_valid, check_output_path_valid
from ms_service_profiler.utils.log import set_log_level, logger


def _find_ascend_pt_dirs(parent_dir: str) -> List[str]:
    """
    扫描指定目录，返回所有以 'ascend_pt' 结尾的子目录路径。
    用于定位性能分析数据根目录。
    """
    if not os.path.isdir(parent_dir):
        return []
    ascend_pt_dirs = []
    try:
        # 遍历 parent_dir 下的所有条目
        for item in os.listdir(parent_dir):
            full_path = os.path.join(parent_dir, item)
            # 仅保留是目录且名称以 'ascend_pt' 结尾的项
            if os.path.isdir(full_path) and item.endswith('ascend_pt'):
                ascend_pt_dirs.append(full_path)
    except OSError as err:
        logger.warning("Failed to list %s: %s", parent_dir, err)
    return sorted(ascend_pt_dirs)


def _extract_prof_number(prof_name: str) -> int:
    """
    从 PROF_XXX_... 格式的目录名中提取数字编号。
    若无法匹配，返回无穷大（用于排序时排到最后）。
    """
    match = re.search(r'PROF_(\d+)_', prof_name)
    return int(match.group(1)) if match else float('inf')


def _scan_ascend_pt_devices(pt_dir: str) -> Dict[int, Tuple[int, str]]:
    device_map = {}
    for item in os.listdir(pt_dir):
        prof_path = os.path.join(pt_dir, item)
        if not (item.startswith('PROF_') and os.path.isdir(prof_path)):
            continue

        prof_num = _extract_prof_number(item)
        for dev_item in os.listdir(prof_path):
            if not (dev_item.startswith('device_') and dev_item[7:].isdigit()):
                continue
            dev_num = int(dev_item[7:])
            if dev_num not in device_map or prof_num < device_map[dev_num][0]:
                device_map[dev_num] = (prof_num, pt_dir)
    return device_map


def extract_device_to_ascend_pt_map(root_dir: str) -> Dict[int, str]:
    """
    构建 device_id 到 ascend_pt 路径的映射。
    规则：对每个 device_id，选择 PROF 编号最小的 profile 对应的 ascend_pt 路径。
    """
    device_map = {}
    ascend_pt_dirs = _find_ascend_pt_dirs(root_dir)

    # 遍历每个 ascend_pt 目录（如 xxx/ascend_pt）
    for pt_dir in ascend_pt_dirs:
        try:
            device_map.update(_scan_ascend_pt_devices(pt_dir))
        except OSError as err:
            logger.warning("Error scanning %s: %s", pt_dir, err)
            continue

    # 返回最终映射：device_id -> ascend_pt 路径
    return {dev: pt for dev, (_, pt) in device_map.items()}


def match_ascend_pt_paths_by_device(input_root: str, golden_root: str) -> Tuple[str, str]:
    """
    智能匹配 input 与 golden 的 ascend_pt 路径，用于后续算子比对。
    匹配策略：
      1. 优先按相同 device_id 精确匹配；
      2. 若无重合设备，则降级使用各自最小 device_id 对应的路径；
      3. 若某方无任何有效结构，则回退到取第一个 ascend_pt 目录（或空）。
    返回 (input_ascend_pt_path, golden_ascend_pt_path)
    """
    input_map = extract_device_to_ascend_pt_map(input_root)
    golden_map = extract_device_to_ascend_pt_map(golden_root)

    # 若 golden 无任何 device 映射，直接回退到目录级匹配
    if not golden_map:
        golden_pts = _find_ascend_pt_dirs(golden_root)
        golden_pt = golden_pts[0] if golden_pts else ""
        input_pts = _find_ascend_pt_dirs(input_root)
        input_pt = input_pts[0] if input_pts else ""
        return input_pt, golden_pt

    # 尝试按 device_id 精确匹配（以 golden 为基准）
    for dev_num in sorted(golden_map.keys()):
        if dev_num in input_map:
            return input_map[dev_num], golden_map[dev_num]

    # 降级策略：golden 取最小 device_id，input 取最小 device_id（若存在），否则取第一个目录
    min_golden_dev = min(golden_map.keys())
    golden_pt = golden_map[min_golden_dev]
    if input_map:
        min_input_dev = min(input_map.keys())
        input_pt = input_map[min_input_dev]
    else:
        input_pts = _find_ascend_pt_dirs(input_root)
        input_pt = input_pts[0] if input_pts else ""
    return input_pt, golden_pt


def read_sql_from_given_path(given_path: str) -> pd.DataFrame:
    """
    从给定路径的 Trace_Service/*.db 中读取 tx_data_df 表数据，并合并所有 DB 文件内容。
    返回一个包含所有 span 记录的 DataFrame。
    """
    trace_service_dir = os.path.join(given_path, "Trace_Service")
    if not os.path.isdir(trace_service_dir):
        logger.error("'Trace_Service' directory not found in: %s", given_path)
        return pd.DataFrame()

    profiler_inputs = []
    # 遍历 Trace_Service 目录下的所有 .db 文件
    for file in os.listdir(trace_service_dir):
        if file.endswith('.db'):
            db_path = os.path.join(trace_service_dir, file)
            try:
                # 使用 DBDataSource 解析数据库
                data_dict = DBDataSource.process(db_path)
                df = data_dict.get('tx_data_df')
                if isinstance(df, pd.DataFrame) and not df.empty:
                    profiler_inputs.append(df)
            except Exception as err:
                logger.warning("Failed to process %s: %s", db_path, err)

    # 若未加载任何有效数据，记录错误
    if not profiler_inputs:
        logger.error("No valid .db data found in Trace_Service directory: %s", trace_service_dir)
        return pd.DataFrame()

    # 合并所有 DataFrame（纵向拼接）
    return pd.concat(profiler_inputs, axis=0, ignore_index=True)


def validate_and_clean_df(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """
    验证并清洗输入的 DataFrame：
      - 检查是否为空；
      - 检查是否包含必需列 'name'；
      - 剔除 'name' 为空的行。
    """
    if df.empty:
        logger.error("%s data is empty.", source_name)
        return pd.DataFrame()
    if 'name' not in df.columns:
        logger.error("Column 'name' not found in %s data.", source_name)
        return pd.DataFrame()
    cleaned = df.dropna(subset=['name']).reset_index(drop=True)
    logger.info("%s: loaded %d valid records.", source_name, len(cleaned))
    return cleaned


def compute_stats(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """
    对 span 数据按算子名（name）分组，计算耗时统计指标（AVG/P50/P90）。
    label 用于标识数据来源，如 'Input' 或 'Golden'。
    返回以 'name' 为索引的统计 DataFrame。
    """
    stats = df.groupby('name')['during_time'].agg(
        [('AVG', 'mean'), ('P50', lambda x: x.quantile(0.5)), ('P90', lambda x: x.quantile(0.9))]
    )
    # 重命名列为 Input-AVG / Golden-P90 等格式
    stats.columns = [f"{label}-{col}" for col in stats.columns]
    return stats


def compute_comparison(input_stats, golden_stats):
    """
    执行 Input 与 Golden 的 span 性能比对，生成包含绝对差值和相对变化率的报表。

    计算规则：
      - DIFF = Input - Golden
      - RDIFF = (Input - Golden) / Golden （若 Golden == 0，则 RDIFF = NaN）
      - RDIFF 以百分比形式输出（×100），保留两位小数

    过滤规则：
      - 剔除 Input 和 Golden 所有指标（AVG/P50/P90）均为 0 或 NaN 的无效行。

    列顺序：name, Golden-*, Input-*, DIFF-*, RDIFF-*
    """
    stat_cols = ['AVG', 'P50', 'P90']
    input_cols = [f"Input-{s}" for s in stat_cols]
    golden_cols = [f"Golden-{s}" for s in stat_cols]
    diff_cols = [f"DIFF-{s}" for s in stat_cols]
    rdiff_cols = [f"RDIFF-{s}(%)" for s in stat_cols]

    expected_columns = ['name'] + golden_cols + input_cols + diff_cols + rdiff_cols

    # 处理空输入情况：用全 NaN 占位以保持结构一致
    if input_stats.empty and golden_stats.empty:
        return pd.DataFrame(columns=expected_columns)

    if input_stats.empty:
        input_stats = pd.DataFrame({col: pd.Series(dtype='float64') for col in input_cols})
        input_stats.index.name = 'name'
    if golden_stats.empty:
        golden_stats = pd.DataFrame({col: pd.Series(dtype='float64') for col in golden_cols})
        golden_stats.index.name = 'name'

    # 外连接合并 Golden 和 Input 数据（按算子名）
    merged = golden_stats.join(input_stats, how='outer')
    for col in golden_cols + input_cols:
        if col not in merged.columns:
            merged[col] = np.nan

    # 计算差异指标：遍历 AVG/P50/P90 三类统计量
    for stat in stat_cols:
        inp_col = f"Input-{stat}"
        gold_col = f"Golden-{stat}"
        diff_col = f"DIFF-{stat}"
        rdiff_col = f"RDIFF-{stat}(%)"

        # 绝对差值：Input - Golden
        merged[diff_col] = merged[inp_col] - merged[gold_col]

        # 相对变化率：(Input - Golden) / Golden → 转换为百分比
        numerator = merged[diff_col]
        denominator = merged[gold_col]
        # 仅当 Golden ≠ 0 且 Input/Golden 均非空时计算有效 RDIFF
        valid = (denominator != 0) & denominator.notna() & merged[inp_col].notna()
        rdiff_val = np.where(valid, numerator / denominator, np.nan)
        merged[rdiff_col] = rdiff_val * 100  # 转百分比

    # 将 'name' 从索引转为普通列
    result = merged.reset_index()

    # 补全可能缺失的列（防御性编程）
    for col in expected_columns:
        if col not in result.columns:
            result[col] = np.nan
    result = result[expected_columns].copy()

    # === 过滤无效行：剔除 Input 和 Golden 所有指标均为 0 或 NaN 的记录 ===
    def is_all_zero_or_nan(row):
        all_vals = []
        # 收集所有非 NaN 的数值
        for col in golden_cols + input_cols:
            val = row[col]
            if pd.notna(val):
                all_vals.append(val)
        # 若无有效数值，或所有有效数值都是 0，则视为无效行
        if not all_vals:
            return True
        return all(v == 0.0 for v in all_vals)

    # 应用过滤：仅保留至少有一个非零有效值的行
    mask = ~result.apply(is_all_zero_or_nan, axis=1)
    result = result[mask].copy().reset_index(drop=True)

    # === 数值精度统一处理 ===
    # RDIFF 列（百分比）保留 2 位小数
    rdiff_cols_exist = [col for col in result.columns if col.startswith('RDIFF-')]
    result[rdiff_cols_exist] = result[rdiff_cols_exist].round(2)

    # 其他浮点列（Golden/Input/DIFF）也统一保留 2 位小数
    other_float_cols = [col for col in result.columns if col != 'name' and not col.startswith('RDIFF-')]
    result[other_float_cols] = result[other_float_cols].round(2)

    return result


def arg_parse(subparsers):
    """
    解析命令行参数。
    支持 input_path、golden_path、output-path 和 log-level。
    """
    parser = subparsers.add_parser(
        "compare", formatter_class=argparse.ArgumentDefaultsHelpFormatter, help="Compare performance profiles"
    )
    parser.add_argument("input_path", type=check_input_dir_valid, help="Directory of input profile data")
    parser.add_argument("golden_path", type=check_input_dir_valid, help="Directory of golden profile data")
    parser.add_argument(
        "--output-path",
        type=check_output_path_valid,
        default=os.path.join(os.getcwd(), 'compare_result'),
        help="Output directory for comparison result",
    )
    parser.add_argument(
        '--log-level',
        choices=['debug', 'info', 'warning', 'error', 'fatal', 'critical'],
        default='info',
        help='Log level',
    )
    parser.set_defaults(func=main)


def main(args):
    """
    主函数：执行完整的性能比对流程。
    包含两个主要部分：
      1. 调用外部工具 msprof-analyze 进行算子级比对；
      2. 自定义 Span 级别比对（基于 Trace_Service 数据）。
    """
    set_log_level(args.log_level)

    # === Step 1: 智能匹配 input 与 golden 的 ascend_pt 路径 ===
    input_pt, golden_pt = match_ascend_pt_paths_by_device(args.input_path, args.golden_path)

    # === Step 2: 调用外部工具执行算子级性能比对（msprof-analyze compare）===
    # 说明：
    #   - 此功能由 MindStudio 内置工具 msprof-analyze 提供；
    #   - 用于比对算子执行时间、资源占用等详细指标；
    #   - 输入为两个符合 ascend_pt/PROF_*/device_* 结构的目录；
    #   - 输出 HTML/CSV 报告至 --output_path；
    #   - 若路径无效（如缺少 device 目录），则跳过此步骤并记录原因。
    if input_pt and golden_pt:
        normalized_input_pt = os.path.abspath(os.path.normpath(input_pt))
        normalized_golden_pt = os.path.abspath(os.path.normpath(golden_pt))
        normalized_output_path = os.path.abspath(os.path.normpath(args.output_path))
        cmd = [
            "msprof-analyze",
            "compare",
            "-d",
            normalized_input_pt,
            "-bp",
            normalized_golden_pt,
            "--output_path",
            normalized_output_path,
        ]
        # subprocess.run receives an argument list with shell=False, so path
        # values are not interpreted by a shell. shlex.quote is only for logs.
        logger.info("Executing operator comparison command: %s", ' '.join(shlex.quote(c) for c in cmd))
        subprocess.run(cmd, check=True)  # nosec B603
    else:
        missing_parts = []
        if not input_pt:
            missing_parts.append(
                f"input path '{args.input_path}' does not contain a valid 'ascend_pt' directory "
                f"(e.g., */ascend_pt/PROF_*/device_*/)"
            )
        if not golden_pt:
            missing_parts.append(
                f"golden path '{args.golden_path}' does not contain a valid 'ascend_pt' directory "
                f"(e.g., */ascend_pt/PROF_*/device_*/)"
            )

        reason = "; ".join(missing_parts) if missing_parts else "unknown reason"
        logger.info(
            "Skipping operator comparison: %s. Expected structure: <root>/ascend_pt/PROF_<num>_<suffix>/device_<id>/",
            reason,
        )

    # === Step 3: 自定义 Span 级别性能比对（基于 Trace_Service 中的 tx_data_df）===
    # 说明：
    #   - 读取 input/golden 路径下的 Trace_Service/*.db；
    #   - 按算子名聚合 during_time，计算 AVG/P50/P90；
    #   - 生成差异报告（含绝对差值和相对变化率）；
    #   - 结果保存为 span_comparation_result.csv。
    input_df = validate_and_clean_df(read_sql_from_given_path(args.input_path), "Input")
    if input_df.empty:
        return

    golden_df = validate_and_clean_df(read_sql_from_given_path(args.golden_path), "Golden")
    if golden_df.empty:
        return

    # 分别计算 Input 和 Golden 的统计指标
    input_stats = compute_stats(input_df, 'Input')
    golden_stats = compute_stats(golden_df, 'Golden')

    # 执行比对并生成结果表
    result_df = compute_comparison(input_stats, golden_stats)

    # 保存结果到 CSV
    save_dataframe_to_csv(result_df, args.output_path, 'span_comparation_result.csv')
    logger.info("Comparison finished. Results saved to %r", args.output_path)


if __name__ == '__main__':
    argument_parser = argparse.ArgumentParser()
    sub_parser = argument_parser.add_subparsers()
    arg_parse(sub_parser)
    parsed_args = argument_parser.parse_args()
    parsed_args.func(parsed_args)
