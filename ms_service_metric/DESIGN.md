# ms\_service\_metric 设计文档

## 1. 项目概述

### 1.1 背景

ms\_service\_metric 是从 ms\_service\_profiler/patcher 中提取出来的独立 metric 功能模块，作为独立的库发布。主要用于监控和分析服务（如 vLLM）的性能指标。

### 1.2 目标

- 功能保持不变（除非特别说明）
- 代码结构清晰，职责分离
- 性能优先，简化hook函数内部逻辑
- 支持动态开关（共享内存 + SIGUSR1信号）
- 保持对外接口和配置兼容

### 1.3 与原项目的关系

| 特性        | ms\_service\_profiler | ms\_service\_metric |
| --------- | --------------------- | ------------------- |
| Profiling | ✅ 支持                  | ❌ 不支持               |
| Metrics   | ✅ 支持                  | ✅ 支持                |
| 动态开关      | C++回调                 | 共享内存+信号             |
| 独立部署      | ❌ 依赖C++               | ✅ 纯Python           |

## 2. 项目结构

```text
ms_service_metric/                           # 项目根目录
├── pyproject.toml                           # 项目配置
├── README.md                                # 项目说明
├── DESIGN.md                                # 设计文档
├── ms_service_metric/                       # 主包（与项目名一致）
│   ├── __init__.py                          # 包初始化
│   ├── __main__.py                          # 命令行入口
│   ├── core/                                # 核心模块
│   │   ├── __init__.py
│   │   ├── symbol_handler_manager.py        # SymbolHandlerManager核心类
│   │   ├── symbol.py                        # Symbol类
│   │   ├── handler.py                       # Handler抽象基类和MetricHandler实现
│   │   ├── config/                          # 配置相关模块
│   │   │   ├── __init__.py
│   │   │   ├── symbol_config.py             # SymbolConfig配置类
│   │   │   └── metric_control_watch.py      # MetricConfigWatch类
│   │   ├── hook/                            # Hook相关模块
│   │   │   ├── __init__.py
│   │   │   ├── hook_chain.py                # HookChain类（双向链表管理多hook）
│   │   │   ├── hook_helper.py               # HookHelper类（函数替换辅助）
│   │   │   └── inject.py                    # 字节码注入
│   │   └── module/                          # 模块相关模块
│   │       ├── __init__.py
│   │       └── symbol_watcher.py            # SymbolWatcher类（单例）
│   ├── handlers/                            # 内置handlers
│   │   ├── __init__.py
│   │   └── builtin.py                       # 内置handler实现（default_handler等）
│   ├── adapters/                            # 框架适配器
│   │   ├── __init__.py
│   │   ├── vllm/                            # vLLM适配
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py                   # vLLM适配器入口
│   │   │   ├── metrics_init.py              # vLLM metrics初始化
│   │   │   ├── handlers/                    # vLLM专用handlers目录
│   │   │   │   ├── __init__.py
│   │   │   │   ├── metric_handlers.py       # metric handlers
│   │   │   │   └── meta_handlers.py         # meta handlers
│   │   │   └── config/
│   │   │       ├── default.yaml             # vLLM默认配置
│   │   │       └── v1_metrics.yaml          # vLLM V1 metrics配置
│   │   └── sglang/                          # SGLang适配
│   │       ├── __init__.py
│   │       ├── adapter.py                   # SGLang适配器入口
│   │       └── config/
│   │           └── default.yaml             # SGLang默认配置
│   ├── metrics/                             # Metrics相关模块
│   │   ├── __init__.py
│   │   ├── metrics_manager.py               # MetricsManager类
│   │   └── meta_state.py                    # 元数据状态管理
│   ├── utils/                               # 工具模块
│   │   ├── __init__.py
│   │   ├── expr_eval.py                     # 表达式求值（ExprEval）
│   │   ├── exceptions.py                    # 异常定义
│   │   ├── logger.py                        # 日志工具
│   │   ├── function_context.py              # 函数上下文
│   │   └── shm_manager.py                   # 共享内存管理器
│   └── control/                             # 控制端程序
│       ├── __init__.py
│       └── cli.py                           # 命令行控制工具（ms-service-metric）
└── tests/                                   # 测试目录
    ├── __init__.py
    ├── conftest.py                          # pytest配置和fixture
    ├── test_config_compatibility.py         # 配置兼容性测试
    ├── test_design.md                       # 测试设计文档
    └── unit/                                # 单元测试
        ├── __init__.py
        ├── test_exceptions.py               # 异常类测试
        ├── test_expr_eval.py                # 表达式求值测试
        ├── test_handler.py                  # Handler测试
        ├── test_hook_chain.py               # HookChain测试
        ├── test_logger.py                   # 日志工具测试
        ├── test_metrics_manager.py          # MetricsManager测试
        ├── test_symbol_config.py            # SymbolConfig测试
        ├── test_symbol_hook.py              # Symbol hook测试
        ├── test_symbol_watcher.py           # SymbolWatcher测试
        └── test_utils.py                    # 工具函数测试
```

## 3. 核心类设计

### 3.1 SymbolHandlerManager（核心管理类）

**职责：**

- 管理所有的handler和Symbol
- 根据配置动态加载和卸载handler和symbol
- 将所有其他类串联起来的核心类

**关键设计：**

1. 基于handler的增删，自动处理symbol对象
2. 简化锁的使用（仅保护\_enabled和批量操作的原子性）
3. 批量apply\_hook，而不是每个handler变化都reapply
4. 处理打开时，暂停所有symbol的hook/unhook操作，完成后统一执行
5. 支持优雅停止（graceful stop），根据lock\_patch属性决定是否保留handler

**类定义：**

```python
class SymbolHandlerManager:
    """Symbol和Handler的核心管理类"""
    
    def __init__(self):
        self._config = SymbolConfig()
        self._watcher = SymbolWatcher()  # 单例
        self._metrics_manager = get_metrics_manager()  # 单例
        self._control_watch = MetricConfigWatch()
        self._symbols: Dict[str, Symbol] = {}
        self._handlers: Dict[str, Handler] = {}
        self._enabled = False
        self._lock = threading.Lock()
        self._updating = False
        
    def initialize(self, config_path: Optional[str] = None, default_config_path: Optional[str] = None):
        """初始化所有组件"""
        
    def shutdown(self):
        """关闭管理器"""
        
    def _on_control_state_change(self, is_start: bool, timestamp: int):
        """控制状态变化回调"""
        
    def _update_handlers(self, config: Dict[str, List[Dict]]):
        """根据配置更新handlers"""
        
    def _add_handler(self, handler: Handler):
        """添加handler，自动管理symbol生命周期"""
        
    def _remove_handler(self, handler_id: str):
        """移除handler，如果symbol没有handlers则自动删除"""
        
    def _update_handler(self, handler: Handler):
        """更新handler（直接替换）"""
        
    def _apply_all_hooks(self):
        """批量应用所有symbols的hooks"""
        
    def _stop_all_symbols(self):
        """停止所有symbols"""
        
    def _stop_all_symbols_graceful(self):
        """优雅地停止所有symbols（支持lock_patch）"""
        
    def is_updating(self) -> bool:
        """检查是否正在批量更新"""
        
    def is_enabled(self) -> bool:
        """检查是否启用"""
```

**控制状态处理逻辑：**

