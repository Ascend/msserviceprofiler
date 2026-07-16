# msServiceProfiler 开发指南

## 1. 项目概述

### 1.1 项目简介

msServiceProfiler（服务化调优工具）是面向推理服务化场景的性能数据采集、解析与分析工具。本工具主要使用msServiceProfiler接口，在MindIE、vLLM和SGLang推理服务化进程中，采集关键过程的开始和结束时间点，识别关键函数或迭代等信息，记录关键事件，支持多样的信息采集，对性能问题快速定位。

### 1.2 核心功能模块

| 模块        | 路径                           | 说明                            |
| :-------- | :--------------------------- | :---------------------------- |
| C++采集核心   | `cpp/`                       | 高性能数据采集接口，提供C++语言支持           |
| Python主模块 | `ms_service_profiler/`       | 数据解析、比对、分析等基础能力               |
| 自动寻优工具    | `ms_serviceparam_optimizer/` | 自动寻优工具                        |
| 专家建议      | `msservice_advisor/`         | 性能分析专家建议工具                    |
| 第三方依赖     | `3rdparty/`                  | OpenTelemetry、Ascend SDK等第三方库 |

## 2. 开发环境配置

### 2.1 开发软件推荐

| 软件      | 用途           |
| :------ | :----------- |
| VSCode  | Python/C++开发 |
| CLion   | C++开发（推荐）    |
| PyCharm | Python开发（推荐） |

### 2.2 环境依赖

#### 2.2.1 系统要求

- **操作系统**：Linux（CentOS、Ubuntu等主流发行版）
- **硬件平台**：昇腾NPU

#### 2.2.2 软件依赖

| 软件名     | 版本要求     | 用途      |
| :------ | :------- | :------ |
| Python  | >= 3.10  | 运行时环境   |
| cmake   | >= 3.11  | C++项目构建 |
| gcc/g++ | 支持 C++14 | C++编译器  |
| git     | 无        | 代码管理    |
| sqlite3 | 无        | 数据库依赖   |

#### 2.2.3 Python依赖

**运行时依赖**：

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

**开发测试依赖**：

```text
coverage
pytest
pytest-mock
pytest_check
jsonschema
pytest-asyncio
```

#### 2.2.4 CANN环境

