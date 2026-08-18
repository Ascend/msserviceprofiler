# \_\_enter\_\_/\_\_exit\_\_<a name="ZH-CN_TOPIC_0000002149528604"></a>

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

在进入的时候，自动调用span\_start函数，用于记录过程开始的时间点；在退出的时候，自动调用span\_end函数，用于记录过程的结束时间点。

## 函数原型<a name="section759854510169"></a>

```python
def __enter__(self):
def __exit__(self, exc_type, exc_val, exc_tb):
```

## 参数说明<a name="section354791521716"></a>

无

## 返回值说明<a name="section776014535188"></a>

无