```text
关闭命令 (is_start=False):
  - 如果当前已启用，根据lock_patch属性决定是否保留handler
  - 如果当前已禁用，无操作

开启命令 (is_start=True):
  - 如果当前已启用且时间戳相同：重复命令，无操作
  - 如果当前已启用且时间戳不同：重启，关闭所有→重载配置→重新应用
  - 如果当前已禁用：普通开启，重载配置→应用
```

### 3.2 Symbol（Symbol类）

**职责：**

- 代表一个需要hook的符号
- 管理其handlers（不允许重复）
- 直接监听模块加载事件（不通过SymbolHandlerManager中转）
- 根据Manager状态决定是否执行hook/unhook
- 支持优雅停止（lock\_patch功能）

**类定义：**

```python
class Symbol:
    """Symbol类，代表一个需要hook的符号
    
    使用 HookChain 管理多个 Symbol 对同一个函数的 hook 形成调用链。
    支持在链表头部插入节点（insert_at_head=True）。
    """
    
    def __init__(
        self,
        symbol_path: str,
        watcher: "SymbolWatcher",
        manager: "SymbolHandlerManager"
    ):
        self._symbol_path = symbol_path
        self._module_path, self._attr_path = symbol_path.split(':', 1)
        self._handlers: Dict[str, Handler] = {}
        self._hook_applied = False
        self._module_loaded = False
        self._pending_hook = False
        self._watcher = watcher
        self._manager = manager
        self._hook_node: Optional[HookNode] = None  # HookChain 节点
        self._hook_chain: Optional[HookChain] = None  # HookChain 实例
        self._target: Optional[Any] = None  # 缓存导入的目标对象
        
    @property
    def symbol_path(self) -> str:
        """symbol完整路径"""
        
    @property
    def module_path(self) -> str:
        """模块路径"""
        
    @property
    def hook_applied(self) -> bool:
        """是否已经应用hook"""
        
    def add_handler(self, handler: Handler):
        """添加handler（不允许重复）"""
        
    def remove_handler(self, handler_id: str):
        """移除handler"""
        
    def update_handler(self, handler: Handler):
        """更新handler（直接替换）"""
        
    def is_empty(self) -> bool:
        """检查是否没有handlers"""
        
    def hook(self):
        """应用hook（对外接口）"""
        
    def _apply_hook(self):
        """内部核心方法：应用或更新hook"""
        
    def unhook(self):
        """恢复原始函数"""
        
    def stop(self):
        """停止监听并解绑"""
        
    def stop_unlocked(self) -> Tuple[List[str], List[str]]:
        """停止未锁定的handlers，返回(已删除ids, 保留ids)"""
        
    def _build_final_hook(
        self,
        target: Any,
        ori_wrap: Any,
        wrap_funcs: List[Callable],
        context_funcs: List[Callable],
        chain: HookChain
    ) -> Callable:
        """构建最终的hook函数"""
        
    def _build_wrap_chain(self, target: Any, ori_wrap: Any, wrap_funcs: List[Callable]) -> Callable:
        """构建wrap函数链（洋葱模型）"""
        
    def _build_sync_wrap_chain(self, ori_wrap: Any, wrap_funcs: List[Callable]) -> Callable:
        """构建同步wrap函数链"""
        
    def _build_async_wrap_chain(self, ori_wrap: Any, wrap_funcs: List[Callable]) -> Callable:
        """构建异步wrap函数链"""
        
    def _build_context_wrap_handler(self, wrap_chain: Any, context_funcs: List[Callable]) -> Callable:
        """将context handlers封装成一个wrap handler"""
        
    def _build_hook_with_injection(
        self,
        target: Any,
        context_funcs: List[Callable],
        chain: HookChain,
    ) -> Callable:
        """构建带字节码注入的hook"""
```

**Handler合并策略：**

```text
1. 分离wrap handlers和context handlers
2. 执行顺序：
   a. context handlers（需要locals）-> 字节码注入
   b. context handlers（不需要locals）-> 封装成wrap handler
   c. wrap handlers -> 直接包装（洋葱模型）

3. 示例：
   原函数 -> injection(need_locals_handlers) -> context_wrap(no_need_locals_handlers) -> wrap_chain
```

**洋葱模型示例：**

```text
配置顺序: handler1, handler2, handler3
执行顺序: handler1 -> handler2 -> handler3 -> 原函数 -> handler3 -> handler2 -> handler1

wrap_chain构建:
  chain = target  # 最内层是原函数
  for wrap_func in reversed(wrap_funcs):  # 反向遍历
      chain = create_layer(wrap_func, chain)
```

### 3.3 Handler（Handler抽象基类）

**职责：**

- 定义Handler的基础接口（抽象基类）
- 所有自定义Handler都应该继承此类

**类定义：**

```python
class Handler(ABC):
    """Handler抽象基类：定义Symbol需要的基础接口"""
    
    @property
    @abstractmethod
    def id(self) -> str:
        """获取handler唯一标识符"""
        pass
    
    @abstractmethod
    def get_hook_func(self, target: Callable) -> tuple[HandlerType, Callable]:
        """获取hook函数，返回(handler类型, hook函数)"""
        pass
    
    @property
    def name(self) -> str:
        """获取handler名称"""
        return self.id
    
    def __hash__(self) -> int:
        """支持hash，用于set和dict"""
        return hash(self.id)
    
    def __eq__(self, other: object) -> bool:
        """支持相等比较"""
        if not isinstance(other, Handler):
            return False
        return self.id == other.id
```

### 3.4 MetricHandler（Handler的具体实现）

**职责：**

- 负责加载内置的handler或者用户自定义的handler
- 将hook\_func分类为wrap\_func和context\_funcs
- 自动检测handler类型（通过函数签名）
- 提供唯一的handler\_id（从hook\_func的完整路径生成）
- 支持metrics配置
- 支持lock\_patch属性（关闭时不删除）

**类定义：**

```python
class MetricHandler(Handler):
    """MetricHandler类：支持metrics配置的Handler实现"""
    
    def __init__(
        self,
        name: str,
        symbol_info: dict,
        hook_func: Callable,
        min_version: Optional[str] = None,
        max_version: Optional[str] = None,
        metrics_config: Optional[List[MetricConfig]] = None,
        lock_patch: bool = False
    ):
        self._name = name
        self._symbol_info = symbol_info
        self._symbol_path = symbol_info.get("symbol_path")
        self._hook_func = hook_func
        self._min_version = min_version
        self._max_version = max_version
        self._metrics_config = metrics_config or []
        self._lock_patch = lock_patch
        
        # 分类hook_func，同时确定handler_type
        handler_type, hook_func = self._classify_hook_func(hook_func)
        if handler_type != None:
            self._handler_type = handler_type
            self._hook_func = hook_func
        else:
            self._handler_type = None
        
        # 生成唯一ID
        self._id = self._generate_id()
        
    @property
    def id(self) -> str:
        """获取handler ID"""
        
    @property
    def name(self) -> str:
        """获取handler名称"""
        
    @property
    def symbol_path(self) -> str:
        """获取所属symbol路径"""
        
    @property
    def handler_type(self) -> HandlerType:
        """获取handler类型"""
        
    @property
    def lock_patch(self) -> bool:
        """是否锁定patch（关闭时不删除）"""
        
    def get_hook_func(self, target: Callable) -> tuple[HandlerType, Callable]:
        """获取hook函数"""
        
    def equals(self, other: 'MetricHandler') -> bool:
        """比较两个handler是否相等（考虑配置变化）"""
        
    def _classify_hook_func(self, func) -> HandlerType:
        """将hook_func分类为wrap_func或context_func"""
        
    def _create_context_manager(self, func: Callable) -> Optional[Callable]:
        """尝试将函数转换为上下文管理器"""
        
    @classmethod
    def from_config(cls, config: Dict, symbol_path: str) -> 'MetricHandler':
        """从配置创建MetricHandler实例"""
        
    @staticmethod
    def _import_handler(handler_path: str) -> Callable:
        """导入handler函数"""
        
    @staticmethod
    def _parse_metrics_config(metrics_config: list) -> List[MetricConfig]:
        """解析metrics配置"""
```

