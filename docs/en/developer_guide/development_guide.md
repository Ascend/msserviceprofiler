# msServiceProfiler Development Guide

<!-- md-trans-meta sourceCommit=baa00b57bba45e0e150679d059c55e5cc1b52b22 translatedAt=2026-08-18T06:08:19.182Z pushedAt=2026-08-18T06:12:18.181Z -->

## 1. Project Overview

### 1.1 Project Overview

msServiceProfiler is a performance data collection, parsing, and analysis tool for inference service scenarios. This tool mainly uses the msServiceProfiler interface to collect the start and end time points of key processes in the MindIE, vLLM, and SGLang inference service processes, identify information such as key functions or iterations, record key events, support diverse information collection, and quickly locate performance issues.

### 1.2 Core Functional Modules

| Module        | Path                           | Description                            |
| :-------- | :--------------------------- | :---------------------------- |
| C++ Collection Core   | `cpp/`                       | High-performance data collection interface with C++ language support           |
| Python Main Module | `ms_service_profiler/`       | Basic capabilities such as data parsing, comparison, and analysis               |
| Auto-tuning tool    | `ms_serviceparam_optimizer/` | Auto-tuning tool                        |
| Expert Advisor      | `msservice_advisor/`         | Performance analysis expert advisor tool                    |
| Third-party Dependencies     | `3rdparty/`                  | Third-party libraries such as OpenTelemetry and Ascend SDK |

## 2. Development Environment Configuration

### 2.1 Recommended Development Software

| Software | Purpose |
| :------ | :----------- |
| VSCode  | Python/C++ development |
| CLion   | C++ development (recommended) |
| PyCharm | Python development (recommended) |

### 2.2 Environment Dependencies

#### 2.2.1 System Requirements

- **Operating System**: Linux (CentOS, Ubuntu, and other mainstream distributions)

- **Hardware Platform**: Ascend NPU

#### 2.2.2 Software Dependencies

| Software Name | Version Requirement | Purpose |
| :------ | :------- | :------ |
| Python | >= 3.10 | Runtime environment |
| cmake | >= 3.11 | C++ project build |
| gcc/g++ | Supports C++14 | C++ compiler |
| git | None | Code management |
| sqlite3 | None | Database dependency |

#### 2.2.3 Python Dependencies

**Runtime dependencies**:

```text
pandas~=2.2
openpyxl
numpy
pydantic
psutil
scipy
pyyaml
matplotlib
msguard
loguru
opentelemetry-exporter-otlp-proto-grpc==1.33.1
opentelemetry-exporter-otlp-proto-http==1.33.1
bytecode>=0.17.0
```

**Development and test dependencies**:

```text
coverage
pytest
pytest-mock
pytest_check
jsonschema
pytest-asyncio
```

#### 2.2.4 CANN Environment

