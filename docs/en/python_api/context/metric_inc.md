# metric\_inc<a name="ZH-CN_TOPIC_0000002149370540"></a>

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

## Function Usage <a name="section463019538153"></a>

Records an incremental metric value.

## Function Prototype<a name="section759854510169"></a>

```python
def metric_inc(self, metric_name, metric_value)
```

## Parameter Description<a name="section354791521716"></a>

|Parameter|Input/Output|Description|
|--|--|--|
|metric_name|Input|Metric name.|
|metric_value|Input|Incremental value. A negative value indicates a decrease.|

## Return Values<a name="section776014535188"></a>

Returns the current Profiler object. Chain calls are supported.
