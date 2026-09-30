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

import json
import numpy as np

from ms_service_profiler.data_source.db_data_source import _extract_spec_decode_accepted_from_msg


class TestExtractSpecDecodeAcceptedFromMsg:
    """测试 _extract_spec_decode_accepted_from_msg"""

    def test_none_returns_none(self):
        assert _extract_spec_decode_accepted_from_msg(None) is None

    def test_float_nan_returns_none(self):
        assert _extract_spec_decode_accepted_from_msg(float("nan")) is None
        assert _extract_spec_decode_accepted_from_msg(np.nan) is None

    def test_non_string_returns_none(self):
        assert _extract_spec_decode_accepted_from_msg(123) is None
        assert _extract_spec_decode_accepted_from_msg({}) is None

    def test_string_not_starting_with_brace_returns_none(self):
        assert _extract_spec_decode_accepted_from_msg("") is None
        assert _extract_spec_decode_accepted_from_msg("  ") is None
        assert _extract_spec_decode_accepted_from_msg("no json") is None

    def test_valid_json_object_without_key_returns_none(self):
        assert _extract_spec_decode_accepted_from_msg('{"other": 1}') is None

    def test_valid_json_with_key_none_returns_none(self):
        assert _extract_spec_decode_accepted_from_msg('{"spec_decode_accepted_by_req": null}') is None

    def test_valid_json_with_dict_value_returns_json_string(self):
        msg = '{"spec_decode_accepted_by_req": {"req_1": 2, "req_2": 1}}'
        out = _extract_spec_decode_accepted_from_msg(msg)
        assert out is not None
        assert json.loads(out) == {"req_1": 2, "req_2": 1}

    def test_valid_json_with_non_dict_value_returns_value_as_is(self):
        msg = '{"spec_decode_accepted_by_req": "already_string"}'
        assert _extract_spec_decode_accepted_from_msg(msg) == "already_string"

    def test_invalid_json_returns_none(self):
        assert _extract_spec_decode_accepted_from_msg("{invalid") is None
        assert _extract_spec_decode_accepted_from_msg('{"spec_decode_accepted_by_req": }') is None

    def test_json_top_level_not_dict_returns_none(self):
        assert _extract_spec_decode_accepted_from_msg("[1,2,3]") is None
