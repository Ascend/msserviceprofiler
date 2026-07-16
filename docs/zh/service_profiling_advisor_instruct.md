# 服务化专家建议工具

## 简介

- 服务化专家建议工具（Service Profiling Advisor）基于 MindIE Service 服务化框架，及 benchmark 的输出结果，可以一键式给出调参建议，提供给用户作为调优参考。工具基于 benchmark 的 instance 输出结果、MindIE Service 的 config.json 配置、NPU显存情况、部署模型等信息，综合分析给出 config.json 中 maxBatchSize、maxPrefillBatchSize 等配置的调参建议，用于提高 TTFT / Throughput 等性能优化指标。
- **注意：由于 CPU、内存等硬件差异，网络环境等不同，以及模型参数配置的细节不同等，当前建议值不能保证性能一定有提升，需要实际修改后验证。**

## 产品支持情况

> **说明：** 昇腾产品的具体型号，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》。

|产品类型| 是否支持 |
|--|:----:|
|Ascend 950 系列产品|×|
|Atlas A3 训练系列产品/Atlas A3 推理系列产品|√|
|Atlas A2 训练系列产品/Atlas A2 推理系列产品|√|
|Atlas 200I/500 A2 推理产品|√|
|Atlas 推理系列产品|√|
|Atlas 训练系列产品|x|

## 使用前准备

### 环境准备

- 准备一台昇腾Atlas 800I A2 训练系列的NPU服务器。
- **Python环境**：需要Python 3.10或更高版本。
- **依赖包安装**：

```bash
pip install scipy loguru pandas psutil  # 安装必要的依赖
```

### 数据准备

- MindIE benchmark 结果输出正常，生成的instance文件夹放置路径为/your/path/instance/。
- MindIE Service config.json 文件配置正确，一般位于/usr/local/Ascend/mindie/latest/mindie-service/conf目录下。

## 工具安装

- **源码安装**：服务化专家建议工具依赖服务化工具作为入口，如果没有安装服务化工具，请先完成[msServiceProfiler工具](msserviceprofiler_install_guide.md)的安装。

```bash
git clone https://gitcode.com/Ascend/msserviceprofiler.git  # 如已拉取，则不用重复拉取
cd msserviceprofiler/msservice_advisor
pip install .
msserviceprofiler advisor -h
```

## 工具卸载

```bash
pip uninstall msservice_advisor
```

## 功能介绍

### 功能说明

- **使用场景一（根据 NPU 显存、输入输出长度、模型大小推荐 decode 的 `maxBatchSize`）**
  - 需要提供 `instance` 文件夹，或手动指定输入输出的 token 长度 `-in, --input_token_num` 以及 `-out, --output_token_num`。
  - 需要提供 MindIE Service config.json 文件，以获取模型路径。
  - 需要 MindIE Service config.json 中配置的 `npuDeviceIds` 对应的 NPU 显存占用贴近拉起 MindIE Service 前的实际占用情况，或显式指定 MindIE Service config.json 中的 `npuMemSize`。
- **使用场景二（根据 benchmark 输出的 `instance` 结果，拟合数据并给出 `maxBatchSize` 以及 `maxPrefillBatchSize` 建议值）**
  - 需要提供 `instance` 文件夹，且其中样本量不少于1000条。
  - 如果同时提供了 `使用场景一` 需要的数据，其中的 `maxBatchSize` 会综合考虑 `使用场景一` 的建议值。

### 注意事项

**安全警告：请勿以 root 用户身份运行此工具。使用过高权限执行操作可能危及系统安全，建议使用普通用户账户运行。**

### 命令格式

```bash
# 指定输入输出的 token 长度 -in, --input_token_num 以及 -out, --output_token_num
msserviceprofiler advisor -in 4096 -out 256

# 或提供 instance 文件夹
msserviceprofiler advisor -i /your/path/instance/
```

### 参数说明

