# Link<a name="ZH-CN_TOPIC_0000002184555049"></a>

## 产品支持情况<a name="section8178181118225"></a>

> [!NOTE]
>
>昇腾产品的具体型号，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》

<!-- npu="950" id1 -->
- 昇腾950PR&950DT系列产品：不支持
<!-- end id1 -->
<!-- npu="A3" id2 -->
- 昇腾A3系列产品：不支持
<!-- end id2 -->
<!-- npu="910b" id3 -->
- 昇腾A2系列产品：支持
<!-- end id3 -->
<!-- npu="310b" id4 -->
- 昇腾310B系列产品：不支持
<!-- end id4 -->
<!-- npu="310p" id5 -->
- 昇腾310P系列产品：支持
<!-- end id5 -->
<!-- npu="910" id6 -->
- 昇腾910系列产品：不支持
<!-- end id6 -->

> [!NOTE]
> 
>针对昇腾A2系列产品，当前仅支持该系列产品中的Atlas 800I A2 推理服务器。
>针对昇腾310P系列产品，当前仅支持该系列产品中的Atlas 300I Duo 推理卡 + A800-3000推理服务器。

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