**Handler分类规则：**

```text
- 生成器函数 -> context_func, 返回 HandlerType.CONTEXT
  - 1个参数(ctx): 不需要locals
  - 2个参数(ctx, local_values): 需要locals
- ContextManager子类 -> context_func, 返回 HandlerType.CONTEXT
- 其他 -> wrap_func, 返回 HandlerType.WRAP
```

**Handler函数签名：**

```python
# Wrap Handler
def wrap_handler(ori_func, *args, **kwargs):
    # 前置处理
    result = ori_func(*args, **kwargs)  # 必须显式调用原函数
    # 后置处理
    return result

# Context Handler（不需要locals，1个参数）
def simple_context_handler(ctx):
    # ctx: FunctionContext对象
    # 前置处理
    yield  # 原函数在这里执行
    # 后置处理（可以访问ctx.return_value）

# Context Handler（需要locals，2个参数）
def advanced_context_handler(ctx, local_values):
    # ctx: FunctionContext对象
    # local_values: 函数的locals字典
    # 前置处理
    yield  # 原函数在这里执行
    # 后置处理（可以访问ctx.return_value和local_values）
```

### 3.5 FunctionContext（函数上下文类）

**职责：**

- 存储函数执行上下文（local\_values、return\_value）
- 提供便捷方法访问local\_values

**类定义：**

```python
class FunctionContext:
    """函数执行上下文"""
    
    def __init__(self):
        self._local_values: Optional[Dict[str, Any]] = None
        self.return_value: Any = None
    
    @property
    def local_values(self) -> Optional[Dict[str, Any]]:
        """获取函数的locals字典"""
        
    @local_values.setter
    def local_values(self, value: Optional[Dict[str, Any]]):
        """设置函数的locals字典"""
        
    def get(self, key: str, default: Any = None) -> Any:
        """从local_values中获取值，模拟dict的get方法"""
        
    def __getitem__(self, key: str) -> Any:
        """支持通过 ctx['var'] 语法访问local_values"""
        
    def __contains__(self, key: str) -> bool:
        """支持 'var' in ctx 语法检查local_values中是否存在某变量"""
```

**使用示例：**

```python
# 在context handler中使用
def my_handler(ctx, local_values):
    # 前置处理
    x = ctx.get('x', 0)  # 获取局部变量x，默认值0
    y = ctx['y']  # 直接使用字典语法
    if 'z' in ctx:  # 检查变量是否存在
        z = ctx.get('z')
    
    yield  # 原函数执行
    
    # 后置处理
    result = ctx.return_value
```

### 3.6 HookChain（Hook链管理类）

**职责：**

- 使用双向链表管理多个 hook 函数
- 支持动态添加、删除和调用 hook
- 支持在链表头部或尾部插入节点
- 每个 Symbol 创建一个节点，多个 Symbol 可以形成调用链
- 提供异常保护机制

**类定义：**

```python
class HookNode:
    """Hook 链表节点"""
    
    def __init__(self, chain: 'HookChain', prev_node: Optional['HookNode'] = None):
        self.chain = chain
        self.hook_func = self.call_prev  # 默认调用前一个
        self.prev_node = prev_node
        self.next_node: Optional[HookNode] = None
    
    @property
    def ori_wrap(self):
        """返回调用链中下一个函数的包装器"""
        return self.call_prev
    
    def set_hook_func(self, hook_func: Callable):
        """设置当前节点的 hook 函数"""
        self.hook_func = hook_func
    
    def call_prev(self, *args, **kwargs):
        """调用上一个 hook 函数（洋葱模型向内）"""
        if self.prev_node:
            return self.prev_node.hook_func(*args, **kwargs)
        else:
            return self.chain._call_ori_func(*args, **kwargs)
    
    def remove(self) -> bool:
        """从链表中移除当前节点"""
        return self.chain.remove_chain_node(self)
    
    def recover(self):
        """恢复原始函数（别名remove）"""
        return self.remove()


class HookChain:
    """Hook 链表管理器"""

    def __init__(self, ori_func: Callable):
        self.ori_func = ori_func
        self.head: Optional[HookNode] = None
        self.tail: Optional[HookNode] = None
        self._nodes: Dict[int, HookNode] = {}  # 使用id(node)作为key的字典
        self._lock = threading.Lock()
        self._helper = None
        self._last_result = NO_RESULT  # 保存最后一次调用的结果
        
    def set_last_result(self, result):
        """设置最后一次调用的结果"""
        
    def _call_ori_func(self, *args, **kwargs):
        """调用原始函数并保存结果"""
        
    def add_chain_node(self, insert_at_head: bool = False) -> HookNode:
        """添加节点，返回 HookNode
        
        Args:
            insert_at_head: 如果为 True，插入到链表头部；否则插入到尾部（默认）
        """
        
    def remove_chain_node(self, node: HookNode) -> bool:
        """删除节点"""
        
    def get_chain_info(self) -> dict[str, Any]:
        """获取 chain 的调试信息"""
        
    def print_chain_info(self, action: str = "Info"):
        """打印 chain 的调试信息"""
        
    def exec_chain_closure(self):
        """返回执行hook链的闭包函数，带有异常保护机制"""
        
    def __call__(self, *args, **kwargs):
        """调用链表的最后一个节点"""


def get_chain(ori_func: Callable) -> HookChain:
    """获取或创建 HookChain（公共函数，带缓存）"""
```

**使用方式：**

```python
# Symbol 类中使用 hook_chain
from ms_service_metric.core.hook.hook_chain import get_chain

class Symbol:
    def hook(self):
        # 1. 获取或创建chain
        self._hook_chain = get_chain(self._target)
        
        # 2. 在头部添加节点
        self._hook_node = self._hook_chain.add_chain_node(insert_at_head=True)
        
        # 3. 构建 hook 函数（使用 ori_wrap 作为调用链中下一个函数）
        final_hook = self._build_final_hook(
            self._hook_chain.ori_func,
            self._hook_node.ori_wrap,
            wrap_funcs, 
            context_funcs, 
            self._hook_chain
        )
        
        # 4. 设置 hook 函数
        self._hook_node.set_hook_func(final_hook)
    
    def unhook(self):
        # 通过移除节点恢复原始函数
        if self._hook_node:
            self._hook_node.remove()
            self._hook_node = None
```

**异常保护机制：**

