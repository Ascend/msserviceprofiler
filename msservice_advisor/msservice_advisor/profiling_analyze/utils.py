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
import json
import csv
import logging
from collections import namedtuple
from glob import glob
from msguard.security import open_s
from msguard import validate_params, Rule

TARGETS = namedtuple("TARGETS", ["FirstTokenTime", "Throughput"])("FirstTokenTime", "Throughput")
_SUGGESTION_TYPES = ["env", "system", "config"]
SUGGESTION_TYPES = namedtuple("SUGGESTION_TYPES", _SUGGESTION_TYPES)(*_SUGGESTION_TYPES)
MAX_FILE_SIZE = 10
BYTES_TO_GB = 1024**3
MAX_DEVICE_ID_LIST_LENGTH = 128

LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "fatal": logging.FATAL,
    "critical": logging.CRITICAL,
}


def str_ignore_case(value):
    return value.lower().replace("_", "").replace("-", "")


def get_dict_value_by_pos(dict_value, target_pos):
    cur = dict_value
    for kk in target_pos.split(":"):
        if not cur:
            cur = None
            break
        if isinstance(cur, list) and str.isdigit(kk):
            cur = cur[int(kk)]
        elif kk in cur:
            cur = cur[kk]
        else:
            cur = None
            break
    return cur


def set_log_level(level="info"):
    if level.lower() in LOG_LEVELS:
        logger.setLevel(LOG_LEVELS.get(level.lower()))
    else:
        logger.warning("Set %r log level failed.", level)


def set_logger(msit_logger):
    msit_logger.propagate = False
    msit_logger.setLevel(logging.INFO)
    if not msit_logger.handlers:
        stream_handler = logging.StreamHandler()
        formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        stream_handler.setFormatter(formatter)
        msit_logger.addHandler(stream_handler)


logger = logging.getLogger("msservice_advisor_logger")
set_logger(logger)


def get_latest_matching_file(instance_path, pattern):
    files = glob(os.path.join(instance_path, pattern))
    return max(files, key=os.path.getmtime) if files else None


def _process_csv_rows(reader):
    """Process rows from a CSV DictReader and return a dictionary of columns."""
    result = {}
    for row in reader:
        for key, value in row.items():
            result.setdefault(key, []).append(value)
    return result


def read_csv(file_path):
    logger.info("Reading CSV file: %r", file_path)
    try:
        with open_s(file_path, mode="r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames:
                logger.error("CSV file %r has no headers or is empty.", file_path)
                return None
            result = _process_csv_rows(reader)
            if not result:
                logger.error("CSV file %r is empty or has no valid data.", file_path)
                return None
    except csv.Error as e:
        logger.error("CSV file %r is not properly formatted: %s", file_path, e)
        return None
    except Exception as e:
        logger.error("Failed to read CSV file %r: %s", file_path, e)
        return None
    return result


def read_json(file_path):
    logger.info("Reading JSON file: %r", file_path)
    try:
        with open_s(file_path, mode="r", encoding="utf-8") as ff:
            result = json.load(ff)
            if not isinstance(result, dict):
                logger.error("JSON file %r does not contain a JSON object.", file_path)
                return None
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON file %r: %s", file_path, e)
        return None
    except Exception as e:
        logger.error("Failed to read JSON file %r: %s", file_path, e)
        return None
    return result


@validate_params({'file_path': Rule.input_file_read})
def read_csv_or_json(file_path):
    if not file_path or not os.path.exists(file_path):
        logger.warning("File does not exist: %r", file_path)
        return None
    if file_path.endswith(".json"):
        return read_json(file_path)
    elif file_path.endswith(".csv"):
        return read_csv(file_path)
    else:
        logger.warning("Unsupported file format: %r", file_path)
        return None


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


def is_root():
    return os.name != 'nt' and os.getuid() == 0
