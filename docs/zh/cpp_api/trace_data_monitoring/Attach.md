# Attach<a name="ZH-CN_TOPIC_0000002487000272"></a>

## 产品支持情况<a name="section13361171693320"></a>

> [!NOTE]
>
>昇腾产品的具体型号，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》

<!-- npu="950" id1 -->
- Ascend 950PR&950DT系列产品：不支持
<!-- end id1 -->
<!-- npu="A3" id2 -->
- Atlas A3系列产品：不支持
<!-- end id2 -->
<!-- npu="910b" id3 -->
- Atlas A2系列产品：支持
<!-- end id3 -->
<!-- npu="310b" id4 -->
- Atlas 200I/500 A2推理产品：不支持
<!-- end id4 -->
<!-- npu="310p" id5 -->
- Atlas推理系列产品：支持
<!-- end id5 -->
<!-- npu="910" id6 -->
- Atlas训练系列产品：不支持
<!-- end id6 -->

> [!NOTE]
> 
>针对Atlas A2系列产品，当前仅支持该系列产品中的Atlas 800I A2推理服务器。
>针对Atlas推理系列产品，当前仅支持该系列产品中的Atlas 300I Duo推理卡 + Atlas 800推理服务器（型号：3000）。

## 功能说明<a name="section12591713163317"></a>

附加Trace信息到当前上下文。

## 函数原型<a name="section1121883194711"></a>

```cpp
size_t Attach(const TraceId traceId, const SpanId spanId, const bool isSample = true)
```

## 参数说明<a name="section11506138144714"></a>

**表 1**  参数说明

|参数名|输入/输出|说明|
|--|--|--|
|traceId|输入|Trace ID。|
|spanId|输入|跨度ID。|
|isSample|输入|是否采样（默认true）。|

## 返回值说明<a name="section16621124213476"></a>

返回上下文索引，作为[Unattach](Unattach.md)的调用参数。