```python
def execute_hook_chain(*args, **kwargs):
    """执行 hook 链，带有异常保护机制
    
    保护策略：
    1. 先将 _last_result 重置为 NO_RESULT
    2. 执行 hook 链
    3. 如果执行过程中发生异常：
       - 如果 _last_result 还是 NO_RESULT（说明还没调用到 ori_func），主动调用一次 ori_func 并返回
       - 如果 _last_result 是异常（说明 ori_func 抛出了异常），直接重新抛出
       - 如果 _last_result 已经有正常值（说明已经调用过 ori_func），直接返回保存的结果
    4. 如果正常执行完成，返回 hook 链的结果
    """
```

### 3.7 HookHelper（Hook辅助类）

**职责：**

- 负责具体的函数替换和恢复
- 保存原始函数，支持恢复
- 解析目标对象（支持函数、方法、类属性）

**类定义：**

```python
class HookHelper:
    """Hook辅助类
    
    负责具体的函数替换和恢复操作。
    只负责简单的函数替换，复杂的handler合并逻辑由Symbol类处理。
    """
    
    def __init__(self, target: Any, hook_func: Callable):
        self._target = target
        self._hook_func = hook_func
        self._original_func: Optional[Callable] = None
        self._replaced = False
        self._target_obj, self._target_name = self._parse_target(target)
        
    def _parse_target(self, target: Any) -> tuple:
        """解析目标对象，确定容器和属性名"""
        
    def replace(self):
        """应用hook，替换目标函数"""
        
    def recover(self):
        """恢复原始函数"""
        
    @property
    def is_replaced(self) -> bool:
        """是否已经应用hook"""
        
    @property
    def original_func(self) -> Optional[Callable]:
        """原始函数"""
```

### 3.8 MetricsManager（Prometheus指标管理器）

**职责：**

- 管理所有Prometheus指标的注册、记录和查询
- 支持多种指标类型：Histogram、Counter、Gauge、Summary
- 提供标签管理和表达式求值功能
- 支持多进程环境下的指标收集
- 自动添加dp标签

**类定义：**

```python
class MetricType(str, Enum):
    """指标类型枚举"""
    TIMER = "timer"          # 耗时指标（使用Histogram实现）
    HISTOGRAM = "histogram"  # 直方图
    COUNTER = "counter"      # 计数器
    GAUGE = "gauge"          # 仪表盘
    SUMMARY = "summary"      # 摘要


@dataclass
class MetricConfig:
    """指标配置数据结构"""
    name: str
    type: MetricType
    expr: str = ""
    buckets: Optional[List[float]] = None
    labels: Optional[Dict[str, str]] = None


class MetricsManager:
    """Prometheus指标管理器"""
    
    def __init__(self):
        self._metrics: Dict[str, Any] = {}
        self._label_definitions: Dict[str, List[Dict[str, str]]] = {}
        self._registry: Optional[CollectorRegistry] = None
        self._metric_prefix: str = ""
        
    @property
    def metric_prefix(self) -> str:
        """获取指标名称前缀"""
        
    @metric_prefix.setter
    def metric_prefix(self, prefix: str):
        """设置指标名称前缀"""
        
    def _get_appropriate_registry(self) -> CollectorRegistry:
        """获取合适的Prometheus注册表（支持多进程）"""
        
    def _generate_custom_buckets(self, max_end: float = 1000, max_precision: int = 6) -> List[float]:
        """生成自定义直方图分桶"""
        
    def _add_prefix(self, metric_name: str) -> str:
        """为指标名称添加前缀"""
        
    def _add_dp_label_name(self, label_names: Optional[List[str]] = None) -> List[str]:
        """为指标添加默认的dp域标签名"""
        
    def _add_dp_label_value(self, labels: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """为指标添加默认的dp域标签值"""
        
    def _sanitize_metric_name(self, name: str) -> str:
        """清理指标名称，确保符合Prometheus规范"""
        
    def register_metric(
        self,
        metric_config: MetricConfig,
        label_names: Optional[List[str]] = None
    ) -> Optional[Any]:
        """注册指标"""
        
    def add_label_definition(self, metric_name: str, label_name: str, expr: str):
        """添加标签定义"""
        
    def get_label_definitions(self) -> Dict[str, List[Dict[str, str]]]:
        """获取标签定义字典"""
        
    def record_metric(
        self,
        metric_name: str,
        value: Union[int, float],
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """记录指标值"""
        
    def get_registry(self) -> Optional[CollectorRegistry]:
        """获取使用的registry"""
        
    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有已创建的指标"""
        
    def get_or_create_metric(
        self,
        metric_name: str,
        label_names: Optional[List[str]] = None,
        metric_type: MetricType = MetricType.TIMER,
        buckets: Optional[List[float]] = None
    ) -> "MetricsManager":
        """获取或创建指标"""
        
    def clear_metrics(self):
        """清除所有指标"""


# 全局MetricsManager实例（单例）
_metrics_manager_instance: Optional[MetricsManager] = None

def get_metrics_manager() -> MetricsManager:
    """获取全局MetricsManager实例"""
```

### 3.9 SymbolWatcher（模块加载监视器，单例）

**职责：**

- 监听Python模块的导入事件
- 当模块加载时通知注册的回调
- 按模块管理回调，确保回调时就是确认的模块被加载
- 单例模式，确保全局只有一个监视器实例

**类定义：**

```python
class ModuleEventType(Enum):
    """模块事件类型"""
    LOADED = "loaded"
    UNLOADED = "unloaded"


class ModuleEvent:
    """模块事件"""
    
    def __init__(self, module_name: str, event_type: ModuleEventType, module=None):
        self.module_name = module_name
        self.type = event_type
        self.module = module


class SymbolWatchFinder(importlib.abc.MetaPathFinder):
    """模块导入监听器
    
    通过插入到sys.meta_path来监听模块导入事件。
    """
    
    def __init__(self, watcher: "SymbolWatcher"):
        self._watcher = watcher
        self._target_modules: Set[str] = set()
        
    def add_target_module(self, module_name: str):
        """添加目标模块"""
        
    def remove_target_module(self, module_name: str):
        """移除目标模块"""
        
    def find_spec(self, fullname: str, path, target=None):
        """查找模块spec，包装loader以触发回调"""


class SymbolWatcher:
    """Symbol监视器（单例）
    
    多次实例化返回同一个对象，确保全局只有一个监视器实例。
    """
    
    _instance: Optional["SymbolWatcher"] = None
    _initialized: bool = False
    _singleton_lock: threading.Lock = threading.Lock()
    
    def __new__(cls) -> "SymbolWatcher":
        """确保只有一个实例"""
        
    def __init__(self):
        """初始化（仅第一次调用有效）"""
        
    def watch(self, callback: Callable[[str], None]):
        """监听所有模块的加载事件（全局回调）"""
        
    def unwatch(self, callback: Callable[[str], None]):
        """取消监听所有模块的加载事件"""
        
    def has_global_callbacks(self) -> bool:
        """检查是否有注册的全局回调"""
        
    def watch_module(self, module_name: str, callback: Callable[[ModuleEvent], None]):
        """监听指定模块的事件"""
        
    def unwatch_module(self, module_name: str, callback: Callable[[ModuleEvent], None]):
        """取消监听指定模块的事件"""
        
    def start(self):
        """启动监视器（插入到sys.meta_path）"""
        
    def uninstall(self):
        """卸载监视器（从sys.meta_path移除）"""
        
    def stop(self):
        """停止监视器"""
        
    def is_module_loaded(self, module_name: str) -> bool:
        """检查模块是否已加载"""
        
    def _notify_module_loaded(self, module_name: str):
        """通知模块加载事件"""
```

