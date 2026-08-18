# MetricScopeAsGlobal<a name="ZH-CN_TOPIC_0000002149395898"></a>

## 产品支持情况<a name="section8178181118225"></a>

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

## 功能说明<a name="section20806203412478"></a>

定义一个指标类的作用范围为全局，默认即全局，可不调用该函数。

## 函数原型<a name="section1121883194711"></a>

```cpp
inline Profiler &MetricScopeAsGlobal()
```

## 参数说明<a name="section11506138144714"></a>

无

## 返回值说明<a name="section8800235121218"></a>

Profiler&返回当前对象，支持链式调用。
