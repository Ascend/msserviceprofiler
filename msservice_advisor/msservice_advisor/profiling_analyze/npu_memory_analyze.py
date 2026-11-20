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

import math
import os
import re
import subprocess  # nosec B404: invokes fixed npu-smi queries

from msguard import validate_params, Rule

from .register import register_analyze, answer, GLOBAL_DATA
from .utils import logger, SUGGESTION_TYPES, BYTES_TO_GB, MAX_DEVICE_ID_LIST_LENGTH
from .utils import read_csv_or_json


def get_directory_size(path):
    total_size = 0
    for dirpath, _, filename in os.walk(path):
        for f in filename:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)

    return total_size / BYTES_TO_GB


def get_benchmark_token_num(benchmark, info_name):
    token_num = benchmark.get("result_perf", {}).get(info_name, {}).get('average', "0")
    return int(float(token_num))


def extract_token_num(benchmark, input_params):
    """
    获取请求输入参数：
    input_token_num: 输入长度。优先从用户输入中获取; 用户未输入从benchmark中获取
    avg_token_num: 平均输出长度。优先从benchmark中获取; 未获取到则与用户输入相等
    """
    # get from benchmark
    input_token_num = input_params.input_token_num
    avg_token_num = input_params.output_token_num
    input_token_num = get_benchmark_token_num(benchmark, 'InputTokens') if input_token_num <= 0 else input_token_num
    avg_token_num = get_benchmark_token_num(benchmark, 'GeneratedTokens') if avg_token_num <= 0 else avg_token_num
    logger.info(f"input_token_num: {input_token_num}, avg_output_token_num: {avg_token_num}")

    if input_token_num <= 0:
        logger.warning("input_token_num not provided and failed extracting from benchmark. Skipping now")
    if avg_token_num <= 0:
        logger.warning("output_token_num not provided and failed extracting from benchmark. Skipping now")
    return input_token_num, avg_token_num


def get_schedule_config_info(backend_config, output_token_num):
    schedule_config = backend_config.get('ScheduleConfig', {})
    cache_block_sizes = schedule_config.get('cacheBlockSize', {})

    if not cache_block_sizes:
        raise Exception("mindie-server config.json missing 'cacheBlockSize'.")

    if output_token_num == 0:
        output_token_num = int(schedule_config['maxIterTimes'])  # 未取到则打断

    logger.info(f"output_token_num: {output_token_num}, cache_block_sizes: {cache_block_sizes}")
    return output_token_num, cache_block_sizes


def get_model_config_info(model_configs, tp, npu_device_ids):
    if tp == 0:
        tp_config = model_configs.get('tp')
        tp = int(tp_config) if tp_config else len(npu_device_ids)
        tp = max(1, tp)

    model_weight_path = model_configs.get('modelWeightPath')
    if not model_weight_path:
        raise Exception("mindie-server config.json missing 'modelWeightPath'.")

    logger.info(f"tp: {tp}, model_weight_path: {model_weight_path}")
    return tp, model_weight_path


def extract_server_config_params(server_config, output_token_num, tp=1):
    """
    获取mindie-server config.json中的参数信息
    output_token_num: 请求输出长度。优先从用户输入中获取; 用户未输入等于conf中的maxIterTimes。
    tp: tp域信息。优先从优先从用户输入中获取; 用户未输入等于conf中的tp; 如果conf未配置tp, 则默认为使用的npu卡数。
    cache_block_sizes: cache块大小,一般为128。从conf中的cacheBlockSize获取。
    npu_device_ids: 使用npu的卡号。从config中的npuDeviceIds获取。
    model_weight_path: 使用的模型权重路径, 从conf中的modelWeightPath获取。
    npu_mem_size: 单卡预留给kvcache的显存, 单位GB, 从conf中的npuMemSize获取。获取为-1则需要重新计算显存大小。
    sp: Sequence Parallelism策略, 对Sequence进行切分, 从conf中的sp获取, 若未配置默认为1。
    """
    backend_config = server_config.get('BackendConfig', {})
    output_token_num, cache_block_sizes = get_schedule_config_info(backend_config, output_token_num)

    npu_device_ids = backend_config.get('npuDeviceIds', [[]])[0]
    if not npu_device_ids or len(npu_device_ids) == 0 or len(npu_device_ids) >= MAX_DEVICE_ID_LIST_LENGTH:
        raise Exception("mindie-server config.json missing 'npuDeviceIds' or it's invalid.")
    logger.info(f"npu_device_ids: {npu_device_ids}")

    model_configs = backend_config.get('ModelDeployConfig', {}).get('ModelConfig', [[]])[0]
    tp, model_weight_path = get_model_config_info(model_configs, tp, npu_device_ids)

    return dict(
        output_token_num=output_token_num,
        cache_block_sizes=cache_block_sizes,
        npu_device_ids=npu_device_ids,
        tp=tp,
        model_weight_path=model_weight_path,
        npu_mem_size=model_configs.get('npuMemSize', 0),
        sp=model_configs.get('sp', 1),
    )


