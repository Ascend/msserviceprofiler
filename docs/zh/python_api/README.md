# 总体说明<a name="ZH-CN_TOPIC_0000002149048764"></a>

## 接口简介<a name="zh-cn_topic_0000002108084148_section172424491588"></a>

msServiceProfiler模块提供推理服务化性能数据采集（Python）接口，用于实现采集服务化调优场景性能数据。

推理服务化性能数据采集接口功能介绍和使用示例请参见[数据采集](.././user_guide/msserviceprofiler_serving_tuning_instruct.md#数据采集)。

Python接口导入：from ms\_service\_profiler import Profiler, Level

## 接口列表<a name="zh-cn_topic_0000002108084148_section18403103610813"></a>

具体接口如下：

**表 1**  服务化性能数据采集API（Python）

|接口|说明|
|--|--|
|[init](./context/init.md)|初始化。|
|[__enter__/__exit__](./context/__enter__-__exit__.md)|在进入的时候，自动调用span_start函数，用于记录过程开始的时间点；在退出的时候，自动调用span_end函数，用于记录过程的结束时间点。|
|[span_start](./context/span_start.md)|记录一个过程的开始节点。|
|[span_end](./context/span_end.md)|记录一个过程的结束节点。|
|[event](./context/event.md)|记录一个事件。|
|[link](./context/link.md)|记录不同资源之间的关联。|
|[metric](./context/metric.md)|记录一个指标类数值。|
|[metric_inc](./context/metric_inc.md)|记录一个指标类的增量数值。|
|[metric_scope](./context/metric_scope.md)|定义一个指标类的作用范围。|
|[metric_scope_as_req_id](./context/metric_scope_as_req_id.md)|定义一个指标类的作用范围为请求级别。|
|[launch](./context/launch.md)|正式将该请求记录落盘。|
|[attr](./context/attr.md)|添加属性，返回当前对象，支持链式调用。|
|[domain](./context/domain.md)|指定该数据的域，相同域的记录在trace数据中归为一类。|
|[res](./context/res.md)|添加资源ID，数据和timeline根据资源ID进行关联。|
|[get_msg](./context/get_msg.md)|获取当前记录的数据。|
