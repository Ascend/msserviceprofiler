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

from ms_service_profiler import Profiler, Level
from ms_service_profiler.patcher.core.module_hook import patcher

from .utils import classify_requests


# 延迟导入避免循环依赖；model_handlers 不导入本模块
def _get_state():
    from .model_handlers import _get_state as _get

    return _get()


def _normalize_req_id(req):
    if isinstance(req, dict):
        rid = req.get("rid")
        if rid is not None:
            return rid
        return None
    return req


@patcher(
    hook_points=("vllm_ascend.worker.model_runner_v1", "NPUModelRunner.propose_draft_token_ids"),
    min_version="0.9.1",
)
def propose_draft_token_ids_npu(original_func, this, *args, **kwargs):
    """用 specDecoding span 包裹草稿模型执行，耗时由 Profiler 的 span 起止自动记录。"""
    scheduler_output = args[2] if len(args) > 2 else None
    scheduled_spec = getattr(scheduler_output, "scheduled_spec_decode_tokens", None) if scheduler_output else None
    if not scheduled_spec or not isinstance(scheduled_spec, dict):
        return original_func(this, *args, **kwargs)

    try:
        state = _get_state()
        request_id_list, request_id_with_iter_list, batch_type = classify_requests(state, scheduler_output)
    except Exception:
        return original_func(this, *args, **kwargs)

    if not request_id_with_iter_list:
        return original_func(this, *args, **kwargs)

    state.mtp_num_draft_by_req = {str(req_id): len(tokens) for req_id, tokens in scheduled_spec.items()}

    spec_res_list = []
    for res in request_id_with_iter_list:
        rid = res.get("rid")
        if rid is None:
            continue
        rid_str = str(rid)
        spec_tokens = len(scheduled_spec.get(rid_str, scheduled_spec.get(rid, [])))
        spec_res_list.append(
            {
                "rid": rid,
                "iter": res.get("iter"),
                "type": res.get("type"),
                "num_scheduled_tokens": spec_tokens,
                "num_prompt_tokens": res.get("num_prompt_tokens"),
                "num_computed_tokens": spec_tokens,
                "num_spec_output_tokens": spec_tokens,
                "num_spec_accepted_tokens": 0,  # propose 时尚未执行 target，无法得知
            }
        )

    prof_spec = Profiler(Level.INFO).domain("Execute")
    prof_spec.res(spec_res_list)
    prof_spec.attr("batch_type", batch_type)
    prof_spec.attr("accepted_ratio", 0.0)
    prof_spec.attr("accepted_ratio_per_pos", {})
    prof_spec.span_start("specDecoding")
    try:
        return original_func(this, *args, **kwargs)
    finally:
        prof_spec.span_end()


def _read_num_accepted_from_output_token_ids(output_token_ids, req_ids):
    """从 rejection sampler 原始输出读取每请求 accepted 数。

    output_token_ids 的每行形状为 [max_spec_len + 1]，占位符为 -1。
    该行非占位符 token 数 = accepted + 1（最后一个是 recovered 或 bonus），故 accepted = max(valid_count - 1, 0)。
    """
    if output_token_ids is None or not req_ids:
        return {}
    try:
        if hasattr(output_token_ids, "detach"):
            arr = output_token_ids.detach().cpu().numpy()
        elif hasattr(output_token_ids, "cpu"):
            arr = output_token_ids.cpu().numpy()
        else:
            return {}
        batch = min(len(req_ids), int(arr.shape[0]))
        accepted = {}
        for i in range(batch):
            valid_count = int((arr[i] != -1).sum())
            rid = _normalize_req_id(req_ids[i])
            accepted[str(rid)] = max(valid_count - 1, 0)
        return accepted
    except Exception:
        return {}


@patcher(
    hook_points=[
        ("vllm_ascend.sample.rejection_sampler", "AscendRejectionSampler.forward"),
        ("vllm_ascend.sample.rejection_sampler", "rejection_sample"),
    ],
    min_version="0.9.1",
)
def capture_rejection_output(original_func, *args, **kwargs):
    """从 rejection sampler 的原始输出解析每请求 accepted 数并写入 state，供 execute_model_runner 打出 spec_decode_accepted_by_req。类方法 forward 与函数 rejection_sample 复用同一 handler。"""
    ret = original_func(*args, **kwargs)
    try:
        state = _get_state()
        req_ids = getattr(state, "request_id_list", None) or []
        accepted_by_req = _read_num_accepted_from_output_token_ids(ret, req_ids)
        if accepted_by_req:
            state.mtp_num_accepted_by_req = accepted_by_req
    except Exception:
        return ret
    return ret