@validate_params({'model_weight_path': Rule.input_dir_traverse})
def extract_model_config_params(model_weight_path):
    """
    获取模型参数信息，及模型权重文件总大小
    """
    # get model config.json
    model_config_file = os.path.join(model_weight_path, "config.json")
    logger.info(f"model config path: {model_config_file}")
    model_params = read_csv_or_json(model_config_file)

    # caculate model weight size
    model_weight_size = get_directory_size(model_weight_path)
    logger.info(f"model wight size: {model_weight_size}GB")

    return model_params, model_weight_size


def check_vaild_smi_output(output):
    header_line = None
    for line in output.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith("NPU ID"):
            header_line = stripped_line
            break
    if not header_line:
        raise ValueError("npu-smi info -m output error.")

    # parse column indices
    headers = re.split(r'\s{2,}', header_line)
    col_map = {name: idx for idx, name in enumerate(headers)}

    # vaildate required columns
    requlire_cols = ["NPU ID", "Chip Logic ID"]
    for col in requlire_cols:
        if col not in col_map:
            raise ValueError(f"Missing required column: {col}")

    return header_line, col_map


def get_npu_ids_map():
    """
    使用 npu-smi -m 获取信息
    返回 dict {npu_id: chip_logic_id}, 其中chip_logic_id即为device id
    """
    cmd = ['npu-smi', 'info', '-m']
    try:
        output = subprocess.check_output(  # nosec B603: fixed executable and arguments
            cmd, text=True, stderr=subprocess.STDOUT
        )
    except Exception:
        raise RuntimeError("Command 'npu-smi info -m' failed")

    header_line, col_map = check_vaild_smi_output(output)

    npu_idx = col_map["NPU ID"]
    logic_idx = col_map["Chip Logic ID"]

    npu_ids_map = {}
    for line in output.splitlines():
        # skip empty line and header
        if not line.strip() or line == header_line:
            continue

        # skip invalid columns
        cols = re.split(r'\s{2,}', line.strip())
        if len(cols) < max(npu_idx, logic_idx) + 1:
            continue

        npu_id = cols[npu_idx]
        logic_id = cols[logic_idx]

        if npu_id.isdigit() and logic_id.isdigit():
            npu_ids_map[int(logic_id)] = int(npu_id)

    logger.debug(f"npu_ids_map: {npu_ids_map}")
    return npu_ids_map


def cal_available_gm_memory(gm_capacity, gm_usage):
    if gm_capacity is None or gm_usage is None:
        return 0

    available_mem = gm_capacity * (1 - gm_usage / 100)
    return round(available_mem / 1024, 2)


def cal_npu_gm_memory(npu_id):
    """
    使用 npu-smi info -i {npu_id} -t usages 命令行获取单卡npu内存大小
    M Usage Rate(%): 当前npu占用内存
    M Capacity(MB): npu总内存
    返回 M Capacity * (1 - M Usage Rate)
    """
    try:
        cmd = ['npu-smi', 'info', '-i', str(npu_id), '-t', 'usages']
        output = subprocess.check_output(  # nosec B603: npu_id comes from validated config
            cmd, text=True, stderr=subprocess.STDOUT
        )

        gm_capacity = None
        gm_usage = None
        for line in output.splitlines():
            # Match M capacity line (e.g. "xxM Capacity(MB) : 65536")
            capacity_match = re.match(r"^[^M]*M Capacity\(MB\)\s*:\s*(\d+)\s*$", line.strip())
            if capacity_match:
                gm_capacity = int(capacity_match.group(1))
                continue

            # Match M Usage line (e.g. "xxM Usage Rate(%) : 5")
            usage_match = re.match(r"^[^M]*M Usage Rate\(%\)\s*:\s*(\d+)\s*$", line.strip())
            if usage_match:
                gm_usage = int(usage_match.group(1))
                continue

        return cal_available_gm_memory(gm_capacity, gm_usage)
    except Exception:
        logger.warning("Command npu-smi info -i $npu_id -t usages parse failed")
        return 0


