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
from dataclasses import dataclass

from .logic import FunctionConstraint, IfElseConstraint
from ._path import (
    IsFile,
    Exists,
    IsDir,
    HasSoftLink,
    IsReadable,
    IsWritable,
    IsExecutable,
    IsWritableToGroupOrOthers,
    IsConsistentToCurrentUser,
)
from .base import BaseConstraint


class PathConstraintBuilder:
    """
    Constraint builder for IDE support.

    Available constraints:
        is_file, file_exists, is_dir, has_soft_link, is_readable, is_writable,
        is_executable, is_not_writable_to_group_or_others, is_consistent_to_current_user
    """

    @staticmethod
    def is_file():
        return IsFile()

    @staticmethod
    def file_exists():
        return Exists()

    @staticmethod
    def is_dir():
        return IsDir()

    @staticmethod
    def has_soft_link():
        return HasSoftLink()

    @staticmethod
    def is_readable():
        return IsReadable()

    @staticmethod
    def is_writable():
        return IsWritable()

    @staticmethod
    def is_executable():
        return IsExecutable()

    @staticmethod
    def is_writable_to_group_or_others():
        return IsWritableToGroupOrOthers()

    @staticmethod
    def is_consistent_to_current_user():
        return IsConsistentToCurrentUser()


Path = PathConstraintBuilder


def make_constraint(constraint, description=None):
    if isinstance(constraint, BaseConstraint):
        return constraint

    if callable(constraint):
        return FunctionConstraint(constraint, description)

    raise TypeError(f"Expected a BaseConstraint instance or a callable, but got {type(constraint).__name__}.")


def where(condition, if_constraint, else_constraint, *, description=None):
    return IfElseConstraint(
        condition, make_constraint(if_constraint), make_constraint(else_constraint), description=description
    )


@dataclass(frozen=True)
class Rule:
    read_file_common_check: BaseConstraint = where(
        os.getuid() == 0,
        Path.is_file(),
        Path.is_file()
        & ~Path.has_soft_link()
        & Path.is_readable()
        & ~Path.is_writable_to_group_or_others()
        & Path.is_consistent_to_current_user(),
        description="current user is root",
    )

    exec_file_common_check: BaseConstraint = where(
        os.getuid() == 0,
        Path.is_file(),
        Path.is_file()
        & ~Path.has_soft_link()
        & Path.is_writable()
        & ~Path.is_writable_to_group_or_others()
        & Path.is_consistent_to_current_user(),
        description="current user is root",
    )
