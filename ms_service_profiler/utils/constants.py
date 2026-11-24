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

import re


PATH_WHITE_LIST_REGEX = re.compile(r"[^_A-Za-z0-9/.-]")

KILOBYTE = 1024
DATA_SIZE_WARNING_THRESHOLD = 500 * 1024 * 1024

# Constants migrated from ms_service_profiler_ext/common/constants.py
MAX_BATCH_NUMBER = 1000
US_PER_MS = 1000