def get_available_npu_memory(npu_device_ids):
    # get device-id to npu-id map
    npu_ids_map = get_npu_ids_map()
    if not npu_ids_map:
        raise Exception("parse npu-smi info -m failed.")

    available_npu_memory = float('inf')
    for npu_device_id in npu_device_ids:
        npu_id = npu_ids_map.get(int(npu_device_id), 0)
        pre_npu_memory = cal_npu_gm_memory(npu_id)
        available_npu_memory = min(available_npu_memory, pre_npu_memory)

    logger.debug(f"available_npu_memory: {available_npu_memory}")
    return available_npu_memory


def cal_npu_mem_size(server_params, model_weight_size):
    """
    优先从mindie-server config.json的npuMemSize获取, 若该值非法, 则使用公式计算
    计算显存公式：
    Floor[(单卡可用显存 - 权重/NPU卡数) * 系数]
    """
    # get from mindie server config, GB
    npu_mem_size = server_params.get('npu_mem_size', -1)
    if npu_mem_size > 0:
        logger.info(f"npu_mem_size got from server_params: {npu_mem_size}GB")
        return npu_mem_size
    if 'npu_device_ids' not in server_params:
        logger.error(f"npu_device_ids not found in server_params={server_params}")
        return 0

    npu_device_ids = server_params['npu_device_ids']
    if not isinstance(npu_device_ids, (list, tuple)) or len(npu_device_ids) == 0:
        logger.error(f"Empty or invalid npu_device_ids in server_params={server_params}")
        return 0
    npu_num = len(npu_device_ids)

    # calulate npu available memory size
    npu_available_mem = get_available_npu_memory(npu_device_ids)
    fixed_coefficent = 0.8
    npu_mem_size = (npu_available_mem - model_weight_size / npu_num) * fixed_coefficent
    npu_mem_size = max(math.floor(npu_mem_size), 0)

    logger.info(f"Free npu_memory_size for KV cache calculated by npu_device_ids={npu_device_ids}: {npu_mem_size}GB")
    return npu_mem_size


def get_model_param(model_params, param_name):
    param_value = model_params.get(param_name, 0)
    logger.debug(f"{param_name}: {param_value}")
    return param_value


def cal_total_block_num(npu_mem_size, server_params, model_params):
    """
    Total Block Num =
    Floor[npu显存/(模型网络层数*cacheBlockSize*模型注意力头数*注意力头大小*Cache类型字节数*Cache数)]
    其中, Cache数默认为2

    模型config中:
    num_hidden_layers: 模型网络层数
    num_attention_heads: 模型查询头数
    hidden_size: 模型隐藏层维度
    torch_dtype: Cache类型
    num_key_value_heads: kv键值头数
    """
    if npu_mem_size <= 0:
        raise Exception(
            "Available npu memory size is 0. "
            "You need to stop mindie-server process or choose other available npu devices."
        )

    tp = server_params['tp']  # tp checked before cannot be 0
    cache_block_sizes = server_params['cache_block_sizes']

    num_hidden_layers = get_model_param(model_params, 'num_hidden_layers')
    num_attention_heads = get_model_param(model_params, 'num_attention_heads')
    hidden_size = get_model_param(model_params, 'hidden_size')
    torch_dtype = get_model_param(model_params, 'torch_dtype')
    torch_dtype_size = 1 if torch_dtype == "uint8" else 2  # bf16 type dtype byte is 2

    # for MHA models, attention_size is hidden_size
    attention_size = hidden_size / tp
    num_key_value_heads = model_params.get('num_key_value_heads')
    if num_key_value_heads:
        logger.debug(f"num_key_value_heads:{num_key_value_heads}")

        # for GQA or MLA model, attention_size is num_key_value_heads plus attention_head_size
        if num_attention_heads <= 0:
            raise ValueError('Invalid num_attention_heads.')
        attention_head_size = hidden_size / num_attention_heads / tp
        attention_size = attention_head_size * num_key_value_heads
    logger.debug(f"attention_size: {attention_size}")

    denominator = num_hidden_layers * cache_block_sizes * attention_size * torch_dtype_size * 2
    if denominator <= 0:
        raise ValueError('Calculate total block num with invalid denominator.')

    return math.floor(npu_mem_size * BYTES_TO_GB / denominator)


