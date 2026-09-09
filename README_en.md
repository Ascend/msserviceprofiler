<!-- md-trans-meta sourceCommit=8bbd83215246d3a7d72a80c3882c3c0d8f900220 translatedAt=2026-08-18T11:29:46.053Z pushedAt=2026-08-18T11:33:07.826Z -->

<h1 align="center">MindStudio Service Profiler</h1>
<div align="center">
<p><b><span style="font-size:24px;">Ascend AI Serving Tuning Tool</span></b></p>

 [![License](https://badgen.net/badge/Quick Start/QuickStart/blue)](./docs/en/quick_start.md)
 [![License](https://badgen.net/badge/AI Q&A/DeepWiki/blue)](https://deepwiki.com/mindstudio-docs/master)
 [![License](https://badgen.net/badge/AI Q&A/ZRead/blue)](https://zread.ai/mindstudio-docs/master)
 [![License](https://badgen.net/badge/Ascend Community/Community/blue)](https://www.hiascend.com/cn/developer/software/mindstudio)
 [![License](https://badgen.net/badge/Report Issues/Issues/blue)](https://gitcode.com/Ascend/msserviceprofiler/issues)

</div>

English | [简体中文](./README.md)

## ✨ Latest News

- [2026-03-24] Added support for Prometheus online monitoring.

- [2025-12-30] Added support for Torch Profiler data collection and parsing.

- [2025-11-30] Integrated with the OpenTelemetry ecosystem and supports end-to-end trace tracking.

- [2025-11-24] Added support for non-intrusive automatic instrumentation collection for the vLLM framework.

- [2025-11-07] Released the plugin-based mode for automatic optimization.

## ℹ️ Overview

MindStudio Service Profiler is a full-stack performance analysis and tuning tool designed specifically for large model inference services. Through non-intrusive collection, high-performance data persistence, and multi-dimensional correlation analysis, it helps users gain deep insight into the runtime performance of inference frameworks (such as MindIE, vLLM, and SGLang) on Ascend hardware and accurately locate performance bottlenecks.

## 🗺️ Directory Structure

The key directories are as follows. For a detailed directory description, see [Project Directory](docs/en/dir_structure.md).

```ColdFusion
├─docs                             # Documentation directory
├─include                          # Directory for external collection APIs
├─ms_service_profiler              # Basic functionality directory (parsing, data comparison, etc.). This is the main Python source directory.
│ ├─tracer                        # Trace data monitoring directory
│ ├─patcher                       # vLLM service profiling directory
├─msservice_advisor/               # Expert advice tool directory
├─ms_serviceparam_optimizer/                  # Auto-optimization tool directory
└── cpp                            # Basic functionality directory (collection). This is the main C++ source directory
└─test                             # Test directory
```

## 🛠️ Tool Installation

To install the msServiceProfiler tool, for details, see [msServiceProfiler Tool Installation Guide](docs/en/msserviceprofiler_install_guide.md).

## 🚀 Quick Start

The Quick Start for the msServiceProfiler service-oriented tuning tool includes the necessary operation steps and parameter descriptions. For details, see [Quick Start](docs/en/quick_start.md).

## ⚙️ Feature Introduction

For different usage scenarios, you are advised to quickly experience this tool in the following order:

1. **Serving performance tuning**: Gain a detailed understanding of the service-oriented tuning data format, visualization analysis methods, and typical tuning process. See Also [Serving Tuning Tool](docs/en/msserviceprofiler_serving_tuning_instruct.md).

2. **Dedicated collection for vLLM / SGLang scenarios**: If you focus on only one framework, you can directly refer to the corresponding service-oriented performance collection tool usage guide:

    - [vLLM Serving Performance Collection Tool](docs/en/vLLM_service_oriented_performance_collection_tool.md)

    - [SGLang Serving Performance Collection Tool](docs/en/SGLang_service_oriented_performance_collection_tool.md)

3. **Trace data link monitoring (MindIE scenario)**: When you need to connect the server-side request link to the OTLP ecosystem such as Jaeger, see [Trace Data Monitoring Tool](docs/en/msserviceprofiler_trace_data_monitoring_instruct.md).

4. **Prometheus online monitoring (vLLM scenario)**: If you need to perform online monitoring on vLLM-Ascend with Prometheus, see [vLLM Serving Prometheus Data Monitoring Tool User Guide](docs/en/vLLM_metrics_tool_instruct.md). Prometheus and Grafana are third-party open-source software and are not part of the MindStudio product release package. You can select other compatible monitoring and visualization solutions based on the actual environment. If you use Prometheus, use a secure version and complete the necessary security hardening.

5. **Comparison and multi-dimensional analysis of collected data**: When comparing performance results of different versions/configurations or performing in-depth analysis from multiple dimensions, see:

    - [Serving Performance Data Comparison Tool](docs/en/ms_service_profiler_compare_tool_instruct.md)

    - [Serving Multi-dimensional Analysis Tool](docs/en/msserviceprofiler_multi_analyze_instruct.md)

    - [Serving Decomposition Tool](docs/en/service_performance_split_tool_instruct.md)

6. **Automatic Optimization and Expert Suggestions (Advanced Capabilities)**: To perform automatic parameter optimization or obtain expert suggestions based on existing collected data, see also:

    - [Serving Auto-tuning Tool](docs/en/serviceparam_optimizer_instruct.md)

    - [Serving Auto-tuning Plugin Mode](docs/en/serviceparam_optimizer_plugin_instruct.md)

    - [Serving Expert Advice Tool](docs/en/service_profiling_advisor_instruct.md)

## 🌌 Intelligent Search

To improve document lookup efficiency, we provide multiple efficient search methods:  
🔹 [AI Q&A (DeepWiki)](https://deepwiki.com/mindstudio-docs/master): natural language Q&A for quickly grasping the project architecture and module relationships.   
🔹 [AI Q&A (ZRead)](https://zread.ai/mindstudio-docs/master): better Q&A experience for precisely locating feature usage and details.   
🔹 [Exact Search (ReadTheDocs)](https://mindstudio-docs-master.readthedocs.io): keyword full-text search for directly accessing interfaces, parameters, and error messages.  

## ⚖️ Related Notes

- [Release Notes](https://gitcode.com/Ascend/msserviceprofiler/releases)

- [Contribution Guide](CONTRIBUTING.md)

- [Disclaimer](./docs/en/legal/disclaimer.md)

- [License Notice](./docs/en/legal/license_notice.md)

## 🤝 Suggestions and Communication

You are welcome to contribute to the community. If you have any questions or suggestions, submit them to [Issues](https://gitcode.com/Ascend/msserviceprofiler/issues), and we will reply as soon as possible. Thank you for your support.

|                                                                         Instant Interaction (WeChat Group)                                                                          |                                                                               Official News (Official Account)                                                                                | In-depth Support (Assistant/Forum)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
|:----------------------------------------------------------------------------------------------------------------------------------------------------------:|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------:|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| <img src="https://raw.gitcode.com/Ascend/docs/files/master/common/Writing_Template/figures/qr_code_wechat_work.png" width="120"><br><sub>*Scan the QR code to join the technical exchange group*</sub> | <img src="https://raw.gitcode.com/Ascend/docs/files/master/common/Writing_Template/figures/qr_code_wechat_official_account.png" width="120"><br><sub>*Scan the QR code to follow the official account*</sub> | Scan the QR code to join the group and follow the official account for the fastest communication platform for MindStudio users and developers:<br> **Quick Questions:** Discuss technical issues with community members in real time<br>**Stay Updated:** Get version release and feature update notifications as soon as possible<br> **Experience Sharing:** Exchange best practices and hands-on insights with developers  <br> <br> **More Support Channels**:👉 Ascend Assistant: [![WeChat](https://img.shields.io/badge/WeChat-07C160?style=flat-square&logo=wechat&logoColor=white)](https://gitcode.com/Ascend/msit/blob/master/docs/zh/figures/readme/xiaozhushou.png) 👉 Ascend Forum: [![Website](https://img.shields.io/badge/Website-%231e37ff?style=flat-square&logo=RSS&logoColor=white)](https://www.hiascend.com/forum/) |

## 🙏 Acknowledgments

msServiceProfiler is jointly contributed by the following departments of Huawei:

- Ascend Computing MindStudio Development Department

Thanks to every PR from the community. Contributions to msServiceProfiler are welcome!

## About the MindStudio Team

The Huawei MindStudio full-process development toolchain team is committed to providing end-to-end Ascend AI app development solutions, enabling developers to efficiently complete training development. For more information, visit [Ascend Community](https://www.hiascend.com/developer/software/mindstudio) and [Ascend Forum](https://www.hiascend.com/forum/).
