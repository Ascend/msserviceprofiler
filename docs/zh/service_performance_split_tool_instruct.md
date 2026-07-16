# 服务化拆解工具

## 简介

服务化拆解工具（Service Performance Split Tool）基于msServiceProfiler工具采集的性能数据拆解服务化Batch执行中各阶段耗时，如组Batch、数据下发、模型执行、数据接收等。通过拆解识别性能瓶颈，方便开发人员优化框架。

**基本概念**

- `prefill batch`: Prefill阶段是处理用户输入prompt的初始阶段，在这个阶段，模型需要处理整个输入序列，计算并生成第一个输出token。该阶段执行的batch叫做prefill batch。
- `decode batch`: Decode阶段模型逐个生成后续的输出token，每次生成一个token。相比Prefill阶段，Decode阶段的每次迭代计算量较小，但由于需要逐个生成token，可能会有很多次迭代。该阶段执行的batch叫做decode batch。

## 产品支持情况<a name="ZH-CN_TOPIC_0000002479925980"></a>

> [!NOTE]
>
>昇腾产品的具体型号，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》

|产品类型| 是否支持 |
|--|:----:|
|Ascend 950 系列产品|×|
|Atlas A3 训练系列产品/Atlas A3 推理系列产品|√|
|Atlas A2 训练系列产品/Atlas A2 推理系列产品|√|
|Atlas 200I/500 A2 推理产品|√|
|Atlas 推理系列产品|√|
|Atlas 训练系列产品|x|

> [!NOTE]
> 
>针对Atlas A2 训练系列产品/Atlas A2 推理系列产品，当前仅支持该系列产品中的Atlas 800I A2 推理服务器。
>针对Atlas 推理系列产品，当前仅支持该系列产品中的Atlas 300I Duo 推理卡+Atlas 800 推理服务器（型号：3000）。

## 使用前准备

**环境准备**

完成[msServiceProfiler工具](msserviceprofiler_install_guide.md)的安装。

**版本配套关系**

| 服务化拆解工具 |     CANN     |     MindIE     |
|:-------------:|:------------:|:--------------:|
|     依赖版本      | ≥ CANN 8.2.RC1 | ≥ MindIE 2.1.RC1 |

## 功能介绍

### 功能说明

细粒度拆解服务化性能数据。

**注意事项**

无

### 命令格式

```bash
msserviceprofiler split 
--input-path /path/to/input 
[--output-path path/to/output] 
[--log-level level] 
[--prefill-number prefill_number] 
[--decode-number decode_number]
{
  --prefill-batch-size prefill_batch_size 
  --prefill-rid prefill_rid
  --decode-batch-size decode_batch_size 
  --decode-rid decode_rid
}
```

可选字段用 [] 表示，{} 代表必须从其中选择一个参数。

### 参数说明

| 参数                 | 说明                                                            |是否必选|
| -------------------- | --------------------------------------------------------------- |-----|
| --input-path | 指定性能数据所在路径  |是|
| --output-path | 指定拆解后文件生成路径，默认为当前路径下 output 文件夹 |否|
| --log-level  | 日志级别，可选值debug,info,warning,error,fatal,critical，默认info  |否|
| --prefill-batch-size  | 指定拆解的Prefill batch的batch_size大小，该值可以从batch.csv中的`batch_size`字段中获取，默认值为0 ，代表不执行 prefill性能拆解 |否|
| --prefill-number  | 指定拆解的Prefill batch的数量，用于统计执行时间的最大值、最小值、平均值和标准差，默认值为1 |否|
| --prefill-rid  | 指定拆解的Prefill batch的请求id，该值可以从request.csv 中的`http_rid`字段中获取，默认值为-1，代表不执行prefill性能拆解 |否|
| --decode-batch-size | 指定拆解的Decode batch的batch_size大小，该值可以从batch.csv中的`batch_size`字段中获取，默认值为0，代表不执行 decode性能拆解 |否|
| --decode-number  | 指定拆解的Decode batch的数量，用于统计执行时间的最大值、最小值、平均值和标准差，默认值为1 |否|
| --decode-rid  | 指定拆解的Decode batch的请求id，该值可以从request.csv 中的`http_rid`字段中获取，默认值为-1，代表不执行decode性能拆解 |否|

### 使用示例

- **使用场景 1，指定`batch_size`大小拆解**
  - 如拆解100个`batch_size`为1的`prefill batch`数据，可执行：

    ```sh
    msserviceprofiler split --input-path /path/to/input --output-path /path/to/output/ --prefill-batch-size 1 --prefill-number 100
    ```

    执行完毕在结果路径下生成输出文件`prefill.csv`。
  - 拆解50个`batch_size`为10的`decode batch`数据，可执行：

    ```sh
    msserviceprofiler split --input-path /path/to/input --output-path /path/to/output/ --decode-batch-size 10 --decode-number 50
    ```

    执行完毕在结果路径下生成输出文件`decode.csv`。
- **使用场景 2，指定`rid`拆解**
  - 拆解prefill数据:

    ```sh
    msserviceprofiler split --input-path /path/to/input --output-path /path/to/output/ --prefill-rid efcas2d
    ```

    执行完毕在结果路径下生成输出文件`prefill.csv`。
  - 拆解decode数据:

    ```sh
    msserviceprofiler split --input-path /path/to/input --output-path /path/to/output/ --decode-rid efcas2d
    ```

    执行完毕在结果路径下生成输出文件`decode.csv`。

### **输出说明**

- `prefill.csv`

   | 字段                 | 说明                                            |
  | -------------------- | ----------------------------------------------- |
  | name | 标注batch内事件名称  |
  | during_time(ms) | 当前batch事件的执行时间，单位ms |
  | max  | 事件的最大执行时间，单位ms  |
  | min  | 事件的最小执行时间，单位ms  |
  | mean  | 事件的平均执行时间，单位ms  |
  | std  | 事件执行时间的标准差，单位ms  |
  | pid  | 事件的进程号  |
  | tid  | 事件的线程号  |
  | start_time(ms)  | 当前batch事件的开始时间，显示为时间戳，单位ms  |
  | end_time(ms)  | 当前batch事件的结束时间，显示为时间戳，单位ms  |
  | rid  | 请求ID  |

- `decode.csv`
与 `prefill.csv` 格式相同， `decode.csv` 不含 `rid` 列。
- 采集domain域与解析结果对照表

  | 解析结果                 | 采集domain域                                 |
  | -------------------- | ----------------------------------------------- |
  | prefill.csv | "Request; BatchSchedule; ModelExecute"  |
  | decode.csv | "BatchSchedule; ModelExecute"  |
