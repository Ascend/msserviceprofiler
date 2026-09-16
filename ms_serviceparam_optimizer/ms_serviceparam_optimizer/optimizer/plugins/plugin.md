# 自定义插件开发指导

## 简介

寻优工具支持自定义插件，通过插件用户可自定义搜索参数配置，自定义服务框架自定义性能测试工具。

## 自定义插件开发操作步骤

步骤如下：

1. 创建自己的python项目作为插件。
2. 自定义内容:

**自定义配置**

- 继承Settings类

  settings 是通过pydantic-settings实现的，可在类里面添加 删除属性。例如

  ```python
  from ..config.config import Settings
  
  
  class CusSettings(Settings):
      name: str = "vllm-inference-optimization"
  ```

- 注册settings初始化函数

  在自己的python项目里面添加注册函数，实现注册Settings初始化

  ```python
  def register():
      from vllm_inference_optimization.settings import CusSettings
      from ..config.config import register_settings
      register_settings(lambda : CusSettings())
  ```

- 使用settings
  使用时导入get_setttings 来获取

  ```python
  from ..config.config import get_settings
  settings = get_settings()
  ```

**自定义服务框架**

- 继承msserviceprofiler...optimizer.simulator.SimulatorInterface,实现base_url 和 data_field property,实现update_command方法等。
  例如：

  ```python
   class ms_service_profiler...optimizer.simulator.SimulatorInterface()
      Bases: ABC
  
      操作服务框架。用于操作服务相关功能。
      
      abstract property data_field: Tuple[OptimizerConfigField] | None
          获取data field 属性 
          Returns: Optional[Tuple[OptimizerConfigField]]
          
      abstract property setter data_field: Tuple[OptimizerConfigField] | None
          设置data field 属性 
          Returns: None
      
      abstract update_command() → None
          服务启动前根据data_field更新服务启动命令。更新self.command属性。 
          Returns: None
      
      update_config(params: Tuple[OptimizerConfigField] | None = None) → bool
          根据参数更新服务的配置文件，或者其他配置，服务启动前根据传递的参数值 修改配置文件。使得新的配置生效。 
          Args:
      
              params: 调优参数列表，是一个元组，根据其中每一个元素的value和config position进行定义。
          
          Returns: bool, 返回更新成功或者失败。
          
      abstract stop()
          运行时，其他的准备工作。 
          Returns: None
  ```

- 并在init文件中注册服务框架

  ```python
   from ..optimizer.register import register_simulator
   register_simulator("vllm_infer", VllmSimulator)
  ```

**自定义性能测试benchmark**

- 继承msserviceprofiler...optimizer.benchmark.BenchmarkInterface,实现data_field property, get_performance_index方法等。
  例如：

  ```python
  class VllmBenchMark(BenchmarkInterface):
      def __init__(self, config: Optional[VllmBenchmarkConfig] = None, *args, **kwargs):
  
          if config:
              self.config = config
          else:
              settings = get_settings()
              if settings.name != "vllm-inference-optimization":
                  raise ValueError("Settings is invalidator.")
              self.config = settings.vllm_benchmark
          super().__init__(*args, **kwargs)
          self.command = VllmBenchmarkCommand(self.config.command).command
  ```

- 注册benchmark

  ```python
  from ..optimizer.register import register_benchmarks
  register_benchmarks("vllm_infer_benchmark", VllmBenchMark)
  ```

## 三. 设置插件入口点

将自定义的内容的注册函数添加到入口组'..plugins'即可。

例如. 如下通过调用vllm_inference_optimization模块的register来注册

pyproject.toml

```python
[project.entry - points.'..plugins']
vllm_inference_optimization = "vllm_inference_optimization:register"
```

## 四. 使用插件

通过寻优工具的调用参数来指定插件实现的模块。
例如，新注册了。服务框架vllm_infer 和 性能测试客户端 vllm_infer_benchmark
先 查看支持的服务和benchmark工具,是否包含刚刚注册的

```bash
msserviceprofiler optimizer -h
```

```ColdFusion
options:
-h, --help show this help message and exit
-lb, --load_breakpoint
Continue from where the last optimization was aborted.
--backup Whether to back up data.
-e {vllm，vllm_infer}, --engine {vllm, vllm_infer}
Specifies the engine to be used.
-b {vllm_benchmark，vllm_infer_benchmark}, --benchmark {vllm_benchmark, vllm_infer_benchmark}
Specified benchmark to be used.
```

指定插件的实现进行寻优

msserviceprofiler optimizer -e vllm_infer -b vllm_infer_benchmark

常用数据结构定义