You need to install the matching CANN Toolkit development package and configure the CANN environment variables. For details, see [CANN Quick Installation](https://www.hiascend.com/en/cann/download).

## 3. Code Download and Project Structure

### 3.1 Code Pull Process

```bash
# Fork the code to your own repository, and use git to clone the code from your remote repository to the local machine
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler
```

### 3.2 Directory Structure Description

For the detailed directory structure, see [Directory Structure Description](../dir_structure.md).

## 4. Compilation and Build

> The following commands must be executed in the root directory of the source code repository.

### 4.1 One-click Installation

For detailed installation instructions, see [msServiceProfiler Tool Installation Guide](../msserviceprofiler_install_guide.md).

### 4.2 Script-based Build

#### 4.2.1 Build the RUN Installation Package

```bash
# Build the RUN package (including the .whl package and dynamic libraries)
bash scripts/build.sh
```

The build artifacts are located in the `output/` directory.

#### 4.2.2 One-click Build and Upgrade

The script performs the following steps:

1. Download third-party files

2. Build the run package

3. Perform the upgrade

```bash
# Use ASCEND_TOOLKIT_HOME as the upgrade path
export ASCEND_TOOLKIT_HOME=/usr/local/Ascend/ascend-toolkit
bash scripts/build_and_upgrade.sh

# Or manually specify the upgrade path
bash scripts/build_and_upgrade.sh --install-path=/usr/local/Ascend/ascend-toolkit
```

### 4.3 Step-by-step Build

#### 4.3.1 C++ Compilation

```bash
# // Create the build directory
mkdir build && cd build

# // Configure CMake
cmake ..

# // Compile
make -j$(nproc)
```

**Debug version compilation**:

If gdb or vscode graphical breakpoint debugging is required, build the debug version:

```bash
cmake .. -DCMAKE_BUILD_TYPE=Debug
make -j$(nproc)
```

#### 4.3.2 Python Environment Configuration

```bash
# Install in development mode (with hot reload)
pip install -e .

# Install test dependencies
pip install -e ".[test]"
```

### 4.4 Build Artifact Description

After a successful build, the artifacts are located in the following directories:

| Artifact      | Path            | Description                                   |
| :------ | :------------ | :----------------------------------- |
| Dynamic library     | `build/`      | libms\_service\_profiler.so          |
| Python package | site-packages | ms\_service\_profiler module              |
| run installation package  | `output/`     | mindstudio-service-profiler\_xxx.run |

## 5. Development and Debugging

### 5.1 C++ Backend Debugging

#### 5.1.1 Compiling the Debug Version

```bash
cmake .. -DCMAKE_BUILD_TYPE=Debug
make -j$(nproc)
```

#### 5.1.2 CLion Debugging Configuration

1. Open the project root directory with CLion.

2. Configure the CMake option: `-Dms_service_profiler_BUILD_TESTS=ON`

3. Set breakpoints and start debugging.

### 5.2 Python Module Debugging

#### 5.2.1 Development Mode Installation

```bash
pip install -e ".[test]"
```

#### 5.2.2 Running Tests Locally

```bash
# Run a single test file
python -m pytest test/ut/python/test_profiler.py -v

# Run a specified test case
python -m pytest test/ut/python/test_profiler.py::test_function_name -v
```

### 5.3 Joint Debugging Guide (End-to-end Verification)

End-to-end verification covers the complete chain from collection to parsing.

**Step 1: Configuring environment variables**

```bash
export SERVICE_PROF_CONFIG_PATH="./ms_service_profiler_config.json"
```

**Step 2: Starting the service for collection**

Start the target service (MindIE/vLLM/SGLang) and check the logs to confirm that msServiceProfiler has started.

```text
[msservice_profiler] [PID:225] [INFO] [ParseEnable:179] profile enable_: false
```

**Step 3: Parsing the collected data**

After collection is complete, use the parsing tool to parse the data and generate parsing artifacts, including .csv, .json, .db, and other files.

```bash
python -m ms_service_profiler.parse --input-path=./prof_dir
```

**Step 4: Verifying the parsing artifacts**

Check whether the parsing artifacts are generated correctly.

```bash
# View the parsing artifacts
ls ./output/

# Expected artifacts:
# - CSV files (request analysis, scheduling analysis, etc.)
# - JSON files (trace data)
# - DB files (database format)
```

### 5.4 Code Modification Verification Process

Depending on the type of modified code, the verification process is divided into two types.

#### 5.4.1 Modifying C++ Code

After modifying the C++ code (in the `cpp/` directory), you need to recompile it and replace the dynamic library:

```bash
# 1. Recompile the C++ code
mkdir build && cd build
cmake ..
make -j$(nproc)

# 2. Replace the dynamic library
cp build/libms_service_profiler.so /path/to/install/lib/

# 3. Start the service for collection verification
export SERVICE_PROF_CONFIG_PATH="./ms_service_profiler_config.json"
# Start the target service for collection

# 4. Run UT/ST
./test/run_ut.sh cpp
```

For parsing and verifying the collected data, see [5.3 Joint Debugging Guide](#53-joint-debugging-guide-end-to-end-verification).

#### 5.4.2 Modifying Python Code

After modifying the Python code (in the `ms_service_profiler/` directory):

```bash
# 1. Install in development mode (with hot reload)
pip install -e .
```

**Verification steps** (select based on the modified content):

- Modify collection-related code: start the service to perform collection verification.

- Modify parsing-related code: directly parse the data for verification (see [5.3 Joint Debugging Guide](#53-joint-debugging-guide-end-to-end-verification)).

```bash
# 2. Run the UT
./test/run_ut.sh ms_service_profiler

# 3. Run the ST
python test/run_st.py
# Or
bash test/run_st.sh
```

### 5.5 Collection Development Guide for Different Frameworks

Different frameworks adopt different collection methods. During development, refer to the corresponding documents.

#### 5.5.1 MindIE Framework (Intrusive Instrumentation)

MindIE uses intrusive instrumentation for collection, which requires directly calling the collection interface in the code.

**Development Guide**:

- C++ API: See [Serving Tuning C++ API](../cpp_api/serving_tuning/README.md)

- Python API: See [Serving Tuning Python API](../python_api/README.md)

- Usage Instructions: See [Serving Tuning Tool User Guide](../msserviceprofiler_serving_tuning_instruct.md)

**Development Process**:

1. Add collection interface calls (span\_start/span\_end, etc.) at the target code locations.

2. Compile and replace the dynamic library (if C++ code is modified).

3. Start the service to verify the collection effect.

#### 5.5.2 vLLM Framework (Dynamic Hook)

vLLM adopts dynamic hook for collection. Collection points are defined by configuring a YAML file, without modifying the framework source code.

**Development Guide**:

- Usage Instructions: See [vLLM Service-oriented Performance Collection Tool User Guide](../vLLM_service_oriented_performance_collection_tool.md)

- Point Configuration: See [vLLM Point Configuration User Guide](../vLLM_service_oriented_performance_collection_tool.md#symbol-configuration-user-guide)

- Configuration File: `ms_service_profiler/patcher/vllm/config/service_profiling_symbols.yaml`

- Hook Implementation: `ms_service_profiler/patcher/vllm/handlers/`

**Development Process**:

1. Modify the YAML configuration file to add new collection points, or modify the hook logic in handlers.

2. Set the environment variable `PROFILING_SYMBOLS_PATH` to point to the configuration file.

3. Start the vLLM service to verify the collection effect.

#### 5.5.3 SGLang Framework (Dynamic Hook)

SGLang uses dynamic hook for collection, similar to vLLM.

**Development Guide**:

- Usage Instructions: See [SGLang Service-oriented Performance Collection Tool User Guide](../SGLang_service_oriented_performance_collection_tool.md)

- Configuration File: `ms_service_profiler/patcher/sglang/config/service_profiling_symbols.yaml`

- Hook implementation: `ms_service_profiler/patcher/sglang/handlers/`

**Configuration description**: The YAML configuration format of SGLang is the same as that of vLLM. For details, see [vLLM Symbol Configuration User Guide](../vLLM_service_oriented_performance_collection_tool.md#symbol-configuration-user-guide).

**Development process**:

1. Import the collection module in the SGLang entry file.

2. Modify the YAML configuration file or hook logic.

3. Start the SGLang service to verify the collection effect.

### 5.6 Parsing Development Guide

#### 5.6.1 Parsing Process Overview

The parsing process converts the collected raw data into deliverables in CSV, JSON, DB, and other formats:

```text
Raw data → DataSource loading → Pipeline process → Plugin → Exporter → Artifact
```

#### 5.6.2 Key Code Entry Points

| Module    | Entry File                                   | Description                |
| :---- | :----------------------------------------- | :---------------- |
| Parsing Entry  | `ms_service_profiler/parse.py`             | Command-line entry point that parses parameters and starts the parsing process. |
| Data Source   | `ms_service_profiler/data_source/`         | Loads raw data in different formats.      |
| Processing Pipeline  | `ms_service_profiler/pipeline/`            | Orchestrates the data processing flow.         |
| Plugin System  | `ms_service_profiler/plugins/`             | Data processing plugins.           |
| Exporter Factory | `ms_service_profiler/exporters/factory.py` | Creates and manages exporters.         |
| Exporter   | `ms_service_profiler/exporters/`           | Exports deliverables in different formats.       |

#### 5.6.3 Example of Adding an Exporter

Create a new exporter in the `ms_service_profiler/exporters/` directory:

```python
# ms_service_profiler/exporters/exporter_xxx.py

from .base import ExporterBase

class ExporterXxx(ExporterBase):
    name = 'xxx'  # Exporter name
    
    @classmethod
    def initialize(cls, args):
        cls.args = args
    
    @classmethod
    def is_provide(cls, formats):
        return 'xxx' in formats  # Any combination of 'csv', 'json', and 'db'
    
    def do_export(self):
        # Implement the export logic.
        data = self.load_data()
        self.save_to_file(data)
```

Register it in `exporters/factory.py`:

```python
from ms_service_profiler.exporters.exporter_xxx import ExporterXxx

class ExporterFactory:
    exporter_cls = [
        # ... other exporters
        ExporterXxx
    ]
```

#### 5.6.4 Example of Adding a Plugin 

Create a new plugin in the `ms_service_profiler/plugins/` directory.

```python
# ms_service_profiler/plugins/plugin_xxx.py

class PluginXxx(PluginBase):
    def parse(self, data, *args, **kwargs):
        # Implement the data processing logic (implement it directly here, or call the helper methods provided by the base class)
        processed_data = data  # Replace with the actual processing logic
        return processed_data
```

#### 5.6.5 Data Flow Description

1. **Data loading**: `DataSource` loads data from the raw data directory.

2. **Pipeline processing**: `Pipeline` orchestrates the processing flow and invokes each `Plugin` in sequence.

3. **Data export**: `Exporter` exports the processed data in the specified format.

```text
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  DataSource │ ──→ │  Pipeline   │ ──→ │   Plugin    │ ──→ │  Exporter   │
│             │     │             │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                              ↓
                                                        ┌─────────────┐
                                                        │ CSV/JSON/DB │
                                                        │             │
                                                        └─────────────┘
```

## 6. Test Guide

### 6.1 Test Framework

- **C++ Tests**: GoogleTest

- **Python Tests**: pytest + coverage

### 6.2 Coverage Requirements

- **Line coverage**: ≥ 80%

- **Branch coverage**: ≥ 60%

### 6.3 UT Execution

#### 6.3.1 One-click Script

```bash
# Run all UT
./test/run_ut.sh

# Run tests for a specified module
./test/run_ut.sh ms_service_profiler
./test/run_ut.sh cpp
./test/run_ut.sh ms_serviceparam_optimizer
./test/run_ut.sh msservice_advisor
```

#### 6.3.2 Step-by-step Execution

**Python UT**:

```bash
# Install test dependencies
pip install -e ".[test]"

# Run tests and generate coverage
python -m coverage run --branch --source "./ms_service_profiler" --omit="test/*" -m pytest test/ut/python/test_ms_service_profiler
python -m coverage report -m --precision=2
```

**C++ UT**:

```bash
# Build the test
cmake -S . -B build -Dms_service_profiler_BUILD_TESTS=ON
cmake --build build --target ms_service_profiler_run_uts ms_service_profiler_run_sts -j$(nproc)

# Run the test
./build/test/ms_service_profiler_run_uts
./build/test/ms_service_profiler_run_sts
```

### 6.4 ST Execution

```bash
# Run ST
python test/run_st.py
# Or
bash test/run_st.sh
```

### 6.5 Adding Developer Tests

When adding new feature code, you are required to supplement  developer tests (DTs) at the same time:

- **C++ DT**: Add test files in the `test/ut/cpp/` directory.

- **Python DT**: Add test files in the `test/ut/python/` directory.

## 7. New Feature Development Guide

This chapter describes the modules that need to be added in different development scenarios:

| Development Scenario                   | Module to Be Added       |
| :--------------------- | :------------ |
| Adding a new deliverable format (such as xlsx, html, etc.) | Exporter   |
| Adding support for a new data source format  | DataSource |
| Adding data processing logic        | Plugin      |
| Adding hook collection for a new framework   | Patcher     |

### 7.1 Adding a New Data Source (DataSource)

**Usage Scenario**: A new data source format needs to be supported (for example, a new database or a new file format).

Create a new data source module in the `ms_service_profiler/data_source/` directory.

```python
# ms_service_profiler/data_source/xxx_data_source.py

from .base_data_source import BaseDataSource

class XxxDataSource(BaseDataSource):
    def __init__(self, config):
        super().__init__(config)
        
    def load(self):
        # // Implement the data loading logic
        pass
        
    def parse(self):
        # // Implement the data parsing logic
        pass
```

### 7.2 Adding an Exporter

**Usage Scenario**: When a new deliverable format is required (such as xlsx, html, or a custom format).

Create a new exporter in the `ms_service_profiler/exporters/` directory.

```python
# ms_service_profiler/exporters/exporter_xxx.py

from .base import ExporterBase

class ExporterXxx(ExporterBase):
    name = 'xxx'  # Exporter name
    
    @classmethod
    def initialize(cls, args):
        cls.args = args
    
    @classmethod
    def is_provide(cls, formats):
        return 'xxx' in formats  # Supported formats
    
    def do_export(self):
        # Implement the export logic
        data = self.load_data()
        self.save_to_file(data)
```

Register it in `exporters/factory.py`:

```python
from ms_service_profiler.exporters.exporter_xxx import ExporterXxx

class ExporterFactory:
    exporter_cls = [
        # ... other exporters
        ExporterXxx
    ]
```

### 7.3 Adding a Plugin

**Usage Scenario**: When data processing logic needs to be added (such as data filtering, data transformation, data aggregation, etc.).

Create a new plugin in the `ms_service_profiler/plugins/` directory.

```python
# ms_service_profiler/plugins/plugin_xxx.py

class PluginXxx:
    def parse(self, data, *args, **kwargs):
        # Implement the data processing logic
        processed_data = self.process(data)
        return processed_data
```

### 7.4 Adding a Patcher Hook

**Usage Scenario**: When you need to add hook collection for a new framework, or add new collection points for an existing framework.

Add a new hook handler in the `ms_service_profiler/patcher/` directory:

```python
# ms_service_profiler/patcher/xxx/handlers/xxx_handlers.py

def xxx_handler(original_func, this, *args, **kwargs):
    """
    Custom hook handler function
    
    Args:
        original_func: Original function object
        this: Calling object (for method calls)
        *args: Positional arguments
        **kwargs: Keyword arguments
    
    Returns:
        Processing result
    """
    # Custom processing logic
    result = original_func(*args, **kwargs)
    return result
```

And register it in the corresponding YAML configuration file:

```yaml
# ms_service_profiler/patcher/xxx/config/service_profiling_symbols.yaml
- symbol: module.path:Class.method
  handler: ms_service_profiler.patcher.xxx.handlers.xxx_handlers.xxx_handler
  domain: Xxx
  name: XxxMethod
```

### 7.5 Collection and Parsing Interface Conventions

The msServiceProfiler tool consists of two parts: **collection** and **parsing**:

#### 7.5.1 Overall Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                        Collection Layer                     │
├─────────────────────────────────────────────────────────────┤
│  C++ collection                 │  Python collection        │
│  (cpp/include/msServiceProfiler)│  (ms_service_profiler/)   │
├─────────────────────────────────────────────────────────────┤
│  MindIE        │  vLLM         │  SGLang                    │
└─────────────────────────────────────────────────────────────┘
                              ↓ Raw data
┌─────────────────────────────────────────────────────────────┐
│                     Parsing Layer                           │
├─────────────────────────────────────────────────────────────┤
│  Python module (ms_service_profiler/)                       │
│  - data_source/    data source import                       │
│  - pipeline/       data processing pipeline                 │
│  - plugins/        plugin handling                          │
│  - exporters/      data export                              │
└─────────────────────────────────────────────────────────────┘
                              ↓ Deliverables
┌─────────────────────────────────────────────────────────────┐
│  CSV      │  JSON    │  DB   │  other formats               │
└─────────────────────────────────────────────────────────────┘
```

#### 7.5.2 C++ Collection Interface

The C++ collection interface is located in the `cpp/include/msServiceProfiler/` directory and provides high-performance data collection capabilities.

| Header File                  | Description           |
| :--------------------------- | :----------- |
| `msServiceProfiler.h`        | Main entry header file       |
| `ServiceProfilerInterface.h` | External interface for serving collection  |
| `Profiler.h`                 | Data collection interface       |
| `Tracer.h`                   | Trace data monitoring interface  |
| `ServiceTracer.h`            | Serving trace tracking interface |
| `Config.h`                   | Collection configuration parsing       |

#### 7.5.3 Python Collection Interface

The Python collection interface implements non-intrusive collection through the Patcher mechanism and supports multiple frameworks.

| Framework | Path                                    | Description            |
| :----- | :------------------------------------ | :------------ |
| MindIE | `ms_service_profiler/profiler.py`     | MindIE framework collection interface  |
| vLLM   | `ms_service_profiler/patcher/vllm/`   | Non-intrusive collection for the vLLM framework   |
| SGLang | `ms_service_profiler/patcher/sglang/` | Non-intrusive collection for the SGLang framework |

#### 7.5.4 Parsing Command Interface

The parsing command is registered through entry_points, providing a unified command-line entry.

```toml
# pyproject.toml
[project.entry-points."ms_service_profiler_plugins"]
"parse" = "ms_service_profiler.parse:arg_parse"
"analyze" = "ms_service_profiler.analyze:arg_parse"
"compare" = "ms_service_profiler.compare:arg_parse"
"split" = "ms_service_profiler.split:arg_parse"
```

Usage Instructions:

```bash
# Parse the collected data
msserviceprofiler parse --input-path=./prof_dir

# Analyze the data
msserviceprofiler analyze --input-path=./output

# Data comparison
msserviceprofiler compare --input-path1=./dir1 --input-path2=./dir2

# Data splitting
msserviceprofiler split --input-path=./prof_dir
```

#### 7.5.5 Parsing Output Format

The format of the deliverables after parsing:

| Format | Description | Purpose |
| :--- | :------ | :------------------- |
| CSV | Tabular data | Request analysis, scheduling analysis, etc. |
| JSON | Trace data | Visualization |
| DB | Database format | MindStudio Insight import |

## 8. Coding Standards

### 8.1 C++ Coding Standards

- Use the C++14 standard.

- Follow the Google C++ Style Guide.

- Compilation options: `-fvisibility=hidden -fPIC -fstack-protector-all`

### 8.2 Python Coding Standards

- Follow the PEP 8 specification.

- Use type hints.

- Docstrings follow the Google style.

### 8.3 Commit Conventions

Commit message format:

```text
<type>(<scope>): <subject>

<body>

<footer>
```

Type:

- `feat`: new feature

- `fix`: bug fix

- `docs`: documentation updates

- `style`: code formatting adjustments

- `refactor`: code refactoring

- `test`: test-related changes

- `chore`: build/tool-related changes

## 9. Packaging and Release

### 9.1 Version Number Specification

Version number format: `major.minor.revision`

Example: `26.0.0`

### 9.2 Packaging Process

#### 9.2.1 Only Building the RUN Package

```bash
# Build the run package
bash scripts/build.sh

# The artifact is located in the output directory
ls output/
```

#### 9.2.2 Build and Upgrade

```bash
# Set the CANN environment variable
export ASCEND_TOOLKIT_HOME=/usr/local/Ascend/ascend-toolkit

# Build the run package and upgrade it to the CANN environment
bash scripts/build_and_upgrade.sh

# The artifact is located in the output directory
ls output/
```

### 9.3 Artifact Verification

```bash
# Verify the installation package
./output/mindstudio-service-profiler-xxx.run --check

# Install
./output/mindstudio-service-profiler-xxx.run --install

# Upgrade (overwrite the .so files, Python packages, and header files)
./output/mindstudio-service-profiler-xxx.run --upgrade
```

**Upgrade Notes**:

The `--upgrade` command will overwrite the following files in the target path:

- `ms_service_profiler/`: Python package

- `libms_service_profiler.so`: dynamic library

- `include/msServiceProfiler/`: header files

During the upgrade, the files to be overwritten will be listed and confirmation will be awaited:

```text
[mindstudio-msserviceprofiler] [INFO]: Upgrade target path: /usr/local/Ascend/cann-x.x.x
[mindstudio-msserviceprofiler] [INFO]: The following files will be overwritten.
  - /usr/local/Ascend/cann-x.x.x/python/site-packages/ms_service_profiler
  - /usr/local/Ascend/cann-x.x.x/python/site-packages/ms_service_profiler/libms_service_profiler.so
  - /usr/local/Ascend/cann-x.x.x/include/msServiceProfiler
Confirm to proceed? [y/N]:
```

> Note: Before the upgrade, manually back up the original files according to the upgrade list.

## 10. FAQs

### 10.1 Compilation Issues

**Q: The compilation reports that sqlite3 cannot be found**

A: You need to install the sqlite3 development library.

```bash
apt-get install libsqlite3-dev
```

**Q: The compilation reports that CANN-related libraries cannot be found**

A: You need to set the CANN environment variables:

```bash
export ASCEND_TOOLKIT_HOME=/usr/local/Ascend/ascend-toolkit
```

### 10.2 Runtime Issues

**Q: A conflicting package 'msserviceprofiler' is reported**

A: Uninstall the old version first.

```bash
pip uninstall msserviceprofiler -y
```

**Q: Changes to the configuration file do not take effect**

A: Ensure that the environment variable `SERVICE_PROF_CONFIG_PATH` is set before the service is started.

### 10.3 Debugging Issues

**Q: How do I view detailed logs?**

A: The tool outputs logs prefixed with `[msservice_profiler]`. Check the standard output or the log file.

**Q: How do I verify that collection is working properly?**

A: Check whether the log contains output similar to the following:

```text
[msservice_profiler] [PID:xxx] [INFO] [DynamicControl:407] Profiler Enabled Successfully!
```

## 11. Related Documents

- [msServiceProfiler Tool Installation Guide](../msserviceprofiler_install_guide.md)

- [Quick Start](../quick_start.md)

- [Serving Tuning Tool User Guide](../msserviceprofiler_serving_tuning_instruct.md)

- [vLLM Serving Performance Collection Tool](../vLLM_service_oriented_performance_collection_tool.md)

- [SGLang Serving Performance Collection Tool](../SGLang_service_oriented_performance_collection_tool.md)

- [Trace Data Monitoring Tool](../msserviceprofiler_trace_data_monitoring_instruct.md)

- [Serving Auto-tuning Tool](../serviceparam_optimizer_instruct.md)

- [Serving Expert Advice Tool](../service_profiling_advisor_instruct.md)

- [Contribution Guide](../../../CONTRIBUTING.md)
