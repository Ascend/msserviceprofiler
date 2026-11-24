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
import logging
import tempfile
import pytest

import msservice_advisor.profiling_analyze.utils as utils  # pylint: disable=no-name-in-module


# Helper functions for file/directory testing
def create_temp_file(size_bytes, content=None):
    """Create a temporary file with specified size"""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        if content:
            temp_file.write(content.encode())
        else:
            temp_file.write(b"0" * size_bytes)
        return temp_file.name


# Test str_ignore_case
def test_str_ignore_case_given_normal_string_when_lowercase_then_processed():
    assert utils.str_ignore_case("Hello") == "hello"
    assert utils.str_ignore_case("HELLO_WORLD") == "helloworld"
    assert utils.str_ignore_case("Mix-Ed_Case") == "mixedcase"


def test_str_ignore_case_given_empty_string_when_processed_then_empty():
    assert utils.str_ignore_case("") == ""


def test_str_ignore_case_given_non_string_when_processed_then_error():
    with pytest.raises(AttributeError):
        utils.str_ignore_case(None)
    with pytest.raises(AttributeError):
        utils.str_ignore_case(123)


def test_str_ignore_case_given_unicode_string_when_processed_then_lowercase():
    assert utils.str_ignore_case("Héllö_Wörld") == "héllöwörld"


# Test set_log_level
def test_set_log_level_given_valid_level_when_set_then_level_changed():
    utils.set_log_level("debug")
    assert utils.logger.level == logging.DEBUG
    utils.set_log_level("INFO")
    assert utils.logger.level == logging.INFO


def test_set_log_level_given_case_variations_when_set_then_works():
    utils.set_log_level("Debug")
    assert utils.logger.level == logging.DEBUG
    utils.set_log_level("ERROR")
    assert utils.logger.level == logging.ERROR


# Test set_logger
def test_set_logger_given_new_logger_when_configured_then_has_handler():
    test_logger = utils.logging.getLogger("test_logger")
    utils.set_logger(test_logger)
    assert len(test_logger.handlers) == 1
    assert test_logger.propagate is False


def test_set_logger_given_existing_handler_when_configured_then_no_duplicate():
    test_logger = logging.getLogger("test_logger2")
    test_logger.addHandler(logging.StreamHandler())
    utils.set_logger(test_logger)
    assert len(test_logger.handlers) == 1  # Original handler replaced?
