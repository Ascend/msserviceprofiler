# 总体说明<a name="ZH-CN_TOPIC_0000002487555372"></a>

## 接口简介

Trace模块提供推理服务化性能数据采集（C++）接口，用于Trace数据监测。

Trace接口功能介绍和使用示例请参见[msServiceProfiler Trace数据监测](../../msserviceprofiler_trace_data_monitoring_instruct.md)。

头文件：$\{INSTALL\_DIR\}/include/Tracer.h

库文件：$\{INSTALL\_DIR\}/lib64/libms\_service\_profiler.so

$\{INSTALL\_DIR\}请替换为CANN软件安装后文件存储路径。以root安装举例，则安装后文件存储路径为：/usr/local/Ascend/cann。

## 示例代码

以下是关键步骤的代码示例，请勿直接拷贝编译运行，仅供参考。

```cpp
// 设置全局资源属性
if (msServiceProfiler::Tracer::IsEnable()) {
    msServiceProfiler::TraceContext::addResAttribute("service.name", "my-service");
    msServiceProfiler::TraceContext::addResAttribute("service.version", "1.0.0");
}
auto& ctx = msServiceProfiler::TraceContext::GetTraceCtx();
size_t indexHeader = ctx.ExtractAndAttach(traceParentHeader, b3Header);
size_t index = ctx.Attach(TraceId{1, 1}, SpanId{1}, true);  // Span 会自动Attach，一般不需要主动调用该函数
// 创建跨度
auto span = msServiceProfiler::Tracer::StartSpanAsActive("MyOperation", "MyModule");
// 设置属性
span.SetAttribute("key", "value")
    .SetStatus(true, "Operation completed successfully");
span.End();
ctx.Unattach(index);
ctx.Unattach(indexHeader);
```

## 接口列表

具体接口如下：

**表 1**  Trace API（C++）

|接口|说明|
|--|--|
|[TraceContext类](TraceContext.md)|Trace上下文管理类，负责管理线程级别的Trace信息。|
|[GetTraceCtx](GetTraceCtx.md)|获取当前线程的Trace上下文实例。|
|[addResAttribute](addResAttribute.md)|添加资源属性（全局属性）。|
|[ExtractAndAttach](ExtractAndAttach.md)|解析HTTPTrace信息并附加到当前上下文。|
|[Attach](Attach.md)|附加Trace信息到当前上下文。|
|[Unattach](Unattach.md)|解除指定索引的Trace上下文。|
|[GetCurrent](GetCurrent.md)|获取当前Trace上下文信息。|
|[Span类](Span_1.md)|跨度类，表示一个具体的操作或请求。|
|[Span](Span.md)|创建一个跨度。|
|[Activate](Activate.md)|激活跨度并开始计时。|
|[SetAttribute](SetAttribute.md)|设置跨度属性。|
|[SetStatus](SetStatus.md)|设置跨度状态。|
|[End](End.md)|结束跨度。|
|[Tracer类](Tracer.md)|提供创建跨度的接口。|
|[StartSpanAsActive](StartSpanAsActive.md)|创建并激活一个跨度。|
|[IsEnable](IsEnable.md)|检查Trace功能是否启用。|
