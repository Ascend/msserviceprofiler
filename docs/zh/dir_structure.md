# 项目目录

msServiceProfiler详细项目目录介绍如下

```text
3rdparty/                                                    # 第三方依赖目录
    ├── CMakeLists.txt                                       # 第三方依赖的根CMakeLists配置文件
    ├── ascend/                                              # 昇腾(Ascend)AI计算平台相关依赖
    │   ├── CMakeLists.txt                                   # 昇腾依赖的CMakeLists配置文件
    │   ├── include/                                         # 头文件目录
    │   │   ├── acl/                                         # 昇腾计算库头文件，用于访问昇腾计算库的各种功能
    │   │   ├── mspti/                                       # 昇腾平台工具接口头文件
    │   │   └── mstx/                                        # 昇腾工具扩展头文件
    │   └── src/                                             # 第三方依赖源码实现目录
    └── opentelemetry/                                       # OpenTelemetry可观测性框架
        ├── include/                                         # OpenTelemetry头文件目录
        └── proto/                                           # Protocol Buffer定义文件
            ├── collector/                                   # 数据收集器相关定义
            │   └── trace/                                   # 追踪数据收集
            ├── common/                                      # 通用定义
            ├── resource/                                    # 资源定义
            └── trace/                                       # 追踪相关定义
├── CMakeLists.txt                                           # 项目根CMakeLists配置文件
├── README.md                                                # 项目说明文档
└── cpp/                                                     # 基础能力目录（采集），C++源码主目录
    ├── CMakeLists.txt                                       # 数据采集模块，C++模块的CMakeLists配置文件
    ├── include/                                             # 采集能力对外接口目录
    │   └── msServiceProfiler/                               # 数据采集头文件
    │       ├── Config.h                                     # 采集配置文件解析头文件
    │       ├── DBExecutor/                                  # 采集数据落盘模块头文件
    │       ├── Profiler.h                                   # 数据采集接口头文件
    │       ├── ServiceProfilerInterface.h                   # 数据采集对外接口头文件
    │       ├── ServiceTracer.h                              # 服务化Trace追踪头文件
    │       ├── Tracer.h                                     # Trace数据监测对外接口头文件
    │       └── msServiceProfiler.h                          # 主入口头文件
    └── src/                                                 # 基础数据采集能力源文件实现目录
docs/                                                        # 文档目录
└── zh/                                                      # 中文文档目录
    ├── cpp_api/                                             # C++ API文档
    │   ├── serving_tuning/                                  # 服务化调优API
    │   │   ├── ${api_name}.md                               # API接口说明，${api_name}表示接口名称
    │   │   ├── macro_definitions.md                         # 宏定义说明
    │   │   ├── public_sys-resources/                        # 公共系统资源图标
    │   │   └── serving_tuning.md                            # C++ API文档总说明
    │   └── trace_data_monitoring/                           # Trace追踪数据监测API
    │       ├── ${api_name}.md                               # API接口说明，${api_name}表示接口名称
    │       ├── public_sys-resources/                        # 公共系统资源图标
    │       └── sample_code.md                               # 示例代码
    ├── python_api/                                          # Python API文档
    │   ├── README.md                                        # Python API说明
    │   └── context/                                         # 上下文相关API
    │       ├── ${api_name}.md                               # API接口说明，${api_name}表示接口名称
    │       ├── public_sys-resources/                        # 公共系统资源图标
    └── figures/                                             # 图表和示意图目录
ms_service_profiler/                                         # 基础能力目录（解析、数据比对等）
    ├── config/                                              # 配置文件目录
    ├── data_source/                                         # 数据源导入模块目录
    │   └── ${name}_source.py                                # ${name}数据源导入模块，name为数据源名称
    └── exporters/                                           # 数据导出器模块目录
    │    └── exporter_${name}.py                             # ${name}数据导出器，name为数据名称
    ├── mstx.py                                              # python数据采集模块
    ├── parse.py                                             # 数据解析主模块
    ├── profiler.py                                          # python数据采集接口
    ├── trace.py                                             # Trace追踪主模块
    ├── analyze.py                                           # 扩展分析功能主模块
    ├── compare.py                                           # 数据对比功能主模块
    ├── split.py                                             # 数据拆解功能主模块
    ├── parse_helper/                                        # 解析辅助工具模块
    ├── pipeline/                                            # 数据处理管道模块
    │   └── pipeline_${name}.py                              # ${name}数据处理管道，name为数据名称
    ├── plugins/                                             # 插件系统模块
    │   ├── plugin_${name}.py                                # ${name}数据处理插件，name为数据名称
    │   └── sort_plugins.py                                  # 插件排序工具
    ├── processor/                                           # 数据处理器模块
    │   └── processor_${name}.py                             # ${name}数据处理器，name为数据名称
    ├── task/                                                # 任务管理模块
    ├── tracer/                                              # Trace追踪模块
    ├── utils/                                               # 工具模块
    │   ├── check/                                           # 检查工具
    │   ├── secur/                                           # 安全模块
    │   │   ├── constraints/                                 # 安全约束
    │   │   └── utils/                                       # 安全常量
    │   └── trace_to_db.py                                   # trace数据从json格式转为db格式处理模块
    └── patcher/                                             # hook采集模块
        ├── config/                                          # 配置样例
        │   ├── custom_handler_example.py                    # 自定义处理器示例
        │   ├── hooks_example.yaml                           # 钩子配置示例
        ├── vllm/                                            # vLLM数据采集模块
        │   ├── config/                                      # vLLM数据采集配置文件目录
        │   ├── handlers/                                    # vLLM数据采集函数钩子
        |   |   ├── v0/                                      # vLLM v0版本函数钩子
        |   |   └── v1/                                      # vLLM v1版本函数钩子
        |   └── service_profiler.py                          # vLLM数据采集入口主类
        ├── sglang/                                          # SGLang数据采集模块
        │   ├── config/                                      # SGLang数据采集配置文件目录
        │   ├── handlers/                                    # SGLang数据采集函数钩子
        |   └── service_patcher.py                           # SGLang数据采集入口主类
msservice_advisor/                                           # 专家建议工具目录
    ├── msservice_advisor/                                   # 专家建议工具主目录
    │   └── profiling_analyze                                # 专家建议各分析器模块
    └── advisor.py                                           # 专家建议主模块
ms_serviceparam_optimizer/                                              # 自动寻优工具目录
    ├──ms_serviceparam_optimizer/                                       # 自动寻优工具主目录
    ├──pyproject.toml                                        # 自动寻优工具项目配置文件
├── pyproject.toml                                           # Python项目配置文件
└── test/                                                    # 测试目录
    ├── CMakeLists.txt                                       # C++测试构建配置
    ├── run_st.py                                            # 系统测试运行脚本(Python)
    ├── run_st.sh                                            # 系统测试运行脚本(Shell)
    ├── run_ut.sh                                            # 单元测试运行脚本
    ├── fuzz/                                                # 模糊测试目录
    │   ├── CMakeLists.txt                                   # 模糊测试构建配置
    │   ├── FuzzMain.cpp                                     # 模糊测试主程序
    │   ├── run_fuzz.sh                                      # 模糊测试运行脚本
    │   └── manager/                                         # 管理模块模糊测试
    │       └── ${name}_fuzz.cpp                             # ${name}模块模糊测试用例
    ├── st/                                                  # 系统测试(System Test)
    │   ├── cpp/                                             # C++系统测试
    │   │   └── test.cpp                                     # C++测试主程序
    │   └── python/                                          # Python系统测试
    │       ├── conftest.py                                  # Pytest配置
    │       ├── analyze/                                     # 分析功能测试
    │       ├── checker/                                     # 数据检查模块
    │       ├── collect/                                     # 数据收集测试
    │       ├── executor/                                    # ST执行器模块
    │       ├── multi_analyze/                               # 多服务性能分析测试
    │       ├── profiler/                                    # 性能分析器测试
    │       └── split/                                       # 数据拆解测试
    └── ut/                                                  # 单元测试(Unit Test)
        ├── cpp/                                             # C++单元测试
        │   ├── include/                                     # 单元测试辅助头文件目录
        │   ├── test${name}.cpp                              # ${name}模块测试用例，${name}为模块名称
        └── python/                                          # Python单元测试
            ├── data_source/                                 # 数据源测试
            ├── eplb_observe/                                # EPLB观测测试
            ├── task/                                        # 任务管理测试
            ├── trace/                                       # Trace监测模块测试
            ├── test_ms_service_profiler_ext/                # 服务化性能分析扩展能力测试
            ├── test_msguard/                                # 安全模块测试
            ├── test_vllm_profiler/                          # vLLM数据采集能力测试
            └── test_${name}.py                              # ${name}模块测试，${name}为模块名称
```
