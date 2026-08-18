# GetCurrent<a name="ZH-CN_TOPIC_0000002486840316"></a>

## 产品支持情况<a name="section13361171693320"></a>

> [!NOTE]
>
>昇腾产品的具体型号，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》

|产品类型|是否支持|
|--|:-:|
|昇腾950PR&昇腾950DT系列产品|×|
|昇腾A3系列产品|×|
|昇腾A2系列产品|√|
|昇腾310B系列产品|×|
|昇腾310P系列产品|√|
|昇腾910系列产品|×|

> [!NOTE]
> 
>针对昇腾A2系列产品，当前仅支持该系列产品中的Atlas 800I A2 推理服务器。
>针对昇腾310P系列产品，当前仅支持该系列产品中的Atlas 300I Duo 推理卡 + A800-3000推理服务器。

## 功能说明<a name="section12591713163317"></a>

获取当前Trace的上下文信息。

## 函数原型<a name="section1121883194711"></a>

```cpp
const TraceContextInfo& GetCurrent()
```

## 参数说明<a name="section11506138144714"></a>

无

## 返回值说明<a name="section16621124213476"></a>

返回当前Trace的上下文信息。
