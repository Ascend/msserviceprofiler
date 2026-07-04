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

import pytest

from executor.exec_sglang_server import ExecSGLangServer
from executor.exec_parse import ExecParse
from checker.sglang_prof_checker import check_prof_data_contains_sglang_points
from checker.csv_checker import check_req_csv, check_batch_csv, check_kvcache_csv
from checker.table_checker import db_connect, check_sglang_db_tables
from checker.trace_checker import check_chrome_tracing


@pytest.fixture(autouse=True)
def skip_if_no_sglang():
    """SGLang 未安装时跳过测试"""
    pytest.importorskip("sglang")


def test_sglang_example(model_path, sglang_port, tmp_workspace):
    '''
    SGLang 场景下基础采集测试
    校验内容包括：
        1、服务能否正常启动并采集
        2、curl 请求能否成功
        3、解析结果是否正常（request/batch/kvcache csv 及 profiler.db）
    执行前需：
        1. 在 Docker 中运行
        2. 执行 bash scripts/build_and_upgrade.sh 完成升级
        3. 传入 --model-path 指定模型路径，如 /data/Qwen2.5-0.5B-Instruct
    '''
    sglang_server = None
    try:
        workspace_path = tmp_workspace

        sglang_server = ExecSGLangServer(workspace_path)
        sglang_server.set_model_path(model_path)
        sglang_server.set_port(sglang_port)
        assert sglang_server.ready_go(), "SGLang 服务启动失败"

        assert sglang_server.curl_test(), "SGLang curl 测试失败"

        # 等待 profiler 将末端点位（含 allocate 等）落盘后再关闭采集，并发时适当延长
        time.sleep(8)
        sglang_server.set_prof_config(enable=0)
        sglang_server.kill()

        prof_data_dir = os.path.join(workspace_path, "prof_data")
        ok, missing = check_prof_data_contains_sglang_points(prof_data_dir)
        assert ok, (
            f"prof_data 目录下缺少以下 SGLang 数据点位（grep 未匹配）: {missing}. 请确认 ms_service_profiler 采集正常。"
        )

        parser = ExecParse()
        parser.set_input_path(os.path.join(workspace_path, "prof_data"))
        parser.set_output_path(os.path.join(workspace_path, "prof_data_out"))
        assert parser.ready_go(), "解析失败"

        output_path = os.path.join(workspace_path, "prof_data_out")
        assert not os.path.exists(os.path.join(output_path, "request_status.csv")), (
            "SGLang 解析输出不应包含 request_status.csv"
        )
        check_req_csv(output_path, complete_req_cnt=2)  # warmup一条，curl一条
        check_batch_csv(output_path)
        check_kvcache_csv(output_path, complete_req_cnt=2)
        check_chrome_tracing(output_path)

        with db_connect(os.path.join(output_path, "profiler.db")) as conn:
            check_sglang_db_tables(conn, complete_req_cnt=2)

    finally:
        if sglang_server:
            sglang_server.kill()
        print("workspace:", tmp_workspace)