### 3.10 SymbolConfig（配置管理类）

**职责：**

- 读取YAML配置文件
- 读取用户配置、默认配置
- 配置合并、自动赋默认值
- 支持两种配置格式：数组格式和字典格式

**类定义：**

```python
class SymbolConfig:
    """Symbol配置管理类"""
    
    ENV_CONFIG_PATH = "MS_SERVICE_METRIC_CONFIG_PATH"
    
    def __init__(self, 
                 user_config_path: Optional[str] = None,
                 default_config_path: Optional[str] = None):
        
    def load(self, config_path: Optional[str] = None, default_config_path: Optional[str] = None) -> Dict[str, List[dict]]:
        """加载并合并配置"""
        
    def reload(self) -> Dict[str, List[dict]]:
        """重新加载配置"""
        
    def _load_default_config(self) -> dict:
        """加载默认配置"""
        
    def _load_user_config(self) -> dict:
        """加载用户配置"""
        
    def _load_yaml(self, path: str) -> dict:
        """加载YAML文件，支持数组格式和字典格式"""
        
    def _convert_array_config(self, config_list: list) -> dict:
        """将数组格式的配置转换为字典格式"""
        
    def _merge_configs(self, default: dict, user: dict) -> dict:
        """合并配置（用户配置追加到默认配置后面）"""
        
    def _fill_defaults(self):
        """为配置填充默认值"""
        
    def get_config(self) -> Dict[str, List[dict]]:
        """获取当前配置"""
        
    def get_symbol_config(self, symbol_path: str) -> List[dict]:
        """获取指定symbol的配置"""
```

### 3.11 MetricConfigWatch（Metric配置动态监视器）

**职责：**

- 使用posix\_ipc共享内存和SIGUSR1信号实现进程间通信
- 支持环境变量配置共享内存和信号量名称前缀
- 简化设计：只需要start标志和时间戳
  - start=False: 关闭metric收集
  - start=True: 开启metric收集
  - 时间戳变化表示需要重启（重新加载配置）

**类定义：**

```python
class MetricConfigWatch:
    """Metric配置监视器
    
    使用posix_ipc共享内存和SIGUSR1信号实现动态开关控制。
    支持多进程同时监听，控制端可以同时向所有进程发送信号。
    """
    
    STATE_OFF = 0
    STATE_ON = 1
    
    def __init__(self, shm_prefix: Optional[str] = None, max_procs: Optional[int] = None):
        
    def register_callback(self, callback: Callable[[bool, int], None]):
        """注册状态变化回调"""
        
    def unregister_callback(self, callback: Callable[[bool, int], None]):
        """注销状态变化回调"""
        
    def start(self):
        """启动监视器（在被控制进程中调用）"""
        
    def stop(self):
        """停止监视器"""
        
    def _register_signal_handler(self):
        """注册SIGUSR1信号处理"""
        
    def _signal_handler(self, signum, frame):
        """SIGUSR1信号处理函数"""
        
    def _check_control_state(self):
        """检查控制状态"""
        
    def get_last_timestamp(self) -> int:
        """获取上次处理的时间戳"""
        
    def is_enabled(self) -> bool:
        """检查当前是否处于开启状态"""
        
    @classmethod
    def set_control_state(cls, is_start: bool, shm_prefix: Optional[str] = None, force: bool = False):
        """设置控制状态（控制端调用）"""
```

### 3.12 SharedMemoryManager（共享内存管理器）

**职责：**

- 统一管理ms\_service\_metric的共享内存操作
- 内存布局定义（支持版本兼容）
- 共享内存创建/连接/断开/释放
- 信号量操作
- 数据读写（状态、时间戳、进程列表）
- 进程管理（添加、清理、验证）
- 发送控制命令和信号
- 版本兼容性处理（能读多少读多少）

**内存布局设计：**

所有偏移量都相对于共享内存起始位置，采用版本兼容设计：

```text
[魔数:4][版本:4][头部长度:4][状态:4][时间戳:4][进程列表偏移:4][头部结束标记:4][进程列表长度:4][进程列表游标:4][PID1:4][PID2:4]...[PIDn:4]
```

**字段说明（每个都是int32）：**

- 魔数 (0x4D534D54 = "MSMT")
- 版本号
- 头部长度（从开始到结束标记的总字节数）
- 状态（STATE\_OFF=0/STATE\_ON=1）
- 时间戳
- 进程列表偏移（相对于共享内存起始位置）
- 头部结束标记 (0xDEADBEEF)
- 进程列表长度（循环列表长度）
- 进程列表游标（循环列表当前位置）
- 进程ID数组...

**版本兼容策略：**

- 使用魔数和头部结束标记验证内存格式
- 版本不匹配时标记 `_version_mismatch`，但尽量读取可用字段
- 通过 `_is_field_available(offset)` 检查字段是否在有效头部长度范围内
- 进程列表不可用时返回异常值（PROC\_LEN\_INVALID = -1）

**类定义：**

```python
class SharedMemoryLayout:
    """共享内存布局定义（版本兼容设计）"""
    
    # 头部字段偏移量（相对于共享内存起始位置）
    OFFSET_MAGIC = 0       # 魔数（int32）
    OFFSET_VERSION = 4     # 版本号（int32）
    OFFSET_HEADER_LEN = 8  # 头部长度（int32）
    OFFSET_STATE = 12      # 状态（int32）
    OFFSET_TIMESTAMP = 16  # 时间戳（int32）
    OFFSET_PROC_OFFSET = 20  # 进程列表偏移（int32）
    OFFSET_HEADER_END = 24 # 头部结束标记（int32）
    
    HEADER_SIZE = 28  # 头部总大小
    
    # 进程列表字段相对偏移（相对于进程列表起始位置）
    PROC_LIST_REL_OFFSET_LEN = 0     # 进程列表长度字段相对偏移
    PROC_LIST_REL_OFFSET_CURSOR = 4  # 进程列表游标字段相对偏移
    PROC_LIST_REL_OFFSET_DATA = 8    # 进程列表数据开始相对偏移
    PROC_LIST_HEADER_SIZE = 8        # 进程列表头部大小（长度+游标）
    PROC_ENTRY_SIZE = 4              # 每个进程ID占用的字节数


class SharedMemoryManager:
    """共享内存管理器"""
    
    # 异常值常量
    PROC_OFFSET_INVALID = -1  # 进程列表偏移异常值
    PROC_LEN_INVALID = -1     # 进程列表长度异常值
    
    def __init__(self, shm_prefix: Optional[str] = None, max_procs: Optional[int] = None):
        """初始化共享内存管理器"""
        
    def connect(self, create: bool = True) -> bool:
        """连接到共享内存
        
        连接到已存在的共享内存时，会自动获取实际大小并调整内存映射。
        如果大小不匹配，会记录警告但继续使用实际大小。
        """
        
    def disconnect(self):
        """断开连接"""
        
    def destroy(self):
        """销毁共享内存和信号量（完全删除）"""
        
    def lock(self):
        """获取信号量锁（阻塞）"""
        
    def unlock(self):
        """释放信号量锁"""
        
    def semaphore_lock(self):
        """获取信号量锁（上下文管理器）"""
        
    def read_int(self, offset: int) -> int:
        """从共享内存读取int32（无符号）"""
        
    def write_int(self, offset: int, value: int):
        """向共享内存写入int32（无符号）"""
        
    def _is_field_available(self, offset: int) -> bool:
        """检查指定偏移量的字段是否可用（在有效头部长度范围内）"""
        
    def get_state(self) -> int:
        """获取当前状态（字段不可用时返回STATE_OFF）"""
        
    def set_state(self, state: int):
        """设置状态"""
        
    def get_timestamp(self) -> int:
        """获取时间戳（字段不可用时返回0）"""
        
    def set_timestamp(self, timestamp: int):
        """设置时间戳"""
        
    def update_state_and_timestamp(self, state: int):
        """同时更新状态和时间戳"""
        
    def _get_proc_offset(self) -> int:
        """获取进程列表偏移（不可用时返回PROC_OFFSET_INVALID）"""
        
    def get_proc_len(self) -> int:
        """获取进程列表长度（不可用时返回PROC_LEN_INVALID）"""
        
    def get_proc_cursor(self) -> int:
        """获取进程列表游标（不可用时返回0）"""
        
    def get_all_procs(self) -> List[int]:
        """获取所有有效进程ID（去重，不可用时返回空列表）"""
        
    def add_process(self, pid: Optional[int] = None) -> int:
        """添加进程到列表（不可用时返回-1）"""
        
    def add_current_process(self) -> int:
        """添加当前进程到列表"""
        
    def cleanup_invalid_processes(self) -> int:
        """清理无效进程（返回清理数量，不可用时返回-1）"""
        
    def get_valid_processes(self) -> List[int]:
        """获取所有有效进程ID（验证进程是否存在）"""
        
    def should_destroy(self) -> bool:
        """检查是否应该销毁共享内存（状态OFF且无有效进程）"""
        
    def send_control_command(
        self,
        is_start: bool,
        force: bool = False,
        send_signal: bool = True
    ) -> Tuple[bool, int, int, bool]:
        """发送控制命令，返回(是否成功, 成功发送信号数, 清理的无效进程数, 是否实际执行了变更)"""
        
    def get_status(self) -> dict:
        """获取完整状态信息（包含version_mismatch标记）"""
```

