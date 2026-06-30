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
# MERCHANTABILITY OR CONDITIONS OF ANY KIND.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------
# pylint: disable=duplicate-code

"""Allow-list checks for ms_service_metric configuration-driven imports."""

ALLOWED_HANDLER_MODULE_PREFIXES = (
    "ms_service_profiler.",
    "ms_service_metric.",
)

ALLOWED_SYMBOL_MODULE_PREFIXES = (
    "vllm.",
    "vllm_ascend.",
    "sglang.",
    "ms_service_profiler.",
    "ms_service_metric.",
)


def is_allowed_handler_module(module_path: str) -> bool:
    return isinstance(module_path, str) and module_path.startswith(ALLOWED_HANDLER_MODULE_PREFIXES)


def is_allowed_symbol_module(module_path: str) -> bool:
    return isinstance(module_path, str) and module_path.startswith(ALLOWED_SYMBOL_MODULE_PREFIXES)
