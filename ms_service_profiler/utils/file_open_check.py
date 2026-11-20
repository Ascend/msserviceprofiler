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
import sys
import stat
import re
import json
import logging

from enum import Enum
from typing import Optional
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.constants import PATH_WHITE_LIST_REGEX

MAX_SIZE_UNLIMITE = -1  # 不限制，必须显式表示不限制，读取必须传入
MAX_SIZE_LIMITE_CONFIG_FILE = 10 * 1024 * 1024  # 10M 普通配置文件，可以根据实际要求变更
MAX_SIZE_LIMITE_NORMAL_FILE = 4 * 1024 * 1024 * 1024  # 4G 普通模型文件，可以根据实际要求变更
MAX_SIZE_LIMITE_MODEL_FILE = 100 * 1024 * 1024 * 1024  # 100G 超大模型文件，需要确定能处理大文件，可以根据实际要求变更

PATH_WHITE_LIST_REGEX_WIN = re.compile(r"[^_:\\A-Za-z0-9/.-]")

PERMISSION_NORMAL = 0o640  # 普通文件
PERMISSION_KEY = 0o600  # 密钥文件
READ_FILE_NOT_PERMITTED_STAT = stat.S_IWGRP | stat.S_IWOTH
WRITE_FILE_NOT_PERMITTED_STAT = stat.S_IWGRP | stat.S_IWOTH

SOLUTION_LEVEL = 35
SOLUTION_LEVEL_WIN = 45
logging.addLevelName(SOLUTION_LEVEL, "\033[1;32m" + "SOLUTION" + "\033[0m")  # green [SOLUTION]
logging.addLevelName(SOLUTION_LEVEL_WIN, "SOLUTION_WIN")

SOFT_LINK_SUB_CHAPTER = 'soft_link_warning_log_solution"'
PATH_LENGTH_SUB_CHAPTER = 'path_length_overflow_warning_log_solution"'
OWNER_SUB_CHAPTER = 'owner_or_ownergroup_warning_log_solution"'
PERMISSION_SUB_CHAPTER = 'path_permission_error_log_solution"'
ILLEGAL_CHAR_SUB_CHAPTER = 'path_contain_illegal_char_error_log_solution"'

RAW_INPUT_PATH = "RAW_INPUT_PATH"

MALICIOUS_CSV_PATTERN = re.compile(r'^[＝＋－+-=%@];[＝＋－+-=%@]')


def solution_log(content):
    logger.log(SOLUTION_LEVEL, "visit %s for detailed solution", content)


def solution_log_win(content):
    logger.log(SOLUTION_LEVEL_WIN, "visit %s for detailed solution", content)


def is_legal_path_length(path):
    if len(path) > 4096 and not sys.platform.startswith("win"):  # linux total path length limit
        logger.warning("file total path %s length out of range (4096), please check the file(or directory) path", path)
        solution_log(PATH_LENGTH_SUB_CHAPTER)
        return True

    if len(path) > 260 and sys.platform.startswith("win"):  # windows total path length limit
        logger.warning("file total path %s length out of range (260), please check the file(or directory) path", path)
        solution_log_win(PATH_LENGTH_SUB_CHAPTER)
        return True

    dirnames = path.split("/")
    for dirname in dirnames:
        if len(dirname) > 255:  # linux single file path length limit
            logger.warning("file name %s length out of range (255), please check the file(or directory) path", dirname)
            solution_log(PATH_LENGTH_SUB_CHAPTER)
            return True
    return True


def is_match_path_white_list(path):
    if PATH_WHITE_LIST_REGEX.search(path) and not sys.platform.startswith("win"):
        logger.error("path: %s contains illegal char, legal chars include A-Z a-z 0-9 _ - / .", path)
        solution_log(ILLEGAL_CHAR_SUB_CHAPTER)
        return False
    if PATH_WHITE_LIST_REGEX_WIN.search(path) and sys.platform.startswith("win"):
        logger.error("path: %s contains illegal char, legal chars include A-Z a-z 0-9 _ - / . : \\", path)
        solution_log_win(ILLEGAL_CHAR_SUB_CHAPTER)
        return False
    return True


def is_legal_args_path_string(path):
    # only check path string
    if not path:
        return True
    if not is_legal_path_length(path):
        return False
    if not is_match_path_white_list(path):
        return False
    return True


class SanitizeErrorType(Enum):
    """
    The errors parameter Enum of the function sanitize_csv_value
    """

    strict = "strict"
    ignore = "ignore"
    replace = "replace"


def sanitize_csv_value(value: str, errors=SanitizeErrorType.strict.value):
    if errors == SanitizeErrorType.ignore.value or not isinstance(value, str):
        return value

    sanitized_value = value
    try:
        float(value)  # in case value is a digit but in str format
    except ValueError as e:  # not digit
        if not MALICIOUS_CSV_PATTERN.search(value):
            pass
        elif errors == SanitizeErrorType.replace.value:
            sanitized_value = ' ' + value
        else:
            msg = f'Malicious value is not allowed to be written to the csv {value}'
            logger.error("Please check the value written to the csv")
            raise ValueError(msg) from e

    return sanitized_value


class OpenException(Exception):
    pass


