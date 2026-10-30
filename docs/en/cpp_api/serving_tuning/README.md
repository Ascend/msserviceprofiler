# Overview<a name="EN-US_TOPIC_0000002184469813"></a>

## API Description <a name="zh-cn_topic_0000001977973392_section883612815318"></a>

The msServiceProfiler module offers C++ APIs for profiling inference services.

For details about the functions and usage examples of the profiling data collection APIs, see *[Data Collection](../../user_guide/msserviceprofiler_serving_tuning_instruct.md#data-collection)*.

Header file: `$\{INSTALL_DIR\}/include/msServiceProfiler.h`

Library file: `$\{INSTALL_DIR\}/lib64/libms_service_profiler.so`

Replace *`$\{INSTALL\_DIR\}`* with the CANN software installation path. For example, if the installation is performed by the `root` user, the path is `/usr/local/Ascend/cann`.

## API List <a name="zh-cn_topic_0000001977973392_section2321145165316"></a>

APIs are listed below.

**Table 1** msServiceProfiler APIs (C++)

|API|Description|
|--|--|
|[IsEnable](IsEnable.md)|Determines whether to enable profiling.|
|[SpanStart](SpanStart.md)|Records the start point of a process.|
|[SpanEnd](SpanEnd.md)|Records the end point of a process.|
|[Metric](Metric.md)|Records a metric value.|
|[MetricInc](MetricInc.md)|Records an incremental metric value.|
|[MetricScope](MetricScope.md)|Defines a metric scope.|
|[MetricScopeAsReqID](MetricScopeAsReqID.md)|Sets the metric scope to the request level.|
|[MetricScopeAsGlobal](MetricScopeAsGlobal.md)|Defines the scope of a metric class as global.|
|[Launch](Launch.md)|Flushes the request record to the disk.|
|[Event](Event.md)|Records an event.|
|[Link](Link.md)|Records the association between different resources.|
|[Attr series](Attr.md)|Adds an attribute and returns the current object, allowing multiple method calls to be chained together.|
|[ArrayResource](ArrayResource.md)|Adds key attributes of array resources.|
|[Resource](Resource.md)|Assigns a resource ID, where data and timeline are associated based on the resource ID.|
|[Domain](Domain.md)|Specifies a domain for the data, where records with the same domain are grouped together in trace data.|
|[NumArrayAttr](NumArrayAttr.md)|Adds an array attribute that accepts only numeric values.|
|[ArrayAttr](ArrayAttr.md)|Adds an array attribute through a callback function.|
|[GetMsg](GetMsg.md)|Obtains the currently recorded data.|
|[Macro Definitions](macro_definitions.md)|Encapsulated profiling statement.|