### 3.13 Inject（字节码注入模块）

**职责：**

- 通过字节码注入在函数入口和返回点插入hook代码
- 支持访问函数locals变量
- 支持context manager类型的handler（需要locals的handler）
- 支持Python 3.8+（不同版本使用不同的字节码指令）

**类定义：**

```python
def inject_function(
    ori_func: Callable,
    context_hook_funcs: List[Callable]
) -> Callable:
    """注入函数
    
    通过字节码注入在函数入口和返回点插入hook代码。
    支持访问函数locals变量。
    
    Args:
        ori_func: 原始函数
        context_hook_funcs: 上下文管理器函数列表
            每个函数签名应为: def handler(ctx, local_values): yield
    
    Returns:
        注入后的函数
    """
```

### 3.14 MetaState（进程元数据状态管理）

**职责：**

- 提供每个进程独立的元数据存储
- 用于在metrics中提供额外的标签信息
- 支持动态更新和获取，供handlers使用
- 写操作线程安全，读操作无锁（允许读到旧数据）

**类定义：**

```python
class MetaState:
    """进程元数据状态类
    
    每个进程有独立的MetaState实例，存储该进程的元数据信息。
    支持动态更新和获取。
    注意：get() 方法不加锁，允许读取到旧数据以获得更好的性能。
    Python GIL 保证 dict.get() 操作的原子性。
    """
    
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._lock = threading.Lock()  # 仅用于写操作
        
    def get(self, key: str, default: Any = None) -> Any:
        """获取元数据值（无锁，允许读到旧数据）"""
        
    def set(self, key: str, value: Any):
        """设置元数据值"""
        
    def update(self, data: Dict[str, Any]):
        """批量更新元数据"""
        
    def remove(self, key: str) -> bool:
        """删除元数据"""
        
    def clear(self):
        """清空所有元数据"""
        
    def get_all(self) -> Dict[str, Any]:
        """获取所有元数据"""
        
    def has(self, key: str) -> bool:
        """检查是否存在某个键"""
        
    @property
    def dp_rank(self) -> int:
        """获取数据并行rank（便捷属性）"""
        
    @property
    def model_name(self) -> str:
        """获取模型名称（便捷属性）"""


# 全局MetaState实例（单例）
_meta_state_instance: Optional[MetaState] = None

def get_meta_state() -> MetaState:
    """获取全局MetaState实例（单例模式）"""
    
def reset_meta_state():
    """重置全局MetaState实例"""
    
def get_dp_rank() -> int:
    """获取当前进程的dp_rank"""
    
def set_dp_rank(rank: int):
    """设置当前进程的dp_rank"""
    
def get_model_name() -> str:
    """获取当前进程的模型名称"""
    
def set_model_name(name: str):
    """设置当前进程的模型名称"""
```

### 3.15 ExprEval（表达式求值器）

**职责：**

- 支持安全的数学表达式求值
- 可用于配置中的表达式计算
- 支持变量、函数调用、属性访问、下标访问等操作

**类定义：**

```python
class ExprEval:
    """表达式求值器
    
    解析并求值数学表达式，支持以下特性：
    - 基本数学运算: +, -, *, /, //, %, **
    - 变量引用: 从params中获取变量值
    - 函数调用: abs, round, len, max, min等
    - 属性访问: obj.attr
    - 下标访问: list[index], dict[key]
    """
    
    OPERATOR = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
    }
    
    FUNCTION = {
        'abs': abs, 'round': round, 'len': len, 'int': int,
        'float': float, 'str': str, 'max': max, 'min': min,
        'pow': pow, 'sqrt': math.sqrt, 'sin': math.sin,
        'cos': math.cos, 'tan': math.tan, 'log': math.log,
        'exp': math.exp, 'ceil': math.ceil, 'floor': math.floor,
    }
    
    def __init__(self, expression: str):
        """初始化表达式求值器"""
        
    def __call__(self, params: Dict[str, Any], *args, **kwargs) -> Any:
        """求值表达式"""
        
    def register_function(self, name: str, func: Callable):
        """注册自定义函数"""


def evaluate_expression(expression: str, params: Dict[str, Any]) -> Any:
    """便捷函数：求值表达式"""
```

### 3.16 内置Handlers（builtin.py）

**职责：**

- 提供常用的内置handler函数
- 可用于配置中直接使用

**主要函数：**

```python
def default_handler(metrics_config: List[MetricConfig], is_async: bool = False, **kwargs) -> Callable:
    """创建默认handler
    
    根据metrics配置中是否包含expr字段决定是否需要locals：
    - 有expr：需要locals，创建2参数context handler
    - 无expr：不需要locals，创建1参数context handler或wrap handler
    
    支持同步和异步函数。
    """
```

### 3.17 CLI控制工具（cli.py）

**职责：**

- 提供命令行接口，用于控制目标进程中metric收集的开关
- 通过共享内存和SIGUSR1信号与目标进程通信

**使用方式：**

```bash
ms-service-metric on      # 开启metric收集
ms-service-metric off     # 关闭metric收集
ms-service-metric restart # 重启metric收集（重新加载配置）
ms-service-metric status  # 查看状态
```

**环境变量：**