- ..config.config.OptimizerConfigField

  ```python
  class ..config.config.OptimizerConfigField(*, name: str = 'max_batch_size', config_position: str = 'BackendConfig.ScheduleConfig.maxBatchSize', min: float = 0.0, max: float = 100.0, dtype: str = 'float', value: int | float | bool | None = None, dtype_param: Any = None)
      Bases: BaseModel
      寻优参数的结构定义。    
      
      config_position: str  # 位置定义，当前支持一种是BackendConfig.ScheduleConfig，表示修改mindieconfig.json里面的参数，一种是env，表示将该参数设置为环境变量，变量名为name名称
      dtype: str # 参数类型定义 
      dtype_param: Any  # 转换数据为指定数据类型时，提供的额外参数。
      max: float # 表示该参数最小值，作为参数变化范围限制下限
      min: float  # 表示该参数最大值，作为参数变化范围限制上限
      name: str  # 字段命名，设置环境变量时 将其全部大写作为变量名 config_position用来区分如何更新字段的值，
      value: int | float | bool | None  # 参数值，例如将该值修改到配置文件中，或者设置为环境变量的值 dtype_param: 类型转换时 需要的转换参数
  ```

- ..config.config.PerformanceIndex

  ```python
  class ..config.config.PerformanceIndex(*, generate_speed: float | None = None, time_to_first_token: float | None = None, time_per_output_token: float | None = None, success_rate: float | None = None, throughput: float | None = None)
  
      Bases: BaseModel
      benchmark 获取到的性能指标。
      
      generate_speed: float| None  # 输出的吞吐（token/s），建议传
      success_rate: float | None # 请求成功返回的百分比，建议传
      throughput: float | None # qps，建议传
      time_per_output_token: float | None  # tpot，建议传
      time_to_first_token: float | None # ttft， 建议传
  ```

### 配置自定义

..config.config.register_settings

```python
..config.config.register_settings(func: Callable | None = None) → None
注册自定义settings，可以提供函数生成。
 Args:
 func: 生成settings的函数。 
 
 Returns: None
```

### benchmark 接口

```python
class ..optimizer.benchmark.BenchmarkInterface()
    Bases: ABC
    property num_prompts: Tuple[OptimizerConfigField] | None
        获取获取数据的请求数 属性 
        Returns: Optional[Tuple[OptimizerConfigField]]
        
    property setter num_prompts: Tuple[OptimizerConfigField] | None
        设置获取数据的请求数 属性 
        Returns: None
        
    property data_field: Tuple[OptimizerConfigField] | None
        获取data field 属性 
        Returns: Optional[Tuple[OptimizerConfigField]]
        
    abstract property setter data_field: Tuple[OptimizerConfigField] | None
        设置data field 属性 
        Returns: None
    
    abstract get_performance_index() → PerformanceIndex
        获取性能指标 
        Returns: 指标数据类
    
    abstract stop()
        运行时，其他的准备工作。 
        Returns: None
    
    abstract update_command() → None
        服务启动前根据data_field更新服务启动命令。更新self.command属性。 
        Returns: None
```

并在init文件中注册benchmark

```python
class ..optimizer.simulator.SimulatorInterface()
    Bases: ABC

    操作服务框架。用于操作服务相关功能。
    
    abstract property data_field: Tuple[OptimizerConfigField] | None
        获取data field 属性 
        Returns: Optional[Tuple[OptimizerConfigField]]
        
    abstract property setter data_field: Tuple[OptimizerConfigField] | None
        设置data field 属性 
        Returns: None
    
    abstract update_command() → None
        服务启动前根据data_field更新服务启动命令。更新self.command属性。 
        Returns: None
    
    update_config(params: Tuple[OptimizerConfigField] | None = None) → bool
        根据参数更新服务的配置文件，或者其他配置，服务启动前根据传递的参数值 修改配置文件。使得新的配置生效。 
        Args:
    
            params: 调优参数列表，是一个元组，根据其中每一个元素的value和config position进行定义。
        
        Returns: bool, 返回更新成功或者失败。
        
    abstract stop()
        运行时，其他的准备工作。 
        Returns: None
```

设置插件入口点

将自定义的内容的注册函数添加到入口组'ms_service_profiler...plugins'即可。

例如. 如下通过调用vllm_inference_optimization模块的register来注册

pyproject.toml

```python
[project.entry - points.'ms_service_profiler...plugins']
vllm_inference_optimization = "vllm_inference_optimization:register"
```

安装插件

入口设置为..plugins

例如：

```python
[project.entry-points.'..plugins']
vllm_inference_optimization="vllm_inference_optimization:register"
```

使用插件模式前需要先在插件目录中（确保当前路径下包含pyproject.toml）对插件进行安装：

```bash
pip install -e .
```

使用插件

可以通过寻优工具的调用参数来指定插件实现的模块。

例如，新注册了。服务框架vllm_infer 和 性能测试客户端 vllm_infer_benchmark

先 查看支持的服务和benchmark工具,是否包含刚刚注册的

```bash
msserviceprofiler optimizer -h
```

```ColdFusion
options:
-h, --help show this help message and exit
-lb, --load_breakpoint
Continue from where the last optimization was aborted.
--backup Whether to back up data.
-e {vllm，vllm_infer}, --engine {vllm， vllm_infer}
Specifies the engine to be used.
-b {vllm_benchmark，vllm_infer_benchmark}, --benchmark {vllm_benchmark， vllm_infer_benchmark}
Specified benchmark to be used.
```

指定插件的实现进行寻优

```bash
msserviceprofiler optimizer -e vllm_infer -b vllm_infer_benchmark
```
