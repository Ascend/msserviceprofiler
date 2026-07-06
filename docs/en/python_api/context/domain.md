# domain<a name="ZH-CN_TOPIC_0000002184847765"></a>

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

Specifies a domain for the data, where records with the same domain are grouped together in trace data.

## Function Prototype<a name="section759854510169"></a>

```python
def domain(self, domain)
```

## Parameter Description<a name="section354791521716"></a>

|Parameter|Input/Output|Description|
|--|--|--|
|domain|Input|Domain name|

## Return Values<a name="section776014535188"></a>

Returns the current Profiler object. Chain calls are supported.
