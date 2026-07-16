# 服务化性能数据比对工具

## 简介

服务化性能数据比对工具（msServiceProfiler Compare Tool）：用于对比分析大模型推理服务化场景中不同版本或不同框架的性能数据差异，支持生成可视化报告和结构化数据输出。

**基本概念**

- 服务总体维度：包含服务级吞吐量、时延等核心指标。
- 请求维度：单个请求的完整处理周期指标。
- 批处理维度：批处理任务的分段性能指标。

## 产品支持情况
>
> **说明：** <br>
>昇腾产品的具体型号，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》。

|产品类型| 是否支持 |
|--|:----:|
|Ascend 950 系列产品|×|
|Atlas A3 训练系列产品/Atlas A3 推理系列产品|√|
|Atlas A2 训练系列产品/Atlas A2 推理系列产品|√|
|Atlas 200I/500 A2 推理产品|√|
|Atlas 推理系列产品|√|
|Atlas 训练系列产品|x|

> **须知：** <br>
>针对Atlas A2 训练系列产品/Atlas A2 推理系列产品，当前仅支持该系列产品中的Atlas 800I A2 推理服务器。<br>
>针对Atlas 推理系列产品，当前仅支持该系列产品中的Atlas 300I Duo 推理卡+Atlas 800 推理服务器（型号：3000）。

## 使用前准备

- 完成[msServiceProfiler工具](msserviceprofiler_install_guide.md)的安装。  
- 如需算子比对功能，则先完成[msprof-analyze工具](https://gitcode.com/Ascend/msprof-analyze)的安装。

**数据准备**

- 完成服务化性能数据采集，获得两份待比对的性能数据，具体采集方式请参见[服务化调优工具](https://gitcode.com/Ascend/msserviceprofiler/blob/master/docs/zh/msserviceprofiler_serving_tuning_instruct.md)。  
- 算子比对场景要求使用[服务化调优工具](https://gitcode.com/Ascend/msserviceprofiler/blob/master/docs/zh/msserviceprofiler_serving_tuning_instruct.md)采集性能数据时，配置acl_task_time参数值为3，确保采集的性能数据文件目录中包含以_ascend_pt为后缀的算子数据文件。

**约束**

- 仅支持CANN 8.1.RC1及以上版本。
- 需配合MindIE 2.0.RC1及以上使用。
- 输入数据必须通过msServiceProfiler工具解析生成。

## 功能介绍

**功能说明**

提供服务化场景的性能数据差异比对，支持生成Excel格式的结构化比对报告。

**命令格式**

```bash
msserviceprofiler compare <input_path> <golden_path> [--output-path <output_path>] [--log-level <log_level>]
```

**参数说明**

| 参数          | 可选/必选 | 说明                                                         |
| ------------- | --------- | ------------------------------------------------------------ |
| input_path    | 必选      | 待分析数据目录（需包含msServiceProfiler解析后的数据）。      |
| golden_path   | 必选      | 基准数据目录。                                               |
| --output-path | 可选      | 结果输出目录（默认：./compare_result）。                     |
| --log-level   | 可选      | 设置日志级别，取值为：<br>&#8226; debug：调试级别。该级别的日志记录了调试信息，便于开发人员或维护人员定位问题。<br>&#8226; info：正常级别。记录工具正常运行的信息。默认值。<br>&#8226; warning：警告级别。记录工具和预期的状态不一致，但不影响整个进程运行的信息。<br>&#8226; error：一般错误级别。<br>&#8226; critical：严重错误级别。<br>&#8226; fatal：致命错误级别。 |

**使用示例**

```bash
# 执行默认比对
msserviceprofiler compare ./profiling_data/v1 ./profiling_data/v2

```

## 输出结果文件说明

**输出目录说明**

span_comparation_result.csv文件展示所有数据pair的绝对误差和相对误差。包含多个span名称，展示不同span时间差异。

输出目录结构如下：

```ColdFusion
|- output_path
    |- span_comparation_result.csv
    
```

**字段说明**  

**表1** span_comparation_result.csv

|字段| 说明                                                 |
|--|----------------------------------------------------|
|Golden-AVG| 标杆数据的平均值。                                          |
|Golden-P50| 标杆数据的50分位值。                                        |
|Golden-P90| 标杆数据的90分位值。                                        |
|Input-AVG| 比对数据的平均值。                                          |
|Input-P50| 比对数据的50分位值。                                        |
|Input-P90| 比对数据的90分位值。                                        |
|DIFF-AVG| 比对数据和标杆数据平均值之间的差异。DIFF = Input - Golden            |
|DIFF-P50| 比对数据和标杆数据50分位值之间的差异。                               |
|DIFF-P90| 比对数据和标杆数据90分位值之间的差异。                               |
|RDIFF-AVG(%)| 比对数据和标杆数据平均值之间的差异。RDIFF = (Input - Golden) / Golden |
|RDIFF-P50(%)| 比对数据和标杆数据50分位值之间的差异。                            |
|RDIFF-P90(%)| 比对数据和标杆数据90分位值之间的差异。                            |
