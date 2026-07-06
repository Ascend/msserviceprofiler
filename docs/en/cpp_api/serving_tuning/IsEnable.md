# IsEnable<a name="ZH-CN_TOPIC_0000002149188972"></a>

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

Determines whether to enable profiling. If the input parameter level is lower than the configured level, `true` is returned.

## Function Prototype<a name="section1121883194711"></a>

```CPP
inline bool IsEnable(Level msgLevel = level)
```

## Parameter Description<a name="section11506138144714"></a>

**Table 1** Parameters

|Parameter|Input/Output|Remarks|
|--|--|--|
|msgLevel|Input|A specified collection level. For details, see `profiler_level` in the profiling configuration file.|

## Return Values<a name="section16621124213476"></a>

Returns `true` if profiling is enabled, or `false` if profiling is disabled.
