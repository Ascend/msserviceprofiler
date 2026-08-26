# Project Directory

The msServiceprofiler project directory is described as follows:

```ColdFusion
3rdparty/                                                    # Directory for third-party dependencies
    ├── CMakeLists.txt                                       # Root CMakeLists configuration file for third-party dependencies
    ├── ascend/                                              # Dependencies for the Ascend AI computing platform
    │   ├── CMakeLists.txt                                   # CMakeLists configuration file for Ascend dependencies
    │   ├── include/                                         # Directory for header files
    │   │   ├── acl/                                         # Header files for the Ascend computing library, providing APIs to access its various features.
    │   │   ├── mspti/                                       # Header files for the Ascend platform tooling interfaces
    │   │   └── mstx/                                        # Header files for Ascend tooling extensions
    │   └── src/                                             # Source code directory for third-party dependencies
    └── opentelemetry/                                       # OpenTelemetry observability framework
        ├── include/                                         # Directory for OpenTelemetry header files
        └── proto/                                           # Protocol Buffer definition files
            ├── collector/                                   # Data collector definitions
            │   └── trace/                                   # Trace data collection
            ├── common/                                      # Common definitions
            ├── resource/                                    # Resource definitions
            └── trace/                                       # Trace-related definitions
├── CMakeLists.txt                                           # Root CMakeLists configuration file for the project
├── README.md                                                # Project description document
└── cpp/                                                     # Main C++ source directory for core profiling functionality
    ├── CMakeLists.txt                                       # CMakeLists configuration file for C++ profiling module
    ├── include/                                             # Directory for public profiling interfaces
    │   └── msServiceProfiler/                               # Profiling header files
    │       ├── Config.h                                     # Header files for parsing the profiling configuration file
    │       ├── DBExecutor/                                  # Header files for the data persistence module
    │       ├── Profiler.h                                   # Header files for profiling APIs
    │       ├── ServiceProfilerInterface.h                   # Header files for public profiling APIs
    │       ├── ServiceTracer.h                              # Header files for service trace
    │       ├── Tracer.h                                     # Header files for trace monitoring APIs
    │       └── msServiceProfiler.h                          # Main entry header file
    └── src/                                                 # Source code directory for core profiling implementation
docs/                                                        # Document directory
└── zh/                                                      # Chinese document directory
    ├── cpp_api/                                             # C++ API documents
    │     ├── serving_tuning/                                # Serving tuning API
    │     ├── ${api_name}.md                                 # API description, where ${api_name} indicates the API name.
    │     ├── macro_definitions.md                           # Macro definitions
    │     ├── public_sys-resources/                          # Public system resources
    │     └── serving_tuning.md                              # C++ API documents
    │ └── trace_data_monitoring/                             # Trace monitoring API
    │       ├── ${api_name}.md                               # API description, where ${api_name} indicates the API name.
    │       ├── public_sys-resources/                        # Public system resources
    │       └── sample_code.md                               # Sample code
    ├── python_api/                                          # Python API documents
    │   ├── README.md                                        # Python API description
    │   └── context/                                         # Context-related APIs
    │       ├── ${api_name}.md                               # API description, where ${api_name} indicates the API name.
    │       ├── public_sys-resources/                        # Public system resources
    └── figures/                                             # Charts and schematics
ms_service_profiler/                                         # Directory of core functionalities (such as parsing and data comparison)
    ├── config/                                              # Directory of configuration files
    ├── data_source/                                         # Directory for the data source import module
    ├──── ${name}_source.py                                  # ${name} data source import module, where *name* indicates the data source name.
    └── exporters/                                           # Directory for the data exporter module
    ├──── exporter_${name}.py                                # ${name} data exporter, where *name* indicates the data name.
    └── ms_service_profiler_ext/                             # Profiling extension package for serving performance
        ├── analyze.py                                       # Analysis extension main module
        ├── compare.py                                       # Main module for data comparison
        ├── split.py                                         # Main module for data breakdown
        ├── common/                                          # Common tool modules
        ├── compare_tools/                                   # Data comparison module
        ├── exporters/                                       # Extension module for the data exporter
        └── split_processor/                                 # Processor module for data breakdown
    ├── mstx.py                                              # Python profiling module
    ├── parse.py                                             # Main module for data parsing
    ├── profiler.py                                          # Python profiling API
    ├── trace.py                                             # Main trace module
    ├── parse_helper/                                        # Auxiliary parsing module
    ├── pipeline/                                            # Data processing pipeline modules
    ├── pipeline_${name}.py                                  # ${name} data processing pipeline, where *name* indicates the data name.
    ├── plugins/                                             # System plugins
    ├── plugin_${name}.py                                    # ${name} data processing plugin, where *name* indicates the data name.
    │   └── sort_plugins.py                                  # Plugin sorter
    ├── processor/                                           # Data processor modules
    │   └── processor_${name}.py                             # ${name} data processor, where *name* indicates the data name.
    ├── task/                                                # Task management module
    ├── tracer/                                              # Trace module
    ├── utils/                                               # Tool modules
    │   ├── check/                                           # Check tool
    │   ├── secur/                                           # Security module
    │   ├── constraints/                                     # Security constraints
    │   └── utils/                                           # Security constant
    │   └── trace_to_db.py                                   # Module for converting trace data from JSON format to DB format
    └── patcher/                                             # Hook-based profiling module
        ├── config/                                          # Configuration examples
        ├── custom_handler_example.py                        # Custom handler example
        │   ├── hooks_example.yaml                           # Hook configuration example
        ├── vllm/                                            # vLLM data collection module
        │   ├── config/                                      # Directory for vLLM profiling configuration files
        │   ├── handlers/                                    # vLLM function hooks for data collection
        |   ├── v0/                                          # vLLM v0 version function hook
        |   └── v1/                                          # vLLM v1 version function hook
        |   └── service_profiler.py                          # vLLM data collection entry
        ├── sglang/                                          # SGLang data collection module
        │   ├── config/                                      # Directory for SGLang profiling configuration files
        │   ├── handlers/                                    # SGLang data collection function
        |   └── service_patcher.py                           # SGLang data collection entry
msservice_advisor/                                           # Directory for Service Profiling Advisor
    ├── msservice_advisor/                                   # Main directory for Service Profiling Advisor
    │   └── profiling_analyze                                # Analyzer modules for Service Profiling Advisor
    └── advisor.py                                           # Main analyzer module for Service Profiling Advisor
ms_serviceparam_optimizer/                                   # Directory for Serviceparam Optimizer
    ├──ms_serviceparam_optimizer/                            # Main directory for Serviceparam Optimizer
    ├──pyproject.toml                                        # Project configuration file for Serviceparam Optimizer
├── pyproject.toml                                           # Python project configuration file
└── test/                                                    # Test directory
    ├── CMakeLists.txt                                       # C++ test build configuration
    ├── run_st.py                                            # System test script (Python)
    ├── run_st.sh                                            # System test running script (Shell)
    ├── run_ut.sh                                            # Unit test script
    ├── fuzz/                                                # Fuzzing test directory
    │   ├── CMakeLists.txt                                   # Build configuration for fuzz testing
    │   ├── FuzzMain.cpp                                     # Main program for fuzzing
    │   ├── run_fuzz.sh                                      # Fuzzy test script
    │   └── manager/                                         # Management module fuzz testing
    │       └── ${name}_fuzz.cpp                             # Fuzz tests for the ${name} module
    ├── st/                                                  # System test
    │   ├── cpp/                                             # C++ System Test
    │   │   └── test.cpp                                     # C++ test
    │   └── python/                                          # Python System Test
    │       ├── conftest.py                                  # Pytest Configuration
    │       ├── analyze/                                     # Test the analysis function.
    │       ├── checker/                                     # Data check module
    │       ├── collect/                                     # Data collection test
    │       ├── executor/                                    # ST Executor Module
    │       ├── multi_analyze/                               # Multi-service performance analysis test
    │       ├── profiler/                                    # Performance analyzer test
    │       └── split/                                       # Data splitting test
    └── ut/                                                  # Unit test
        ├── cpp/                                             # C++ unit test
        │   ├── include/                                     # Directory for storing unit test auxiliary header files
        │   ├── test${name}.cpp                              # ${name} module. ${name} indicates the module name.
        └── python/                                          # Python unit test
            ├── data_source/                                 # Data source test
            ├── eplb_observe/                                # EPLB observation test
            ├── task/                                        # Test the task management function.
            ├── trace/                                       # Test the trace monitoring module.
            ├── test_ms_service_profiler_ext/                # Service profiling extension tests
            ├── test_msguard/                                # Test the security module.
            ├── test_vllm_profiler/                          # vLLM profiling tests
            └── test_${name}.py                              # ${name} module test. ${name} indicates the module name.