需要安装配套版本的CANN Toolkit开发套件包并配置CANN环境变量，具体请参见[CANN快速安装](https://www.hiascend.com/cann/download)。

## 3. 代码下载与项目结构

### 3.1 代码拉取流程

```bash
# Fork代码到自己仓库，并使用git从自己远程仓库clone代码到本地
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler
```

### 3.2 目录结构说明

详细目录结构请参考[目录结构说明](../dir_structure.md)。

## 4. 编译构建

> 以下命令需在代码仓根目录下执行。

### 4.1 一键式安装

详细安装说明请参考[msServiceProfiler工具安装指南](../msserviceprofiler_install_guide.md)。

### 4.2 脚本方式构建

#### 4.2.1 构建run安装包

```bash
# 构建run包（包含whl包和动态库）
bash scripts/build.sh
```

构建结果位于 `output/` 目录下。

#### 4.2.2 一键构建并升级

该脚本执行以下步骤：

1. 下载三方文件
2. 构建 run 包
3. 执行升级

```bash
# 使用 ASCEND_TOOLKIT_HOME 作为升级路径
export ASCEND_TOOLKIT_HOME=/usr/local/Ascend/ascend-toolkit
bash scripts/build_and_upgrade.sh

# 或手动指定升级路径
bash scripts/build_and_upgrade.sh --install-path=/usr/local/Ascend/ascend-toolkit
```

### 4.3 分步骤构建

#### 4.3.1 C++编译

```bash
# 创建构建目录
mkdir build && cd build

# 配置CMake
cmake ..

# 编译
make -j$(nproc)
```

**Debug版本编译**：

如果需要进行gdb或vscode图形化断点调试，需要编译debug版本：

```bash
cmake .. -DCMAKE_BUILD_TYPE=Debug
make -j$(nproc)
```

#### 4.3.2 Python环境配置

```bash
# 安装开发模式（支持代码修改后即时生效） 
pip install -e .

# 安装测试依赖
pip install -e ".[test]"
```

### 4.4 编译产物说明

编译成功后，产物位于以下目录：

| 产物      | 路径            | 说明                                   |
| :------ | :------------ | :----------------------------------- |
| 动态库     | `build/`      | libms\_service\_profiler.so          |
| Python包 | site-packages | ms\_service\_profiler模块              |
| run安装包  | `output/`     | mindstudio-service-profiler\_xxx.run |

## 5. 开发调试

### 5.1 C++后端调试

#### 5.1.1 Debug版本编译

```bash
cmake .. -DCMAKE_BUILD_TYPE=Debug
make -j$(nproc)
```

#### 5.1.2 CLion调试配置

1. 使用CLion打开项目根目录
2. 配置CMake选项：`-Dms_service_profiler_BUILD_TESTS=ON`
3. 设置断点并启动调试

### 5.2 Python模块调试

#### 5.2.1 开发模式安装

```bash
pip install -e ".[test]"
```

#### 5.2.2 本地运行测试

```bash
# 运行单个测试文件
python -m pytest test/ut/python/test_profiler.py -v

# 运行指定测试用例
python -m pytest test/ut/python/test_profiler.py::test_function_name -v
```

### 5.3 联调指南（端到端验证）

端到端验证涵盖采集→解析完整链路：

**Step 1：配置环境变量**

```bash
export SERVICE_PROF_CONFIG_PATH="./ms_service_profiler_config.json"
```

**Step 2：启动服务进行采集**

启动目标服务（MindIE/vLLM/SGLang），检查日志确认msServiceProfiler已启动：

```text
[msservice_profiler] [PID:225] [INFO] [ParseEnable:179] profile enable_: false
```

**Step 3：解析采集数据**

采集完成后，使用解析工具行解析后，生成解析产物，包含csv、json、db等文件：

```bash
python -m ms_service_profiler.parse --input-path=./prof_dir
```

**Step 4：验证解析产物**

检查解析产物是否正确生成：

```bash
# 查看解析产物
ls ./output/

# 预期产物：
# - csv文件（请求分析、调度分析等）
# - json文件（trace数据）
# - db文件（数据库格式）
```

### 5.4 代码修改验证流程

根据修改的代码类型，验证流程分为两种：

#### 5.4.1 修改C++代码

修改C++代码（`cpp/`目录）后，需要重新编译并替换动态库：

```bash
# 1. 重新编译C++代码
mkdir build && cd build
cmake ..
make -j$(nproc)

# 2. 替换动态库
cp build/libms_service_profiler.so /path/to/install/lib/

# 3. 拉起服务进行采集验证
export SERVICE_PROF_CONFIG_PATH="./ms_service_profiler_config.json"
# 启动目标服务进行采集

# 4. 执行UT/ST测试
./test/run_ut.sh cpp
```

解析采集数据验证请参考[5.3 联调指南](#53-联调指南端到端验证)。

#### 5.4.2 修改Python代码

修改Python代码（`ms_service_profiler/`目录）后：

```bash
# 1. 安装开发模式（代码修改即时生效）
pip install -e .
```

**验证步骤**（根据修改内容选择）：

- 修改采集相关代码：拉起服务进行采集验证
- 修改解析相关代码：直接解析数据验证（参考[5.3 联调指南](#53-联调指南端到端验证)）

```bash
# 2. 执行UT测试
./test/run_ut.sh ms_service_profiler

# 3. 执行ST测试
python test/run_st.py
# 或
bash test/run_st.sh
```

### 5.5 不同框架采集开发指南

不同框架采用不同的采集方式，开发时请参考对应文档：

#### 5.5.1 MindIE框架（侵入式打点）

MindIE采用侵入式打点采集，需要在代码中直接调用采集接口。

**开发指南**：

- C++接口：参考[服务化调优 C++ API](../cpp_api/serving_tuning/README.md)
- Python接口：参考[服务化调优 Python API](../python_api/README.md)
- 使用说明：参考[服务化调优工具使用指南](../msserviceprofiler_serving_tuning_instruct.md)

**开发流程**：

1. 在目标代码位置添加采集接口调用（span\_start/span\_end等）
2. 编译并替换动态库（如修改C++代码）
3. 拉起服务验证采集效果

#### 5.5.2 vLLM框架（动态Hook）

vLLM采用动态Hook方式采集，通过配置YAML文件定义采集点，无需修改框架源码。

**开发指南**：

- 使用说明：参考[vLLM服务化性能采集工具使用指南](../vLLM_service_oriented_performance_collection_tool.md)
- 点位配置：参考[vLLM点位配置使用指南](../vLLM_service_oriented_performance_collection_tool.md#点位配置使用指南)
- 配置文件：`ms_service_profiler/patcher/vllm/config/service_profiling_symbols.yaml`
- Hook实现：`ms_service_profiler/patcher/vllm/handlers/`

**开发流程**：

1. 修改YAML配置文件添加新的采集点，或修改handlers中的Hook逻辑
2. 设置环境变量 `PROFILING_SYMBOLS_PATH` 指向配置文件
3. 拉起vLLM服务验证采集效果

#### 5.5.3 SGLang框架（动态Hook）

SGLang采用动态Hook方式采集，与vLLM类似。

**开发指南**：

- 使用说明：参考[SGLang服务化性能采集工具使用指南](../SGLang_service_oriented_performance_collection_tool.md)
- 配置文件：`ms_service_profiler/patcher/sglang/config/service_profiling_symbols.yaml`
- Hook实现：`ms_service_profiler/patcher/sglang/handlers/`

**配置说明**：SGLang的YAML配置格式与vLLM相同，参考[vLLM点位配置使用指南](../vLLM_service_oriented_performance_collection_tool.md#点位配置使用指南)。

**开发流程**：

1. 在SGLang入口文件导入采集模块
2. 修改YAML配置文件或Hook逻辑
3. 拉起SGLang服务验证采集效果

### 5.6 解析开发指南

#### 5.6.1 解析流程概述

解析流程将采集的原始数据转换为CSV、JSON、DB等格式交付件：

```text
原始数据 → DataSource加载 → Pipeline处理 → Plugin插件 → Exporter导出 → 交付件
```

#### 5.6.2 关键代码入口

| 模块    | 入口文件                                       | 说明                |
| :---- | :----------------------------------------- | :---------------- |
| 解析入口  | `ms_service_profiler/parse.py`             | 命令行入口，解析参数并启动解析流程 |
| 数据源   | `ms_service_profiler/data_source/`         | 加载不同格式的原始数据       |
| 处理管道  | `ms_service_profiler/pipeline/`            | 数据处理流程编排          |
| 插件系统  | `ms_service_profiler/plugins/`             | 数据处理插件            |
| 导出器工厂 | `ms_service_profiler/exporters/factory.py` | 创建和管理导出器          |
| 导出器   | `ms_service_profiler/exporters/`           | 导出不同格式的交付件        |

#### 5.6.3 新增Exporter示例

在 `ms_service_profiler/exporters/` 目录下创建新的导出器：

```python
# ms_service_profiler/exporters/exporter_xxx.py

from .base import ExporterBase

class ExporterXxx(ExporterBase):
    name = 'xxx'  # 导出器名称
    
    @classmethod
    def initialize(cls, args):
        cls.args = args
    
    @classmethod
    def is_provide(cls, formats):
        return 'xxx' in formats  # 'csv', 'json', 'db' 任意组合
    
    def do_export(self):
        # 实现导出逻辑
        data = self.load_data()
        self.save_to_file(data)
```

注册到 `exporters/factory.py`：

```python
from ms_service_profiler.exporters.exporter_xxx import ExporterXxx

class ExporterFactory:
    exporter_cls = [
        # ... 其他导出器
        ExporterXxx
    ]
```

#### 5.6.4 新增Plugin示例

在 `ms_service_profiler/plugins/` 目录下创建新的插件：

```python
# ms_service_profiler/plugins/plugin_xxx.py

class PluginXxx(PluginBase):
    def parse(self, data, *args, **kwargs):
        # 实现数据处理逻辑（直接在此处实现，或调用基类提供的辅助方法）
        processed_data = data  # 替换为实际处理逻辑
        return processed_data
```

#### 5.6.5 数据流转说明

1. **数据加载**：`DataSource` 从原始数据目录加载数据
2. **管道处理**：`Pipeline` 编排处理流程，依次调用各个 `Plugin`
3. **数据导出**：`Exporter` 将处理后的数据导出为指定格式

```text
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  DataSource │ ──→ │  Pipeline   │ ──→ │   Plugin    │ ──→ │  Exporter   │
│  数据加载    │     │  流程编排    │     │  数据处理    │     │  数据导出    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                              ↓
                                                        ┌─────────────┐
                                                        │ CSV/JSON/DB │
                                                        │   交付件     │
                                                        └─────────────┘
```

## 6. 测试指南

### 6.1 测试框架

- **C++测试**：GoogleTest
- **Python测试**：pytest + coverage

### 6.2 覆盖率要求

- **行覆盖率**：≥ 80%
- **分支覆盖率**：≥ 60%

### 6.3 UT测试执行

#### 6.3.1 一键式脚本

```bash
# 运行所有UT测试
./test/run_ut.sh

# 运行指定模块测试
./test/run_ut.sh ms_service_profiler
./test/run_ut.sh cpp
./test/run_ut.sh ms_serviceparam_optimizer
./test/run_ut.sh msservice_advisor
```

#### 6.3.2 分步骤执行

**Python UT测试**：

```bash
# 安装测试依赖
pip install -e ".[test]"

# 运行测试并生成覆盖率
python -m coverage run --branch --source "./ms_service_profiler" --omit="test/*" -m pytest test/ut/python/test_ms_service_profiler
python -m coverage report -m --precision=2
```

**C++ UT测试**：

```bash
# 构建测试
cmake -S . -B build -Dms_service_profiler_BUILD_TESTS=ON
cmake --build build --target ms_service_profiler_run_uts ms_service_profiler_run_sts -j$(nproc)

# 运行测试
./build/test/ms_service_profiler_run_uts
./build/test/ms_service_profiler_run_sts
```

### 6.4 ST测试执行

```bash
# 运行ST测试
python test/run_st.py
# 或
bash test/run_st.sh
```

### 6.5 新增开发者测试

新增特性代码时，要求同时补充DT（开发者测试）：

- **C++ DT**：在 `test/ut/cpp/` 目录下添加测试文件
- **Python DT**：在 `test/ut/python/` 目录下添加测试文件

## 7. 新功能开发指南

本章节说明不同开发场景下需要新增的模块：

| 开发场景                   | 需要新增的模块       |
| :--------------------- | :------------ |
| 增加新的交付件格式（如xlsx、html等） | Exporter导出器   |
| 支持新的数据源格式              | DataSource数据源 |
| 增加数据处理逻辑               | Plugin插件      |
| 为新框架添加Hook采集           | Patcher钩子     |

### 7.1 新增数据源（DataSource）

**使用场景**：需要支持新的数据源格式（如新的数据库、新的文件格式等）。

在 `ms_service_profiler/data_source/` 目录下创建新的数据源模块：

```python
# ms_service_profiler/data_source/xxx_data_source.py

from .base_data_source import BaseDataSource

class XxxDataSource(BaseDataSource):
    def __init__(self, config):
        super().__init__(config)
        
    def load(self):
        # 实现数据加载逻辑
        pass
        
    def parse(self):
        # 实现数据解析逻辑
        pass
```

### 7.2 新增导出器（Exporter）

**使用场景**：需要增加新的交付件格式（如xlsx、html、自定义格式等）。

在 `ms_service_profiler/exporters/` 目录下创建新的导出器：

```python
# ms_service_profiler/exporters/exporter_xxx.py

from .base import ExporterBase

class ExporterXxx(ExporterBase):
    name = 'xxx'  # 导出器名称
    
    @classmethod
    def initialize(cls, args):
        cls.args = args
    
    @classmethod
    def is_provide(cls, formats):
        return 'xxx' in formats  # 支持的格式
    
    def do_export(self):
        # 实现导出逻辑
        data = self.load_data()
        self.save_to_file(data)
```

注册到 `exporters/factory.py`：

```python
from ms_service_profiler.exporters.exporter_xxx import ExporterXxx

class ExporterFactory:
    exporter_cls = [
        # ... 其他导出器
        ExporterXxx
    ]
```

### 7.3 新增插件（Plugin）

**使用场景**：需要增加数据处理逻辑（如数据过滤、数据转换、数据聚合等）。

在 `ms_service_profiler/plugins/` 目录下创建新的插件：

```python
# ms_service_profiler/plugins/plugin_xxx.py

class PluginXxx:
    def parse(self, data, *args, **kwargs):
        # 实现数据处理逻辑
        processed_data = self.process(data)
        return processed_data
```

### 7.4 新增Patcher钩子

**使用场景**：需要为新框架添加Hook采集，或为现有框架添加新的采集点。

在 `ms_service_profiler/patcher/` 目录下添加新的钩子处理器：

```python
# ms_service_profiler/patcher/xxx/handlers/xxx_handlers.py

def xxx_handler(original_func, this, *args, **kwargs):
    """
    自定义Hook处理函数
    
    Args:
        original_func: 原始函数对象
        this: 调用对象（对于方法调用）
        *args: 位置参数
        **kwargs: 关键字参数
    
    Returns:
        处理结果
    """
    # 自定义处理逻辑
    result = original_func(*args, **kwargs)
    return result
```

并在对应的YAML配置文件中注册：

```yaml
# ms_service_profiler/patcher/xxx/config/service_profiling_symbols.yaml
- symbol: module.path:Class.method
  handler: ms_service_profiler.patcher.xxx.handlers.xxx_handlers.xxx_handler
  domain: Xxx
  name: XxxMethod
```

### 7.5 采集与解析接口约定

msServiceProfiler工具分为**采集**和**解析**两部分：

#### 7.5.1 整体架构

```text
┌─────────────────────────────────────────────────────────────┐
│                        采集层                                │
├─────────────────────────────────────────────────────────────┤
│  C++采集接口                    │  Python采集接口            │
│  (cpp/include/msServiceProfiler)│  (ms_service_profiler/)   │
├─────────────────────────────────────────────────────────────┤
│  MindIE框架  │  vLLM框架  │  SGLang框架                   │
└─────────────────────────────────────────────────────────────┘
                              ↓ 原始数据
┌─────────────────────────────────────────────────────────────┐
│                        解析层                                │
├─────────────────────────────────────────────────────────────┤
│  Python解析模块 (ms_service_profiler/)                       │
│  - data_source/    数据源导入                                │
│  - pipeline/       数据处理管道                              │
│  - plugins/        插件处理                                  │
│  - exporters/      数据导出                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓ 交付件
┌─────────────────────────────────────────────────────────────┐
│  CSV文件  │  JSON文件  │  DB文件  │  其他格式               │
└─────────────────────────────────────────────────────────────┘
```

#### 7.5.2 C++采集接口

C++采集接口位于 `cpp/include/msServiceProfiler/` 目录，提供高性能数据采集能力：

| 头文件                          | 说明           |
| :--------------------------- | :----------- |
| `msServiceProfiler.h`        | 主入口头文件       |
| `ServiceProfilerInterface.h` | 服务化采集对外接口    |
| `Profiler.h`                 | 数据采集接口       |
| `Tracer.h`                   | Trace数据监测接口  |
| `ServiceTracer.h`            | 服务化Trace追踪接口 |
| `Config.h`                   | 采集配置解析       |

#### 7.5.3 Python采集接口

Python采集接口通过Patcher机制实现无侵入式采集，支持多框架：

| 框架     | 路径                                    | 说明            |
| :----- | :------------------------------------ | :------------ |
| MindIE | `ms_service_profiler/profiler.py`     | MindIE框架采集接口  |
| vLLM   | `ms_service_profiler/patcher/vllm/`   | vLLM框架无侵入采集   |
| SGLang | `ms_service_profiler/patcher/sglang/` | SGLang框架无侵入采集 |

#### 7.5.4 解析命令接口

解析命令通过entry\_points注册，提供统一的命令行入口：

```toml
# pyproject.toml
[project.entry-points."ms_service_profiler_plugins"]
"parse" = "ms_service_profiler.parse:arg_parse"
"analyze" = "ms_service_profiler.analyze:arg_parse"
"compare" = "ms_service_profiler.compare:arg_parse"
"split" = "ms_service_profiler.split:arg_parse"
```

使用方式：

```bash
# 解析采集数据
msserviceprofiler parse --input-path=./prof_dir

# 数据分析
msserviceprofiler analyze --input-path=./output

# 数据比对
msserviceprofiler compare --input-path1=./dir1 --input-path2=./dir2

# 数据拆解
msserviceprofiler split --input-path=./prof_dir
```

#### 7.5.5 解析输出格式

解析后的交付件格式：

| 格式   | 说明      | 用途                   |
| :--- | :------ | :------------------- |
| CSV  | 表格数据    | 请求分析、调度分析等           |
| JSON | Trace数据 | 可视化展示                |
| DB   | 数据库格式   | MindStudio Insight导入 |

## 8. 代码规范

### 8.1 C++代码规范

- 使用C++14标准
- 遵循Google C++ Style Guide
- 编译选项：`-fvisibility=hidden -fPIC -fstack-protector-all`

### 8.2 Python代码规范

- 遵循PEP 8规范
- 使用类型注解（Type Hints）
- 文档字符串遵循Google风格

### 8.3 提交规范

提交信息格式：

```text
<type>(<scope>): <subject>

<body>

<footer>
```

类型（type）：

- `feat`：新功能
- `fix`：修复bug
- `docs`：文档更新
- `style`：代码格式调整
- `refactor`：代码重构
- `test`：测试相关
- `chore`：构建/工具相关

## 9. 出包发布

### 9.1 版本号规范

版本号格式：`主版本号.次版本号.修订号`

示例：`26.0.0`

### 9.2 出包流程

#### 9.2.1 仅构建run包

```bash
# 构建run包
bash scripts/build.sh

# 产物位于output目录
ls output/
```

#### 9.2.2 构建并升级

```bash
# 设置CANN环境变量
export ASCEND_TOOLKIT_HOME=/usr/local/Ascend/ascend-toolkit

# 构建run包并升级到CANN环境
bash scripts/build_and_upgrade.sh

# 产物位于output目录
ls output/
```

### 9.3 产物验证

```bash
# 验证安装包
./output/mindstudio-service-profiler-xxx.run --check

# 安装
./output/mindstudio-service-profiler-xxx.run --install

# 升级（覆盖so、Python包、头文件）
./output/mindstudio-service-profiler-xxx.run --upgrade
```

**升级说明**：

`--upgrade` 命令将覆盖目标路径下的以下文件：

- `ms_service_profiler/`：Python包
- `libms_service_profiler.so`：动态库
- `include/msServiceProfiler/`：头文件

升级执行时将列出将被覆盖的文件并等待确认：

```text
[mindstudio-msserviceprofiler] [INFO]: Upgrade target path: /usr/local/Ascend/cann-x.x.x
[mindstudio-msserviceprofiler] [INFO]: The following files will be overwritten.
  - /usr/local/Ascend/cann-x.x.x/python/site-packages/ms_service_profiler
  - /usr/local/Ascend/cann-x.x.x/python/site-packages/ms_service_profiler/libms_service_profiler.so
  - /usr/local/Ascend/cann-x.x.x/include/msServiceProfiler
Confirm to proceed? [y/N]:
```

> 注意：升级前请根据升级列表手动备份原文件。

## 10. FAQ常见问题

### 10.1 编译问题

**Q: 编译时提示找不到sqlite3？**

A: 需要安装sqlite3开发库：

```bash
apt-get install libsqlite3-dev
```

**Q: 编译时提示找不到CANN相关库？**

A: 需要设置CANN环境变量：

```bash
export ASCEND_TOOLKIT_HOME=/usr/local/Ascend/ascend-toolkit
```

### 10.2 运行问题

**Q: 提示冲突包'msserviceprofiler'？**

A: 需要先卸载旧版本：

```bash
pip uninstall msserviceprofiler -y
```

**Q: 配置文件修改后不生效？**

A: 确保在服务启动前设置环境变量 `SERVICE_PROF_CONFIG_PATH`。

### 10.3 调试问题

**Q: 如何查看详细日志？**

A: 工具会输出以 `[msservice_profiler]` 开头的日志，检查标准输出或日志文件。

**Q: 如何验证采集是否正常工作？**

A: 检查日志中是否有类似以下输出：

```text
[msservice_profiler] [PID:xxx] [INFO] [DynamicControl:407] Profiler Enabled Successfully!
```

## 11. 相关文档

- [msServiceProfiler工具安装指南](../msserviceprofiler_install_guide.md)
- [快速入门](../quick_start.md)
- [服务化调优工具使用指南](../msserviceprofiler_serving_tuning_instruct.md)
- [vLLM服务化性能采集工具](../vLLM_service_oriented_performance_collection_tool.md)
- [SGLang服务化性能采集工具](../SGLang_service_oriented_performance_collection_tool.md)
- [Trace数据监测工具](../msserviceprofiler_trace_data_monitoring_instruct.md)
- [服务化自动寻优工具](../serviceparam_optimizer_instruct.md)
- [服务化专家建议工具](../service_profiling_advisor_instruct.md)
- [贡献指南](../../../CONTRIBUTING.md)
