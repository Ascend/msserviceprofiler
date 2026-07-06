# MindStudio Service Profiler

## What's New

- [2025.12.30] Added support for Torch Profiler data collection and parsing.
- [2025.11.30] Added integration with the OpenTelemetry ecosystem for data tracing.
- [2025.11.24] Added support for non-intrusive auto-instrumentation to collect vLLM framework serving profile data.
- [2025.11.07] Added support for auto-optimization plug-in.
- [2025.09.30] Added support for auto-optimizing MindIE's Prefill-Decode (PD) disaggregation deployment on a single A2 server.
- [2025.09.30] Added support for fine-tuning in auto-optimization to improve search efficiency.
- [2025.09.30] Added support for operator communication data collection and parsing.
- [2025.09.30] Added support for collecting service profile data on the coordinator in the streaming request-response mode.
- [2025.09.30] Added support for parsing service profile data to generate `request_inference_forward.csv` and `request_status.csv` tables.
- [2025.09.30] Added support for expert load heatmap analysis for MindIE dynamic load balancing.
- [2025.08.25] Added support for profile data collection and parsing for the vLLM-v1 service framework.

## Overview

This document describes the profiling tool (msServiceProfiler) for inference serving. The msServiceProfiler APIs collect start and end times for key processes, identify main functions or iterations, and record important events during the MindIE and vLLM inference serving. msServiceProfiler profiles various data and helps pinpoint performance issues quickly.

## Directory Structure

The key directories are as follows. For details, see [Project Directory](docs/en/dir_structure.md).

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

## Tool Installation

To install msServiceProfiler, see [msServiceProfiler Installation Guide](docs/en/msserviceprofiler_install_guide.md).

## Quick Start

For a quick start with msServiceProfiler, including necessary operation steps and parameter descriptions, see [Quick Start](docs/en/quick_start.md).

## Function Description

For different usage scenarios, you can experience this tool quickly in the following order:

1. **Service performance optimization**: For details about the profile data formats, visualization analysis methods, and typical tuning workflows, see [msServiceProfiler](docs/en/msserviceprofiler_serving_tuning_instruct.md).
2. **vLLM-/SGLang-specific collection**: If focusing on a specific framework, see the corresponding guide:
   - [vLLM Service Profiler](docs/en/vLLM_service_oriented_performance_collection_tool.md)
   - [SGLang Service Profiler](docs/en/SGLang_service_oriented_performance_collection_tool.md)
3. **Trace data link monitoring**: To export server request traces to OTLP-compliant backends such as Jaeger, see [Trace Data Monitoring Tool](docs/en/msserviceprofiler_trace_data_monitoring_instruct.md).
4. **Comparison and multi-dimensional analysis on collected data**: To compare performance results from different versions/configurations or perform in-depth analysis from multiple dimensions, see the following documents:
   - [msServiceProfiler Compare Tool](docs/en/ms_service_profiler_compare_tool_instruct.md)
   - [msServiceProfiler Multi Analyze](docs/en/msserviceprofiler_multi_analyze_instruct.md)
   - [Service Performance Split Tool](docs/en/service_performance_split_tool_instruct.md)
5. **Auto-optimization and expert suggestions (advanced capabilities)**: For details about how to automatically optimize parameters or obtain expert suggestions based on the collected data, see the following documents:
   - [Serviceparam Optimizer](docs/en/serviceparam_optimizer_instruct.md)
   - [Serviceparam Optimizer Plugin Mode](docs/en/serviceparam_optimizer_plugin_instruct.md)
   - [Service Expert Advisor](docs/en/service_profiling_advisor_instruct.md)
6. **Online monitoring and Prometheus integration (vLLM scenario)**: For details about how to monitor Prometheus metrics online in the vLLM-Ascend framework, see [vLLM Serving Prometheus Metric Monitoring Tool User Guide](docs/en/vLLM_metrics_tool_instruct.md).

## How to Contribute

For instructions on reporting issues, requesting features, and contributing code to msServiceProfiler, see [Contributing to MindStudio ServiceProfiler](CONTRIBUTING.md).

