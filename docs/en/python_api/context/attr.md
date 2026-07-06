# attr<a name="ZH-CN_TOPIC_0000002149370548"></a>

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

Adds an attribute and returns the current object, allowing multiple method calls to be chained together. When data is parsed into a trace, the attribute appears in the `args` field.

## Function Prototype<a name="section759854510169"></a>

```python
def attr(self, key, value)
```

## Parameter Description<a name="section354791521716"></a>

|Parameter|Input/Output|Description|
|--|--|--|
|key|Input|Attribute name|
|value|Input|Property value|

## Return Values<a name="section776014535188"></a>

Returns the current Profiler object, allowing multiple method calls to be chained together.
