# MetricInc<a name="ZH-CN_TOPIC_0000002184676769"></a>

## 产品支持情况<a name="section8178181118225"></a>

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

## 功能说明<a name="section20806203412478"></a>

记录一个指标类的增量数值。

## 函数原型<a name="section1121883194711"></a>

```cpp
template <typename T>
inline Profiler &MetricInc(const char *metricName, T value)
```

## 参数说明<a name="section11506138144714"></a>

**表 1**  参数说明

|参数名|输入/输出|说明|
|--|--|--|
|metricName|输入|指标名字。|
|value|输入|增量数值，为负数时表示减少。|

## 返回值说明<a name="section8800235121218"></a>

Profiler&返回当前对象，支持链式调用。
