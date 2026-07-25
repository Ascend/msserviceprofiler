#!/bin/bash

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

# This script is used to run ut and st testcase.

set -eu

CUR_DIR=$(dirname $(readlink -f $0))
COV_DIR=${CUR_DIR}/coverage
UT_PYTHON_DIR=${CUR_DIR}/ut/python
PROJECT_DIR=$(readlink -f ${CUR_DIR}/..)
BUILD_DIR=${PROJECT_DIR}/build
ENABLE_CACHE="${ENABLE_CACHE:-0}"

LINE_COV_TARGET=80
BRANCH_COV_TARGET=60
TARGET_DATE="${TARGET_DATE:-2026/04/01}"

declare -A BASELINE_LINE_COV=(
    ["ms_service_profiler"]=73
    ["ms_serviceparam_optimizer"]=75
    ["msservice_advisor"]=80
    ["ms_service_metric"]=80
)

BASELINE_DATE="${BASELINE_DATE:-2026/02/04}"


function clean() {
    [[ "${ENABLE_CACHE}" != "1" && -d "${BUILD_DIR}" ]] && rm -rf "${BUILD_DIR}"

    if [ ! -d ${COV_DIR} ]; then
        mkdir -p ${COV_DIR}
    fi
}


# ------------------------------------------------------------------------------
# Coverage Check Rules
# - Verify overall coverage for modified modules
# - Coverage requirements rise linearly daily based on each module's baseline coverage
# - Target Date: 2026-02-28 | Line Coverage Target: 80% | Branch Coverage Target: 60%

# Usage Example:
#   ./test/run_ut.sh ms_service_profiler
# ------------------------------------------------------------------------------
function check_coverage() {
    local module_name=$1
    echo "[check_coverage]模块: $module_name"

    local arch=$(uname -m)
    if [ "$arch" != "aarch64" ]; then
        echo "[check_coverage]当前架构为 ${arch}，跳过覆盖率检查（仅 ARM 机器检查）"
        return 0
    fi

    coverage_file="${COV_DIR}/coverage_${module_name}.json"
    python3 -m coverage json -o $coverage_file
    local total_line=$(python3 -c "import json; data=json.load(open('$coverage_file')); print(data['totals']['percent_statements_covered'])")
    local total_branch=$(python3 -c "import json; data=json.load(open('$coverage_file')); print(data['totals']['percent_branches_covered'])")

    if [ -z "$total_line" ]; then
        echo "[check_coverage]错误: 无法获取覆盖率报告"
        exit 1
    fi

    if [ -z "$total_branch" ]; then
        total_branch="0"
    fi

    local baseline_line=${BASELINE_LINE_COV[$module_name]:-0}

    if [ "$baseline_line" -eq "0" ]; then
        baseline_line=$LINE_COV_TARGET
        return 0
    fi

    local current_timestamp=$(date +%s)
    local baseline_timestamp=$(date -d "$BASELINE_DATE" +%s 2>/dev/null || echo "0")
    if [ "$module_name" = "ms_serviceparam_optimizer" ]; then
        baseline_timestamp=$(date -d "2026/2/25" +%s 2>/dev/null || echo "0")
    fi
    local target_timestamp=$(date -d "$TARGET_DATE" +%s 2>/dev/null || echo "0")

    if [ "$baseline_timestamp" -eq "0" ] || [ "$target_timestamp" -eq "0" ]; then
        echo "[check_coverage]错误: 无法解析日期格式 '$BASELINE_DATE' 或 '$TARGET_DATE'"
        exit 1
    fi

    local total_days=$(( (target_timestamp - baseline_timestamp) / 86400 ))
    local current_days=$(( (current_timestamp - baseline_timestamp) / 86400 ))

    if [ "$current_days" -lt 0 ]; then
        current_days=0
    fi

    if [ "$current_days" -gt "$total_days" ]; then
        current_days=$total_days
    fi

    local progress=$(awk "BEGIN {printf \"%.2f\", $current_days * 100 / $total_days}")
    local line_cov_requirement=$(awk "BEGIN {printf \"%.2f\", $baseline_line + ($LINE_COV_TARGET - $baseline_line) * $current_days / $total_days}")
    local branch_cov_requirement=$BRANCH_COV_TARGET
    local failed=0

    if (( $(awk "BEGIN {print ($total_line < $line_cov_requirement) ? 1 : 0}") )); then
        echo "[check_coverage]行覆盖率 ${total_line}% 低于要求 ${line_cov_requirement}%"
        failed=1
    else
        echo "[check_coverage]行覆盖率 ${total_line}% 达标"
    fi

    if (( $(awk "BEGIN {print ($total_branch < $branch_cov_requirement) ? 1 : 0}") )); then
        echo "[check_coverage]分支覆盖率 ${total_branch}% 低于要求 ${branch_cov_requirement}%"
        failed=1
    else
        echo "[check_coverage]分支覆盖率 ${total_branch}% 达标"
    fi

    if [ $failed -eq 1 ]; then
        echo "[check_coverage]覆盖率检查失败！请为修改的模块添加足够的测试用例"
        exit 1
    fi
}


