# Link<a name="ZH-CN_TOPIC_0000002184555049"></a>

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

Records the association between different resources. Different modules assign unique IDs to identical requests in real-world usage. Associates the IDs of two systems.

## Function Prototype<a name="section1121883194711"></a>

```c++
void Link(const ResID &fromRid, const ResID &toRid)
```

## Parameter Description<a name="section11506138144714"></a>

**Table 1** Parameters

|Parameter|Input/Output|Remarks|
|--|--|--|
|fromRid|Input|ResID type. ResID can be implicitly converted from a character string or a number.|
|toRid|Input|ResID type. ResID can be implicitly converted from a character string or a number.|

## Return Values<a name="section8800235121218"></a>

None
