# MindStudio Service Profiler Feature Design Specifications

|                                           |                                                                                                                                                                              |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SIG group:                                | msserviceprofiler                                                                                                                                                            |
| Incorporated into the following versions: | 26.0.0                                                                                                                                                                       |
| Designer:                                 | [mjsz11](https://gitcode.com/mjsz11)    /[yaohan404](https://gitcode.com/yaohan404)    /[panyj1993](https://gitcode.com/panyj1993)    /[ChenHuiwen](https://gitcode.com/ChenHuiwen/)     |
| Date:                                     | 2026.01. 20                                                                                                                                                                  |

**Revision records**

| Date        | Revised version | Revision Description | Authors                                                                                                                                                                      | Audited                                                                                 |
| ----------- | --------------- | -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 2026.01. 20 | 0.1             | New                  | [mjsz11](https://gitcode.com/mjsz11)    /[yaohan404](https://gitcode.com/yaohan404)    /[panyj1993](https://gitcode.com/panyj1993)    /[ChenHuiwen](https://gitcode.com/ChenHuiwen/)     | [yaohan404](https://gitcode.com/yaohan404)    /[panyj1993](https://gitcode.com/panyj1993)     |

**The Table of Contents**

# 1. Feature Overview

This document describes the enhancement solution for the monitoring and performance analysis capabilities of the service-oriented framework. With the rapid popularization of AI inference applications in enterprise-level scenarios, the observability of inference services is required. This solution provides an end-to-end observability system for coverage counter monitoring, link tracing, and performance analysis through systematic function enhancement, helping customers implement efficient monitoring, alarm reporting, capacity planning, and performance optimization. The core value of this solution is to provide production-level observable capabilities for inference services and help enterprises build a complete AI O&M system. The flexible configuration mechanism and non-intrusive collection technology reduce the usage threshold. Supports unified standards for multiple frameworks, ensuring sustainable evolution of technical solutions. This document describes feature requirement analysis, function scope definition, and architecture design key points. It is intended for the development, test, and O&M personnel of the monitoring system of the service-oriented framework.

## 1.1. Scope

Includes the performance data collection, data parsing, and data analysis modules in the service-oriented inference scenario.

 * **The indicator monitoring system is enhanced. User-defined indicators, such as the function execution time, internal variables, input parameters, and output parameters, can be collected. Dynamic start and stop and automatic label injection capabilities are supported.**
 * **Optimized trace link tracing: Supports trace collection, automatic TraceID generation, and unified parsing of multi-frame link data in a large-scale expert parallel solution.**
 * **Performance analysis capability expansion: supports SGLang framework collection, multi-modal data processing, and speculative inference analysis.**
 * **Ease-of-use optimization: Provides toolchain enhancements, such as command line control, quick parsing, data comparison, and visualized optimization.**
 * **Standardization construction: Develop service-based collection standards and implement unified analysis and display of multi-framework data.**

## 1.2. Feature Requirement List

| Requirement No. | Requirement name                                                                                                   | Feature Description                                                                                                                                                                                                           | Remarks                                                                                              |
| --------------- | ------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| 001             | Online monitoring dashboard (VLLM)                                                                                 | Build online monitoring in the inference scenario. Use Prometheus to capture and visualize key vLLM runtime metrics for monitoring, alarm reporting, capacity planning, and performance optimization.                         | Sub-requirements: Function execution time can be used as a metric for custom configuration and push. |
| 002             | Supports dynamic start and stop of metric push.                                                                    | Provides the dynamic start and stop capability, supports on-demand metric loading, controls the start and stop of metric collection by modifying the configuration file, and supports multiple start and stop and hot update. | Reduces application running pressure and supports separate control from profiling.                   |
| 003             | Automatically collects DPs as metric labels.                                                                       | All user-defined metrics automatically contain the dp and role labels. The scheduling process automatically adds the actual values. The request process uses the default value -- 1. Load balancing problems can be checked.  | The DP load is uneven.                                                                               |
| 004             | Supports the customization of the same function in multiple places.                                                | The same function can be collected by metric and profiling at the same time. The metric push function can be compiled by customizing handlers. The configuration guide is provided.                                           | Ensure compatibility and flexibility                                                                 |
| 005             | Function variables, input parameters, and output parameters can be used as metrics.                                | Obtains internal variables and input and output values of functions as metrics or labels, and supports simple calculation. (Array length, dictionary value, and type conversion)                                              | Extended Metric Collection Dimension                                                                 |
| 006             | Monitoring vllm core metrics                                                                                       | Core indicators, such as the TPS, delay statistics, time split, BatchSize, and input and output length, are correctly displayed on Grafana.                                                                                   | Reusable vllm native metric                                                                          |
| 007             | Monitors speculative inference indicator data.                                                                     | Configuring Speculative Decoding Indicators (Average acceptance step, acceptance rate, and number of tokens), properly presented in Grafana                                                                                   | Speculative inference optimization scenarios are supported.                                          |
| 008             | Supports monitoring of vllm DPLB indicator data.                                                                   | Configure the DP-related indicators (such as the request length and block quantity allocation) to be collected and correctly displayed on Grafana.                                                                            | DP load monitoring                                                                                   |
| 009             | Supports online trace.                                                                                             | In the Motor warehouse, trace collection is added to support the large-scale expert parallel solution. SpanIDs are generated to interconnect with the original traceIDs and traceIDs are recorded in logs.                    | Sub-requirement: Pushing Trace Information in the Scenario of Large-scale Concurrent Expert Solution |
| 010             | Automatically generating TraceIDs                                                                                  | Provides environment variables to automatically generate TraceIDs, and supports probability sampling and error sampling mechanisms to enhance the internal monitoring capability of a single service.                         | Optimized the Trace Collection Coverage Scenario                                                     |
| 011             | Collects core SGLang service-oriented indicators.                                                                  | Adapts to the SGLang framework, reuses the vllm configuration logic, and collects key information such as the scheduling execution process, KVCache, and request queue.                                                       | In-depth adaptation to the new framework is supported.                                               |
| 012             | Parsing the SGLang torch profiler                                                                                  | Automatically enables torch profiler data parsing during SGLang servitized parsing and supports normal visualization in Insight.                                                                                              | Improve the SGLang profiling capability.                                                             |
| 013             | Supports SGLang torch profiler collection.                                                                         | Enables the SGLang to enable or disable the torch profiler through the service profiler, and supports the configuration of the stack, memory, and collection step.                                                            | Reuse the same capability as the VM.                                                                 |
| 014             | Multi-modal data collection                                                                                        | Supports multi-modal model profiling data collection for the first time, focusing on the time consumed by data processing modules such as text and image.                                                                     | Supports the vLLM-omni multi-modal version.                                                          |
| 015             | Supports MTP and speculative inference data collection.                                                            | Collect speculative inference-related data (number of tokens and draft model inference time) and display the data in the batch CSV and trace charts.                                                                          | Speculative inference optimization technology                                                        |
| 016             | Supports torch profiler collection and parsing.                                                                    | Collects data through the torch profiler interface (supports the Mindie and vllm framework), and automatically identifies and parses torch profiler data.                                                                     | Obtaining Stack Information                                                                          |
| 017             | Use DB format to reduce parsed data                                                                                | The operator data is parsed in the DB format to reduce disk space usage. Alarms and configuration guides for a large amount of data are provided.                                                                             | Optimize data storage efficiency                                                                     |
| 018             | The vllm supports token-level collection.                                                                          | Allows users to specify the number of tokens to be collected and start or stop collection based on the step function to ensure thread security and token inference collection.                                                | Precise control of acquisition range                                                                 |
| 019             | Automatically enabling operator collection based on conditions                                                     | Automatically triggers data collection based on metric monitoring. Data collection can be triggered by batch size and occurrence times. Data collection can be automatically disabled.                                        | Improving tool usability                                                                             |
| 020             | Supports data comparison.                                                                                          | Compares two sets of servitized data, collects statistics on time differences by span name, and generates comparison result CSV files.                                                                                        | Assistant performance difference analysis                                                            |
| 021             | Summary of Key Information After Analysis                                                                          | Exports spans to CSV files, collects time-consuming statistics on key spans, and provides parsing progress prompts and summary reports.                                                                                       | Optimize the parsing experience.                                                                     |
| 022             | Provides the fast parsing capability.                                                                              | Surveys KPIs, provides a quick parsing process, and preferentially displays core data that users care about.                                                                                                                  | Improving the parsing efficiency                                                                     |
| 023             | Data chart display and numerical accuracy optimization                                                             | Optimize data display and numerical accuracy to improve product quality.                                                                                                                                                      | New requirements in the first quarter of 2026                                                        |
| 024             | Provides the non-intrusive automatic instrumentation capability to collect vllm data.                              | Enable non-intrusive data collection, lowering the threshold for use                                                                                                                                                          | New requirements in the first quarter of 2026                                                        |
| 025             | Optimization of the data structure for service-based disk data                                                     | The format of collected data is changed to the visualized slice table, improving the parsing performance and supporting the display of multiple databases at the same time.                                                   | Optimize the data storage structure.                                                                 |
| 026             | Develop collection standards for service-based collection scenarios and supplement points in different frameworks. | Formulate unified collection standards, standardize domain and span definitions, provide standard interfaces, and unified parsing logic.                                                                                      | Establish a standardized system                                                                      |
| 027             | Visual Lane Sorting                                                                                                | Optimized the swimlane label and sorting in the Insight, added the process type identifier, and displayed by DP domain group, improving the visualization effect.                                                             | Improve user experience                                                                              |
| 028             | Starting or Stopping the Profile Using the CLI                                                                     | Enable or disable the profiling by using command lines and use an independent process to monitor configuration changes, improving usability.                                                                                  | Alternate File Modification Method                                                                   |

# 2. Requirement Scenario Analysis

## 2.1 Feature Requirement Source and Value Overview

**Requirement source: With the wide application of the large model inference service in the production environment, financial institutions, cloud service providers, and enterprise users have increasingly urgent requirements for performance monitoring, fault diagnosis, and optimization of the inference service. The existing monitoring system has problems such as incomplete data collection, poor visualization effect, and insufficient usability, which cannot meet the O&M requirements of the production environment.**

**Value Overview:**

 * **For financial institutions: Provides complete AI inference full-link monitoring capabilities to meet the strict SLA and compliance standards of the financial industry.**
 * **For cloud service providers, enhance the observability of service-oriented frameworks such as vLLM and improve service quality and customer satisfaction.**
 * **For development and O&M teams, accurate performance data is provided to support capacity planning, performance optimization, and fault locating.**
 * **Competitive value: Without this feature, users will face problems such as monitoring blind areas, difficult fault locating, and lack of data support for performance optimization. This severely affects the stable running of AI inference in the production environment and user experience.**

## 2.2 Feature Scenario Analysis

### 2.2.1.1. Scenario Trigger Conditions and Objects

**Trigger conditions:**

 * Continuous monitoring is required after the vLLM inference service is deployed in the production environment.
 * Performance deterioration, response timeout, and other exceptions occur.
 * Perform proactive O&M, such as capacity planning and performance optimization.
 * Performance evaluation is required when a new framework (such as SGLang) is connected.

**Intended:**

 * **AI O&M engineers: Have certain AI inference and O&M knowledge and are responsible for routine monitoring and troubleshooting.**
 * **Performance optimization engineers: Have an in-depth understanding of the inference framework architecture and perform performance analysis and optimization.**
 * **Algorithm engineer: Focus on model inference effect and performance.**

### 2.2.2. 2. Main Application Scenarios and Sub-Scenarios

**Scenario 1: Real-time monitoring of the production environment**

 * Sub-Scenario 1.1: Monitoring Core Indicators
 * Sub-Scenario 1.2: Automatic Alarm Reporting
 * Key operations: Configure monitoring indicators, set alarm thresholds, and view monitoring dashboards.

**Scenario 2: Performance fault diagnosis and locating**

 * Sub-Scenario 2.1: Trace Full Link Trace
 * Sub-Scenario 2.2: In-depth Analysis of Performance Data
 * Sub-scenario 2.3: Multi-dimensional data association analysis
 * Key operations: Enable profiling, analyze trace data, and compare performance differences.

**Scenario 3: Capacity planning and performance optimization**

 * Sub-Scenario 3.1: Resource Usage Trend Analysis
 * Sub-Scenario 3.2: Performance Bottleneck Identification
 * Sub-scenario 3.3: Optimization Effect Verification
 * Key operations: Collect performance baselines, analyze optimization space, and verify optimization effects.

**Scenario 4: Multi-framework unified monitoring**

 * Sub-Scenario 4.1: vLLM Framework Monitoring
 * Sub-Scenario 4.2: SGLang Framework Adaptation
 * Sub-Scenario 4.3: Multimodal Model Support
 * Key operations: framework configuration adaptation, data collection and verification, and unified display

## 2.3 Feature Impact Analysis

### 2.3.1. System Position and Peripheral Interfaces

**System location: located at the core layer of the AI inference service monitoring system. It collects data and supports visualized display.**

**Peripheral interfaces:**

 * **Upward interfaces: Grafana visualization, APM call chain platform, and alarm notification system**
 * **Downstream interfaces: vLLM inference engine, SGLang framework, and multi-modal model**
 * **Horizontal interfaces: Prometheus monitoring system, OpenTelemetry standard, and Torch Profiler**

### 2.3.2. Key Constraints and Feature Conflicts

**Constraints on performance impact:**

 * The impact of data collection on the inference performance must be controlled within 5%.
 * Storage and transmission overheads need to be optimized when a large amount of data is collected.

**Compatibility Constraints:**

 * VLLM frameworks of different versions must be supported.
 * Adaptation to multiple hardware platforms (NPU/GPU)
 * Support for multiple deployment environments (cloud/local deployment)

### 2.3.3. Interaction Analysis with Other Requirements

**Positive dependency:**

 * 001 The monitoring dashboard is the basic display platform for other monitoring functions.
 * 009Trace provides the data basis for 020 data comparison.
 * 026 Collection standard provides unified specifications for multi-framework support.

**Potential Conflict:**

 * There is a need for balance between detailed data acquisition and system performance
 * Resource allocation conflicts exist between multi-framework adaptation and function depth.

### 2.3.4. Platform Difference Analysis

**Hardware platform:**

 * Supports Ascend NPU and NVIDIA GPU platforms
 * Data collection policies need to be optimized based on different hardware features.

**Operating system:**

 * Support for mainstream Linux distributions (such as CentOS and Ubuntu)
 * Container-based deployment (Docker and Kubernetes)

### 2.3.5. Compatibility Analysis

**Forward compatibility: Supports monitoring data collection of the existing vLLM version. Backward compatibility: Reserved interfaces support fast access of future new frameworks. Compatibility: Complies with industry standards such as Prometheus and OpenTelemetry.**

### 2.3.6. Constraints and Limitations

**Technical Constraints:**

 * Data collection does not affect the core functions of the inference service.
 * Storage and parsing efficiency needs to be optimized for processing a large amount of data.

**Resource Constraints:**

 * Proper storage space planning is required for monitoring data storage.
 * Real-time data processing requires sufficient computing resources.

**Constraints:**

 * Some advanced functions require a certain technical background.
 * Multi-framework support requires corresponding configuration and adaptation.

### 2.3.7. Hardware Limitations

Not involved.

### 2.3.8. Technical Limitations

Operating system: Linux

Programming language: Python

### 2.3.9. Impact Analysis on the License

Not involved.

### 2.3.10. Impact Analysis on System Performance Specifications

N/A (same as service-oriented specifications)

### 2.3.11. Impact Analysis on System Reliability Specifications

Not involved.

### 2.3.12. Impact Analysis on System Compatibility

Operating system: Linux

Programming language: Python 3.8 or later

### 2.3.13. Impact Analysis on Interaction and Conflicts with Other Key Features

Not involved.

## 2.4 Analysis of implementation solutions for similar community/commercial software

### 2.4.1 Community Open Source Solution Analysis

**Prometheus + Grafana Ecosystem**

 * **Implementation mechanism: Based on the exporter mode, vLLM-exporter is used to collect metrics, Prometheus is used to obtain storage, and Grafana is used to visualize the metrics.**
 * **Advantages: Mature ecosystem, active community, and relatively simple deployment**
 * **Disadvantages:**
    
     * The monitoring dimensions are limited, and the monitoring is mainly oriented to system-level and basic application indicators.
     * Lack of dedicated indicators (such as token-level time consumption and speculative inference indicators) for AI inference scenarios.
     * Code-level performance analysis and trace cannot be implemented.
     * The exporter needs to be developed and maintained.

**OpenTelemetry (OTel)**

 * **Implementation mechanism: Use the OTel SDK to automatically instrument data to collect trace, metric, and log data.**
 * **Advantages: industry standard, multi-language support, and good scalability**
 * **Disadvantages:**
    
     * Inadequate adaptation to the AI inference framework
     * Lack of pre-set instrumented points for frameworks such as vLLM and SGLang
     * The visualization capability is basic and needs to be combined with other tools.

**PyTorch Profiler**

 * **Implementation mechanism: built-in profiling interface based on the PyTorch framework**
 * **Advantages: In-depth integration with PyTorch and strong operator-level performance analysis capabilities**
 * **Disadvantages:**
    
     * Only the PyTorch model, with high frame coupling degree
     * Lack of monitoring at the service-oriented layer (such as request scheduling and resource management)
     * High deployment overhead in the production environment

### 2.4.2. Commercial Software Solution Analysis

**Datadog APM**

 * **Implementation mechanism: agent-based automatic instrumentation and AI monitoring**
 * **Advantage:**
    
     * Out-of-the-box AI inference monitoring dashboard
     * Supports multiple AI frameworks and cloud service platforms.
     * The alarm and automation functions are optimized.
 * **Disadvantages:**
    
     * Higher commercial licensing fees
     * Limited support for domestic AI chips and frameworks
     * Data is stored in third parties, causing security and compliance risks.

**Dynatrace AI Observability**

 * **Implementation mechanism: Full-stack monitoring based on OneAgent and dedicated AI analysis engine**
 * **Advantage:**
    
     * Strong automatic root cause analysis capability
     * AI model performance deterioration detection
     * Enterprise-class reliability and security
 * **Disadvantages:**
    
     * Complex configuration and high learning costs
     * Insufficient support for open-source AI frameworks
     * Limited customization capability

**Weights & Biases (W&B)**

 * **Implementation mechanism: experimental tracking and model monitoring focusing on MLOps**
 * **Advantage:**
    
     * Powerful model experiment management
     * Model version comparison and performance analysis
     * Active developer community
 * **Disadvantages:**
    
     * The inference monitoring in the production environment is relatively weak.
     * Lack of in-depth integration with the service-oriented framework
     * Limited real-time monitoring capability

### 2.4.3. Advantages and Disadvantages Comparison Analysis

| Feature dimension                    | This solution                                                                           | Community Programme                                     | Commercial solution                                                |
| ------------------------------------ | --------------------------------------------------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------ |
| **Monitoring Depth**                 | **Code-level and service-level full-stack monitoring**                                  | Mainly system-level and basic application monitoring    | Mainly application-level monitoring, limited code-level monitoring |
| **AI framework adaptation**          | **In-depth customization of vLLM and SGLang**                                           | General monitoring, which needs to be adapted.          | Mainstream framework support, limited customization                |
| **Performance Overhead**             | **Controllable optimization, target < 5%**                                              | Varies by frame, usually higher                         | Optimized for commercialization, but the agent is heavy.           |
| **Trace capability**                 | **The native supports the scenario trace of the large-scale expert parallel solution.** | Complex configuration and development required          | Complete functions but complex configurations                      |
| **Multimodal support**               | **Multi-modal model monitoring is supported for the first time.**                       | Not supported.                                          | Partially supported, but limited depth                             |
| **Speculative reasoning monitoring** | **Speculative reasoning indicators**                                                    | No dedicated support                                    | No dedicated support                                               |
| **Localization support**             | **Fully supports the Ascend and other Chinese hardware.**                               | Limited support                                         | Limited support or additional costs                                |
| **cost effectiveness**               | **Open source basic + business enhancement**                                            | Completely free but limited features                    | Full-featured but expensive                                        |
| **Customization Flexibility**        | **Highly customizable and controllable source code**                                    | Customizable but requires strong technical capabilities | Customization is limited and depends on vendors.                   |

### 2.4.4. Core Competitive Advantages of the Programme

**Advantages of technical depth:**

 * In-depth optimization for the AI inference scenario, covering all-link monitoring from request scheduling to operator execution.
 * Token-level refined monitoring and speculative inference are supported.
 * Multi-framework unified monitoring architecture, avoiding monitoring fragmentation

**Cost Benefits:**

 * Based on open source technology stacks, avoiding high commercial software licensing fees
 * Optimize the localization environment to reduce the risk of technology dependence.

**Ease-of-use advantages:**

 * Out-of-the-box monitoring configuration and visual dashboard
 * Intelligent anomaly detection and root cause analysis capabilities
 * Unified configuration management interface, simplifying O&M

**Ecosystem integration advantages:**

 * In-depth integration with HUAWEI CLOUD APM, Insight, and other products
 * Industry standards (Prometheus, OpenTelemetry, etc.)
 * Provide compliance support for specific industries such as finance and government.

This solution achieves a balance between technical depth and practicability in the AI inference monitoring field. This solution not only avoids the function fragmentation problem of the open source solution, but also overcomes the disadvantages of the commercial solution, such as high cost and difficulty in customization, and provides comprehensive and reliable monitoring assurance for the stable running of the AI inference service in the production environment.

# 3. Feature/Function Implementation Principles

## 3.1. Objectives

This document provides guidance for the R&D, test, and subsequent optimization of performance tools. This tool focuses on inference service-based performance data collection, parsing, analysis, and automatic optimization, improving inference efficiency and reducing resource consumption.

## 3.2. Overall Solution

 * Data collection: provides Python and C++ high-performance data collection interfaces and common collection semantics for inference services. It also provides the hardware collection capability. It also provides functions such as automatic start and stop, and refined collection and control.
 * Data analysis: Analyzes collected data and generates basic data such as tables and timelines, facilitating performance analysis.
 * Data analysis: provides the data analysis function and compares data in different frameworks, helping users quickly locate problems.

```plantuml
@startuml

actor User
component MindIE
component VLLM
component MindStudio {

component msServiceProfiler {
    component Collection and parsing {
        component Data collection {
           component Profiler collection
           component Trace collection
           component Metric collection
        }
        component Data parsing
    }
    component Analysis and tuning {
        component Pre-check tool
        component Data analysis
    }
}
component msprof
}

User..|> Pre-check tool : usage
User..|> Data parsing : usage
User..|> Data analysis : usage
User..|> MindIE : usage
User..|> VLLM : usage
MindIE..|> Data collection : usage
VLLM..|> Data collection : usage
Data collection..|> msprof : usage

@enduml
```

# 4. Function execution time can be used as a metric and can be customized and pushed

## 4.1. Design Idea

Define the function execution time indicators to be collected in the YAML configuration file. The environment variables can be used to control whether to enable the function. Insert the timing logic before and after the target function is executed, calculate the time required, and convert the time to the metric data of the Histogram type. Users can customize metric names and the boundary configuration of Histogram buckets. Data can be exposed to Prometheus for capture through the Prometheus client library.

## 4.2. Constraints

1. Ensure that the timing logic has a minimum impact on the performance of the original function.
2. The Histogram bucket configuration must be determined during application startup and cannot be modified during application running.

--------------------

# 5. Supports dynamic start and stop of metric push

## 5.1. Design Idea

The mechanism of the profiling configuration file is reused, and the start and stop fields for metrics collection are added. Dynamic configuration reloading is implemented through file monitoring or signal mechanism. Starts the independent configuration management thread to monitor configuration file changes and controls the start and stop of data collection by using the thread-safe flag to ensure that the configuration changes take effect in real time.

## 5.2 Constraints

1. Metric configuration information (such as bucket) cannot be modified during running, and collection can only be started or stopped.
2. There may be millisecond-level delay from the time when the configuration takes effect.

--------------------

# 6. Automatically collects DPs as metric labels

## 6.1. Design Idea

The labels of all user-defined metrics always contain the dp and role fields. The scheduling process automatically obtains the current DP information and PD role during metric collection. The request process uses the default value -1. The context transfer mechanism is used to carry the DP and role information in the function call chain to ensure that the scheduling-related indicators can be correctly marked after the benchmark starts.

## 6.2. Constraints

1. The metrics in the startup phase may fail to obtain DP and role information.
2. The vLLM scheduling process needs to support the interface for obtaining DP and role information.

--------------------

# 7. Supports the customization of the same function in multiple places

## 7.1. Design Idea

The configuration combination policy is used to allow the same function to be configured with both profiling and metric collection. Establish separate processing pipelines for each acquisition type to avoid mutual interference. Users can customize metrics push functions and provide templates and guidance documents. Users can compile specific logic to process complex metrics calculation and push requirements.

## 7.2. Constraints

1. Multiple configurations of the same function cannot cause metric names that conflict.
2. Thread security must be ensured for customized handlers.

--------------------

# 8. Supports customized configuration and push of variables, input parameters, and output parameters in functions as metrics

## 8.1. Design Idea

The extended configuration syntax supports variable extraction expressions, including function input and output, and internal variables. The built-in simple calculation engine supports operations such as array length, dictionary value, attribute access, and basic calculation. The calculation result can be used as a metric value or label value, and is output in the Prometheus standard format.

## 8.2. Constraints

1. Variable extraction may increase function execution overhead.
2. Complex Calculation Expressions May Affect Performance

--------------------

# 9. Supports monitoring of core VM indicators

## 9.1. Design Idea

Core indicators such as TPS, delay statistics, and time division are collected in configuration mode. The vLLM native metric mechanism is reused to supplement the missing monitoring points. A unified monitoring panel is constructed in Grafana to display various indicators in a visualized manner, support multi-dimensional query, and alarm configuration.

## 9.2. Constraints

1. The vLLM version needs to support internal interfaces.
2. Some in-depth monitoring may slightly affect performance.

--------------------

# 10. Monitor speculative inference indicator data

## 10.1. Design Idea

A monitoring point is inserted into the critical path of speculative reasoning to collect indicators such as the acceptance step, acceptance rate, and number of tokens. Records statistics by Histogram and Counter Metrics, and constructs a dedicated monitoring panel in Grafana to display speculative inference effects in real time.

## 10.2. Constraints

1. Speculation inference required is enabled and functioning properly
2. The monitoring point must match the speculative inference algorithm version.

--------------------

# 11. Supports monitoring of vllm DPLB indicator data

## 11.1. Design Idea

Monitors the request length distribution and block allocation of each DP. Real-time values are recorded by Gauge metrics and DP labels are used to separate data from multiple DPs. Create a load balancing monitoring panel in Grafana to help locate DP load imbalance problems.

## 11.2. Constraints

1. Requires multi-DP environment support
2. Block statistics must be supported by the internal data structure of the vLLM.

--------------------

# 12. Push trace information in the scenario where a large number of experts are deployed concurrently

## 12.1. Design Idea

Integrate the Trace collection SDK in the Motor warehouse, generate spanID, associate the spanID with the original TraceID, and transfer the spanID to the LLM warehouse. The asynchronous log recording mode is used. Trace information is written into log files of specified levels, ensuring performance and reliability in the scenario where a large number of experts are deployed concurrently.

## 12.2. Constraints

1. Compatible with the existing log system
2. Large-scale expert parallel solutions may increase log storage pressure.

--------------------

# 13. Automatically generating TraceIDs

## 13.1. Design Idea

Provides environment variables to control the automatic trace generation, and supports probability sampling and error sampling. The sampling configuration is based on environment variables. When a request is processed, the system determines whether to perform trace collection to ensure that the sampling result meets the expectation.

## 13.2. Constraints

1. The automatically generated TraceID must be globally unique.
2. Exercise caution when setting the sampling rate to avoid impact on performance.

--------------------

# 14. Collects core SGLang service-oriented indicators

## 14.1. Design Ideas

Reconstruct the vLLM configuration logic to support the SGLang framework and collect key information such as the scheduling execution process, KVCache, and request queue. Use the mediation to convert SGLang-specific data into the standard Trace format to ensure that the data can be properly displayed in the Insight.

## 14.2. Constraints

1. The SGLang framework is required to provide necessary monitoring interfaces.
2. The data format must be compatible with the existing parsing logic.

--------------------

# 15. SGLang torchprofiler parsing is supported

## 15.1. Design Ideas

Automatically identifies and parses torch profiler data in the SGLang service-based parsing process. Invoke the native parsing API of Torch to process data and convert the data into a format that can be identified by the Insight to ensure that the performance data can be correctly visualized.

## 15.2. Constraints

1. The torch profiler data format must be stable.
2. The parsing process may increase processing time.

--------------------

# 16. Supports SGLang torchprofiler collection

## 16.1. Design Idea

The service profiler control interface is extended to support the start and stop control of the torch profiler in the SGLang framework. The vLLM configuration mechanism is reused. Parameters such as the stack, memory, and collection step can be configured to ensure function consistency.

## 16.2. Constraints

1. The SGLang needs to support torch profiler integration.
2. The collection switch must ensure thread security.

--------------------

# 17. Supports multi-modal data collection

## 17.1. Design Ideas

According to the characteristics of multi-modal model, the acquisition points are inserted in the key paths of text and image processing modules. The collection phase and indicators are defined in the configuration file, and the time consumption of each module is displayed in the timeline. Models such as Qwen2.5-omni-3B are supported.

## 17.2. Constraints

1. Requires multimodal model version support
2. Special modules such as image processing may require customized acquisition logic.

--------------------

# 18. Supports MTP and speculative inference data collection

## 18.1. Design Ideas

Collect indicators such as the number of tokens, number of received tokens, and draft model inference time in the critical path of speculative inference. Request-level data is recorded in Batch CSV, and speculative inference time is marked in the trace diagram. Multiple draft models are supported.

## 18.2. Constraints

1. The speculative inference function must be enabled.
2. Data acquisition needs to be synchronized with the inference process.

--------------------

# 19. Supports torchprofiler collection and parsing

## 19.1. Design Ideas

Integrates the torch profiler collection interface for the Mindie and vLLM frameworks to support data collection and automatic identification. Invoke torch profiler to parse and process data to ensure that the Insight can be properly visualized and analyzed.

## 19.2. Constraints

1. The PyTorch version must be compatible.
2. Collecting a large amount of data may affect performance.

--------------------

# 20. Use the DB format to reduce the parsed data

## 20.1. Design Ideas

The operator data parsing output format is changed from JSON to a more compact DB format. A warning and alarm mechanism is added before parsing. When the data volume is too large, you are advised not to generate the JSON format. Significantly reduce disk space usage through formatting optimization.

## 20.2. Constraints

1. The DB format needs to be compatible with the existing tool chain.
2. Format changes require sufficient version transition period

--------------------

# 21. VLM supports token-level collection

## 21.1. Design Idea

Collects the number of tokens based on the step function mechanism of the service-oriented framework. Insert the collection control logic into the key node in token inference to ensure thread security and accurate collection of operator data within the target token range.

## 21.2. Constraints

1. An accurate token counting mechanism is required.
2. Acquisition control needs to be accurately synchronized with the inference process

--------------------

# 22. Automatically enabling operator collection based on conditions

## 22.1. Design Ideas

Monitors the batchsize indicator in the metric. When the specified conditions (size and number of times) are met, the operator collection is automatically triggered. The tool is automatically closed based on the existing time and token control mechanism, improving the usability of the tool.

## 22.2. Constraints

1. The metric monitoring system is required to run properly.
2. Conditional triggering may have slight delay

--------------------

# 23. Supports data comparison

## 23.1. Design Ideas

Develop the data comparison command, enter two collection file paths, and compare time statistics by span name. Outputs results in CSV format, including AVG, P50, and P90 statistics and difference calculation. Supports performance difference analysis.

## 23.2. Constraints

1. The collected data must have the same span structure.
2. Large-scale data comparison may take a long time.

--------------------

# 24. Summary of key information after analysis

## 24.1. Design Ideas

Export span data to CSV files. After the parsing is complete, statistics on the duration of key spans are generated. This feature includes the longest request analysis, average time required by each phase/P90, and displays the progress bar during the parsing, improving user experience.

## 24.2 Constraints

1. Key spans must be clearly defined and identified.
2. Progress estimates require accurate performance baseline data

--------------------

# 25. Provide the fast parsing capability

## 25.1. Design Ideas

Analyze the performance indicators that mindie and vLLM users are most concerned about and establish a quick parsing process. Key performance data is first extracted and displayed, and then completely parsed to balance the response speed and data integrity.

## 25.2. Constraints

1. Quick parse may not contain all the details
2. Prioritization of key metrics needs to be specified.

--------------------

# 26. Optimize the data structure of service-based disk distribution

## 26.1. Design Ideas

The collected data is stored in the visualized slice table format to avoid intermediate conversion. The database index is optimized to improve query performance and ensure that data can be directly displayed in MindStudio Insight, reducing data copy overhead.

## 26.2. Constraints

1. Data structure changes must be compatible with the Insight frontend.
2. The performance of large-amount data writes must be ensured.

--------------------

# 27. Develop collection standards for service-based collection scenarios and supplement points in different frameworks

## 27.1. Design Ideas

Formulate unified collection standards and specifications, and define core domain and span names and attributes. The standard points are supplemented in the vLLM framework, the parsing code is optimized to support the standard format, and the enumerated value interface is provided for users to use.

## 27.2. Constraints

1. Framework features must be taken into consideration in standard formulation.
2. Point supplementation requires the support of the framework version.

--------------------

# 28. Visual Lane Sorting

## 28.1. Design Ideas

Add scheduling process/inference process labels to a service-oriented data swimlane. Hostname and DP domain labels are supported. The display logic is unified by DP domain, improving the readability and fault locating efficiency of the GUI.

## 28.2. Constraints

1. The collected data must contain sufficient process ID information.
2. The sorting logic must adapt to different deployment scenarios.

--------------------

# 29. Starting and Stopping the Profile Using the CLI

## 29.1. Design Ideas

Develop an independent configuration management process to control the start and stop of the profiling through the CLI. The shared memory or inter-process communication mechanism is used to notify users of process configuration changes, avoiding frequent file read and write and improving usability.

## 29.2. Constraints

1. Reliable communication between processes must be ensured.
2. Command line control requires a permission management mechanism.

# 30. Reliability & Availability Design

## 30.1. Redundancy Design

**N/A: This feature collects monitoring data and is an observable component. It does not involve service data storage and core system functions. The loss of monitoring data does not affect the normal running of the vLLM core inference service.**

## 30.2. Fault Management

### 30.2.1. Fault detection

1. **Monitoring the status of the data collection process: Monitors the running status of the data collection process through the heartbeat mechanism.**
2. **Configuration validity check: Check the syntax and semantics during configuration file loading to prevent incorrect configurations from taking effect.**
3. **Data collection exception detection: Monitors the success rate of indicator collection and records detailed logs when an exception occurs.**

### 30.2.2. Fault Isolation

1. **Collection module isolation: Each collection module (metric, profiling, and trace) is independent of each other. A fault on a single module does not affect other functions.**
2. **Resource isolation: An independent memory buffer is used during data collection to avoid affecting the performance of vLLM core services.**

### 30.2.3. Fault Recovery

1. **Automatic retry mechanism: For temporary collection failures, a limited number of automatic retry is supported.**
2. **Elegant degradation: When resources are insufficient, the system automatically suspends the collection of non-key data to ensure core monitoring functions.**
3. **Configuration hot heavy load: Dynamic configuration update is supported. Abnormal configurations can be restored without restarting services.**

### 30.2.4. Alarm Design

1. **Key fault alarms: The collection process exits abnormally and configuration loading fails.**
2. **Performance exception alarm: An alarm is generated when the resource usage during collection exceeds the threshold.**

## 30.3. Overload control design

### 30.3.1. Traffic Detection and Control

1. **Data volume monitoring: Monitors the collected data volume in real time and sets the upper limit of memory usage.**
2. **Degradation policy:**
    
     * Slightly overloaded: Degrade low-frequency collection items first.
     * Medium overload: Pauses the collection of large data, such as profiling, and retains the core metric.
     * Heavy overload: Only the most critical running status indicators are retained.

### 30.3.2. Rate limiting mechanism

1. **Collection frequency limit: The minimum collection interval can be configured for each monitoring item to avoid excessive collection.**
2. **Data sampling control: Probabilistic sampling is supported and automatically enabled when the data volume is too large.**
3. **Queue buffer management: Set a proper size of the collected data buffer. When the buffer is full, the oldest data is discarded.**

### 30.3.3. Priority Guarantee

1. **Core indicators are preferred. Key service indicators, such as TPS and latency, have the highest collection priority.**
2. **Fault data priority: Error and abnormal monitoring data is preferentially collected and reported.**

## 30.4. Services are not interrupted during the upgrade

### 30.4.1. Compatibility Design

1. **Configuration backward compatibility: The new version supports the configuration file format of the old version and automatically adapts new fields.**
2. **Data format compatibility: The collected data format must be compatible with versions to ensure that the parsing tool can correctly process the data.**
3. **API interface stability: The external monitoring interface remains stable and provides a transition period when the interface is changed.**

### 30.4.2. Hot Upgrade Support

1. **Dynamic library loading: The collection module supports dynamic loading and unloading, implementing upgrade without shutdown.**
2. **Configuration retention: The current configuration status is retained during the upgrade and is automatically restored after the upgrade.**

### 30.4.3. Rollback Mechanism

1. **Version rollback: supports quick rollback to the previous stable version.**
2. **Configuration backup: The current configuration is automatically backed up before the upgrade and restored during the rollback.**

## 30.5. Design for human error

### 30.5.1. Operation safety

1. **High-risk operation confirmation: Reconfirmation is required for operations such as starting and stopping the profile and resetting the configuration.**
2. **Operation audit logs: All configuration changes and key operations are recorded in detailed audit logs.**
3. **Hierarchical permission control: Differentiate the permission of read-only monitoring users and configuration management users.**

### 30.5.2. Configuring Protection

1. **Configuration syntax verification: The YAML configuration file is strictly verified during loading. If the configuration file is incorrect, the loading is rejected.**
2. **Value range check: Check the proper value range of numeric parameters to prevent extreme values from affecting the system.**
3. **Configuration backup and restoration: supports configuration version management and one-click restoration.**

### 30.5.3. Error Prevention

1. **Configuration template: provides standard configuration templates to reduce configuration complexity.**
2. **Real-time preview: The collection effect can be previewed after the configuration is modified. The settings take effect only after the modification is confirmed.**
3. **Operation guide: provides detailed steps and risk warnings for key operations.**

## 30.6. Fault Prediction and Prevention Design

### 30.6.1. Health Status Monitoring

1. **Self-monitoring metrics: collects component running status metrics, such as memory usage and queue depth.**
2. **Performance trend analysis: Monitors and collects performance change trends and predicts potential problems.**
3. **Resource usage warning: Insufficient resources, such as disk space and memory, are warned in advance.**

### 30.6.2. Preventive Maintenance

1. **Periodic self-check: Perform component health status self-check periodically and handle problems in advance.**
2. **Capacity planning: Provide capacity planning suggestions based on the data growth trend.**
3. **Performance optimization suggestions: Provide configuration optimization suggestions based on running data.**

### 30.6.3. Data Quality Assurance

1. **Data integrity check: Periodically check the integrity and consistency of collected data.**
2. **Data collection delay monitoring: Monitors the real-time data collection and generates an alarm when the delay is too long.**
3. **Abnormal mode detection: detects abnormal modes of collected data through machine learning.**

# 31. Feature Non-Functional Quality Attribute Design

## 31.1. Testability

### 31.1.1. Test Direction

1. **Function correctness test: Verify the accuracy and completeness of the collection of monitoring indicators.**
2. **Performance impact test: To test the impact of the collection function on the vLLM inference performance (P99 delay increase < 5%).**
3. **Stability test: long-term running test to verify memory leakage and resource reclamation.**

### 31.1.2. Boundary Value Test

1. **Configuration boundary: Test the extreme values of the YAML configuration. (for example, overlong metric name and abnormal bucket settings)**
2. **Data volume boundary: Test the data collection stability in the scenario of high concurrency and large data volume.**
3. **Resource Boundaries: Test degradation behavior when system resources are insufficient.**

### 31.1.3. Abnormal Scenario Test

1. **Configuration error: Test fault tolerance handling of error configuration files.**
2. **Process exception: Test the recovery mechanism after the collection process exits abnormally.**
3. **Network exception: Test data buffering and processing when Prometheus connection fails.**

## 31.2. Serviceability

### 31.2.1. O&M Document

1. **Deployment Guide: Provides detailed installation configuration instructions and best practices**
2. **Troubleshooting manual: contains troubleshooting procedures and solutions for common problems.**
3. **Performance Optimization Guide: Guides How to Optimize Collection Configurations Based on Service Scenarios**

### 31.2.2. Monitoring Alarms

1. **Health check interface: provides RESTful interfaces for checking service status.**
2. **Key indicator monitoring: Monitors the running status of the collection service and generates alarms.**
3. **Log classification: supports DEBUG, INFO, WARNING, and ERROR logs to facilitate fault locating.**

### 31.2.3. Maintenance Tools

1. **Configuration verification tool: provides configuration syntax and semantic verification tools.**
2. **Data sampling tool: supports temporary data collection for problem analysis.**
3. **Performance analysis tool: built-in collection performance analysis function**

## 31.3. Evolvability

### 31.3.1. Architecture Design

1. **Plug-in architecture: New monitoring indicator types can be extended by plug-ins.**
2. **Configuration-driven: Most functions are implemented through configuration, reducing code modification requirements.**
3. **Interface abstraction: Clear interfaces for collection, processing, and output, facilitating function expansion.**

### 31.3.2. Version Planning

1. **Modular functions: Each sub-requirement is implemented independently and supports on-demand deployment.**
2. **Backward compatibility: New versions ensure compatibility of old configurations and data.**
3. **Progressive upgrade: supports function gray release and A/B test.**

## 31.4. Openness

### 31.4.1. Standard Interface

1. **Prometheus standard: The output of monitoring metrics complies with the Prometheus data format standard.**
2. **OpenTelemetry compatibility: Trace data supports the OpenTelemetry standard format.**
3. **RESTful API: The configuration management API complies with the RESTful design specifications.**

### 31.4.2. Integration Capabilities

1. **Multi-framework support: The architecture design supports multiple inference frameworks, such as vLLM and SGLang.**
2. **Scalable data source: Adds new data collection sources.**
3. **Output format extension: Supports other monitoring system data formats except Prometheus.**

## 31.5. Compatibility

### 31.5.1. Version Compatibility

1. **Configuration compatibility: The new version is compatible with the configuration file format of the old version. The obsolete parameters are clearly displayed.**
2. **Data compatibility: The format of collected data is forward compatible, ensuring that historical data can be parsed.**
3. **API compatibility: The transition period and version identifier are provided for external interface changes.**

### 31.5.2. Environment Compatibility

1. **Multi-version vLLM support: adapts to main vLLM versions and maintains stable core interfaces.**
2. **Python version compatibility: supports Python 3.8+ major versions.**
3. **OS compatibility: Mainstream Linux distributions are supported.**

## 31.6. Scalability/Scalability

### 31.6.1. Horizontal Expansion

1. **Distributed collection: Supports collaborative collection of multiple instances and distinguishes data sources by tags.**
2. **Load balancing: Dynamic allocation of collection tasks is supported to avoid single-point bottlenecks.**
3. **Data sharding: Data can be ingested by time or service in scenarios with a large amount of data.**

### 31.6.2. Vertical Expansion

1. **Resource elasticity: The usage of collection resources can be dynamically adjusted to adapt to different scales.**
2. **Performance optimization: The collection frequency and precision can be adjusted as required.**
3. **Storage optimization: Collected data compression and archiving policies are supported.**

## 31.7. Maintainability

### 31.7.1. Diagnostic capability

1. **Detailed logs: Key operations are recorded in detailed logs, including request IDs for tracing.**
2. **Running indicator: The collection service exposes running status indicators for monitoring and diagnosis.**
3. **Debugging mode: Enables detailed debugging information to facilitate fault locating.**

### 31.7.2. Maintenance Interface

1. **Dynamic configuration: Supports configuration updates during runtime without restarting services.**
2. **Status query: Provides various status query interfaces to learn the running status of each collection module.**
3. **One-click diagnosis: integrates the automatic diagnosis tool to quickly identify common problems.**

### 31.7.3. Complete Documentation

1. **Code comments: The core code has detailed comments, describing the design intent and implementation logic.**
2. **Architecture document: provides system architecture and module design documents.**
3. **Change History: Maintain detailed version change history and compatibility description.**

# 32. (Optional) Data Structure Design

None

# 33. List of references

**Table Catalogue**

**Figure Catalogue**

**List of abbreviations:**

| Abbreviations | Full spelling English full name | Chinese explanation Chinese explanation |
| ------------- | ------------------------------- | --------------------------------------- |
| -             | -                               | -                                       |
