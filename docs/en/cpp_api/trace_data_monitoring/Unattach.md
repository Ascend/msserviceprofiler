# Unattach<a name="ZH-CN_TOPIC_0000002519000165"></a>

## Supported Products<a name="section13361171693320"></a>

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

## Description<a name="section12591713163317"></a>

Detaches the trace context associated with a specified index.

## Function Prototype<a name="section1121883194711"></a>

```CPP
void Unattach(const size_t index)
```

## Parameter Description<a name="section11506138144714"></a>

**Table 1** Parameters

|Parameter|Input/Output|Description|
|--|--|--|
|index|Input|Index of a context to detach.|

## Return Values<a name="section16621124213476"></a>

None
