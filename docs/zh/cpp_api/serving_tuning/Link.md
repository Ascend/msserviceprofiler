# Link<a name="ZH-CN_TOPIC_0000002184555049"></a>

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

## 功能说明<a name="section20806203412478"></a>

记录不同资源之间的关联，实际应用时不同模块对同一个请求使用不同的编号。将两个系统的编号关联起来。

## 函数原型<a name="section1121883194711"></a>

```c++
void Link(const ResID &fromRid, const ResID &toRid)
```

## 参数说明<a name="section11506138144714"></a>

**表 1**  参数说明

|参数名|输入/输出|说明|
|--|--|--|
|fromRid|输入|ResID类型，ResID可以由字符串或数值隐式转换。|
|toRid|输入|ResID类型，ResID可以由字符串或数值隐式转换。|

## 返回值说明<a name="section8800235121218"></a>

无