## Contact Us

<div>
  <a href="https://raw.gitcode.com/kali20gakki1/Imageshack/raw/main/CDC0BEE2-8F11-477D-BD55-77A15417D7D1_4_5005_c.jpeg">
    <img src="https://img.shields.io/badge/WeChat-07C160?style=for-the-badge&logo=wechat&logoColor=white"></a>
</div>

## Disclaimer

### To msServiceProfiler Users

1. The models and datasets referenced in msServiceProfiler test cases and examples are used only for functional testing. Huawei does not provide any model weights or datasets. If you use this data for training or inference, you must comply with the respective model and dataset licenses. Huawei is not responsible for any infringement disputes arising from your use of these models and datasets.
2. If you encounter any issues while using msServiceProfiler (including but not limited to functional or compliance problems), please submit an Issue on GitCode. We will review and address it promptly.
3. msServiceProfiler depends on third-party open-source software like OpenTelemetry, which is provided and maintained by their respective communities. Resolution of issues in these dependencies relies on community contributions and feedback. You acknowledge that the msServiceProfiler repository does not guarantee fixes for issues in third-party software, nor does it guarantee testing or correction of all vulnerabilities or errors in such software.
4. You are responsible for any data generated while using msServiceProfiler. We recommend deleting all related data after use to prevent leaks or unnecessary exposure.
5. Do not distribute or disseminate data generated by msServiceProfiler through this tool. Huawei is not responsible for any information leaks, data leaks, or other consequences resulting from such actions.
6. You are responsible for the security of any commands you run with msServiceProfiler and bear all risks and losses from improper use. Huawei is not responsible for issues caused by incorrect command input.

### To data owners

If you do not want your model or dataset to be mentioned in msServiceProfiler, or if you wish to update its description, please submit an issue on GitCode. We will delete or update your description according to your request. Thank you for your understanding and contribution to msServiceProfiler.

## License

For the license of msServiceProfiler, see [LICENSE](./LICENSE).<br>
Documentation in the `docs` directory of msServiceProfiler is licensed under CC-BY 4.0. For details, see [LICENSE](./docs/LICENSE).

## Contribution Statement

1. Submit an error report: If you find a non-security vulnerability in msServiceProfiler, first search the **Issues** in the msServiceProfiler repository to avoid submitting duplicates. If the vulnerability is not listed, create a new issue. If you discover a security-related problem, do not disclose it publicly. Please refer to the security handling guidelines for details. All error reports must include complete information about the issue.
2. Security issue handling: For guidance on handling security issues in this project, please contact the core team via email for instructions.
3. Resolving existing issues: Browse open Issues to identify issues that need attention, and attempt to fix them.
4. Proposing new functions: Use the **Feature** tag when creating an issue for a new function. We will review and confirm proposals regularly.
5. How to contribute:<br>
    a. Fork the repository of the project.<br>
    b. Clone it to your local machine.<br>
    c. Create a development branch.<br>
    d. Perform local tests. Ensure all unit tests (including new ones) pass before submitting your code.<br>
    e. Submit your code.<br>
    f. Create a pull request (PR).<br>
    g. Code review: You need to modify the code based on review comments and push updates again. You may need to push multiple updates.<br>
    h. Once your PR has sufficient approvals, the committer will conduct the final review.<br>
    i. After your PR is approved and all tests pass, the CI system will merge it into the project's main branch.<br>

## Security Declaration

For security information, public endpoints, and communication matrix, see [msServiceProfiler Security Statement](docs/en/security_statement.md).

## Suggestions and Feedback

You are welcome to contribute to the community. If you have any questions or suggestions, please submit [issues](https://gitcode.com/Ascend/msserviceprofiler/issues). We will reply as soon as possible. Thank you for your support.

## Acknowledgments

msServiceProfiler is jointly developed by the following Huawei departments:

- Ascend Computing MindStudio Development Dept

Thank you to everyone in the community for your PRs. We warmly welcome contributions to msServiceProfiler!