function run_ms_service_profiler_python_ut() {
    local UT_DIR="${UT_PYTHON_DIR}/test_ms_service_profiler"

    pip3 install -e "${PROJECT_DIR}[test]"
    python3 -m coverage run --branch --source "${PROJECT_DIR}/ms_service_profiler" --omit="test/*" -m pytest ${UT_DIR}
    python3 -m coverage report -m --precision=2
    python3 -m coverage xml -o ${COV_DIR}/coverage.xml
    check_coverage "ms_service_profiler"
}


function run_ms_service_profiler_cpp_ut() {
    local BUILD_TEST_DIR=${BUILD_DIR}/test
    local UT_TARGET="ms_service_profiler_run_uts"
    local ST_TARGET="ms_service_profiler_run_sts"
    local UT_BUILD_CACHE_DIR=${BUILD_TEST_DIR}/CMakeFiles/${UT_TARGET}.dir
    local ST_BUILD_CACHE_DIR=${BUILD_TEST_DIR}/CMakeFiles/${ST_TARGET}.dir
    local UT_COV_INFO=${COV_DIR}/ut_server_profiler.info
    local ST_COV_INFO=${COV_DIR}/st_server_profiler.info
    local OVERALL_COV_INFO=${COV_DIR}/test_server_profiler.info
    local COV_REPORT_DIR=${COV_DIR}/report

    if [ "$ENABLE_CACHE" != "1" ]; then
        cmake -S ${PROJECT_DIR}/ -B ${BUILD_DIR} -Dms_service_profiler_BUILD_TESTS=ON
        cmake --build ${BUILD_DIR} --target ${UT_TARGET} ${ST_TARGET} -j$(nproc)
    fi

    export LD_LIBRARY_PATH=${BUILD_DIR}/3rdparty/ascend:/opt/_internal/sqlite3/lib:$LD_LIBRARY_PATH
    ${BUILD_TEST_DIR}/${UT_TARGET}
    ${BUILD_TEST_DIR}/${ST_TARGET}
}


function run_ms_serviceparam_optimizer_ut() {
    local UT_DIR="${UT_PYTHON_DIR}/test_optimizer"

    if ! pip3 show ms_service_profiler > /dev/null; then
        pip3 install -e "${PROJECT_DIR}[test]"
    fi

    pip3 install -e "${PROJECT_DIR}/ms_serviceparam_optimizer[test]"
    PYTHONPATH=$PROJECT_DIR/ms_serviceparam_optimizer python3 -m coverage run \
        --branch \
        --source "${PROJECT_DIR}/ms_serviceparam_optimizer" \
        --omit="test/*" \
        -m pytest ${UT_DIR}

    python3 -m coverage report -m --precision=2
    python3 -m coverage xml -o ${COV_DIR}/coverage.xml
    check_coverage "ms_serviceparam_optimizer"
}


function run_msservice_advisor_ut() {
    local UT_DIR="${UT_PYTHON_DIR}/test_msservice_advisor"

    if ! pip3 show ms_service_profiler > /dev/null; then
        pip3 install -e "${PROJECT_DIR}[test]"
    fi

    pip3 install -e "${PROJECT_DIR}/msservice_advisor"
    PYTHONPATH=$PROJECT_DIR/msservice_advisor python3 -m coverage run \
        --branch \
        --source "${PROJECT_DIR}/msservice_advisor" \
        --omit="test/*" \
        -m pytest ${UT_DIR}

    python3 -m coverage report -m --precision=2
    python3 -m coverage xml -o ${COV_DIR}/coverage.xml
    check_coverage "msservice_advisor"
}


function run_ms_service_metric_python_ut() {
    local UT_DIR="${UT_PYTHON_DIR}/test_ms_service_metric"

    # Install ms_service_metric once with development extras for test tooling.
    if ! pip3 show ms_service_metric > /dev/null; then
        pip3 install -e "${PROJECT_DIR}/ms_service_metric[dev]"
    fi
    # Omit vendor integration entrypoints / framework-specific handlers from line targets (~75% on core code).
    python3 -m coverage run \
        --branch \
        --source "${PROJECT_DIR}/ms_service_metric/ms_service_metric" \
        --omit="test/*,*/adapters/sglang/*,*/adapters/vllm/handlers/*,*/adapters/vllm/adapter.py,*__main__.py" \
        -m pytest ${UT_DIR}

    python3 -m coverage report -m --precision=2
    python3 -m coverage xml -o ${COV_DIR}/coverage.xml
    check_coverage "ms_service_metric"
}


function main() {
    clean

    local -A tests_mapping=(
        ["ms_service_profiler"]="run_ms_service_profiler_python_ut"
        ["cpp"]="run_ms_service_profiler_cpp_ut"
        ["ms_serviceparam_optimizer"]="run_ms_serviceparam_optimizer_ut"
        ["msservice_advisor"]="run_msservice_advisor_ut"
        ["ms_service_metric"]="run_ms_service_metric_python_ut"

    )

    if [ $# -eq 0 ]; then
        for func in "${tests_mapping[@]}"; do
            $func
        done
        exit 0
    fi

    while [ $# -gt 0 ]; do
        test_name="$1"
        test_fn="${tests_mapping[$test_name]:-}"

        if [ -z "${test_fn}" ]; then
            echo "错误: 未知的测试项 '$test_name'"
            echo "可用选项: ${!tests[*]}"
            exit 1
        fi

        ${test_fn}
        shift
    done
}

main "$@"
