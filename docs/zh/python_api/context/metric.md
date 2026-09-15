# metric<a name="ZH-CN_TOPIC_0000002184809445"></a>

## 产品支持情况<a name="section8178181118225"></a>

> [!NOTE]
>
>昇腾产品的具体型号，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》

<!-- npu="950" id1 -->
- Ascend 950PR&950DT 系列产品：不支持
<!-- end id1 -->
<!-- npu="A3" id2 -->
- Atlas A3 系列产品：不支持
<!-- end id2 -->
<!-- npu="910b" id3 -->
- Atlas A2 系列产品：支持
<!-- end id3 -->
<!-- npu="310b" id4 -->
- Atlas 200I/500 A2 推理产品：不支持
<!-- end id4 -->
<!-- npu="310p" id5 -->
- Atlas 推理系列产品：支持
<!-- end id5 -->
<!-- npu="910" id6 -->
- Atlas 训练系列产品：不支持
<!-- end id6 -->

> [!NOTE]
> 
>针对Atlas A2 系列产品，当前仅支持该系列产品中的Atlas 800I A2 推理服务器。
>针对Atlas 推理系列产品，当前仅支持该系列产品中的Atlas 300I Duo 推理卡 + A800-3000推理服务器。

## 函数功能<a name="section463019538153"></a>

记录一个指标类数值。

## 函数原型<a name="section759854510169"></a>

```python
def metric(self, metric_name, metric_value):
```

## 参数说明<a name="section354791521716"></a>

|参数名|输入/输出|说明|
|--|--|--|
|metric_name|输入|指标名字。|
|metric_value|输入|数值。|

## 返回值说明<a name="section776014535188"></a>

Profiler返回当前对象，支持链式调用。
