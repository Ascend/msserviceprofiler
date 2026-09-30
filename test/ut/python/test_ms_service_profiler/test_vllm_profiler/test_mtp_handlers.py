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

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import numpy as np

from ms_service_profiler.patcher.vllm.handlers.v1 import mtp_handlers


class TestNormalizeReqId:
    """测试 _normalize_req_id"""

    def test_dict_with_rid(self):
        assert mtp_handlers._normalize_req_id({"rid": "req_1"}) == "req_1"
        assert mtp_handlers._normalize_req_id({"rid": 123}) == 123

    def test_dict_without_rid_or_rid_none(self):
        assert mtp_handlers._normalize_req_id({}) is None
        assert mtp_handlers._normalize_req_id({"rid": None}) is None

    def test_non_dict_returns_as_is(self):
        assert mtp_handlers._normalize_req_id("req_2") == "req_2"
        assert mtp_handlers._normalize_req_id(456) == 456


class TestReadNumAcceptedFromOutputTokenIds:
    """测试 _read_num_accepted_from_output_token_ids"""

    def test_none_output_or_empty_req_ids_returns_empty(self):
        assert mtp_handlers._read_num_accepted_from_output_token_ids(None, ["r1"]) == {}
        assert mtp_handlers._read_num_accepted_from_output_token_ids(MagicMock(), []) == {}

    def test_tensor_like_with_detach_cpu_numpy(self):
        # 每行非 -1 的个数 = valid_count, accepted = valid_count - 1
        arr = np.array([[1, 2, 3, -1, -1], [1, 2, -1, -1, -1]], dtype=np.int64)  # 3 和 2 个有效 -> accepted 2, 1
        mock_tensor = MagicMock()
        mock_tensor.detach.return_value.cpu.return_value.numpy.return_value = arr
        req_ids = [{"rid": "a"}, "b"]
        result = mtp_handlers._read_num_accepted_from_output_token_ids(mock_tensor, req_ids)
        assert result == {"a": 2, "b": 1}

    def test_tensor_like_with_cpu_numpy_only(self):
        arr = np.array([[1, 2, -1]], dtype=np.int64)  # 2 有效 -> accepted 1
        mock_tensor = MagicMock()
        del mock_tensor.detach
        mock_tensor.cpu.return_value.numpy.return_value = arr
        result = mtp_handlers._read_num_accepted_from_output_token_ids(mock_tensor, ["x"])
        assert result == {"x": 1}

    def test_no_detach_no_cpu_returns_empty(self):
        mock_tensor = MagicMock(spec=[])
        result = mtp_handlers._read_num_accepted_from_output_token_ids(mock_tensor, ["r1"])
        assert result == {}

    def test_valid_count_zero_or_one_gives_zero_accepted(self):
        arr = np.array([[-1, -1, -1]], dtype=np.int64)  # 0 有效 -> accepted 0
        mock_tensor = MagicMock()
        mock_tensor.detach.return_value.cpu.return_value.numpy.return_value = arr
        result = mtp_handlers._read_num_accepted_from_output_token_ids(mock_tensor, ["r1"])
        assert result == {"r1": 0}

    def test_exception_returns_empty(self):
        mock_tensor = MagicMock()
        mock_tensor.detach.return_value.cpu.return_value.numpy.side_effect = RuntimeError("npu error")
        result = mtp_handlers._read_num_accepted_from_output_token_ids(mock_tensor, ["r1"])
        assert result == {}


