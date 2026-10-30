# Overview<a name="EN-US_TOPIC_0000002149048764"></a>

## API Description <a name="zh-cn_topic_0000002108084148_section172424491588"></a>

The msServiceProfiler module offers Python APIs for profiling inference services.

For details about the functions and usage examples of these APIs, see [Data Collection](.././user_guide/msserviceprofiler_serving_tuning_instruct.md#data-collection).

Python API import: from ms_service_profiler import Profiler, Level

## API List<a name="zh-cn_topic_0000002108084148_section18403103610813"></a>

The specific APIs are as follows.

**Table 1** Serving data profiling APIs (Python)

|Interface|Description|
|--|--|
|[init](./context/init.md)|Performs initialization.|
|[__enter__/__exit__](./context/__enter__-__exit__.md)|Upon entry, automatically calls the `span_start` function to record the start time of a process; upon exit, automatically calls the `span_end` function to record the end time of a process.|
|[span_start](./context/span_start.md)|Records the start point of a process.|
|[span_end](./context/span_end.md)|Records the end point of a process.|
|[event](./context/event.md)|Records an event.|
|[link](./context/link.md)|Records the association between different resources.|
|[metric](./context/metric.md)|Records a metric value.|
|[metric_inc](./context/metric_inc.md)|Records an incremental metric value.|
|[metric_scope](./context/metric_scope.md)|Defines a metric scope.|
|[metric_scope_as_req_id](./context/metric_scope_as_req_id.md)|Sets the metric scope to the request level.|
|[launch](./context/launch.md)|Flushes the request record to the disk.|
|[attr](./context/attr.md)|Adds an attribute and returns the current object. Chain calls are supported.|
|[domain](./context/domain.md)|Specifies a domain for the data, where records with the same domain are grouped together in trace data.|
|[res](./context/res.md)|Assigns a resource ID, where data and timeline are associated based on the resource ID.|
|[get_msg](./context/get_msg.md)|Obtains the currently recorded data.|