| 参数                 | 可选/必选 | 说明                                                            |
| -------------------- | --------- | --------------------------------------------------------------- |
| -i 或 --instance_path  | 可选        | benchmark 输出的 instance 路径，不输入则默认不读取其中相关信息用于分析。  |
| -s 或 --service_config_path  | 可选        | MindIE Service 路径或 config.json 文件路径，默认值为 MindIE Service 的环境变量 `MIES_INSTALL_PATH`，如果均未配置则使用 /usr/local/Ascend/mindie/latest/mindie-service。 |
| -t 或 --target         | 可选        | 调参指标。可选值：<br> • ttft: 首token时延。<br> • firsttokentime: 首token时延。<br> • throughput：吞吐。<br> 默认值为ttft。       |
| -m 或 --target_metrics | 可选        | 调参指标的具体项。可选值：<br> • average：平均值。<br> • max：最大值。<br> • min：最小值。<br> • P75：百分之75分位值。<br> • P90：百分之90分位值。<br> • SLO_P90：满足特定SLO约束条件下百分之90的分位值。<br> • P99：百分之99分位值。<br> • N：百分之N分位值。<br>默认值为average。 |
| -l 或 --log_level  | 可选        | 日志级别。可选值：<br> • debug：调试级别日志。<br> • info：执行信息级别日志。<br> • warning：告警级别日志。<br> • error：错误级别日志。<br> • fatal：致命级别日志。<br> • critical：关键级别日志。<br>默认值为info。  |
| -in 或 --input_token_num  | 可选        | 请求输入长度，需为正整数。不输入则默认从benchmark的instance结果中获取。 |
| -out 或 --output_token_num  | 可选        | 请求输出长度，需为正整数。不输入则默认为 MindIE Service config.json的maxIterTimes值。 |
| -tp 或 --tp  | 可选        | tp域大小，需为正整数。不输入则默认从 MindIE Service config.json文件中获取，未取到则默认为1。 |

### 使用示例

- **使用场景一**：输入 -i 参数或 -in 参数，MindIE Service config.json 中相关参数配置正确，并且满足服务化配置的可用 NPU 显存不为 0（即上述[功能说明-使用场景一](#功能说明)的第三点）。

```bash
msserviceprofiler advisor -in 4096 -out 256
```

- **使用场景二**：根据 `-i, --instance_path` 指定的 benchmark 输出 `instance` 结果，拟合数据并给出 `maxBatchSize` 以及 `maxPrefillBatchSize` 建议值，其中 `maxBatchSize` 会综合考虑 `建议结果1` 的建议值。

```bash
msserviceprofiler advisor -i /your/path/instance/
```

### 输出说明

专家建议命令执行完成后输出调参建议，结果如下：

- **使用场景一**
  - 结果表示根据当前可用显存信息、模型结构信息、MindIE Service config.json配置信息及请求输入输出长度等情况综合考虑，计算出当前 MindIE Service config.json中的maxBatchSize的建议取值范围。
  - 建议用户根据下述提示，将 MindIE Service config.json中的maxBatchSize设置为平均值大小，maxPrefillBatchSize设置为maxBatchSize的一半，重新拉起服务化运行，观察性能是否提升。
  - 若性能有提升，则可尝试逐渐向range中的最大值靠近，观察性能指标变化情况。
  - 若maxBatchSize值设置过大，则会导致模型拉起失败，此时应当将该值向range中的最小值靠近，直到模型能成功拉起。
  - maxPrefillBatchSize通常都设置为maxBatchSize的一半。

```text
# msservice_advisor_logger - INFO - </think>
# msservice_advisor_logger - INFO -
# msservice_advisor_logger - INFO - <advice>
# msservice_advisor_logger - INFO - [config] maxBatchSize
# msservice_advisor_logger - INFO - [advice] 取值范围为 [xx, xx]，平均值为 xx
# msservice_advisor_logger - INFO - [reason] 经过对当前显存信息的计算，建议将maxBatchSize的值设置为平均值大小，并逐渐向范围最大值调整，以占满整个显存
# msservice_advisor_logger - INFO - </advice>
```

- **使用场景二**
  - 结果给出 `maxBatchSize` 以及 `maxPrefillBatchSize` 建议值，其中 `maxBatchSize` 会综合考虑 `建议结果1` 的建议值。
  - **可尝试将该推荐值应用到 `config.json` 中，并重新验证性能查看是否有所提升，如果结果不理想，可尝试只应用其中一个值，并验证推理性能。**
  - 该方式下同时会生成拟合数据图像，用于查看拟合数据是否合理。

```text
# msservice_advisor_logger - INFO - 拟合画图路径：func_curv_031734.png
# msservice_advisor_logger - INFO - <think>
# ...
# msservice_advisor_logger - INFO - </think>
# msservice_advisor_logger - INFO -
# msservice_advisor_logger - INFO - <advice>
# msservice_advisor_logger - INFO - [config] maxBatchSize
# msservice_advisor_logger - INFO - [advice] 尝试设置为 25，原值50
# msservice_advisor_logger - INFO - [reason] 经过当前不同batch的时延数据，通过函数拟合分析，建议最优batch_size
# msservice_advisor_logger - INFO -
# msservice_advisor_logger - INFO - [config] maxPrefillBatchSize
# msservice_advisor_logger - INFO - [advice] 尝试设置为 50，原值100
# msservice_advisor_logger - INFO - [reason] 经过当前不同batch的时延数据，通过函数拟合分析，建议最优batch_size
# msservice_advisor_logger - INFO -
# msservice_advisor_logger - INFO - </advice>
```
