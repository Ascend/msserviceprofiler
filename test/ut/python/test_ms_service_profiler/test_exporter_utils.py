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
import unittest
import os
import sqlite3
from pathlib import Path
import shutil
import pytest
import pandas as pd

# 测试目标模块
from ms_service_profiler.exporters.utils import (
    create_sqlite_db,
    save_dataframe_to_csv,
    check_input_dir_valid,
    check_output_path_valid,
    is_empty_directory,
    visual_db_fp,
    get_path_total_size,
)


@pytest.fixture
def cleanup_db_file():
    """测试后清理数据库文件"""
    global visual_db_fp
    yield
    if os.path.exists(visual_db_fp):
        os.remove(visual_db_fp)
    visual_db_fp = ''


@pytest.fixture
def sample_dataframe():
    """提供一个示例DataFrame"""
    return pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})


def test_create_sqlite_db_success(tmpdir, cleanup_db_file):  # pylint: disable=redefined-outer-name
    """测试成功创建SQLite数据库"""
    output_dir = os.path.join(os.getcwd(), "output_test")
    os.makedirs(output_dir, exist_ok=True)
    os.chmod(output_dir, 0o740)
    create_sqlite_db(str(output_dir))
    db_fp = Path(output_dir, 'profiler.db')
    conn = sqlite3.connect(db_fp)
    conn.close()
    assert os.path.exists(str(db_fp))


def test_save_dataframe_to_csv_success(tmpdir, sample_dataframe):  # pylint: disable=redefined-outer-name
    """测试成功保存DataFrame到CSV文件"""
    try:
        output_dir = os.path.join(os.getcwd(), "output_test")
        os.makedirs(output_dir, exist_ok=True)
        os.chmod(output_dir, 0o740)
        file_name = "test.csv"
        save_dataframe_to_csv(sample_dataframe, str(output_dir), file_name)

        file_path = os.path.join(str(output_dir), file_name)
        assert os.path.exists(file_path)
        df = pd.read_csv(file_path)
        assert df.equals(sample_dataframe)
    finally:
        # 清理
        shutil.rmtree(output_dir)


def test_save_dataframe_to_csv_none_output(sample_dataframe):  # pylint: disable=redefined-outer-name
    """测试output为None时是否跳过保存"""
    save_dataframe_to_csv(sample_dataframe, None, "test.csv")
    # 无异常即为通过


def test_check_input_dir_valid_success(tmpdir):
    """测试输入路径验证成功"""
    test_dir = tmpdir.mkdir("test_input")
    os.chmod(test_dir, 0o755)
    result = check_input_dir_valid(str(test_dir))
    assert result == str(test_dir)


def test_is_empty_directory_success(tmpdir):
    """测试输入路径为空"""
    test_dir = tmpdir.mkdir("test_input")
    os.chmod(test_dir, 0o755)
    result = is_empty_directory(test_dir)
    assert result


def test_check_output_path_valid_success(tmpdir):
    """测试输出路径验证成功"""
    test_dir = tmpdir.mkdir("test_output")
    result = check_output_path_valid(str(test_dir))
    assert result == os.path.abspath(str(test_dir))


def test_check_output_path_valid_create_dir(tmpdir):
    """测试输出路径不存在时自动创建"""
    test_dir = os.path.join(str(tmpdir), "new_dir")
    result = check_output_path_valid(test_dir)
    assert os.path.exists(test_dir)
    assert result == os.path.abspath(test_dir)


@unittest.skipIf(os.getuid() == 0, "root can write anything")
def test_check_output_path_valid_failure_not_writable(tmpdir):
    """测试输出路径存在且为目录时校验通过，即使目录不可写（函数不检查可写性）"""
    test_dir = tmpdir.mkdir("test_output")
    os.chmod(str(test_dir), 0o444)  # 只读权限

    result = check_output_path_valid(str(test_dir))
    assert result == os.path.abspath(str(test_dir))