def cal_block_nums(input_tokens: int, cache_block_size: int, output_tokens: int, avg_tokens: int):
    """
    所需最大Block Num = Ceil(输入token数/cache_block_size)+Celi(最大输出token数/cache_block_size)
    所需最小Block Num = Ceil(输入token数/cache_block_size)
    所需平均Block Num = Ceil(输入token数/cache_block_size)+Celi(平均输出token数/cache_block_size)
    """
    if any(arg <= 0 for arg in locals().values()):
        return 0, 0, 0

    input_block_num = math.ceil(input_tokens / cache_block_size)
    output_block_num = math.ceil(output_tokens / cache_block_size)
    avg_block_num = math.ceil(avg_tokens / cache_block_size)
    logger.debug(
        f"input_block_num: {input_block_num}, output_block_num: {output_block_num}, avg_block_num: {avg_block_num}"
    )

    # max, min, avg
    return input_block_num + output_block_num, input_block_num, input_block_num + avg_block_num


def cal_max_batch_size_range(total_block_num: int, max_block: int, min_block: int, avg_block: int, sp: int):
    """
    最小maxBatchSize = Floor[Total Block Num/(所需最大Block Num/SP)]
    最大maxBatchSize = Floor[Total Block Num/(所需最小Block Num/SP)]
    平均maxBatchSize = Floor[Total Block Num/(所需平均Block Num/SP)]
    """
    if any(arg <= 0 for arg in locals().values()):
        return 0, 0, 0

    logger.debug(f"sp: {sp}")
    return (
        total_block_num // math.ceil(max_block / sp),  # min
        total_block_num // math.ceil(min_block / sp),  # max
        total_block_num // math.ceil(avg_block / sp),  # avg
    )


def write_to_answer(min_batch, max_batch, avg_batch):
    if any(arg <= 0 for arg in locals().values()):
        return

    answer(
        suggesion_type=SUGGESTION_TYPES.config,
        suggesion_item="maxBatchSize",
        action=f"取值范围为 [{min_batch}, {max_batch}]，平均值为 {avg_batch}",
        reason="经过对当前显存信息的计算，建议将maxBatchSize的值设置为average大小，并逐渐向范围最大值调整，以占满整个显存",
    )


@register_analyze()
def find_max_batch_size_range(server_config, benchmark, input_params):
    # get input token number and average output token num
    input_token_num, avg_token_num = extract_token_num(benchmark, input_params)

    if not server_config:
        logger.warning("service_config_path is required calculating model weight size and others. Skipping now.")
        return

    # get server info from server config.json
    try:
        server_params = extract_server_config_params(server_config, input_params.output_token_num, input_params.tp)
    except Exception as e:
        logger.warning(f"Extract server config params failed due to {e}. Skipping now.")
        return

    if "model_weight_path" not in server_params:
        logger.warning("model_weight_path not found in service config.json. Skipping now.")
        return

    # get model info from model config.json
    try:
        model_params, model_weight_size = extract_model_config_params(server_params["model_weight_path"])
    except Exception as e:
        logger.warning(f"Invalid model weight due to {e}. Skipping now.")
        return

    # caculate npu memory
    try:
        npu_mem_size = cal_npu_mem_size(server_params, model_weight_size)
        total_block_num = cal_total_block_num(npu_mem_size, server_params, model_params)
        logger.debug(f"total_block_num:{total_block_num}")
    except Exception as e:
        logger.warning(f"Npu memory calculation failed due to {e}. Skipping now.")
        return

    # caculate block numbers
    max_block, min_block, avg_block = cal_block_nums(
        input_token_num, server_params['cache_block_sizes'], server_params['output_token_num'], avg_token_num
    )
    logger.info(f"max_block_num:{max_block}  min_block_num:{min_block}  avg_block_num:{avg_block}")

    # caculate max_batch_size
    min_batch, max_batch, avg_batch = cal_max_batch_size_range(
        total_block_num, max_block, min_block, avg_block, server_params['sp']
    )
    logger.info(f"max_batch_size:{max_batch}  min_batch_size:{min_batch}  avg_batch_size:{avg_batch}")

    write_to_answer(min_batch, max_batch, avg_batch)
    GLOBAL_DATA["maxBatchSize"] = {"min": min_batch, "max": max_batch, "avg": avg_batch}
