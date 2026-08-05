#!/usr/bin/python3
# -*- coding: utf-8 -*-
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
import argparse
import logging
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class BuildManager:
    """
    统一构建管理：依赖拉取 → 编译 → 安装 / 测试。

    用法:
        python build.py                             完整构建（拉取依赖 + Release 编译）
        python build.py local                       本地构建（跳过依赖拉取, Release 编译）
        python build.py test                        单元测试（拉取依赖 + Debug 编译 + 执行测试）
        python build.py test local                  单元测试（跳过依赖拉取, Debug 编译 + 执行测试）
        python build.py --version/-v <version>      指定构建版本号（用于 run/exe/dmg 包）
        python build.py --extra/-e KEY=VALUE        指定额外构建选项，可多次使用

    参数说明:
        - 参数: command    : 构建动作: 为空时为全构建, local 为跳过依赖下载, test 为运行单元测试。
        - 参数: --version  : 构建版本号，不传时默认 1.0.0。
        - 参数: --extra    : 额外构建选项，格式为 KEY=VALUE，可多次指定。
    """

    def __init__(self):
        self.project_root = Path(__file__).resolve().parent
        ap = argparse.ArgumentParser(description='Build the project and optionally run tests.')
        ap.add_argument(
            'command',
            nargs='*',
            default=[],
            choices=[[], 'local', 'test'],
            help='Build action: omit for full build, "local" to skip dependency download, "test" to run unit tests',
        )
        ap.add_argument(
            '-v', '--version', type=str, default='1.0.0', help='Build version for run/exe/dmg packages (default: 1.0.0)'
        )
        ap.add_argument(
            '-e',
            '--extra',
            metavar='KEY=VALUE',
            action='append',
            default=[],
            help='Extra build options in KEY=VALUE format, can be specified multiple times',
        )
        self.args = ap.parse_args()

    def _execute_command(self, cmd, timeout_seconds=36000, cwd=None, env=None):
        logging.info("Running: %s", " ".join(cmd))
        subprocess.run(cmd, timeout=timeout_seconds, check=True, cwd=cwd, env=env)

    def _archive_artifacts(self):
        # 归档产物：output 下的 run 包、build/output_whl_dir 下的 whl 包
        artifacts_dir = self.project_root / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)

        sources = [
            self.project_root / "output",
            self.project_root / "build" / "output_whl_dir",
        ]
        for src_dir in sources:
            if not src_dir.is_dir():
                continue
            for file_path in src_dir.iterdir():
                if file_path.is_file():
                    logging.info("Archiving %s -> %s", file_path, artifacts_dir / file_path.name)
                    shutil.copy2(file_path, artifacts_dir / file_path.name)

    def _run_tests(self):
        modify_file = Path("/tmp/modify_files.txt")
        if not modify_file.is_file():
            self._execute_command(["bash", "test/run_ut.sh"])
            return

        lines = modify_file.read_text(encoding="utf-8").splitlines()

        if any("test/presmoke" in line for line in lines):
            logging.info("检测到补充预冒烟用例，跳过测试")
            return

        if any(line.endswith(".sh") for line in lines):
            logging.info("检测到 shell 脚本修改，运行全量测试")
            self._execute_command(["bash", "test/run_ut.sh"])
            return

        module_map = [
            ("ms_service_profiler", "ms_service_profiler"),
            ("optimizer", "ms_serviceparam_optimizer"),
            ("msservice_advisor", "msservice_advisor"),
            ("cpp", "cpp"),
        ]
        tests_to_run = []
        for keyword, module in module_map:
            if any(keyword in line for line in lines):
                tests_to_run.append(module)

        target_branch = os.environ.get("TARGET_BRANCH", "")
        if target_branch == "master" and any("ms_service_metric" in line for line in lines):
            tests_to_run.append("ms_service_metric")

        if not tests_to_run:
            logging.info("没有检测到源码修改，跳过测试")
        else:
            logging.info("运行测试: %s", " ".join(tests_to_run))
            self._execute_command(["bash", "test/run_ut.sh"] + tests_to_run)

    def run(self):
        os.chdir(self.project_root)

        if 'test' in self.args.command:
            # -------------------- 单元测试 --------------------
            self._run_tests()
        else:
            # -------------------- 产品构建 --------------------
            if 'local' not in self.args.command:
                self._execute_command(["bash", "scripts/download_thirdparty.sh"])

            # only_down_deps 在依赖下载后、构建前检查
            extra_options = {}
            for opt in self.args.extra:
                key, _, val = opt.partition('=')
                extra_options[key] = val
            if extra_options.get('only_down_deps') == 'true':
                logging.info("only_down_deps=true, exiting after dependency download.")
                return

            logging.info("--version: %s", self.args.version)
            for opt in self.args.extra:
                key, _, val = opt.partition('=')
                logging.info("--extra: %s = %s", key, val)

            self._execute_command(["bash", "scripts/build.sh", self.args.version])

            for stale_whl in (self.project_root / "build" / "output_whl_dir").glob("*.whl"):
                stale_whl.unlink()

            self._execute_command(["bash", "scripts/build_whl.sh", self.args.version])
            self._archive_artifacts()


if __name__ == "__main__":
    try:
        BuildManager().run()
    except Exception:
        logging.error("Unexpected error: %s", traceback.format_exc())
        sys.exit(1)
