# SetStatus<a name="ZH-CN_TOPIC_0000002486840318"></a>

## Supported Products<a name="section13361171693320"></a>

>[!NOTE]
>
>For details about Ascend product models, see [Ascend Product Models](https://www.hiascend.com/document/detail/en/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html).

|Product Type|Supported (Yes/No)|
|--|:-:|
|Atlas A3 Training Products and Atlas A3 Inference Products|No|
|Atlas A2 Training Products and Atlas A2 Inference Products|Yes|
|Atlas 200I/500 A2 inference products|No|
|Atlas Inference Products|Yes|
|Atlas training products|No|

>[!NOTE]
>
>For Atlas A2 training products/Atlas A2 inference products, only the Atlas 800I A2 inference server is supported.
>For Atlas inference products, only the Atlas 300I Duo inference card and Atlas 800 inference server (model 3000) are supported.

## Description<a name="section12591713163317"></a>

Sets the span status.

## Function Prototype<a name="section1121883194711"></a>

```CPP
Span& SetStatus(const bool isSuccess, const std::string& msg)
```

## Parameter Description<a name="section11506138144714"></a>

**Table 1** Parameters

|Parameter|Input/Output|Remarks|
|--|--|--|
|isSuccess|Input|Service status. The value is `true` or `false`.|
|msg|Input|Status information.|

## Return Values<a name="section16621124213476"></a>

Returns a reference to a Span object, allowing multiple method calls to be chained together.
