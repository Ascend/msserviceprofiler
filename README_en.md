<h1 align="center">MindStudio Service Profiler</h1>

<div align="center">
<p><b><span style="font-size:24px;">Ascend AI Serving Tuning Tool</span></b></p>

 [![Quick Start](https://badgen.net/badge/Quick%20Start/QuickStart/blue)](./docs/en/quick_start/quick_start.md)
 [![Exact Search](https://badgen.net/badge/Exact%20Search/ReadTheDocs/blue)](https://msserviceprofiler.readthedocs.io/zh-cn/latest/)
 [![AI Q&A](https://badgen.net/badge/AI%20Q%26A/DeepWiki/blue)](https://deepwiki.com/mindstudio-docs/master)
 [![AI Q&A](https://badgen.net/badge/AI%20Q%26A/ZRead/blue)](https://zread.ai/mindstudio-docs/master)
 [![Ascend Community](https://badgen.net/badge/Ascend%20Community/Community/blue)](https://www.hiascend.com/en/developer/software/mindstudio)
 [![Report an Issue](https://badgen.net/badge/Report%20an%20Issue/Issues/blue)](https://gitcode.com/Ascend/msserviceprofiler/issues)

</div>

English | [简体中文](https://gitcode.com/Ascend/msserviceprofiler/blob/master/README.md)

## ✨ Latest News

🔹 [2026.03.24] Prometheus online monitoring is supported.<br>
🔹 [2025.12.30] Torch Profiler data collection and parsing are supported.<br>
🔹 [2025.11.30] Integrated with the OpenTelemetry ecosystem to support end-to-end trace tracking.<br>
🔹 [2025.11.24] Non-intrusive automatic instrumentation collection is supported for the vLLM framework.<br>
🔹 [2025.11.07] The plugin-based mode for automatic tuning is released.<br>

## ℹ️ Overview

MindStudio Service Profiler is a full-stack performance analysis and tuning tool designed specifically for large model inference services. Through non-intrusive collection, high-performance data persistence, and multi-dimensional correlation analysis, it helps users gain deep insight into the runtime performance of inference frameworks (such as MindIE, vLLM, and SGLang) on Ascend hardware and accurately locate performance bottlenecks.

## ⚙️ Features

For different usage scenarios, this tool provides the following features. For details, see the corresponding reference documents.

| Feature | Description | Documentation |
|:---|:---|:---|
| [Performance tuning] Serving performance tuning | Understand the serving tuning data format, visualization analysis methods, and typical tuning process | [Click to view](docs/en/user_guide/msserviceprofiler_serving_tuning_instruct.md) |
| [Performance collection] vLLM serving performance collection | Dedicated serving performance collection for vLLM scenarios | [Click to view](docs/en/user_guide/vLLM_service_oriented_performance_collection_tool.md) |
| [Performance collection] SGLang serving performance collection | Dedicated serving performance collection for SGLang scenarios | [Click to view](docs/en/user_guide/SGLang_service_oriented_performance_collection_tool.md) |
| [Data monitoring] MindIE trace data link monitoring | Connects the server-side request link to the OTLP ecosystem such as Jaeger | [Click to view](docs/en/user_guide/msserviceprofiler_trace_data_monitoring_instruct.md) |
| [Online monitoring] vLLM Prometheus online monitoring | Works with Prometheus to perform online monitoring on vLLM-Ascend | [Click to view](docs/en/user_guide/vLLM_metrics_tool_instruct.md) |
| [Comparison analysis] Performance data comparison | Compares performance results of different versions or configurations | [Click to view](docs/en/user_guide/ms_service_profiler_compare_tool_instruct.md) |
| [Comparison analysis] Multi-dimensional analysis | Performs in-depth analysis of the collected performance data from multiple dimensions | [Click to view](docs/en/user_guide/msserviceprofiler_multi_analyze_instruct.md) |
| [Comparison analysis] Split analysis | Performs fine-grained split analysis of the serving performance data | [Click to view](docs/en/user_guide/service_performance_split_tool_instruct.md) |
| [Tuning suggestions] Serving automatic tuning | Performs automatic parameter tuning based on the existing collected data | [Click to view](docs/en/user_guide/serviceparam_optimizer_instruct.md) |
| [Tuning suggestions] Serving automatic tuning plugin mode | Performs automatic parameter tuning in plugin mode | [Click to view](docs/en/user_guide/serviceparam_optimizer_plugin_instruct.md) |
| [Tuning suggestions] Serving expert advice | Obtains performance tuning expert advice based on the collected data | [Click to view](docs/en/user_guide/service_profiling_advisor_instruct.md) |

## 🚀 Quick Start

For a quick start to the msServiceProfiler serving tuning tool, including the necessary operation steps and parameter descriptions, see [Quick Start](docs/en/quick_start/quick_start.md).

## 🛠️ Tool Installation

The msServiceProfiler tool supports online installation, offline installation, and source code installation. For details, see [msServiceProfiler Installation Guide](docs/en/install_guide/msserviceprofiler_install_guide.md).

## 💡 Typical Cases

For more cases, see [msServiceProfiler Typical Cases](./docs/en/best_practices/README.md).

## 🌌 Smart Search

To improve the efficiency of document lookup, we provide several efficient search methods:<br>
🔹 [AI Q&A (DeepWiki)](https://deepwiki.com/mindstudio-docs/master): Natural language Q&A for quickly grasping the project architecture and module relationships.<br>
🔹 [AI Q&A (ZRead)](https://zread.ai/mindstudio-docs/master): A better Chinese Q&A experience for precisely locating feature usage and details.<br>
🔹 [Exact Search (ReadTheDocs)](https://mindstudio-docs-master.readthedocs.io): Full-text keyword search for directly accessing information about APIs, parameters, error messages, and more.<br>

## 🛠️ Contributing Guide

We welcome contributions to the project. See [Contributing Guide](https://gitcode.com/Ascend/msserviceprofiler/blob/master/CONTRIBUTING.md).

## ⚖️ Related Information

🔹 [Release Notes](https://gitcode.com/Ascend/msserviceprofiler/releases)<br>
🔹 [License Notice](./docs/en/legal/license_notice.md)<br>
🔹 [Disclaimer](./docs/en/legal/disclaimer.md)<br>

## 🤝 Suggestions and Feedback

We welcome everyone to contribute to the community. If you have any questions or suggestions, please submit an [issue](https://gitcode.com/Ascend/msserviceprofiler/issues), and we will respond as soon as possible. Thank you for your support.

| Instant Messaging (WeChat Group) | Official News (Official Account) | In-Depth Support (Assistant/Forum) |
| :---: | :---: | :---- |
| <img src="https://raw.gitcode.com/Ascend/docs/files/master/common/Writing_Template/figures/qr_code_wechat_work.png" width="120"><br><sub>*Scan the QR code to join the technical exchange group*</sub> | <img src="https://raw.gitcode.com/Ascend/docs/files/master/common/Writing_Template/figures/qr_code_wechat_official_account.png" width="120"><br><sub>*Scan the QR code to follow the official account*</sub> | Scan the QR code to join the group and follow the official account for the fastest communication platform for MindStudio users and developers:<br> **Quick Questions:** Discuss technical issues with community members in real time<br>**Stay Updated:** Get version release and feature update notifications as soon as possible<br> **Experience Sharing:** Exchange best practices and hands-on insights with developers  <br> <br> **More Support Channels**:<br>👉 Ascend Assistant: [![WeChat](https://img.shields.io/badge/WeChat-07C160?style=flat-square&logo=wechat&logoColor=white)](https://gitcode.com/Ascend/msit/blob/master/docs/zh/figures/readme/xiaozhushou.png)<br> 👉 Ascend Forum: [![Website](https://img.shields.io/badge/Website-%231e37ff?style=flat-square&logo=RSS&logoColor=white)](https://www.hiascend.com/forum/) |

## 🙏 Acknowledgments

This tool is jointly contributed by Huawei Technologies Co., Ltd. and community developers.
Thank you for every PR from the community. Contributions are welcome.
