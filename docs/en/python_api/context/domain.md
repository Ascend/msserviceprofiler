# domain<a name="EN-US_TOPIC_0000002184847765"></a>

## Supported Products<a name="section8178181118225"></a>

> [!NOTE]
>
>For details about Ascend product models, see [Ascend Product Models](https://www.hiascend.com/document/detail/en/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html).

<!-- npu="950" id1 -->
- <term>Ascend 950PR&950DT products</term>: Supported
<!-- end id1 -->
<!-- npu="A3" id2 -->
- <term>Atlas A3 products</term>: Supported
<!-- end id2 -->
<!-- npu="910b" id3 -->
- <term>Atlas A2 products</term>: Supported
<!-- end id3 -->
<!-- npu="310b" id4 -->
- <term>Atlas 200I/500 A2 inference products</term>: Supported
<!-- end id4 -->
<!-- npu="310p" id5 -->
- <term>Atlas inference products</term>: Supported
<!-- end id5 -->
<!-- npu="910" id6 -->
- <term>Atlas training products</term>: Not supported
<!-- end id6 -->

> [!NOTE]
>
>For Atlas A2 products, only the Atlas 800I A2 in this series is supported.
>For Atlas inference products, only the Atlas 300I Duo inference card and Atlas 800 inference server (model 3000) in this series are supported.

## Function Usage <a name="section463019538153"></a>

Specifies a domain for the data, where records with the same domain are grouped together in trace data.

## Function Prototype<a name="section759854510169"></a>

```python
def domain(self, domain):
```

## Parameter Description<a name="section354791521716"></a>

|Parameter|Input/Output|Description|
|--|--|--|
|domain|Input|Domain name|

## Return Values<a name="section776014535188"></a>

Returns the current Profiler object. Chain calls are supported.
