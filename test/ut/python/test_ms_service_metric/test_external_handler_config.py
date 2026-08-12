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
"""Configuration source tests for user-owned external Handlers."""

from ms_service_metric.core.config.symbol_config import SymbolConfig


def test_given_env_config_directory_when_load_then_commits_external_handler_root(
    tmp_path,
    monkeypatch,
):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "metrics.yaml").write_text(
        "- symbol: m.n:o\n  handler: custom_handler:record\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(SymbolConfig.ENV_CONFIG_PATH, str(config_dir))

    config = SymbolConfig()
    config.load()

    assert config.get_user_handler_root() == str(config_dir.resolve())


def test_given_env_config_file_when_load_then_parent_is_external_handler_root(
    tmp_path,
    monkeypatch,
):
    config_file = tmp_path / "metrics.yaml"
    config_file.write_text(
        "- symbol: m.n:o\n  handler: custom_handler:record\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(SymbolConfig.ENV_CONFIG_PATH, str(config_file))

    config = SymbolConfig()
    config.load()

    assert config.get_user_handler_root() == str(tmp_path.resolve())


def test_given_user_owned_framework_config_when_load_then_enables_its_handler_root(
    tmp_path,
):
    config_file = tmp_path / "metrics.yaml"
    config_file.write_text(
        "- symbol: m.n:o\n  handler: custom_handler:record\n",
        encoding="utf-8",
    )

    config = SymbolConfig(
        user_config_path=str(config_file),
        framework_config_is_user=True,
    )
    config.load()

    assert config.get_user_handler_root() == str(tmp_path.resolve())
