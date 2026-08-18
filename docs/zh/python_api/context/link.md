# link<a name="ZH-CN_TOPIC_0000002149528608"></a>

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

## 函数功能<a name="section463019538153"></a>

记录不同资源之间的关联，实际应用时不同模块对同一个请求使用不同的编号，将两个系统的编号关联起来。

## 函数原型<a name="section759854510169"></a>

```python
def link(self, from_rid, to_rid):
```

## 参数说明<a name="section354791521716"></a>

|参数名|输入/输出|说明|
|--|--|--|
|from_rid|输入|资源ID。|
|to_rid|输入|资源ID|

## 返回值说明<a name="section776014535188"></a>

无
