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

from .base import BasePathConstraint


class Exists(BasePathConstraint):
    description = "an existing path"

    def is_satisfied_by(self, val):
        return self._get_path_stat(val) is not None


class IsFile(BasePathConstraint):
    description = "a regular file"

    def is_satisfied_by(self, val):
        stat_result = self._get_path_stat(val)
        return stat_result is not None and stat.S_ISREG(stat_result.st_mode)


class IsDir(BasePathConstraint):
    description = "a directory"

    def is_satisfied_by(self, val):
        stat_result = self._get_path_stat(val)
        return stat_result is not None and stat.S_ISDIR(stat_result.st_mode)


class HasSoftLink(BasePathConstraint):
    """Check if path contains a soft link; if path does not exist, raise FileNotFoundError."""

    description = "a soft link"

    def is_satisfied_by(self, val):
        norm_path = os.path.normpath(os.path.abspath(val))
        components = norm_path.split(os.sep)

        current = os.path.sep
        for part in components[1:]:
            if not part:
                continue
            current = os.path.join(current, part)
            current_stat = self._get_path_stat(current)
            if current_stat is None:
                raise FileNotFoundError(f"Path component {current!r} does not exist.")
            if stat.S_ISLNK(current_stat.st_mode):
                return True

        final_stat = self._get_path_stat(norm_path)
        if final_stat is None:
            raise FileNotFoundError(f"Path {norm_path!r} does not exist.")

        return stat.S_ISLNK(final_stat.st_mode)


class IsReadable(BasePathConstraint):
    description = "a readable path"

    def is_satisfied_by(self, val):
        return os.access(val, os.R_OK)


class IsWritable(BasePathConstraint):
    description = "a writable path"

    def is_satisfied_by(self, val):
        return os.access(val, os.W_OK)


class IsExecutable(BasePathConstraint):
    description = "an executable path"

    def is_satisfied_by(self, val):
        return os.access(val, os.X_OK)


class IsWritableToGroupOrOthers(BasePathConstraint):
    description = "writable to group or others"

    def is_satisfied_by(self, val):
        stat_result = self._get_path_stat(val)
        if stat_result is None:
            raise FileNotFoundError(f"The path {val!r} does not exist or cannot be accessed.")

        return bool(stat_result.st_mode & (stat.S_IWGRP | stat.S_IWOTH))


class IsConsistentToCurrentUser(BasePathConstraint):
    description = "consistent with the current user"

    def is_satisfied_by(self, val):
        stat_result = self._get_path_stat(val)
        if stat_result is None:
            raise FileNotFoundError(f"The path {val!r} does not exist or cannot be accessed.")

        return stat_result.st_uid == os.geteuid()
