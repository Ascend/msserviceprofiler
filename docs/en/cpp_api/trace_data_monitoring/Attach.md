# Attach<a name="EN-US_TOPIC_0000002487000272"></a>

## Supported Products<a name="section13361171693320"></a>

> [!NOTE]
>
>For details about Ascend product models, see [Ascend Product Models](https://www.hiascend.com/document/detail/en/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html).

<!-- npu="950" id1 -->
- <term>Ascend 950PR&950DT products</term>: Not supported
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

## Description<a name="section12591713163317"></a>

Attaches trace information to the current context.

## Function Prototype<a name="section1121883194711"></a>

```cpp
size_t Attach(const TraceId traceId, const SpanId spanId, const bool isSample = true)
```

## Parameter Description<a name="section11506138144714"></a>

**Table 1** Parameters

|Parameter|Input/Output|Remarks|
|--|--|--|
|traceId|Input|Trace ID.|
|spanId|Input|Span ID.|
|isSample|Input|Specifies whether to perform sampling. The default value is `true`.|

## Return Values<a name="section16621124213476"></a>

Returns a context index, which is used as the argument when calling [Unattach](Unattach.md).
