# metric\_scope\_as\_req\_id<a name="ZH-CN_TOPIC_0000002149528612"></a>

## 产品支持情况<a name="section8178181118225"></a>

> [!NOTE]
>
>昇腾产品的具体型号，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》

|产品类型|是否支持|
|--|:-:|
|Ascend 950 系列产品|×|
|Atlas A3 训练系列产品/Atlas A3 推理系列产品|×|
|Atlas A2 训练系列产品/Atlas A2 推理系列产品|√|
|Atlas 200I/500 A2 推理产品|×|
|Atlas 推理系列产品|√|
|Atlas 训练系列产品|×|

> [!NOTE]
> 
>针对Atlas A2 训练系列产品/Atlas A2 推理系列产品，当前仅支持该系列产品中的Atlas 800I A2 推理服务器。
>针对Atlas 推理系列产品，当前仅支持该系列产品中的Atlas 300I Duo 推理卡+Atlas 800 推理服务器（型号：3000）。

## 函数功能<a name="section463019538153"></a>

定义一个指标类的作用范围为请求级别。

## 函数原型<a name="section759854510169"></a>

```python
def metric_scope_as_req_id(self)
```

## 参数说明<a name="section354791521716"></a>

无

## 返回值说明<a name="section776014535188"></a>

Profiler返回当前对象，支持链式调用。
