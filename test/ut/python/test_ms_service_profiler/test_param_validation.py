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
import stat
import random
import unittest
from unittest import mock

from ms_service_profiler.utils.secur import validate_params, Path, InvalidParameterError, where


class TestParamValidation(unittest.TestCase):
    @staticmethod
    def create_func_with_constraints(constraints):
        @validate_params({"a": constraints})
        def foo(a):
            pass

        return foo

    @classmethod
    def setUpClass(cls):
        cls.arg_name = "a"
        cls.cur_dir = "."
        cls.prev_dir = ".."
        cls.full_mode = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO

    def setUp(self):
        self.random_path = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=8))

    def test_file_exists(self):
        test_func = self.create_func_with_constraints(Path.file_exists())
        self.assertRaises(InvalidParameterError, test_func, self.random_path)
        self.assertIsNone(test_func(__file__))

    def test_is_file(self):
        test_func = self.create_func_with_constraints(Path.is_file())
        self.assertRaises(InvalidParameterError, test_func, self.random_path)
        self.assertIsNone(test_func(__file__))

    def test_is_dir(self):
        test_func = self.create_func_with_constraints(Path.is_dir())
        self.assertRaises(InvalidParameterError, test_func, self.random_path)
        self.assertIsNone(test_func(self.cur_dir))

    def test_has_no_soft_link(self):
        test_func = self.create_func_with_constraints(~Path.has_soft_link())
        try:
            os.symlink(self.prev_dir, self.random_path)
            self.assertRaises(InvalidParameterError, test_func, self.random_path)
            self.assertRaises(InvalidParameterError, test_func, os.path.join(self.random_path, "test"))
            self.assertRaises(OSError, test_func, os.path.join(self.random_path * 2))
        finally:
            if os.path.islink(self.random_path) or os.path.exists(self.random_path):
                os.unlink(self.random_path)
        self.assertIsNone(test_func(self.cur_dir))

    @unittest.skipIf(os.geteuid() == 0, "all paths are readable to super user")
    def test_is_readable(self):
        test_func = self.create_func_with_constraints(Path.is_readable())
        not_readable_mode = self.full_mode ^ stat.S_IRUSR ^ stat.S_IRGRP ^ stat.S_IROTH
        try:
            with open(self.random_path, "w", encoding="utf-8"):
                pass
            os.chmod(self.random_path, not_readable_mode)
            self.assertRaises(InvalidParameterError, test_func, self.random_path)
        finally:
            if os.path.exists(self.random_path):
                os.remove(self.random_path)

    @unittest.skipIf(os.geteuid() == 0, "all paths are writable to super user")
    def test_is_writable(self):
        test_func = self.create_func_with_constraints(Path.is_writable())
        not_writable_mode = self.full_mode ^ stat.S_IWUSR ^ stat.S_IWGRP ^ stat.S_IWOTH
        try:
            with open(self.random_path, "w", encoding="utf-8"):
                pass
            os.chmod(self.random_path, not_writable_mode)
            self.assertRaises(InvalidParameterError, test_func, self.random_path)
        finally:
            if os.path.exists(self.random_path):
                os.remove(self.random_path)

    @unittest.skipIf(os.geteuid() == 0, "all paths are executable to super user")
    def test_is_executable(self):
        test_func = self.create_func_with_constraints(Path.is_executable())
        not_executable_mode = self.full_mode ^ stat.S_IXUSR ^ stat.S_IXGRP ^ stat.S_IXOTH
        try:
            with open(self.random_path, "w", encoding="utf-8"):
                pass
            os.chmod(self.random_path, not_executable_mode)
            self.assertRaises(InvalidParameterError, test_func, self.random_path)
        finally:
            if os.path.exists(self.random_path):
                os.remove(self.random_path)

    def test_is_consistent_to_current_user(self):
        test_func = self.create_func_with_constraints(Path.is_consistent_to_current_user())
        with mock.patch("os.stat", return_value=os.stat_result([0] * 4 + [os.getuid() + 1] + [0] * 5)):
            self.assertRaises(InvalidParameterError, test_func, self.random_path)

    def test_combined_constraints_with_and(self):
        test_func = self.create_func_with_constraints(Path.is_file() & Path.is_readable())
        self.assertRaises(InvalidParameterError, test_func, self.random_path)
        self.assertIsNone(test_func(__file__))

    def test_combined_constraints_with_or(self):
        test_func = self.create_func_with_constraints(Path.is_file() | Path.is_dir())
        self.assertRaises(InvalidParameterError, test_func, self.random_path)
        self.assertIsNone(test_func(__file__))
        self.assertIsNone(test_func(self.cur_dir))

    def test_combined_constraints_with_and_or(self):
        test_func = self.create_func_with_constraints((Path.is_file() & Path.is_readable()) | Path.is_dir())
        self.assertRaises(InvalidParameterError, test_func, self.random_path)
        self.assertIsNone(test_func(__file__))
        self.assertIsNone(test_func(self.cur_dir))

    def test_if_else_constraint(self):
        test_func = self.create_func_with_constraints(
            where(Path.is_file() & Path.is_readable(), Path.is_file(), Path.is_dir())
        )
        self.assertRaises(InvalidParameterError, test_func, self.random_path)
        self.assertIsNone(test_func(__file__))
        self.assertIsNone(test_func(self.cur_dir))

    def test_nested_if_else_constraint(self):
        test_func = self.create_func_with_constraints(
            where(Path.is_file() & Path.is_readable(), Path.is_file(), Path.is_dir() & Path.is_writable())
        )
        self.assertRaises(InvalidParameterError, test_func, self.random_path)
        self.assertIsNone(test_func(__file__))
        with mock.patch("os.access", return_value=False):
            self.assertRaises(InvalidParameterError, test_func, self.cur_dir)
        with mock.patch("os.access", return_value=True):
            self.assertIsNone(test_func(self.cur_dir))

    def test_user_defined_function_constraint(self):
        test_func = self.create_func_with_constraints(lambda value: isinstance(value, int) and value % 2 == 0)
        self.assertRaises(InvalidParameterError, test_func, 3)
        self.assertIsNone(test_func(4))
        self.assertRaises(InvalidParameterError, test_func, "not an int")

    def test_user_defined_function_constraint_not_valid(self):
        self.assertRaises(ValueError, self.create_func_with_constraints(lambda val, another_val: True), 3)
        self.assertRaises(TypeError, self.create_func_with_constraints(lambda val: "non bool"), 3)
