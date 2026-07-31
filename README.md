<h1 align="center">MindStudio Service Profiler</h1>

<div align="center">
<p><b><span style="font-size:24px;">昇腾 AI 服务化调优工具</span></b></p>

 [![License](https://badgen.net/badge/快速入门/QuickStart/blue)](./docs/zh/quick_start.md)
 [![License](https://badgen.net/badge/精确搜索/ReadTheDocs/blue)](https://msserviceprofiler.readthedocs.io/zh-cn/latest/)
 [![License](https://badgen.net/badge/AI问答/DeepWiki/blue)](https://deepwiki.com/mindstudio-docs/master)
 [![License](https://badgen.net/badge/AI问答/ZRead/blue)](https://zread.ai/mindstudio-docs/master)
 [![License](https://badgen.net/badge/昇腾社区/Community/blue)](https://www.hiascend.com/cn/developer/software/mindstudio)
 [![License](https://badgen.net/badge/报告问题/Issues/blue)](https://gitcode.com/Ascend/msserviceprofiler/issues)

</div>

## ✨ 最新消息

🔹 [2026.03.24] 支持 Prometheus 在线监测。  
🔹 [2025.12.30] 支持Torch Profiler数据采集与解析。  
🔹 [2025.11.30] 对接 OpenTelemetry 生态，支持全链路 Trace 追踪。  
🔹 [2025.11.24] 支持 vLLM 框架的无侵入自动插桩采集。  
🔹 [2025.11.07] 发布自动寻优插件化模式。  

## ℹ️ 简介

MindStudio Service Profiler 是一款专为大模型推理服务设计的全栈性能分析与调优工具。它通过无侵入式采集、高性能数据持久化及多维关联分析，帮助用户深入洞察推理框架（如 MindIE, vLLM, SGLang）在昇腾硬件上的运行表现，精准定位性能瓶颈。

## ⚙️ 功能介绍

面向不同使用场景，本工具提供以下功能，详细用法请参见对应参考文档：

| 功能名称                       | 功能描述                               | 详细介绍                                                                   |
|:---------------------------|:-----------------------------------|:-----------------------------------------------------------------------|
| 【性能调优】服务化性能调优              | 理解服务化调优数据格式、可视化分析方式及典型调优流程         | [点击查看](docs/zh/msserviceprofiler_serving_tuning_instruct.md)           |
| 【性能采集】vLLM 服务化性能采集         | 针对 vLLM 框架场景的专项服务化性能采集             | [点击查看](docs/zh/vLLM_service_oriented_performance_collection_tool.md)   |
| 【性能采集】SGLang 服务化性能采集       | 针对 SGLang 框架场景的专项服务化性能采集           | [点击查看](docs/zh/SGLang_service_oriented_performance_collection_tool.md) |
| 【数据监测】MindIE Trace 数据链路监测  | 将服务端请求链路打通到 Jaeger 等 OTLP 生态       | [点击查看](docs/zh/msserviceprofiler_trace_data_monitoring_instruct.md)    |
| 【在线监测】vLLM Prometheus 在线监测 | 在 vLLM-Ascend 上结合 Prometheus 做在线监控 | [点击查看](docs/zh/vLLM_metrics_tool_instruct.md)                          |
| 【比对分析】性能数据比对               | 对不同版本/配置的性能结果做对比分析                 | [点击查看](docs/zh/ms_service_profiler_compare_tool_instruct.md)           |
| 【比对分析】多维度解析                | 从多维度对采集的性能数据做深入分析                  | [点击查看](docs/zh/msserviceprofiler_multi_analyze_instruct.md)            |
| 【比对分析】拆解分析                 | 对服务化性能数据做细粒度拆解分析                   | [点击查看](docs/zh/service_performance_split_tool_instruct.md)             |
| 【寻优建议】服务化自动寻优              | 在已有采集数据基础上进行参数自动寻优                 | [点击查看](docs/zh/serviceparam_optimizer_instruct.md)                     |
| 【寻优建议】服务化自动寻优插件模式          | 以插件化模式进行参数自动寻优                     | [点击查看](docs/zh/serviceparam_optimizer_plugin_instruct.md)              |
| 【寻优建议】服务化专家建议              | 基于采集数据获取性能调优专家建议                   | [点击查看](docs/zh/service_profiling_advisor_instruct.md)                  |

## 🚀 快速入门

msServiceProfiler服务化调优工具的快速入门，包括必要的操作步骤、参数说明等，具体请参见《[快速入门](docs/zh/quick_start.md)》。

## 🛠️ 工具安装

安装msServiceProfiler工具，详情请参见《[msServiceProfiler 安装指南](docs/zh/msserviceprofiler_install_guide.md)》。

## 🌌 智能检索

为提升文档查阅效率，我们提供多种高效检索方式：  
🔹 [AI 问答（DeepWiki）](https://deepwiki.com/mindstudio-docs/master)：自然语言问答，快速把握项目架构与模块关系。   
🔹 [AI 问答（ZRead）](https://zread.ai/mindstudio-docs/master)：中文问答体验更优，精准定位功能用法与细节。   
🔹 [精确搜索（ReadTheDocs）](https://mindstudio-docs-master.readthedocs.io)：关键词全文检索，直达接口、参数与报错等信息。  

## 🛠️ 贡献指南

欢迎参与项目贡献，请参见《[贡献指南](CONTRIBUTING.md)》。

## ⚖️ 相关说明

🔹《[版本说明](https://gitcode.com/Ascend/msserviceprofiler/releases)》  
🔹《[许可证声明](./docs/zh/legal/license_notice.md)》  
🔹《[免责声明](./docs/zh/legal/disclaimer.md)》  

## 🤝 建议与交流

欢迎大家为社区做贡献。如果有任何疑问或建议，请提交 [Issues](https://gitcode.com/Ascend/msserviceprofiler/issues)，我们会尽快回复。感谢您的支持。

|                                                                         即时互动（微信群）                                                                          |                                                                               官方资讯（公众号）                                                                                | 深度支持（助手/论坛）                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
|:----------------------------------------------------------------------------------------------------------------------------------------------------------:|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------:|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| <img src="https://raw.gitcode.com/Ascend/docs/files/master/common/Writing_Template/figures/qr_code_wechat_work.png" width="120"><br><sub>*扫码加入技术交流群*</sub> | <img src="https://raw.gitcode.com/Ascend/docs/files/master/common/Writing_Template/figures/qr_code_wechat_official_account.png" width="120"><br><sub>*扫码关注官方公众号*</sub> | 扫码入群并关注公众号，直达 MindStudio 用户与开发者最快捷的交流平台：<br> **快速提问：** 与社区小伙伴即时探讨技术问题<br>**掌握动态：** 第一时间获取版本发布与功能更新通知<br> **经验共享：** 与广大开发者交流最佳实践与实战心得  <br> <br> **更多支持渠道**：👉 昇腾助手：[![WeChat](https://img.shields.io/badge/WeChat-07C160?style=flat-square&logo=wechat&logoColor=white)](https://gitcode.com/Ascend/msit/blob/master/docs/zh/figures/readme/xiaozhushou.png) 👉 昇腾论坛：[![Website](https://img.shields.io/badge/Website-%231e37ff?style=flat-square&logo=RSS&logoColor=white)](https://www.hiascend.com/forum/) |

## 🙏 致谢

本工具由华为公司的下列部门联合贡献：  
🔹 昇腾计算MindStudio开发部  
🔹 昇腾计算生态使能部  
🔹 华为云昇腾云服务  
感谢来自社区的每一个PR，欢迎贡献！
