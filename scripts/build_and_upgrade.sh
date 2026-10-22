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

# 一键构建 run 包并执行升级，封装「下载三方 -> 构建 -> 升级」全流程

set -ueo pipefail

print_help() {
    cat << 'EOF'
用法:
  bash scripts/build_and_upgrade.sh [选项]

选项:
  --install-path=PATH  指定升级目标路径（CANN Toolkit 安装目录）
  --quiet              跳过升级确认提示（非交互模式使用）
  --help, -h           显示此帮助信息

示例:
  # 使用 ASCEND_TOOLKIT_HOME 作为升级路径
  export ASCEND_TOOLKIT_HOME=/usr/local/Ascend/ascend-toolkit
  bash scripts/build_and_upgrade.sh

  # 手动指定升级路径
  bash scripts/build_and_upgrade.sh --install-path=/usr/local/Ascend/ascend-toolkit

  # 非交互模式（CI 等场景）
  bash scripts/build_and_upgrade.sh --install-path=/path/to/cann --quiet
EOF
}

CUR_DIR=$(dirname "$(readlink -f "$0")")
TOP_DIR=$(realpath "${CUR_DIR}/..")
OUTPUT_DIR=${TOP_DIR}/output
MSSERVICE_RUN_NAME="mindstudio-service-profiler"

INSTALL_PATH=""
QUIET_FLAG=0

# 解析参数
for arg in "$@"; do
    case "$arg" in
        --install-path=*)
            INSTALL_PATH="${arg#--install-path=}"
            INSTALL_PATH="${INSTALL_PATH%/}"
            ;;
        --quiet)
            QUIET_FLAG=1
            ;;
        --help|-h)
            print_help
            exit 0
            ;;
        *)
            echo "[ERROR] 未知参数: $arg，请使用 --help 查看用法"
            exit 1
            ;;
    esac
done

# 确定升级路径
if [ -n "$INSTALL_PATH" ]; then
    UPGRADE_PATH="$INSTALL_PATH"
    USE_INSTALL_PATH_ARG=1
elif [ -n "${ASCEND_TOOLKIT_HOME:-}" ]; then
    UPGRADE_PATH="${ASCEND_TOOLKIT_HOME%/}"
    USE_INSTALL_PATH_ARG=0
else
    echo "[ERROR] 请设置 ASCEND_TOOLKIT_HOME 环境变量，或使用 --install-path 指定升级路径"
    exit 1
fi

if [ ! -d "$UPGRADE_PATH" ]; then
    echo "[ERROR] 升级路径不存在: $UPGRADE_PATH"
    exit 1
fi

echo "[INFO] 升级目标路径: $UPGRADE_PATH"
echo "[INFO] 开始构建并升级 msServiceProfiler..."
echo ""

# Step 1: 下载三方文件
echo "[STEP 1/3] 下载三方文件..."
cd "$TOP_DIR"
bash scripts/download_thirdparty.sh || { echo "[ERROR] 下载三方文件失败"; exit 1; }
echo ""

# Step 2: 构建 run 包
echo "[STEP 2/3] 构建 run 包..."
bash scripts/build.sh || { echo "[ERROR] 构建 run 包失败"; exit 1; }
echo ""

# Step 3: 执行升级
echo "[STEP 3/3] 执行升级..."
RUN_FILE=$(find "$OUTPUT_DIR" -maxdepth 1 -name "${MSSERVICE_RUN_NAME}_*.run" -type f 2>/dev/null | head -1 || true)
if [ -z "$RUN_FILE" ] || [ ! -f "$RUN_FILE" ]; then
    echo "[ERROR] 未找到 run 包: ${OUTPUT_DIR}/${MSSERVICE_RUN_NAME}_*.run"
    exit 1
fi

UPGRADE_ARGS=("--upgrade")
[ "$USE_INSTALL_PATH_ARG" -eq 1 ] && UPGRADE_ARGS+=("--install-path=${UPGRADE_PATH}")
[ "$QUIET_FLAG" -eq 1 ] && UPGRADE_ARGS+=("--quiet")

"$RUN_FILE" "${UPGRADE_ARGS[@]}" || { echo "[ERROR] 升级执行失败"; exit 1; }

echo ""
echo "[INFO] 构建并升级完成。"