- `MS_SERVICE_METRIC_SHM_PREFIX`: 共享内存和信号量名称前缀（默认: /ms\_service\_metric）
- `MS_SERVICE_METRIC_MAX_PROCS`: 最大进程数（默认: 1000）

## 4. 配置格式

### 4.1 数组格式（与原始配置兼容）

```yaml
- symbol: module.path:ClassName.method_name
  handler: module.path:function_name  # 可选
  min_version: "0.1.0"  # 可选
  max_version: "1.0.0"  # 可选
  lock_patch: false  # 可选，为true时关闭不删除此handler
  metrics:
    - name: metric_name
      type: timer
      expr: "duration"  # 可选，有expr时需要locals
      buckets: [0.1, 0.5, 1.0]  # 可选
      labels:
        - name: label_name
          expr: "expression"

- symbol: module.path:ClassName.method_name
  metrics:  # 无handler时使用默认handler
    - name: metric_name
      type: timer
```

### 4.2 字典格式

```yaml
module.path:ClassName.method_name:
  - handler: module.path:function_name
    metrics:
      - name: metric_name
        type: timer
```

## 5. 关键流程

### 5.1 初始化流程

```text
SymbolHandlerManager.initialize()
  ├── 加载配置 (SymbolConfig.load)
  ├── 注册控制回调 (_on_control_state_change)
  ├── 启动控制监视器 (MetricConfigWatch.start)
  └── 启动模块监视器 (SymbolWatcher.start)
```

### 5.2 模块加载流程

```text
模块导入
  └── SymbolWatchFinder.find_spec
       └── LoaderWrapper.exec_module
            └── SymbolWatcher._notify_module_loaded
                 └── Symbol._on_module_loaded
                      └── Symbol.hook (如果不在批量更新中)
                           └── Symbol._apply_hook
                                ├── 创建/复用 HookChain
                                ├── 构建 final_hook
                                └── 设置 hook 函数
```

### 5.3 控制命令处理流程

```text
收到SIGUSR1信号
  └── MetricConfigWatch._signal_handler
       └── MetricConfigWatch._check_control_state
            └── SymbolHandlerManager._on_control_state_change
                 ├── 关闭: _stop_all_symbols_graceful
                 │    └── Symbol.stop_unlocked (根据lock_patch)
                 ├── 重载配置: SymbolConfig.reload
                 ├── 更新handlers: _update_handlers
                 └── 应用hooks: _apply_all_hooks
```

### 5.4 Hook执行流程

```text
被hook函数被调用
  └── HookChain.__call__
       └── HookChain.exec_chain_closure
            └── HookNode.hook_func (最后一个节点)
                 └── Symbol._build_final_hook 返回的函数
                      ├── context handlers (需要locals) -> 字节码注入
                      ├── context handlers (不需要locals) -> 封装成wrap
                      └── wrap handlers (洋葱模型)
                           └── 原函数
```

### 5.5 Hook 过程时序图

Hook 过程是指从框架适配器启动、用户发送开启命令、到最终目标函数被替换为 Hook 闭包的完整链路。整个过程拆分为三个子流程：**初始化与开关触发**、**Handler 差异更新**、**Hook 注入与函数替换**。

#### 5.5.1 初始化与开关触发

本流程描述从 vLLM 进程启动到用户发送开启命令、Manager 收到回调的完整链路。

- **Adapter** 负责框架适配，初始化时设置版本、Metrics 环境、dp\_rank，然后创建并初始化 Manager
- **Manager** 是核心管理类，初始化时加载配置、注册控制回调、启动 Watcher
- **Control** 是动态开关监视器，通过共享内存+SIGUSR1信号实现进程间通信
- **Watcher** 是模块加载监视器，通过 `sys.meta_path` 拦截模块导入

```mermaid
sequenceDiagram
    participant Adapter as VLLMMetricAdapter
    participant Manager as SymbolHandlerManager
    participant Control as MetricControlWatch
    participant Watcher as SymbolWatcher

    Note over Adapter: vLLM进程启动，entry_points自动触发

    Adapter->>Adapter: initialize()<br/>检测版本/设置Metrics环境/设置dp_rank
    Adapter->>Manager: new SymbolHandlerManager(version)
    Adapter->>Manager: initialize(config_path, default_config_path)<br/>加载配置/注册回调/启动监视器

    Manager->>Control: register_callback(_on_control_state_change)<br/>注册开关状态变化回调
    Manager->>Control: start()<br/>连接共享内存/注册SIGUSR1/添加进程PID
    Manager->>Watcher: start()<br/>将Finder插入sys.meta_path[0]

    Note over Control: 用户执行 ms-service-metric on<br/>CLI写入共享内存+发送SIGUSR1

    Control->>Control: _signal_handler()<br/>收到SIGUSR1信号
    Control->>Control: _check_control_state()<br/>读取共享内存状态和时间戳
    Control->>Manager: _on_control_state_change(True, timestamp)<br/>通知开启或重启
```

#### 5.5.2 Handler 差异更新

本流程描述 Manager 收到开启回调后，如何根据配置差异增删改 Handler，并自动管理 Symbol 生命周期。

- **Manager** 计算新旧 handler 差异，执行增量更新
- **Symbol** 代表一个需要 hook 的符号，管理其 handlers，监听模块加载事件
- **Watcher** 在模块加载完成时通知 Symbol

```mermaid
sequenceDiagram
    participant Manager as SymbolHandlerManager
    participant Symbol as Symbol
    participant Watcher as SymbolWatcher

    Note over Manager: 收到开启回调

    Manager->>Manager: _updating = True<br/>暂停Symbol立即hook
    Manager->>Manager: reload() 配置<br/>关闭期间配置可能已变化
    Manager->>Manager: _update_handlers(config)<br/>计算to_add/to_remove/to_update

    loop 每个新增handler
        Manager->>Manager: _add_handler(handler)<br/>若Symbol不存在则创建
        Manager->>Symbol: new Symbol(symbol_path, watcher, manager)<br/>创建Symbol并注册模块监听
        Symbol->>Watcher: watch_module(module_path, _on_module_loaded)<br/>注册模块加载回调
        alt 模块已加载
            Watcher->>Symbol: _on_module_loaded(event)<br/>立即回调，设置module_loaded
        else 模块未加载
            Note over Symbol: 等待模块加载回调
        end
        Manager->>Symbol: add_handler(handler)<br/>将handler添加到Symbol
    end

    loop 每个移除handler
        Manager->>Symbol: remove_handler(handler_id)
        alt Symbol无剩余handler
            Manager->>Symbol: stop()<br/>停止监听并解绑
        end
    end

    Manager->>Manager: _enabled = True, _updating = False
    Manager->>Manager: _apply_all_hooks()<br/>批量应用所有Symbol的hook
```

#### 5.5.3 Hook 注入与函数替换

本流程描述 Symbol 如何将多个 handler 组合成最终的 hook 函数，并通过 HookChain 和 HookHelper 完成原函数替换。

- **Symbol** 负责 handler 分类、构建 final\_hook
- **Chain** 是 HookChain 双向链表，管理多个 Symbol 对同一函数的 hook
- **Inject** 是字节码注入模块，为 context handler 在函数入口/返回点插入 hook 代码
- **Helper** 是 HookHelper，负责实际的函数替换和恢复

