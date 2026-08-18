<h1 align="center">MindStudio Service Profiler</h1>

<div align="center">

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Cztk5380/msserviceprofiler) [![Docs](https://badgen.net/badge/Docs/readthedocs/green)](https://msserviceprofiler.readthedocs.io/zh-cn/latest/) [![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/) [![License](https://badgen.net/badge/License/MulanPSL-2.0/blue)](https://raw.gitcode.com/Ascend/msserviceprofiler/raw/26.0.0/LICENSE) [![Version](https://badgen.net/badge/Version/26.0.0-alpha.1/orange)](https://gitcode.com/Ascend/msserviceprofiler/releases/tag_MindStudio_26.0.0-alpha.1)
</div>

简体中文 | [English](./README_EN.md)

## 📢 最新消息

- [2026.03.24] 支持 Prometheus 在线监测。
- [2025.12.30] 支持Torch Profiler数据采集与解析。
- [2025.11.30] 对接 OpenTelemetry 生态，支持全链路 Trace 追踪。
- [2025.11.24] 支持 vLLM 框架的无侵入自动插桩采集。
- [2025.11.07] 发布自动寻优插件化模式。

## 📌 简介

MindStudio Service Profiler 是一款专为大模型推理服务设计的全栈性能分析与调优工具。它通过无侵入式采集、高性能数据持久化及多维关联分析，帮助用户深入洞察推理框架（如 MindIE, vLLM, SGLang）在昇腾硬件上的运行表现，精准定位性能瓶颈。

## 🔍 目录结构

关键目录如下，详细目录介绍参见[项目目录](docs/zh/dir_structure.md)。

```ColdFusion
├─docs                             # 文档目录
├─include                          # 采集能力对外接口目录
├─ms_service_profiler              # 基础能力目录（解析、数据比对等），python源码主目录
│  ├─tracer/                       # Trace数据监测能力目录
│  ├─patcher/                      # vLLM、SGLang服务化调优能力目录
├─msservice_advisor/               # 专家建议工具目录
├─ms_serviceparam_optimizer/       # 自动寻优工具目录
├─ms_service_metric/               # 在线监测工具目录
└── cpp                            # 基础能力目录（采集），C++源码主目录
└─test                             # 测试目录
```

## 工具安装

安装msServiceProfiler工具，详情请参见《[msServiceProfiler工具安装指南](docs/zh/msserviceprofiler_install_guide.md)》。

## 🚀 快速入门

msServiceProfiler服务化调优工具的快速入门，包括必要的操作步骤、参数说明等，具体请参见[快速入门](docs/zh/quick_start.md)。

## 📖 功能介绍

面向不同使用场景，建议按照以下顺序快速体验本工具：

1. **服务化性能调优**：详细理解服务化调优数据格式、可视化分析方式及典型调优流程，参见[服务化调优工具](docs/zh/msserviceprofiler_serving_tuning_instruct.md)。

2. **vLLM / SGLang 场景专项采集**：如只关注某一框架，可直接参考对应服务化性能采集工具使用指南：
    - [vLLM 服务化性能采集工具](docs/zh/vLLM_service_oriented_performance_collection_tool.md)
    - [SGLang 服务化性能采集工具](docs/zh/SGLang_service_oriented_performance_collection_tool.md)

3. **Trace 数据链路监测（MindIE 场景）**：需要将服务端请求链路打通到 Jaeger 等 OTLP 生态时，参见[Trace数据监测工具](docs/zh/msserviceprofiler_trace_data_monitoring_instruct.md)。

4. **Prometheus 在线监测（vLLM 场景）**：如需在 vLLM-Ascend 上结合 Prometheus 做在线监控，参见[vLLM 服务化 Prometheus 数据监测工具使用指南](docs/zh/vLLM_metrics_tool_instruct.md)。

5. **采集数据的比对与多维分析**：对不同版本/配置的性能结果做对比或从多维度深入分析时，参见：
    - [服务化性能数据比对工具](docs/zh/ms_service_profiler_compare_tool_instruct.md)
    - [服务化多维度解析工具](docs/zh/msserviceprofiler_multi_analyze_instruct.md)
    - [服务化拆解工具](docs/zh/service_performance_split_tool_instruct.md)

6. **自动寻优与专家建议（进阶能力）**：在已有采集数据基础上进行参数自动寻优或获取专家建议时，参见：
    - [服务化自动寻优工具](docs/zh/serviceparam_optimizer_instruct.md)
    - [服务化自动寻优插件模式](docs/zh/serviceparam_optimizer_plugin_instruct.md)
    - [服务化专家建议工具](docs/zh/service_profiling_advisor_instruct.md)

## 📝 相关说明

- 《[版本说明](./docs/zh/release_notes.md)》
- 《[贡献指南](CONTRIBUTING.md)》
- 《[免责声明](./docs/zh/legal/disclaimer.md)》
- 《[License声明](./docs/zh/legal/license_notice.md)》

## 💬 建议与交流

欢迎大家为社区做贡献。如果有任何疑问或建议，请提交[Issues](https://gitcode.com/Ascend/msserviceprofiler/issues)，我们会尽快回复。感谢您的支持。

|                   📱 关注 MindStudio 公众号                   | 💬 更多交流与支持                                             |
| :----------------------------------------------------------: | :----------------------------------------------------------- |
| <img src="https://raw.gitcode.com/Ascend/msot/files/master/docs/zh/figures/readme/officialAccount.png" width="120"><br><sub>*扫码关注获取最新动态*</sub> | 💡 **加入微信交流群**：<br>关注公众号，回复“交流群”即可获取入群二维码。<br><br>🛠️ **其他渠道**：<br>👉 昇腾助手：[![WeChat](https://img.shields.io/badge/WeChat-07C160?style=flat-square&logo=wechat&logoColor=white)](https://gitcode.com/Ascend/msot/blob/master/docs/zh/figures/readme/xiaozhushou.png)<br>👉 昇腾论坛：[![Website](https://img.shields.io/badge/Website-%231e37ff?style=flat-square&logo=RSS&logoColor=white)](https://www.hiascend.com/forum/) |

## 🤝 致谢

msServiceProfiler由华为公司的下列部门联合贡献：

- 昇腾计算MindStudio开发部

感谢来自社区的每一个PR，欢迎贡献msServiceProfiler！ 

## 关于MindStudio团队

华为MindStudio全流程开发工具链团队致力于提供端到端的昇腾AI应用开发解决方案，使能开发者高效完成训练开发、更多信息请访问 [昇腾社区](https://www.hiascend.com/developer/software/mindstudio) 和 [昇腾论坛](https://www.hiascend.com/forum/)。