class FileStat:
    def __init__(self, file) -> None:
        if not is_legal_path_length(file) or not is_match_path_white_list(file):
            raise OpenException("Path name is too long or contains invalid characters.")
        self.file = file
        self.is_file_exist = os.path.exists(file)
        if self.is_file_exist:
            self.file_stat = os.stat(file)
            self.realpath = os.path.realpath(file)
        else:
            self.file_stat = None

    @property
    def is_exists(self):
        return self.is_file_exist

    @property
    def is_softlink(self):
        return os.path.islink(self.file) if self.file_stat else False

    @property
    def is_file(self):
        return stat.S_ISREG(self.file_stat.st_mode) if self.file_stat else False

    @property
    def is_dir(self):
        return stat.S_ISDIR(self.file_stat.st_mode) if self.file_stat else False

    @property
    def file_size(self):
        return self.file_stat.st_size if self.file_stat else 0

    @property
    def permission(self):
        return stat.S_IMODE(self.file_stat.st_mode) if self.file_stat else 0o777

    @property
    def owner(self):
        return self.file_stat.st_uid if self.file_stat else -1

    @property
    def group_owner(self):
        return self.file_stat.st_gid if self.file_stat else -1

    @property
    def is_owner(self):
        return self.owner == (os.geteuid() if hasattr(os, "geteuid") else 0)

    @property
    def is_group_owner(self):
        return self.group_owner in (os.getgroups() if hasattr(os, "getgroups") else [0])

    @property
    def is_user_or_group_owner(self):
        return self.is_owner or self.is_group_owner

    @property
    def is_user_and_group_owner(self):
        return self.is_owner and self.is_group_owner

    def is_basically_legal(self, perm='none', strict_permission=True):
        if sys.platform.startswith("win"):
            return self.check_windows_permission(perm)
        else:
            return self.check_linux_permission(perm, strict_permission=strict_permission)

    def check_basic_permission(self, perm='none'):
        if not self.is_exists and perm != 'write':
            logger.error("path: %s not exist, please check if file or dir is exist", self.file)
            return False
        return True

    def check_linux_permission(self, perm='none', strict_permission=True):
        if not self.check_basic_permission(perm=perm):
            return False
        return True

    def check_windows_permission(self, perm='none'):
        if not self.check_basic_permission(perm=perm):
            return False
        return True

    def is_legal_file_size(self, max_size):
        if not self.is_file:
            logger.error("path: %s is not a file", self.file)
            return False
        if self.file_size > max_size:
            logger.error("file_size: %s byte out of max limit %s byte", self.file_size, max_size)
            return False
        else:
            return True

    def is_legal_file_type(self, file_types: list):
        if not self.is_file and self.is_exists:
            logger.error("path: %s is not a file", self.file)
            return False
        for file_type in file_types:
            if os.path.splitext(self.file)[1] == f".{file_type}":
                return True
        logger.error("path: %s, file type not in %s", self.file, file_types)
        return False


def check_file_exists_and_type(file_stat, file):
    if file_stat.is_exists and file_stat.is_dir:
        raise OpenException(f"Expecting a file, but it's a folder. {file}")


def check_file_owner(file_stat, file):
    if not file_stat.is_owner:
        logger.warning(
            "The file owner is inconsistent with the current process user and is not allowed to write. %s", file
        )
        raise OpenException(
            f"The file owner is inconsistent with the current process user and is not allowed to write. {file}"
        )


def ms_open(file, mode="r", **kwargs):
    file_stat = FileStat(file)

    check_file_exists_and_type(file_stat, file)

    if "r" in mode and not any(flag in mode for flag in ("w", "a", "x", "+")):
        if not file_stat.is_exists:
            raise OpenException(f"No such file or directory. {file}")
    elif any(flag in mode for flag in ("w", "a", "x", "+")) and file_stat.is_exists:
        check_file_owner(file_stat, file)

    try:
        if "b" in mode:
            return open(file, mode, **kwargs)  # pylint: disable=unspecified-encoding
        encoding = kwargs.pop("encoding", "utf-8")
        return open(file, mode, encoding=encoding, **kwargs)
    except OSError as exc:
        raise OpenException(str(exc)) from exc


class UmaskWrapper:
    """Write with preset umask
    >>> with UmaskWrapper():
    >>>     ...
    """

    def __init__(self, umask=0o027):
        self.umask, self.ori_umask = umask, None

    def __enter__(self):
        self.ori_umask = os.umask(self.umask)

    def __exit__(self, exc_type=None, exc_val=None, exc_tb=None):
        os.umask(self.ori_umask)


def get_valid_lib_path(so_name: str) -> Optional[str]:
    allowed_libs = {"libms_service_profiler.so"}

    # 白名单校验
    if so_name not in allowed_libs:
        logging.error("%s is invalid.", so_name)
        return None

    # 环境变量检查
    ascend_home = os.getenv("ASCEND_HOME_PATH")
    if not ascend_home:
        return so_name

    # 路径拼接与校验
    candidate_path = os.path.join(ascend_home, "aarch64-linux", "lib64", so_name)
    real_path = os.path.realpath(candidate_path)

    if os.path.exists(real_path) and os.access(real_path, os.R_OK):
        return real_path
    else:
        return so_name


def safe_json_dump(obj, *args, **kwargs):
    if not isinstance(obj, (str, int, float, bool, type(None), list, dict, tuple)):
        raise TypeError(f"Object of type {type(obj)} is not safe JSON serializable")

    return json.dumps(obj, *args, **kwargs)