```mermaid
sequenceDiagram
    participant Symbol as Symbol
    participant Chain as HookChain
    participant Inject as Inject(字节码注入)
    participant Helper as HookHelper

    Note over Symbol: _apply_hook() 被调用

    Symbol->>Symbol: 分离wrap_funcs和context_funcs<br/>按handler类型分类

    alt 首次hook
        Symbol->>Chain: get_chain(target)<br/>获取或创建HookChain
        Symbol->>Chain: add_chain_node(insert_at_head=True)<br/>添加节点到链表，首次时触发replace_chain
    end

    Symbol->>Symbol: _build_final_hook()<br/>组合所有handler为最终hook函数

    alt 有context_funcs(需要locals)
        Symbol->>Inject: inject_function(target, context_funcs)<br/>在函数入口插入enter hook<br/>在RETURN_VALUE前插入return hook
        Inject-->>Symbol: injected_func(注入后的函数)
    end

    alt 有wrap_funcs(洋葱模型)
        Symbol->>Symbol: _build_wrap_chain()<br/>从内到外构建wrap调用链<br/>handler1→handler2→原函数→handler2→handler1
    end

    Symbol->>Chain: hook_node.set_hook_func(final_hook)<br/>更新节点的hook函数

    alt 首次hook → replace_chain()
        Chain->>Chain: exec_chain_closure()<br/>生成execute_hook_chain闭包(含异常保护)
        Chain->>Helper: new HookHelper(ori_func, closure)<br/>解析target所在容器和属性名
        Helper->>Helper: replace()<br/>setattr(obj, name, hook_func)<br/>原函数被替换为HookChain闭包
    end

    Note over Symbol: _hook_applied = True<br/>目标函数已被替换
```

### 5.6 运行时 Metric 发送时序图

Hook 完成后，业务代码正常调用被 hook 的目标函数时，控制流进入 HookChain 执行闭包，最终触发 handler 中的 metric 记录逻辑。根据 handler 类型分为两条路径：**Context Handler 路径**和 **Wrap Handler 路径**。

#### 5.6.1 Context Handler 执行流程（字节码注入）

当 Symbol 拥有需要访问函数 locals 的 context handler 时，原函数已被字节码注入修改，在入口和返回点插入了 hook 代码。执行过程：

1. **入口注入点**：创建 `FunctionContext`，设置 `local_values`，依次调用各 handler 的 `__enter__`（前置处理）
2. **原函数体**：正常执行业务逻辑
3. **返回注入点**：设置 `return_value` 和最新的 `local_values`，**逆序**调用各 handler 的 `__exit__`（后置处理）
4. **Metric 记录**：在后置逻辑中计算 duration、求值 expr、调用 `MetricsManager.record_metric()` 写入 Prometheus

```mermaid
sequenceDiagram
    participant Caller as 业务调用方
    participant Inject as 注入函数<br/>(字节码修改后)
    participant Handler as Context Handler<br/>(生成器函数)
    participant MetricsMgr as MetricsManager
    participant Prometheus as Prometheus

    Caller->>Inject: target_func(*args, **kwargs)

    Note over Inject: 入口注入点
    Inject->>Inject: hook_func_when_enter(local_values)<br/>创建FunctionContext/设置locals
    Inject->>Handler: handler(ctx).__enter__()<br/>前置处理(如记录start_time)

    Note over Inject: 原函数体正常执行
    Inject->>Inject: 原始字节码执行

    Note over Inject: 返回注入点(每个RETURN_VALUE前)
    Inject->>Inject: hook_func_when_return(ret, local_values)<br/>设置ctx.return_value和locals
    Inject->>Handler: handler.__exit__()<br/>后置处理：计算duration/求值expr
    Handler->>MetricsMgr: record_metric(name, value, labels)<br/>添加dp/role标签
    MetricsMgr->>Prometheus: observe/inc/set(value)<br/>写入Prometheus指标

    Inject-->>Caller: return_value
```

#### 5.6.2 Wrap Handler 执行流程（洋葱模型）

当 Symbol 只有 wrap handler 时，`final_hook` 指向洋葱模型构建的 wrap 链。每个 wrap handler 签名为 `(ori_func, *args, **kwargs)`，必须显式调用 `ori_func` 传递控制权。执行顺序为外→内→外：

```mermaid
sequenceDiagram
    participant Caller as 业务调用方
    participant Wrap1 as Wrap Handler 1<br/>(外层)
    participant Wrap2 as Wrap Handler 2<br/>(内层)
    participant OriFunc as 原始函数
    participant MetricsMgr as MetricsManager

    Caller->>Wrap1: wrap_handler_1(ori, *args, **kwargs)
    Note over Wrap1: 前置处理

    Wrap1->>Wrap2: wrap_handler_2(ori, *args, **kwargs)
    Note over Wrap2: 前置处理

    Wrap2->>OriFunc: ori_func(*args, **kwargs)<br/>最内层调用原函数
    OriFunc-->>Wrap2: result

    Note over Wrap2: 后置处理：计算metric
    Wrap2->>MetricsMgr: record_metric(name, value, labels)
    Wrap2-->>Wrap1: result

    Note over Wrap1: 后置处理：计算metric
    Wrap1->>MetricsMgr: record_metric(name, value, labels)
    Wrap1-->>Caller: result
```

#### 异常保护机制

`HookChain` 的 `execute_hook_chain` 闭包内置了异常保护，确保业务逻辑不受 hook 异常影响：

- 若 hook 链异常且 `_last_result` 为 `NO_RESULT`（原函数未执行），主动调用 `ori_func` 确保业务继续
- 若 `_last_result` 是异常（原函数本身抛出），重新抛出该异常
- 若 `_last_result` 已有正常值（原函数已成功执行），返回保存的结果

## 6. 线程安全

### 6.1 锁的使用

| 类                    | 锁            | 用途                   |
| -------------------- | ------------ | -------------------- |
| SymbolHandlerManager | `_lock`      | 保护\_enabled和批量操作的原子性 |
| SymbolWatcher        | `_lock`      | 保护回调列表和模块集合          |
| HookChain            | `_lock`      | 保护链表操作               |
| MetricsManager       | 无            | 依赖Prometheus客户端的线程安全 |
| MetaState            | `_lock`      | 保护数据字典               |
| SharedMemoryManager  | `_sem` (信号量) | 保护共享内存访问             |

### 6.2 单例模式

以下类使用单例模式：

- `SymbolWatcher`: 通过`__new__`确保全局唯一实例
- `MetricsManager`: 通过模块级变量`_metrics_manager_instance`实现
- `MetaState`: 通过模块级变量`_meta_state_instance`实现

## 7. 异常处理

### 7.1 自定义异常

```python
ServiceMetricError          # 基础异常类
├── ConfigError             # 配置相关错误
├── HandlerError            # Handler相关错误
├── SymbolError             # Symbol相关错误
├── HookError               # Hook操作相关错误
├── MetricsError            # Metrics相关错误
└── SharedMemoryError       # 共享内存相关错误
```

### 7.2 异常处理策略

1. **配置加载失败**: 记录错误，使用空配置继续
2. **Handler创建失败**: 记录错误，跳过该handler
3. **Hook应用失败**: 记录错误，标记\_hook\_applied=False
4. **Hook执行异常**: 异常保护机制确保原函数被调用
5. **共享内存操作失败**: 抛出SharedMemoryError
