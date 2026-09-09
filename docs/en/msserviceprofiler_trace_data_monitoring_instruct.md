# msServiceProfiler Trace for Data Monitoring <a name="ZH-CN_TOPIC_0000002486322046"></a>

## Overview <a name="ZH-CN_TOPIC_0000002518641903"></a>

msServiceProfiler Trace receives, processes, and forwards distributed trace data using the OpenTelemetry Protocol (OTLP). It helps users monitor and analyze the performance of microservices.

It collects data from the MindIE Motor service, including request response time, response status, client IP/port, and server IP/port. Then, it pushes the collected data to OTLP-compliant open-source monitoring platforms such as Jaeger for visualization.

- The current version primarily targets the MindIE inference framework and supports single-node deployment and multi-node Prefill-Decode (PD) competition deployment.
- Trace monitoring is currently supported only for core inference endpoints [/v1/chat](https://www.hiascend.com/document/detail/en/mindie/230/LLMframe/llmdev/mindie_service0078.html) and [/v1/completions](https://www.hiascend.com/document/detail/en/mindie/230/LLMframe/llmdev/mindie_service0323.html) of MindIE.
- For details about data monitoring APIs of msServiceProfiler Trace, see "msServiceProfiler API Reference (C++) \>  [Trace Data Monitoring](./cpp_api/trace_data_monitoring/README.md).
- For details about MindIE Motor, see [MindIE Motor Developer Guide](https://gitcode.com/Ascend/MindIE-Motor-CPP/blob/v3.0.0/docs/en/user_guide/README.md).

## Supported Products<a name="ZH-CN_TOPIC_0000002489576470"></a>

>[!NOTE]
>
>For details about Ascend product models, see [Ascend Product Models](https://www.hiascend.com/document/detail/en/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html).

|Product Type| Supported (Yes/No)|
|--|:----:|
|Ascend 950 products|No|
|Atlas A3 Training Products and Atlas A3 Inference Products|  Yes  |
|Atlas A2 Training Products and Atlas A2 Inference Products|  Yes  |
|Atlas 200I/500 A2 inference products|  Yes  |
|Atlas Inference Products|  Yes  |
|Atlas training products|  No  |

>[!NOTE]
>
>For Atlas A2 training products/Atlas A2 inference products, only the Atlas 800I A2 inference server is supported.
>For Atlas inference products, only the Atlas 300I Duo inference card and Atlas 800 inference server (model 3000) are supported.

## Preparations<a name="ZH-CN_TOPIC_0000002486482024"></a>

**Environment Setup<a name="section151144214396"></a>**

1. In the Ascend environment, install the matching CANN Toolkit and ops operator packages, and configure CANN environment variables. For details, see [CANN Installation Guide](https://www.hiascend.com/en/cann/download).

2. Install [msServiceProfiler](msserviceprofiler_install_guide.md).

3. Install and configure MindIE and ensure that MindIE Motor can run properly. For details, see [MindIE Installation Guide](https://gitcode.com/Ascend/MindIE-Motor/blob/v3.1.0/docs/en/user_guide/maintenance/build_motor_image_from_vllm_ascend.md).

   ```bash
   pip install opentelemetry-exporter-otlp-proto-grpc==1.33.1
   pip install opentelemetry-exporter-otlp-proto-http==1.33.1
   ```

4. Install and configure MindIE and ensure that MindIE Motor can run properly. For details, see [MindIE Installation Guide](https://gitcode.com/Ascend/MindIE-Motor/blob/master/docs/zh/user_guide/deployment/README.md).

5. Establish a stable network connection between the Ascend environment hosting the MindIE Motor service and the OTLP collector (such as Jaeger).

**Constraint<a name="section12833144412392"></a>.**

msServiceProfiler Trace can forward a maximum of 400 concurrent requests. Exceeding this limit may cause request backlogs. If the backlog exceeds 1 million requests, data loss may occur.

Related log messages (the following logs are reported only once per hour):

```ColdFusion
# An alarm is generated when the number of backlogged requests exceeds 100,000.
2025-11-26 15:45:59,038 - 4059906 - msServiceProfiler - WARNING - Trace data is being stacked: {backlog size}
# A data loss alarm is generated when the number of backlogged requests exceeds 1 million.
2025-11-26 15:45:59,522 - 4059906 - msServiceProfiler - WARNING - Trace data queue is full, discarding the oldest data.
```

## Data Collection <a name="ZH-CN_TOPIC_0000002518521923"></a>

### Enabling Data Collection<a name="ZH-CN_TOPIC_0000002486322048"></a>

1. Enable trace collection by configuring the environment variable `MS_TRACE_ENABLE`.

    ```bash
    export MS_TRACE_ENABLE=1
    ```

    - Setting `MS_TRACE_ENABLE` to `1` enables trace collection.
    - If this variable is not set or is set to any other value, trace collection is disabled.

2. Flexibly control sampling by configuring the following environment variables.

    | Environment Variable| Description| 
    |------------|------|
    | `MS_PROFILER_AUTO_TRACE` | Specifies whether to automatically generate a `trace_id` when the request header does not contain one. Setting this variable to `1` enables auto-generation. If this variable is not set or is set to any other value, auto-generation is disabled.| 
    | `MS_PROFILER_SAMPLE_RATE` | Sets the sampling rate. This applies only to a request with automatically generated `trace_id`. The value is a positive integer N, indicating that one sample is collected every N requests. If this variable is not set or is set to any other value, no sampling is performed.| 
    | `MS_PROFILER_SAMPLE_ERROR` | Specifies whether to report only failed requests (applicable to all requests). Setting this variable to `1` reports only error spans. If this variable is not set or is set to any other value, all requests are reported.| 

    ```bash
    # Example of setting environment variables
    
    # Enable auto-generation of trace_id (when missing from request headers).
    export MS_PROFILER_AUTO_TRACE=1

    # Set the sampling rate to 1 per 100 requests (applies only to auto-generated traces).
    export MS_PROFILER_SAMPLE_RATE=100

    # Report only error requests.
    export MS_PROFILER_SAMPLE_ERROR=1
    ```

3. Run the MindIE Motor service.

### Configuring a Target Server for Collection<a name="ZH-CN_TOPIC_0000002518641905"></a>

>[!NOTE]
>
>For security purposes, you are advised to use secure mode with Transport Layer Security (TLS) authentication

Before [starting the trace forward process](#starting-the-trace-forward-process), you need to specify a target collector using environment variables.

Currently, the following four protocols are supported:

- HTTP

    ```bash
    export OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"
    export OTEL_EXPORTER_OTLP_ENDPOINT=http://xxx:xxx/v1/traces # Configure the IP address and port for data forwarding, for example, http://localhost:4318/v1/traces.
    ```

- HTTP + TLS

    ```bash
    export OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"
    export OTEL_EXPORTER_OTLP_ENDPOINT=https://xxx:xxx/v1/traces # Configure the IP address and port for data forwarding, for example, https://localhost:4318/v1/traces.
    export OTEL_EXPORTER_OTLP_CERTIFICATE=/home/certificates/ca/ca.crt # Set the absolute path to the certificate. The directory owner and file owner must match the current user. The directory permission is 700 and the file permission is 600.
    ```

- gRPC

    ```bash
    export OTEL_EXPORTER_OTLP_PROTOCOL="grpc"
    export OTEL_EXPORTER_OTLP_ENDPOINT=http://xxx:xxx # Configure IP address and port number for data forwarding, for example, http://localhost:4317.
    ```

- gRPC + TLS

    ```bash
    export OTEL_EXPORTER_OTLP_PROTOCOL="grpc"
    export OTEL_EXPORTER_OTLP_ENDPOINT=https://xxx:xxx # Configure IP address and port number for data forwarding, for example, https://localhost:4317.
    export OTEL_EXPORTER_OTLP_CERTIFICATE=/home/certificates/ca/ca.crt # Set the absolute path to the certificate. The directory owner and file owner must match the current user. The directory permission is 700 and the file permission is 600.
    ```

>[!NOTE]
>
>This tool depends on the third-party OpenTelemetry library. This document describes only the mandatory parameters required by the tool. For additional features and APIs, see the official documents.
>
>Currently, only server-side TLS authentication is supported. Configuration parameters for mutual TLS authentication are not supported. If these parameters are set, the feature will not function correctly. The following parameters are not supported:
>
>- OTEL\_EXPORTER\_OTLP\_TRACES\_CLIENT\_KEY
>- OTEL\_EXPORTER\_OTLP\_CLIENT\_KEY
>- OTEL\_EXPORTER\_OTLP\_TRACES\_CLIENT\_CERTIFICATE
>- OTEL\_EXPORTER\_OTLP\_CLIENT\_CERTIFICATE

### Starting the Trace Forward Process

**Function Description<a name="section21638528484"></a>**

Starts the trace forward process.

**Precautions<a name="section20819721134913"></a>**

Retry mechanism: If a single request fails to be sent (six retries by default), the trace forward process does not accept subsequent trace data. The data forwarding function is restored only after the request is successfully sent.

**Syntax<a name="section10872103414491"></a>**

```bash
python -m ms_service_profiler.trace [--log-level]
```

For details about the `option` parameter, see [Parameter Description](#section379581401015).

**Parameter Description<a name="section379581401015"></a>**

**Table 1** Parameters

|Option|Description|**Mandatory (Yes/No)**|
|--|--|--|
|--log-level|Sets the log level. The options are as follows:<br>`debug`: debug level. Logs at this level record the debugging information for R&D or maintenance personnel to locate faults.<br>`info`: normal level (default). Logs normal tool operation information.  <br>`warning`: warning level. Logs at this level record information when the tool does not run in an expected state, but the running of the process is not affected.<br>`error`: minor error level. `fatal`: major error level. `critical`: critical error level.|No|

**Examples<a name="section192337387165"></a>**

Start the trace forward process with the default configuration. The command is as follows:

```bash
python -m ms_service_profiler.trace
```

The user starting the trace forward process must match the user starting the MindIE Motor service, and both processes must be in the same network namespace (that is, the same Docker or host).

**Output Description<a name="section738017254237"></a>**

When the forward process starts successfully, output similar to the following is displayed:

```ColdFusion
2025-11-27 18:46:42,737 - 23410 - msServiceProfiler - INFO - Start http/protobuf exporter, endpoint: http://localhost:4318/v1/traces
2025-11-27 18:46:42,737 - 23410 - msServiceProfiler - INFO - Start socket server success, listen addr: OTLP_SOCKET
2025-11-27 18:46:42,737 - 23410 - msServiceProfiler - INFO - Start scheduler task: interval 1s
2025-11-27 18:46:42,738 - 23410 - msServiceProfiler - INFO - Start OTLPForwarderService success, running...
```

### Sending Requests

You are advised to send requests to `/v1/chat/completions` and `/v1/completions` endpoints. In addition, the HTTP headers of requests sent to these two endpoints must contain sampling information. The following header formats are supported:

- W3C Trace Context \(traceparent\)
- B3 Single Header \(single header)
- B3 Multiple Headers \(multiple headers)

For details about the HTTP header format, see the following example:

**W3C Trace Context \(traceparent\)<a name="section3636185692618"></a>**

Example:

```http
traceparent: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
```

**Table 1** W3C Trace Context \(traceparent\)

|Field|Position|Length|Description|Mandatory (Yes/No)|
|--|--|--|--|--|
|version|First two characters|2 characters|Protocol version. The value is fixed to `00`.|Yes|
|trace-id|Characters 3 to 34|32 characters|Global trace ID (16 bytes, 32 hexadecimal characters), which uniquely identifies the entire distributed tracing.|Yes|
|parent-id|Characters 36 to 51|16 characters|Parent span ID (8 bytes, 16 hexadecimal characters), which identifies the direct upstream of the current operation.|Yes|
|trace-flags|Characters 53 and 54|2 characters|Trace flags. Currently, only the least significant bit is used. `01`: sampling enabled; `00`: sampling disabled.|Yes|

**B3 Single Header<a name="section10847195822715"></a>**

Example:

```http
b3: 0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-1-0000000000000001
```

**Table 2** B3 Single Header

|Field|Position|Description|Format|Function|Mandatory (Yes/No)|
|--|--|--|--|--|--|
|TraceId|Characters 1 to 32|Global trace ID|32 hexadecimal characters|Uniquely identifies the distributed tracing.|Yes|
|SpanId|Characters 34 to 49|Current span ID|16 hexadecimal characters|Unique ID of the current service operation.|Yes|
|Sampled|Character 51|Sampling decision|1 character|**`1`: sampling enabled; `0`: sampling disabled**|Yes|
|ParentSpanId|Characters 53 to 68|Parent span ID|16 hexadecimal characters|(Optional) Identifies the direct upstream span.|No|

**B3 Multiple Headers<a name="section1410152418280"></a>**

Example:

```http
X-B3-TraceId: 0af7651916cd43dd8448eb211c80319c
X-B3-SpanId: b7ad6b7169203331
X-B3-Sampled: 1
```

**Table 3** B3 Multiple Headers

|Field|Description|Format|Value|Function|Mandatory (Yes/No)|
|--|--|--|--|--|--|
|X-B3-TraceId|Global trace ID|32 hexadecimal characters (16 bytes)|Any 32-character hexadecimal string|Uniquely identifies the distributed tracing. All related services share the same trace ID.|Yes|
|X-B3-SpanId|Current span ID|16 hexadecimal characters (8 bytes)|Any 16-character hexadecimal string|Unique ID of the current service operation. Each span has its own unique span ID.|Yes|
|X-B3-Sampled|Sampling decision|String|**`1`: sampling enabled; `0`: sampling disabled**|Determines whether to record trace data to the backend system, avoiding excessive performance overhead.|Yes|

**Sending a Request<a name="section113815183112"></a>**

To send requests and enable the trace data monitoring feature, the HTTP headers of the requests must follow one of the preceding header formats. The Span ID and Trace ID provided in the header are used as indexing keys for each request.

To send requests using the W3C Trace Context (traceparent) format, run the following command:

```http
curl http://127.0.0.1:1025/v1/chat/completions \
-X POST \
-H "Content-Type: application/json" -H "traceparent: 04-01f92f3577b34da6a3ce929d0e0e4703-00f067aa0ba90203-01" \
-d '{
"model": "qwen",
"messages": [
{"role": "user", "content": "Use Python to write a simple bubble sort algorithm: "}
],
"max_tokens": 300,
"temperature": 0.5,
"stream": false }'
```

## Output Description<a name="ZH-CN_TOPIC_0000002486322050"></a>

After [sending a request](#sending-requests), you can view the visualization result on an OTLP-compatible open-source monitoring platform such as Jaeger (the Jaeger service must be started beforehand). See the following example for details.

**Figure 1** Visualization result<a name="fig485163113451"></a> 
![](figures/visualization-result.png "Visualized result")

The fields are described as follows:

**Table 1** Basic information

|Field|Description|
|--|--|
|traceID|Unique identifier of a trace. The value is a string, for example, `79f92f3577b34da6a3ce929d0e0e4703`.|
|spanID|Unique identifier of the current span. The value is a string, for example, `4736e32cc09f0000`.|
|operationName|Operation/API name. The value is a string, for example, `server.Request`.|
|startTime|Span start time. The value is an integer, in μs, for example, `1763784983019248`.|
|duration|Span duration. The value is an integer, in μs, for example, `328`.|

**Table 2** Service information

|Field|Description|
|--|--|
|tags[key=otel.scope.name]|Service/Module name. The value is a string, for example, `LLM`.|
|tags[key=server.method]|HTTP request method. The value is a string, for example, `POST`.|
|tags[key=server.path]|Request path. The value is a string, for example, `/v1/chat/completions`.|
|tags[key=span.kind]|Span type. The value is a string, for example, `server`.|

**Table 3** Network information

|Field|Description|
|--|--|
|tags[key=server.net.host.ip]|Server IP address. The value is a string, for example, `127.0.0.7`.|
|tags[key=server.net.host.port]|Server port. The value is a string, for example, `7025`.|
|tags[key=server.net.peer.ip]|Client IP address. The value is a string, for example, `127.0.0.1`.|
|tags[key=server.net.peer.port]|Client port. The value is a string, for example, `36694`.|

**Table 4** Status information

|Field|Description|
|--|--|
|tags[key=error]|Specifies whether an error occurs (this field is present only when a request error occurs). The value is of the Boolean type, for example, `true` when a request error occurs. This field is omitted when the request succeeds.|
|tags[key=otel.status_code]|OpenTelemetry status code. The value is a string, for example, `OK` when the request succeeds, or `ERROR` when the request fails.|
|tags[key=otel.status_description]|Detailed error description (this field is present only when a request error occurs). The value is a string, for example: `{"error":"Request param contains not messages or messages null","error_type":"Input Validation Error"}`.|