class TestProposeDraftTokenIdsNpu:
    """测试 propose_draft_token_ids_npu"""

    def test_no_scheduler_output_calls_original(self):
        original = MagicMock(return_value="orig_ret")
        result = mtp_handlers.propose_draft_token_ids_npu(original, MagicMock(), "a", "b")  # args < 3
        original.assert_called_once()
        assert result == "orig_ret"

    def test_scheduler_output_without_scheduled_spec_calls_original(self):
        scheduler = MagicMock()
        del scheduler.scheduled_spec_decode_tokens
        original = MagicMock(return_value="ret")
        result = mtp_handlers.propose_draft_token_ids_npu(original, MagicMock(), "a", "b", scheduler)
        original.assert_called_once()
        assert result == "ret"

    def test_scheduled_spec_not_dict_calls_original(self):
        scheduler = MagicMock()
        scheduler.scheduled_spec_decode_tokens = "not_a_dict"
        original = MagicMock(return_value="ret")
        result = mtp_handlers.propose_draft_token_ids_npu(original, MagicMock(), "a", "b", scheduler)
        original.assert_called_once()
        assert result == "ret"

    def test_classify_requests_exception_calls_original(self):
        scheduler = MagicMock()
        scheduler.scheduled_spec_decode_tokens = {"r1": [1, 2, 3]}
        original = MagicMock(return_value="ret")
        with patch.object(mtp_handlers, "_get_state") as mock_state:
            mock_state.side_effect = RuntimeError("state error")
            result = mtp_handlers.propose_draft_token_ids_npu(original, MagicMock(), "a", "b", scheduler)
        original.assert_called_once()
        assert result == "ret"

    def test_empty_request_id_with_iter_list_calls_original(self):
        scheduler = MagicMock()
        scheduler.scheduled_spec_decode_tokens = {"r1": [1, 2]}
        original = MagicMock(return_value="ret")
        with patch.object(mtp_handlers, "_get_state"):
            with patch.object(mtp_handlers, "classify_requests") as mock_classify:
                mock_classify.return_value = ([], [], "Decode")  # request_id_with_iter_list 为空
                result = mtp_handlers.propose_draft_token_ids_npu(original, MagicMock(), "a", "b", scheduler)
        original.assert_called_once()
        assert result == "ret"

    def test_happy_path_sets_draft_and_calls_original(self):
        scheduler = MagicMock()
        scheduler.scheduled_spec_decode_tokens = {"req_1": [1, 2, 3], "req_2": [1, 2]}
        original = MagicMock(return_value="orig_ret")
        state = SimpleNamespace()
        with patch.object(mtp_handlers, "_get_state", return_value=state):
            with patch.object(mtp_handlers, "classify_requests") as mock_classify:
                mock_classify.return_value = (
                    [{"rid": "req_1"}, {"rid": "req_2"}],
                    [{"rid": "req_1", "iter": 0}, {"rid": "req_2", "iter": 0}],
                    "Decode",
                )
                with patch.object(mtp_handlers, "Profiler") as MockProfiler:
                    prof = MagicMock()
                    MockProfiler.return_value.domain.return_value = prof
                    result = mtp_handlers.propose_draft_token_ids_npu(original, MagicMock(), "a", "b", scheduler)
        assert state.mtp_num_draft_by_req == {"req_1": 3, "req_2": 2}
        original.assert_called_once()
        assert result == "orig_ret"
        prof.res.assert_called_once()
        prof.span_start.assert_called_once_with("specDecoding")
        prof.span_end.assert_called_once()

    def test_skips_res_with_rid_none(self):
        scheduler = MagicMock()
        scheduler.scheduled_spec_decode_tokens = {"req_1": [1, 2]}
        original = MagicMock(return_value="ret")
        state = SimpleNamespace()
        with patch.object(mtp_handlers, "_get_state", return_value=state):
            with patch.object(mtp_handlers, "classify_requests") as mock_classify:
                mock_classify.return_value = (
                    [{"rid": "req_1"}],
                    [{"rid": "req_1", "iter": 0}, {"rid": None, "iter": 0}],
                    "Decode",
                )
                with patch.object(mtp_handlers, "Profiler") as MockProfiler:
                    prof = MagicMock()
                    MockProfiler.return_value.domain.return_value = prof
                    mtp_handlers.propose_draft_token_ids_npu(original, MagicMock(), "a", "b", scheduler)
        assert prof.res.called, "prof.res should have been called with filtered spec_res_list"
        call_args = prof.res.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0]["rid"] == "req_1"


class TestCaptureRejectionOutput:
    """测试 capture_rejection_output"""

    def test_calls_original_and_returns_ret(self):
        original = MagicMock(return_value="rejection_ret")
        result = mtp_handlers.capture_rejection_output(original, "a", "b")
        original.assert_called_once_with("a", "b")
        assert result == "rejection_ret"

    def test_when_read_accepted_returns_empty_does_not_set_state(self):
        original = MagicMock(return_value=None)
        state = MagicMock()
        state.request_id_list = []
        state.mtp_num_accepted_by_req = None
        with patch.object(mtp_handlers, "_get_state", return_value=state):
            with patch.object(mtp_handlers, "_read_num_accepted_from_output_token_ids", return_value={}):
                mtp_handlers.capture_rejection_output(original, "a")
        assert state.mtp_num_accepted_by_req is None

    def test_when_read_accepted_returns_data_sets_state(self):
        original = MagicMock(return_value=MagicMock())
        state = MagicMock()
        state.request_id_list = ["r1", "r2"]
        with patch.object(mtp_handlers, "_get_state", return_value=state):
            with patch.object(mtp_handlers, "_read_num_accepted_from_output_token_ids") as mock_read:
                mock_read.return_value = {"r1": 2, "r2": 1}
                mtp_handlers.capture_rejection_output(original, "a")
        assert state.mtp_num_accepted_by_req == {"r1": 2, "r2": 1}

    def test_exception_in_try_does_not_raise(self):
        original = MagicMock(return_value=MagicMock())
        with patch.object(mtp_handlers, "_get_state", side_effect=RuntimeError("state err")):
            result = mtp_handlers.capture_rejection_output(original, "a")
        assert result == original.return_value
