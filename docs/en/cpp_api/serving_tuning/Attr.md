# Attr Functions<a name="EN-US_TOPIC_0000002149395902"></a>

## Supported Products<a name="section8178181118225"></a>

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
- <term>Atlas 200I/500 A2 inference products</term>: Not supported
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

## Description <a name="section20806203412478"></a>

Adds an attribute and returns the current object, allowing multiple method calls to be chained together. When data is parsed into a trace, the attribute appears in the `args` field.

## Function Prototype<a name="section1121883194711"></a>

```cpp
template <Level levelAttr = level, typename T>
inline Profiler &Attr(const char *attrName, const T value)
```

## Parameter Description<a name="section11506138144714"></a>

**Table 1** Parameters

|Parameter|Input/Output|Remarks|
|--|--|--|
|attrName|Input|Attribute name.|
|value|Input|Attribute value, which is a number or a character string.|

## Return Values<a name="section8800235121218"></a>

Returns `Profiler&` (a reference to the current object), allowing multiple method calls to be chained together.