class TestGetPathTotalSize:
    """测试 get_path_total_size 函数"""

    def test_single_file_size(self, tmpdir):
        """测试单个文件大小计算"""
        test_dir = str(tmpdir)
        test_file = os.path.join(test_dir, "test.txt")
        content = "Hello World" * 100
        with open(test_file, 'w', encoding="utf-8") as f:
            f.write(content)
        assert os.path.exists(test_file), f"File not found: {test_file}"
        actual_size = os.path.getsize(test_file)
        assert actual_size == len(content.encode()), (
            f"os.path.getsize mismatch: {actual_size} != {len(content.encode())}"
        )
        result = get_path_total_size(test_file)
        assert result == len(content.encode()), f"Expected {len(content.encode())}, got {result}"

    def test_directory_with_multiple_files(self, tmpdir):
        """测试包含多个文件的目录"""
        test_dir = str(tmpdir.mkdir("test_dir"))
        file1 = os.path.join(test_dir, "file1.txt")
        file2 = os.path.join(test_dir, "file2.txt")
        file3 = os.path.join(test_dir, "file3.txt")
        with open(file1, 'w', encoding="utf-8") as f:
            f.write("a" * 100)
        with open(file2, 'w', encoding="utf-8") as f:
            f.write("b" * 200)
        with open(file3, 'w', encoding="utf-8") as f:
            f.write("c" * 300)
        result = get_path_total_size(test_dir)
        assert result == 600

    def test_nested_directory(self, tmpdir):
        """测试嵌套目录"""
        root_dir = str(tmpdir.mkdir("root"))
        sub_dir = os.path.join(root_dir, "subdir")
        os.makedirs(sub_dir)
        file1 = os.path.join(root_dir, "root_file.txt")
        file2 = os.path.join(sub_dir, "sub_file.txt")
        with open(file1, 'w', encoding="utf-8") as f:
            f.write("x" * 100)
        with open(file2, 'w', encoding="utf-8") as f:
            f.write("y" * 200)
        result = get_path_total_size(root_dir)
        assert result == 300

    def test_empty_directory(self, tmpdir):
        """测试空目录"""
        test_dir = str(tmpdir.mkdir("empty_dir"))
        result = get_path_total_size(test_dir)
        assert result == 0

    def test_symlink_is_skipped(self, tmpdir):
        """测试符号链接被跳过"""
        test_dir = str(tmpdir.mkdir("test_dir"))
        real_file = os.path.join(test_dir, "real_file.txt")
        link_path = os.path.join(test_dir, "link.txt")
        with open(real_file, 'w', encoding="utf-8") as f:
            f.write("content" * 100)
        os.symlink(real_file, link_path)
        result = get_path_total_size(test_dir)
        assert result == 700

    def test_size_exceeds_500mb_warning_threshold(self, tmpdir):
        """测试超过500MB阈值时的警告逻辑（模拟parse.py中的检查）"""
        test_dir = str(tmpdir.mkdir("large_dir"))
        large_file = os.path.join(test_dir, "large_file.bin")
        DATA_SIZE_WARNING_THRESHOLD = 500 * 1024 * 1024
        with open(large_file, 'wb') as f:
            f.write(b'x' * (DATA_SIZE_WARNING_THRESHOLD + 1024 * 1024))
        input_size = get_path_total_size(test_dir)
        assert input_size > DATA_SIZE_WARNING_THRESHOLD

    def test_size_boundary_499mb_no_warning(self, tmpdir):
        """测试499MB不应该触发警告"""
        test_dir = str(tmpdir.mkdir("dir_499mb"))
        test_file = os.path.join(test_dir, "file.bin")
        DATA_SIZE_WARNING_THRESHOLD = 500 * 1024 * 1024
        with open(test_file, 'wb') as f:
            f.write(b'x' * (DATA_SIZE_WARNING_THRESHOLD - 1024 * 1024))
        input_size = get_path_total_size(test_dir)
        assert input_size < DATA_SIZE_WARNING_THRESHOLD

    def test_size_boundary_500mb_no_warning(self, tmpdir):
        """测试500MB（边界值）不应该触发警告"""
        test_dir = str(tmpdir.mkdir("dir_500mb"))
        test_file = os.path.join(test_dir, "file.bin")
        DATA_SIZE_WARNING_THRESHOLD = 500 * 1024 * 1024
        with open(test_file, 'wb') as f:
            f.write(b'x' * DATA_SIZE_WARNING_THRESHOLD)
        input_size = get_path_total_size(test_dir)
        assert input_size == DATA_SIZE_WARNING_THRESHOLD

    def test_size_boundary_501mb_warning(self, tmpdir):
        """测试501MB应该触发警告"""
        test_dir = str(tmpdir.mkdir("dir_501mb"))
        test_file = os.path.join(test_dir, "file.bin")
        DATA_SIZE_WARNING_THRESHOLD = 500 * 1024 * 1024
        with open(test_file, 'wb') as f:
            f.write(b'x' * (DATA_SIZE_WARNING_THRESHOLD + 1024 * 1024))
        input_size = get_path_total_size(test_dir)
        assert input_size > DATA_SIZE_WARNING_THRESHOLD
