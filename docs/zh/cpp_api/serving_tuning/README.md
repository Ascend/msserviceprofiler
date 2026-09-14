# 总体说明<a name="ZH-CN_TOPIC_0000002184469813"></a>

## 接口简介<a name="zh-cn_topic_0000001977973392_section883612815318"></a>

msServiceProfiler模块提供推理服务化性能数据采集（C++）接口，用于采集服务化调优场景性能数据。

推理服务化性能数据采集接口功能介绍和使用示例请参见《[数据采集](../../user_guide/msserviceprofiler_serving_tuning_instruct.md#数据采集)》。

头文件：$\{INSTALL\_DIR\}/include/msServiceProfiler.h

库文件：$\{INSTALL\_DIR\}/lib64/libms\_service\_profiler.so

$\{INSTALL\_DIR\}请替换为CANN软件安装后的文件存储路径。以root安装举例，则安装后文件存储路径为：/usr/local/Ascend/cann。

## 接口列表<a name="zh-cn_topic_0000001977973392_section2321145165316"></a>

具体接口如下：

**表 1**  msServiceProfiler API（C++）

|接口|说明|
|--|--|
|[IsEnable](IsEnable.md)|判断是否使能采集数据。|
|[SpanStart](SpanStart.md)|记录一个过程的开始节点。|
|[SpanEnd](SpanEnd.md)|记录一个过程的结束节点。|
|[Metric](Metric.md)|记录一个指标类数值。|
|[MetricInc](MetricInc.md)|记录一个指标类的增量数值。|
|[MetricScope](MetricScope.md)|定义一个指标类的作用范围。|
|[MetricScopeAsReqID](MetricScopeAsReqID.md)|定义一个指标类的作用范围为请求级别。|
|[MetricScopeAsGlobal](MetricScopeAsGlobal.md)|定义一个指标类的作用范围为全局。|
|[Launch](Launch.md)|正式将该请求记录进行落盘。|
|[Event](Event.md)|记录一个事件。|
|[Link](Link.md)|记录不同资源之间的关联。|
|[Attr系列](Attr.md)|添加属性，返回当前对象，支持链式调用。|
|[ArrayResource](ArrayResource.md)|添加数组类资源的关键属性。|
|[Resource](Resource.md)|添加资源ID，数据和timeline根据资源ID进行关联。|
|[Domain](Domain.md)|指定该数据的域，相同域的记录在trace数据中归为一类。|
|[NumArrayAttr](NumArrayAttr.md)|添加数组属性，数组中仅支持数值。|
|[ArrayAttr](ArrayAttr.md)|通过回调函数自定义添加数组属性。|
|[GetMsg](GetMsg.md)|获取当前记录的数据。|
|[宏定义](macro_definitions.md)|封装的采集语句。|
