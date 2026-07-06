# Overview<a name="ZH-CN_TOPIC_0000002487555372"></a>

## API Introduction

The Trace module provides C++ APIs for collecting inference performance data for trace data monitoring.

For details about the functions and usage examples of the Trace APIs, see [msServiceProfiler Trace Data Monitoring](../../msserviceprofiler_trace_data_monitoring_instruct.md).

Header file: $\{INSTALL_DIR\}/include/Tracer.h

Library file: $\{INSTALL_DIR\}/lib64/libms_service_profiler.so

Replace *`$\{INSTALL\_DIR\}`* with the CANN software installation path. For example, if the installation is performed by the `root` user, the path is `/usr/local/Ascend/cann`.

## Sample Code

The following code example illustrates key steps and is for reference only. Do not copy and compile it directly.

```CPP
// Set global resource attributes.
if (msServiceProfiler::Tracer::IsEnable()) {
    msServiceProfiler::TraceContext::addResAttribute("service.name", "my-service");
    msServiceProfiler::TraceContext::addResAttribute("service.version", "1.0.0");
}
auto& ctx = msServiceProfiler::TraceContext::GetTraceCtx();
size_t indexHeader = ctx.ExtractAndAttach(traceParentHeader, b3Header);
size_t index = ctx.Attach(TraceId{1, 1}, SpanId{1}, true); // Spans are attached automatically. This function is generally not needed.
// Create a span.
auto span = msServiceProfiler::Tracer::StartSpanAsActive("MyOperation", "MyModule");
// Set attributes.
span.SetAttribute("key", "value")
    .SetStatus(true, "Operation completed successfully");
span.End();
ctx.Unattach(index);
ctx.Unattach(indexHeader);
```

## API List

APIs are listed below.

**Table 1** Trace APIs (C++)

|API|Description|
|--|--|
|[TraceContext](TraceContext.md)|Trace context management class, which manages thread-level trace information.|
|[GetTraceCtx](GetTraceCtx.md)|Obtains the trace context instance for the current thread.|
|[addResAttribute](addResAttribute.md)|Adds resource attributes (global attributes).|
|[ExtractAndAttach](ExtractAndAttach.md)|Parses HTTP trace information and attaches it to the current context.|
|[Attach](Attach.md)|Attaches trace information to the current context.|
|[Unattach](Unattach.md)|Detaches the trace context with a specified index.|
|[GetCurrent](GetCurrent.md)|Obtains the current trace context.|
|[Span Class](Span_1.md)|Span class, which represents a specific operation or request.|
|[Span](Span.md)|Creates a span.|
|[Activate](Activate.md)|Activates the span and starts timing.|
|[SetAttribute](SetAttribute.md)|Sets the span attribute.|
|[SetStatus](SetStatus.md)|Sets the span status.|
|[End](End.md)|Ends the span.|
|[Tracer Class](Tracer.md)|Provides APIs for creating spans.|
|[StartSpanAsActive](StartSpanAsActive.md)|Creates and activates a span.|
|[IsEnable](IsEnable.md)|Checks whether the trace feature is enabled.|
