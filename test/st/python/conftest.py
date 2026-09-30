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
import shutil
import sys
import uuid

import pytest

try:
    from pytest_check import check_functions

    pytest.assume = check_functions.is_true
except ImportError:

    def _assume(condition, message="assumption failed"):
        assert condition, message

    pytest.assume = _assume

ST_PYTHON_DIR = os.path.dirname(os.path.abspath(__file__))
if ST_PYTHON_DIR not in sys.path:
    sys.path.insert(0, ST_PYTHON_DIR)


def pytest_addoption(parser):
    parser.addoption("--device", action="append", type=int, default=[], help="devices")
    parser.addoption(
        "--mindie-path",
        action="store",
        default="/usr/local/lib/python3.11/site-packages/mindie_llm/",
        help="mindie path",
    )
    parser.addoption("--dataset-path", action="store", default="/dataset", help="dataset path")
    parser.addoption("--model-path", action="store", default="/model", help="model path")
    parser.addoption(
        "--sglang-port",
        action="store",
        type=int,
        default=None,
        help="SGLang server port (default: auto 7399+pid%%10000 for concurrent runs)",
    )
    parser.addoption("--workspace", action="store", default="/workspace", help="workspace path")
    parser.addoption("--debug-mode", action="store", type=bool, default=False, help="debug")
    parser.addoption(
        "--metric-source",
        action="store",
        default="https://gitcode.com/Ascend/msserviceprofiler.git",
        help="ms_service_metric source: git URL, repo path, package path, whl path, or 'installed'",
    )
    parser.addoption(
        "--metric-scenario",
        action="store",
        default="basic",
        help="Metric ST scenario: basic, eplb, dplb, or exception",
    )
    parser.addoption("--metric-ref", action="store", default="master", help="git ref for --metric-source")
    parser.addoption(
        "--metric-install-mode",
        action="store",
        choices=["editable", "installed"],
        default="editable",
        help="How to install ms_service_metric before metric ST",
    )
    parser.addoption("--metric-service-port", action="store", type=int, default=None, help="vLLM port for metric ST")
    parser.addoption(
        "--metric-skip-npu-busy-check",
        action="store_true",
        default=False,
        help="Skip NPU busy preflight checks for metric ST",
    )
    parser.addoption(
        "--metric-npu-memory-threshold",
        action="store",
        type=int,
        default=90,
        help="Fail metric ST preflight when NPU HBM usage rate is at or above this value",
    )
    parser.addoption(
        "--vllm-extra-arg",
        action="append",
        default=[],
        help="Append an advanced vLLM argument to the metric ST service command",
    )
    parser.addoption(
        "--metric-request-count",
        action="store",
        type=int,
        default=1,
        help="Number of completion requests sent by the metric ST scenario",
    )
    parser.addoption("--metric-poll-timeout", action="store", type=float, default=None)
    parser.addoption("--metric-poll-interval", action="store", type=float, default=1.0)
    parser.addoption("--eplb-heat-collection-interval", action="store", type=int, default=4)
    parser.addoption("--eplb-algorithm-execution-interval", action="store", type=int, default=1)
    parser.addoption("--eplb-policy-type", action="store", type=int, default=2)
    parser.addoption("--eplb-num-redundant-experts", action="store", type=int, default=4)
    parser.addoption("--eplb-max-model-len", action="store", type=int, default=4096)


@pytest.fixture(scope="session")
def devices(request):
    devices = request.config.getoption("--device")
    return devices if devices else [0]


@pytest.fixture(scope="session")
def mindie_path(request):
    return request.config.getoption("--mindie-path")


@pytest.fixture(scope="session")
def dataset_path(request):
    return request.config.getoption("--dataset-path")


@pytest.fixture(scope="session")
def model_path(request):
    return request.config.getoption("--model-path")


@pytest.fixture(scope="session")
def sglang_port(request):
    port = request.config.getoption("--sglang-port")
    if port is not None:
        return port
    # 多人并发时避免端口冲突：7399 + pid % 10000
    return 7399 + (os.getpid() % 10000)


@pytest.fixture(scope="session")
def workspace(request):
    workspace_path = request.config.getoption("--workspace")
    os.makedirs(workspace_path, exist_ok=True)
    return workspace_path


@pytest.fixture(scope="session")
def smokedata(workspace):
    return os.path.join(workspace, "smokedata")


@pytest.fixture(scope="session")
def debug(request):
    return request.config.getoption("--debug-mode")


@pytest.fixture(scope="session")
def metric_source(request):
    return request.config.getoption("--metric-source")


@pytest.fixture(scope="session")
def metric_scenario(request):
    return request.config.getoption("--metric-scenario")


@pytest.fixture(scope="session")
def metric_ref(request):
    return request.config.getoption("--metric-ref")


@pytest.fixture(scope="session")
def metric_install_mode(request):
    return request.config.getoption("--metric-install-mode")


@pytest.fixture(scope="session")
def metric_service_port(request):
    return request.config.getoption("--metric-service-port")


@pytest.fixture(scope="session")
def metric_skip_npu_busy_check(request):
    return request.config.getoption("--metric-skip-npu-busy-check")


@pytest.fixture(scope="session")
def metric_npu_memory_threshold(request):
    return request.config.getoption("--metric-npu-memory-threshold")


@pytest.fixture(scope="session")
def vllm_extra_args(request):
    return request.config.getoption("--vllm-extra-arg")


@pytest.fixture(scope="session")
def metric_request_count(request):
    return request.config.getoption("--metric-request-count")


@pytest.fixture(scope="session")
def metric_poll_timeout(request):
    return request.config.getoption("--metric-poll-timeout")


@pytest.fixture(scope="session")
def metric_poll_interval(request):
    return request.config.getoption("--metric-poll-interval")


@pytest.fixture(scope="session")
def metric_scenario_options(request):
    return {
        "eplb_heat_collection_interval": request.config.getoption("--eplb-heat-collection-interval"),
        "eplb_algorithm_execution_interval": request.config.getoption("--eplb-algorithm-execution-interval"),
        "eplb_policy_type": request.config.getoption("--eplb-policy-type"),
        "eplb_num_redundant_experts": request.config.getoption("--eplb-num-redundant-experts"),
        "eplb_max_model_len": request.config.getoption("--eplb-max-model-len"),
    }


@pytest.fixture(scope="function")
def tmp_workspace(debug):
    index = str(uuid.uuid4())
    workspace_path = os.path.join("/tmp/server-smoke", index)
    os.makedirs(workspace_path, exist_ok=True)
    yield workspace_path
    if not debug:
        shutil.rmtree(workspace_path, ignore_errors=True)
    else:
        print("tmp workspace is ", workspace_path)


@pytest.fixture(scope="session")
def smoke_args(devices, mindie_path, dataset_path, model_path, workspace, smokedata, debug):
    return dict(
        devices=devices,
        mindie_path=mindie_path,
        dataset_path=dataset_path,
        model_path=model_path,
        smokedata=smokedata,
        workspace=workspace,
        debug=debug,
    )
