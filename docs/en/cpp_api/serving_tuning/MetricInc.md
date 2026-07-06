# MetricInc<a name="ZH-CN_TOPIC_0000002184676769"></a>

## Supported Products<a name="section8178181118225"></a>

>[!NOTE]
>
>For details about Ascend product models, see [Ascend Product Models](https://www.hiascend.com/document/detail/en/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html).

|Product Type|Supported (Yes/No)|
|--|:-:|
|Atlas A3 training products and Atlas A3 inference products|No|
|Atlas A2 training products and Atlas A2 inference products|Yes|
|Atlas 200I/500 A2 inference products|No|
|Atlas inference products|Yes|
|Atlas training products|No|

>[!NOTE]
>
>For Atlas A2 training products/Atlas A2 inference products, only the Atlas 800I A2 inference server is supported.
>For Atlas inference products, only the Atlas 300I Duo inference card and Atlas 800 inference server (model 3000) are supported.

## Description <a name="section20806203412478"></a>

Records an incremental metric value.

## Function Prototype<a name="section1121883194711"></a>

```CPP
template <typename T>
inline Profiler &MetricInc(const char *metricName, T value)
```

## Parameter Description<a name="section11506138144714"></a>

**Table 1** Parameters

|Parameter|Input/Output|Description|
|--|--|--|
|metricName|Input|Metric name.|
|value|Input|Incremental value. A negative value indicates a decrease.|

## Return Values<a name="section8800235121218"></a>

Returns `Profiler&` (a reference to the current object), allowing multiple method calls to be chained together.
