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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VERSION="${1:-26.0.0}"

cd "${PROJECT_ROOT}"

echo "Building ms_service_profiler version: ${VERSION}"

# 修改版本号
sed -i.bak "s/^version = .*/version = \"${VERSION}\"/" pyproject.toml

# 打包（cwd 切到工程根目录之外，避免 -m build 被根目录下的 build.py 同名遮蔽）
(cd /tmp && python3 -m build --wheel "${PROJECT_ROOT}" --outdir "${TOP_DIR:-${PROJECT_ROOT}}/build/output_whl_dir")

# 恢复原文件
mv pyproject.toml.bak pyproject.toml

cd ms_service_metric

echo "Building ms_service_metric version: ${VERSION}"

# 修改版本号
sed -i.bak "s/^version = .*/version = \"${VERSION}\"/" pyproject.toml

# 打包
python3 -m build --wheel . --outdir "${TOP_DIR:-${PROJECT_ROOT}}/build/output_whl_dir"

# 恢复原文件
mv pyproject.toml.bak pyproject.toml
