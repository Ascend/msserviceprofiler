# ms_service_metric design document

## 1. Project Overview

### 1.1 Background

ms_service_metric is an independent metric function module extracted from ms_service_profiler/patcher and released as an independent library. Monitors and analyzes performance indicators of services, such as vLLM.

### 1.2 Objectives

 * Function remains the same (unless otherwise noted)
 * Clear code structure and SOD
 * Performance first, simplifying the internal logic of the hook function
 * Dynamic switch (shared memory + SIGUSR1 signal)
 * External interfaces and configurations are compatible.

### 1.3 Relationship with the original project

| Features               | ms_service_profiler | ms_service_metric      |
| ---------------------- | ------------------- | ---------------------- |
| Profiling              | Support             | ?? Not supported       |
| Metrics                | Support             | Support                |
| Dynamic switch         | C++ callback        | Shared memory + signal |
| Independent deployment | Depends on C++.     | Pure Python            |

## 2. Project structure

```text
ms_service_metric/                           #Project root directory
├── pyproject.toml                           #Project Configuration
├── README.md                                #Project Description
├── DESIGN.md                                #Design Document
├── ms_service_metric/                       #Main package (consistent with the project name)
│   ├── __init__.py                          #Package initialization
│   ├── __main__.py                          #Command line entry
│   ├── core/                                #Core module
│   │   ├── __init__.py
│   │   ├── symbol_handler_manager.py        #Core class of SymbolHandlerManager.
│   │   ├── symbol.py                        #Symbol Class
│   │   ├── handler.py                       #Handler abstract base class and metricHandler implementation
│   │   ├── config/                          #Configuring Related Modules
│   │   │   ├── __init__.py
│   │   │   ├── symbol_config.py             #SymbolConfig configuration class.
│   │   │   └── metric_control_watch.py      #MetricConfigWatch Class
│   │   ├── hook/                            #Hook-related modules
│   │   │   ├── __init__.py
│   │   │   ├── hook_chain.py                #HookChain class (multi-hook management in a bidirectional linked list)
│   │   │   ├── hook_helper.py               #HookHelper class (function replacement aid)
│   │   │   └── inject.py                    #bytecode injection
│   │   └── module/                          #Module Related Modules
│   │       ├── __init__.py
│   │       └── symbol_watcher.py            #SymbolWatcher class (singleton)
│   ├── handlers/                            #Built-in handlers
│   │   ├── __init__.py
│   │   └── builtin.py                       #Built-in handler implementation (such as default_handler)
│   ├── adapters/                            #Frame adapter
│   │   ├── __init__.py
│   │   ├── vllm/                            #vLLM adaptation
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py                   #vLLM Adapter Inlet
│   │   │   ├── metrics_init.py              #Initializing vLLM metrics
│   │   │   ├── handlers/                    #vLLM dedicated handlers directory
│   │   │   │   ├── __init__.py
│   │   │   │   ├── metric_handlers.py       #metric handlers
│   │   │   │   └── meta_handlers.py         #meta handlers
│   │   │   └── config/
│   │   │       ├── default.yaml             #Default vLLM configuration
│   │   │       └── v1_metrics.yaml          #vLLM V1 metrics configuration
│   │   └── sglang/                          #SGLang adaptation
│   │       ├── __init__.py
│   │       ├── adapter.py                   #SGLang adapter entrance
│   │       └── config/
│   │           └── default.yaml             #SGLang Default Configuration
│   ├── metrics/                             #Metrics Related Modules
│   │   ├── __init__.py
│   │   ├── metrics_manager.py               #MetricsManager Class
│   │   └── meta_state.py                    #Metadata Status Management
│   ├── utils/                               #Tool module
│   │   ├── __init__.py
│   │   ├── expr_eval.py                     #Expression Evaluation (ExprEval)
│   │   ├── exceptions.py                    #Exception definition
│   │   ├── logger.py                        #Log tool
│   │   ├── function_context.py              #Function Context
│   │   └── shm_manager.py                   #Shared memory manager
│   └── control/                             #control end program
│       ├── __init__.py
│       └── cli.py                           #Command Line Control Tool (ms-service-metric)
└── tests/                                   #Test Directory
    ├── __init__.py
    ├── conftest.py                          #pytest configuration and fixture
    ├── test_config_compatibility.py         #Configuration compatibility test
    ├── test_design.md                       #Test Design Document
    └── unit/                                #Unit test
        ├── __init__.py
        ├── test_exceptions.py               #Abnormal test
        ├── test_expr_eval.py                #Expression Evaluation Test
        ├── test_handler.py                  #Handler test
        ├── test_hook_chain.py               #HookChain test
        ├── test_logger.py                   #Log tool test
        ├── test_metrics_manager.py          #MetricsManager test
        ├── test_symbol_config.py            #SymbolConfig test
        ├── test_symbol_hook.py              #Symbol hook test
        ├── test_symbol_watcher.py           #SymbolWatcher test
        └── test_utils.py                    #Tool Function Test
```

## 3. Core design

### 3.1 SymbolHandlerManager (Core Management Class)

**Responsibilities:**

 * Managing all handlers and symbols
 * Dynamically load and unload handlers and symbols based on the configuration.
 * A core class that connects all the other classes together.

**Key Design:**

1. Handler-based addition and deletion, and automatic processing of symbol objects
2. Simplifying the use of locks (Protects only atomicity of _enabled and bulk operations)
3. Batch apply_hook, instead of reapplying every handler change.
4. Pauses the hook/unhook operation for all symbols when the processing is enabled. After the operation is complete, the operation is executed uniformly.
5. Graceful stop is supported. The lock_patch attribute determines whether to retain the handler.

**Class definition:**

```python
class SymbolHandlerManager:
    """Core management class for Symbol and Handler ""
    
    def __init__(self):
        self._config = SymbolConfig()
        self._watcher = SymbolWatcher() # Singleton
        self._metrics_manager = get_metrics_manager() # Single Instance
        self._control_watch = MetricConfigWatch()
        self._symbols: Dict[str, Symbol] = {}
        self._handlers: Dict[str, Handler] = {}
        self._enabled = False
        self._lock = threading.Lock()
        self._updating = False
        
    def initialize(self, config_path: Optional[str] = None, default_config_path: Optional[str] = None):
        Initialize all components."""
        
    def shutdown(self):
        """Close Manager "" ""
        
    def _on_control_state_change(self, is_start: bool, timestamp: int):
        Callback for controlling status changes."""
        
    def _update_handlers(self, config: Dict[str, List[Dict]]):
        """Update handlers based on configuration"""
        
    def _add_handler(self, handler: Handler):
        Add handlers to automatically manage the symbol life cycle."""
        
    def _remove_handler(self, handler_id: str):
        """Remove the handler. If the symbol does not have handlers, the handler is automatically deleted.
        
    def _update_handler(self, handler: Handler):
        Update handler (direct replacement)"""
        
    def _apply_all_hooks(self):
        """Batch apply hooks for all symbols"""
        
    def _stop_all_symbols(self):
        Stop all symbols."""
        
    def _stop_all_symbols_graceful(self):
        """Gracefully stop all symbols (support lock_patch) "" ""
        
    def is_updating(self) -> bool:
        Check whether the batch update is in progress."""
        
    def is_enabled(self) -> bool:
        """Check if "" is enabled
```

**Control status processing logic:**

```text
关闭命令 (is_start=False):
  - 如果当前已启用，根据lock_patch属性决定是否保留handler
  - 如果当前已禁用，无操作

开启命令 (is_start=True):
  - 如果当前已启用且时间戳相同：重复命令，无操作
  - 如果当前已启用且时间戳不同：重启，关闭所有→重载配置→重新应用
  - 如果当前已禁用：普通开启，重载配置→应用
```

### 3.2 Symbol (Symbol)

**Responsibilities:**

 * Indicates a symbol that needs to be hooked.
 * Manage its handlers (repeated handlers are not allowed).
 * Directly listen to module loading events (not forwarded by SymbolHandlerManager)
 * Determine whether to perform hook/unhook based on the Manager status.
 * Graceful stop (lock_patch function)

**Class definition:**

```python
class Symbol:
    """Symbol class, representing a symbol that needs to be hooked.
    
    Use HookChain to manage multiple symbols to form a call chain for hooks of the same function.
    Nodes can be inserted into the header of a linked list (insert_at_head=True).
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
        self._hook_node: Optional[HookNode] = None  #HookChain node
        self._hook_chain: Optional[HookChain] = None  #HookChain Instance
        self._target: Optional[Any] = None  #Cache the imported target object.
        
    @property
    def symbol_path(self) -> str:
        """Full path of symbol ""
        
    @property
    def module_path(self) -> str:
        """ "Module Path"""
        
    @property
    def hook_applied(self) -> bool:
        """Has hook been applied"""
        
    def add_handler(self, handler: Handler):
        Add handlers. (Repeat handlers are not allowed.)"""
        
    def remove_handler(self, handler_id: str):
        """Remove handler"""
        
    def update_handler(self, handler: Handler):
        Update handler (direct replacement)"""
        
    def is_empty(self) -> bool:
        """Check for no handlers"""
        
    def hook(self):
        Application hook (external interface)"""
        
    def _apply_hook(self):
        """Internal Core Method: Apply or Update hook"""
        
    def unhook(self):
        Restore the original function."""
        
    def stop(self):
        """Stop listening and unbind ""
        
    def stop_unlocked(self) -> Tuple[List[str], List[str]]:
        """ "Stop unlocked handlers, return (ids deleted, ids retained)"""
        
    def _build_final_hook(
        self,
        target: Any,
        ori_wrap: Any,
        wrap_funcs: List[Callable],
        context_funcs: List[Callable],
        chain: HookChain
    ) -> Callable:
        """Build the final hook function "" ""
        
    def _build_wrap_chain(self, target: Any, ori_wrap: Any, wrap_funcs: List[Callable]) -> Callable:
        Build a wrap function chain (onion model)"""
        
    def _build_sync_wrap_chain(self, ori_wrap: Any, wrap_funcs: List[Callable]) -> Callable:
        """Build a synchronous wrap function chain "" ""
        
    def _build_async_wrap_chain(self, ori_wrap: Any, wrap_funcs: List[Callable]) -> Callable:
        Build a chain of asynchronous wrap functions."""
        
    def _build_context_wrap_handler(self, wrap_chain: Any, context_funcs: List[Callable]) -> Callable:
        """Encapsulates context handlers into a wrap handler"""
        
    def _build_hook_with_injection(
        self,
        target: Any,
        context_funcs: List[Callable],
        chain: HookChain,
    ) -> Callable:
        "" "Build hooks with bytecode injection"""
```

**Handler merge policy:**

```text
1. 分离wrap handlers和context handlers
2. 执行顺序：
   a. context handlers（需要locals）-> 字节码注入
   b. context handlers（不需要locals）-> 封装成wrap handler
   c. wrap handlers -> 直接包装（洋葱模型）

3. 示例：
   原函数 -> injection(need_locals_handlers) -> context_wrap(no_need_locals_handlers) -> wrap_chain
```

**Onion model example:**

```text
配置顺序: handler1, handler2, handler3
执行顺序: handler1 -> handler2 -> handler3 -> 原函数 -> handler3 -> handler2 -> handler1

wrap_chain构建:
  chain = target  #The innermost layer is the primitive function.
  for wrap_func in reversed(wrap_funcs):  #Reverse Traversal
      chain = create_layer(wrap_func, chain)
```

### 3.3 Handler (handler abstract base class)

**Responsibilities:**

 * Defines the basic interface (abstract base class) of the Handler.
 * All custom Handlers should inherit this class.

**Class definition:**

```python
class Handler(ABC):
    """Handler abstract base class: defines the basic interface required by Symbol ""
    
    @property
    @abstractmethod
    def id(self) -> str:
        Obtain the unique identifier of the handler."""
        pass
    
    @abstractmethod
    def get_hook_func(self, target: Callable) -> tuple[HandlerType, Callable]:
        """Get hook function, return (handler type, hook function) "" ""
        pass
    
    @property
    def name(self) -> str:
        Obtain the handler name."""
        return self.id
    
    def __hash__(self) -> int:
        """Hash is supported for set and dict"""
        return hash(self.id)
    
    def __eq__(self, other: object) -> bool:
        Supports equality comparison."""
        if not isinstance(other, Handler):
            return False
        return self.id == other.id
```

### 3.4 MetricHandler (Implementation of Handler)

**Responsibilities:**

 * Loads built-in handlers or user-defined handlers.
 * Categorize hook_func into wrap_func and context_funcs
 * Automatically detects handler types (through function signature).
 * Provide a unique handler_id (generated from the full path of hook_func)
 * Supporting metrics configuration
 * Supports the lock_patch attribute (not deleted when closed).

**Class definition:**

```python
class MetricHandler(Handler):
    """MetricHandler class: Handler implementation that supports metrics configuration ""
    
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
        
        # Categorize hook_func and determine handler_type.
        handler_type, hook_func = self._classify_hook_func(hook_func)
        if handler_type != None:
            self._handler_type = handler_type
            self._hook_func = hook_func
        else:
            self._handler_type = None
        
        # Generate a unique ID.
        self._id = self._generate_id()
        
    @property
    def id(self) -> str:
        Obtain the handler ID."""
        
    @property
    def name(self) -> str:
        """Obtain the handler name ""
        
    @property
    def symbol_path(self) -> str:
        Obtain the symbol path."""
        
    @property
    def handler_type(self) -> HandlerType:
        """Obtain the handler type ""
        
    @property
    def lock_patch(self) -> bool:
        Whether to lock the patch (not deleted when the patch is closed)"""
        
    def get_hook_func(self, target: Callable) -> tuple[HandlerType, Callable]:
        """Get hook function "" ""
        
    def equals(self, other: 'MetricHandler') -> bool:
        Check whether the two handlers are the same (considering configuration changes)."""
        
    def _classify_hook_func(self, func) -> HandlerType:
        """Categorize hook_func as wrap_func or context_func"""
        
    def _create_context_manager(self, func: Callable) -> Optional[Callable]:
        "" "trying to convert a function to a context manager"""
        
    @classmethod
    def from_config(cls, config: Dict, symbol_path: str) -> 'MetricHandler':
        """Creating a MetricHandler instance from a configuration "" ""
        
    @staticmethod
    def _import_handler(handler_path: str) -> Callable:
        Import handler functions."""
        
    @staticmethod
    def _parse_metrics_config(metrics_config: list) -> List[MetricConfig]:
        """Parse metrics configuration ""
```

**Handler classification rules:**

```text
- 生成器函数 -> context_func, 返回 HandlerType.CONTEXT
  - 1个参数(ctx): 不需要locals
  - 2个参数(ctx, local_values): 需要locals
- ContextManager子类 -> context_func, 返回 HandlerType.CONTEXT
- 其他 -> wrap_func, 返回 HandlerType.WRAP
```

**Handler function signature:**

```python
#Wrap Handler
def wrap_handler(ori_func, *args, **kwargs):
    #Preprocessing
    result = ori_func(*args, **kwargs)  #The original function must be explicitly called.
    #Post-processing
    return result

#Context Handler (locals not required, one parameter)
def simple_context_handler(ctx):
    #ctx: FunctionContext object
    #Preprocessing
    yield  #The original function is executed here.
    #Postprocessing (accessible to ctx.return_value)

#Context Handler (locals required, 2 parameters)
def advanced_context_handler(ctx, local_values):
    #ctx: FunctionContext object
    #local_values: locals dictionary of the function
    #Preprocessing
    yield  #The original function is executed here.
    #Postprocessing (can access ctx.return_value and local_values)
```

### 3.5 FunctionContext (function context class)

**Responsibilities:**

 * Stores the function execution context (local_values, return_value).
 * Provides a convenient way to access local_values

**Class definition:**

```python
class FunctionContext:
    """Function Execution Context ""
    
    def __init__(self):
        self._local_values: Optional[Dict[str, Any]] = None
        self.return_value: Any = None
    
    @property
    def local_values(self) -> Optional[Dict[str, Any]]:
        Obtain the locals dictionary of the function."""
        
    @local_values.setter
    def local_values(self, value: Optional[Dict[str, Any]]):
        """Set the locals dictionary for the function "" ""
        
    def get(self, key: str, default: Any = None) -> Any:
        Obtain the value from local_values and simulate the get method of dict."""
        
    def __getitem__(self, key: str) -> Any:
        """Support for accessing local_values""" through the ctx['var'] syntax
        
    def __contains__(self, key: str) -> bool:
        Supports the'var'in ctx syntax to check whether a variable exists in local_values."""
```

**Example:**

```python
#Used in the context handler
def my_handler(ctx, local_values):
    #Preprocessing
    x = ctx.get('x', 0)  #Obtains the local variable x. The default value is 0.
    y = ctx['y']  #Use dictionary syntax directly
    if 'z' in ctx:  #Check whether the variable exists.
        z = ctx.get('z')
    
    yield  #Original function execution
    
    #Post-processing
    result = ctx.return_value
```

### 3.6 HookChain (Hook Chain Management)

**Responsibilities:**

 * Using a Bidirectional Linked List to Manage Multiple Hook Functions
 * Supports dynamic addition, deletion, and invoking of hooks.
 * Nodes can be inserted at the head or tail of a linked list.
 * Create a node for each symbol. Multiple symbols can form a call chain.
 * An exception protection mechanism is provided.

**Class definition:**

```python
class HookNode:
    """Hook linked list node ""
    
    def __init__ (self, chain: 'HookChain', prev_node: Optional['HookNode'] = None):
        self.chain = chain
        The self.hook_func = self.call_prev # invokes the previous one by default.
        self.prev_node = prev_node
        self.next_node: Optional[HookNode] = None
    
    @property
    def ori_wrap(self):
        Returns the wrapper for the next function in the call chain."""
        return self.call_prev
    
    def set_hook_func(self, hook_func: Callable):
        """Set the hook function of the current node "" ""
        self.hook_func = hook_func
    
    def call_prev(self, *args, **kwargs):
        Call the previous hook function (onion model inward)"""
        if self.prev_node:
            return self.prev_node.hook_func(*args, **kwargs)
        else:
            return self.chain._call_ori_func(*args, **kwargs)
    
    def remove(self) -> bool:
        """Remove the current node from the linked list.
        return self.chain.remove_chain_node(self)
    
    def recover(self):
        Restore the original function (alias remove)."""
        return self.remove()


class HookChain:
    """Hook Linked List Manager "" ""

    def __init__(self, ori_func: Callable):
        self.ori_func = ori_func
        self.head: Optional[HookNode] = None
        self.tail: Optional[HookNode] = None
        The self._nodes: Dict[int, HookNode] = {} # uses id (node) as the key dictionary.
        self._lock = threading.Lock()
        self._helper = None
        self._last_result = NO_RESULT # Save the result of the last call
        
    def set_last_result(self, result):
        """ "Sets the result of the last call."""
        
    def _call_ori_func(self, *args, **kwargs):
        """Call the original function and save the result ""
        
    def add_chain_node(self, insert_at_head: bool = False) -> HookNode:
        Add a node and return HookNode.
        
        Args:
            insert_at_head: If the value is True, insert to the header of the linked list. Otherwise insert to tail (default)
        """
        
    def remove_chain_node(self, node: HookNode) -> bool:
        """Delete node ""
        
    def get_chain_info(self) -> dict[str, Any]:
        Obtain the debugging information about the chain."""
        
    def print_chain_info(self, action: str = "Info"):
        """Print the debugging information of the chain ""
        
    def exec_chain_closure(self):
        Return the closure function that executes the hook chain, with exception protection mechanism."""
        
    def __call__(self, *args, **kwargs):
        """Last node of the call chain list ""


def get_chain(ori_func: Callable) -> HookChain:
    Obtain or create HookChain (public function, cached)"""
```

**How to use:**

```python
#Using hook_chain in the Symbol class
from ms_service_metric.core.hook.hook_chain import get_chain

class Symbol:
    def hook(self):
        #1. Obtain or create a chain.
        self._hook_chain = get_chain(self._target)
        
        #2. Add a node to the header.
        self._hook_node = self._hook_chain.add_chain_node(insert_at_head=True)
        
        #3. Construct the hook function (use ori_wrap as the next function in the call chain).
        final_hook = self._build_final_hook(
            self._hook_chain.ori_func,
            self._hook_node.ori_wrap,
            wrap_funcs, 
            context_funcs, 
            self._hook_chain
        )
        
        #4. Set the hook function.
        self._hook_node.set_hook_func(final_hook)
    
    def unhook(self):
        #Restore the original function by removing the node.
        if self._hook_node:
            self._hook_node.remove()
            self._hook_node = None
```

**Exception protection mechanism:**

```python
def execute_hook_chain(*args, **kwargs):
    """Execute hook chain with exception protection mechanism.
    
    Protection Policy:
    1. Reset _last_result to NO_RESULT.
    2. Run the hook chain.
    3. If an exception occurs during the execution:
       - If _last_result is still NO_RESULT (indicating that ori_func has not been invoked), call ori_func and return.
       - If _last_result is an exception (indicating that the exception is thrown by ori_func), throw it again.
       - If the value of _last_result is normal (indicating that ori_func has been invoked), the saved result is returned.
    4. If the execution is complete, the hook chain result is returned.
    """
```

### 3.7 HookHelper

**Responsibilities:**

 * Replaces and restores specific functions.
 * Saves original functions and supports restoration.
 * Parse the target object (supporting function, method, and class attributes).

**Class definition:**

```python
class HookHelper:
    """Hook auxiliary class
    
    Replaces and restores functions.
    Only simple function replacement is responsible. Complex handler combination logic is processed by the Symbol class.
    """
    
    def __init__(self, target: Any, hook_func: Callable):
        self._target = target
        self._hook_func = hook_func
        self._original_func: Optional[Callable] = None
        self._replaced = False
        self._target_obj, self._target_name = self._parse_target(target)
        
    def _parse_target(self, target: Any) -> tuple:
        """Parse the target object, determine the container and attribute name ""
        
    def replace(self):
        Apply the hook to replace the target function."""
        
    def recover(self):
        """Restore the original function ""
        
    @property
    def is_replaced(self) -> bool:
        """ "Whether hook has been applied"""
        
    @property
    def original_func(self) -> Optional[Callable]:
        """Original function ""
```

### 3.8 MetricsManager (Prometheus Metric Manager)

**Responsibilities:**

 * Manage registration, recording, and query of all Prometheus metrics
 * Supports multiple indicator types, including Histogram, Counter, Gauge, and Summary.
 * Provides the tag management and expression evaluation functions.
 * Collects indicators in the multi-process environment.
 * Automatically add DP tags.

**Class definition:**

```python
class MetricType(str, Enum):
    """Counter type enumeration ""
    TIMER = "timer" #Time consumption indicator (implemented by using Histogram)
    HISTOPGA = "histogram" # Histogram
    COUNTER = "counter" #Counter
    GAUGE = "gauge" #Dashboard
    SUMMARY = "summary" #Summary


@dataclass
class MetricConfig:
    Indicator configuration data structure"""
    name: str
    type: MetricType
    expr: str = ""
    buckets: Optional[List[float]] = None
    labels: Optional[Dict[str, str]] = None


class MetricsManager:
    """Prometheus Metric Manager "" ""
    
    def __init__(self):
        self._metrics: Dict[str, Any] = {}
        self._label_definitions: Dict[str, List[Dict[str, str]]] = {}
        self._registry: Optional[CollectorRegistry] = None
        self._metric_prefix: str = ""
        
    @property
    def metric_prefix(self) -> str:
        Obtain the index name prefix."""
        
    @metric_prefix.setter
    def metric_prefix(self, prefix: str):
        """Set the index name prefix ""
        
    def _get_appropriate_registry(self) -> CollectorRegistry:
        Obtain the appropriate Prometheus registry (supporting multiple processes)"""
        
    def _generate_custom_buckets(self, max_end: float = 1000, max_precision: int = 6) -> List[float]:
        """Generate custom histogram bucket "" ""
        
    def _add_prefix(self, metric_name: str) -> str:
        Add a prefix to the indicator name."""
        
    def _add_dp_label_name(self, label_names: Optional[List[str]] = None) -> List[str]:
        """Add the default dp domain label name for the metric ""
        
    def _add_dp_label_value(self, labels: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        Add the default dp domain label value for the metric."""
        
    def _sanitize_metric_name(self, name: str) -> str:
        """Clear the metric name and ensure that it complies with the Prometheus specification.
        
    def register_metric(
        self,
        metric_config: MetricConfig,
        label_names: Optional[List[str]] = None
    ) -> Optional[Any]:
        Registering Indicators"""
        
    def add_label_definition(self, metric_name: str, label_name: str, expr: str):
        """Add label definition ""
        
    def get_label_definitions(self) -> Dict[str, List[Dict[str, str]]]:
        Obtain the label definition dictionary."""
        
    def record_metric(
        self,
        metric_name: str,
        value: Union[int, float],
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record the indicator value ""
        
    def get_registry(self) -> Optional[CollectorRegistry]:
        Obtain the registry used."""
        
    def get_all_metrics(self) -> Dict[str, Any]:
        """Obtain all created metrics ""
        
    def get_or_create_metric(
        self,
        metric_name: str,
        label_names: Optional[List[str]] = None,
        metric_type: MetricType = MetricType.TIMER,
        buckets: Optional[List[float]] = None
    ) -> "MetricsManager":
        Obtain or create metrics."""
        
    def clear_metrics(self):
        """Clear All Indicators ""


# Global MetricsManager instance (singleton)
_metrics_manager_instance: Optional[MetricsManager] = None

def get_metrics_manager() -> MetricsManager:
    Obtain the global MetricsManager instance."""
```

### 3.9 SymbolWatcher (Module Load Monitor, Single Instance)

**Responsibilities:**

 * Listening for Import Events of the Python Module
 * Callback for notifying the registration when the module is loaded
 * Manage callback by module to ensure that the confirmed module is loaded during callback.
 * Singleton mode, ensuring that only one monitor instance exists globally.

**Class definition:**

```python
class ModuleEventType(Enum):
    """Module Event Type ""
    LOADED = "loaded"
    UNLOADED = "unloaded"


class ModuleEvent:
    Module Event"""
    
    def __init__(self, module_name: str, event_type: ModuleEventType, module=None):
        self.module_name = module_name
        self.type = event_type
        self.module = module


class SymbolWatchFinder(importlib.abc.MetaPathFinder):
    """Module Import Listener
    
    Listen for module import events by inserting into sys.meta_path.
    """
    
    def __init__(self, watcher: "SymbolWatcher"):
        self._watcher = watcher
        self._target_modules: Set[str] = set()
        
    def add_target_module(self, module_name: str):
        """Add target module "" ""
        
    def remove_target_module(self, module_name: str):
        Remove the target module."""
        
    def find_spec(self, fullname: str, path, target=None):
        """Find the module spec, wrap the loader to trigger the callback ""


class SymbolWatcher:
    """Symbol Monitor (Single Instance)
    
    Multiple instantiations return the same object, ensuring that there is only one monitor instance globally.
    """
    
    _instance: Optional["SymbolWatcher"] = None
    _initialized: bool = False
    _singleton_lock: threading.Lock = threading.Lock()
    
    def __new__(cls) -> "SymbolWatcher":
        """Make sure there is only one instance ""
        
    def __init__(self):
        Initialization (valid only for the first call)"""
        
    def watch(self, callback: Callable[[str], None]):
        """Listen to the loading events of all modules (global callback) ""
        
    def unwatch(self, callback: Callable[[str], None]):
        Cancel listening to loading events of all modules."""
        
    def has_global_callbacks(self) -> bool:
        """Check if there is a registered global callback "" ""
        
    def watch_module(self, module_name: str, callback: Callable[[ModuleEvent], None]):
        Listen to the events of the specified module."""
        
    def unwatch_module(self, module_name: str, callback: Callable[[ModuleEvent], None]):
        """Cancel listening to the event of the specified module ""
        
    def start(self):
        Start the monitor (inserted into sys.meta_path)"""
        
    def uninstall(self):
        """Uninstall the monitor (removed from sys.meta_path) "" ""
        
    def stop(self):
        Stop the monitor."""
        
    def is_module_loaded(self, module_name: str) -> bool:
        """Check if the module is loaded
        
    def _notify_module_loaded(self, module_name: str):
        """Notify the module to load the event."""
```

### 3.10 SymbolConfig (Configuration Management)

**Responsibilities:**

 * Read the YAML configuration file.
 * Read user configuration, default configuration
 * Configuration combination and automatic default value assignment
 * Two configuration formats are supported: array format and dictionary format.

**Class definition:**

```python
class SymbolConfig:
    """Symbol configuration management class ""
    
    ENV_CONFIG_PATH = "MS_SERVICE_METRIC_CONFIG_PATH"
    
    def __init__(self, 
                 user_config_path: Optional[str] = None,
                 default_config_path: Optional[str] = None):
        
    def load(self, config_path: Optional[str] = None, default_config_path: Optional[str] = None) -> Dict[str, List[dict]]:
        Load and merge the configuration."""
        
    def reload(self) -> Dict[str, List[dict]]:
        """Reload configuration ""
        
    def _load_default_config(self) -> dict:
        Load the default configuration."""
        
    def _load_user_config(self) -> dict:
        """Load User Configuration ""
        
    def _load_yaml(self, path: str) -> dict:
        Load the YAML file. The array format and dictionary format are supported."""
        
    def _convert_array_config(self, config_list: list) -> dict:
        """Convert configuration in array format to dictionary format ""
        
    def _merge_configs(self, default: dict, user: dict) -> dict:
        Merge configuration (user configuration is appended to the default configuration)"""
        
    def _fill_defaults(self):
        """Populate the default value "" for the configuration
        
    def get_config(self) -> Dict[str, List[dict]]:
        Obtain the current configuration."""
        
    def get_symbol_config(self, symbol_path: str) -> List[dict]:
        """Obtain the configuration of a specified symbol ""
```

### 3.11 MetricConfigWatch

**Responsibilities:**

 * Use the posix_ipc shared memory and SIGUSR1 signal to implement inter-process communication.
 * Configuring shared memory and semaphore name prefixes for environment variables
 * Simplified design: Only the start flag and timestamp are required.
    
     * start=False: disables metric collection.
     * start=True: indicates that metric collection is enabled.
     * Timestamp change indicates that a restart (configuration reload) is required.

**Class definition:**

```python
class MetricConfigWatch:
    """Metric Configuration Monitor
    
    The posix_ipc shared memory and SIGUSR1 signal are used to implement dynamic switch control.
    Multiple processes can be monitored simultaneously. The control end can send signals to all processes at the same time.
    """
    
    STATE_OFF = 0
    STATE_ON = 1
    
    def __init__(self, shm_prefix: Optional[str] = None, max_procs: Optional[int] = None):
        
    def register_callback(self, callback: Callable[[bool, int], None]):
        """Registration status change callback ""
        
    def unregister_callback(self, callback: Callable[[bool, int], None]):
        Callback for deregistration status change"""
        
    def start(self):
        """Start the monitor (invoked in the controlled process) "" ""
        
    def stop(self):
        Stop the monitor."""
        
    def _register_signal_handler(self):
        """Register SIGUSR1 signal processing "" ""
        
    def _signal_handler(self, signum, frame):
        """SIGUSR1 signal processing function"""
        
    def _check_control_state(self):
        """Check control status "" ""
        
    def get_last_timestamp(self) -> int:
        Obtain the timestamp of the last processing."""
        
    def is_enabled(self) -> bool:
        """Check whether the current state is enabled "" ""
        
    @classmethod
    def set_control_state(cls, is_start: bool, shm_prefix: Optional[str] = None, force: bool = False):
        Set the control status (invoked by the control end)."""
```

### 3.12 SharedMemoryManager

**Responsibilities:**

 * Managing shared memory operations of the ms_service_metric table in a unified manner
 * Memory layout definition (supporting version compatibility)
 * Shared memory creation, connection, disconnection, and release
 * Semaphore operation
 * Data read/write (status, timestamp, and process list)
 * Process management (adding, clearing, and verifying)
 * Send control commands and signals
 * Version compatibility processing (read as much as can be read)

**Memory layout design:**

All offsets are relative to the start position of the shared memory and are compatible with the following versions:

```text
[魔数:4][版本:4][头部长度:4][状态:4][时间戳:4][进程列表偏移:4][头部结束标记:4][进程列表长度:4][进程列表游标:4][PID1:4][PID2:4]...[PIDn:4]
```

**Field description (each int32):**

 * Magic Number (0x4D534D54 = "MSMT")
 * Version Number
 * Header length (Total bytes from start to end marker)
 * Status (STATE_OFF=0/STATE_ON=1)
 * Timestamp
 * Process list offset (relative to the start position of the shared memory)
 * Header end mark (0xDEADBEEF)
 * Process List Length (Circular List Length)
 * Process list cursor (current position of the loop list)
 * Process ID array...

**Version compatibility policy:**

 * Verify memory format using magic numbers and end-of-head tags
 * Flag when the version does not match`_version_mismatch`but try to read available fields
 * Passed through`_is_field_available(offset)`Check whether the field is within the valid header length range.
 * Return an exception value (PROC_LEN_INVALID = -1) when the process list is unavailable.

**Class definition:**

```python
class SharedMemoryLayout:
    """Shared Memory Layout Definition (Version Compatibility Design) "" ""
    
    # Header field offset (relative to the start position of the shared memory)
    OFFSET_MAGIC = 0 #Magic Number (int32)
    OFFSET_VERSION = 4 #Version number (int32)
    OFFSET_HEADER_LEN = 8 #Header length (int32)
    OFFSET_STATE = 12 #State (int32)
    OFFSET_TIMESTAMP = 16 #Timestamp (int32)
    OFFSET_PROC_OFFSET = 20 #process list offset (int32)
    OFFSET_HEADER_END = 24 # Header end marker (int32)
    
    HEADER_SIZE = 28 # Total header size.
    
    #Relative offset of the process list field (relative to the start position of the process list).
    PROC_LIST_REL_OFFSET_LEN = 0 # Process List Length Field Offset
    PROC_LIST_REL_OFFSET_CURSOR = 4 # Process List Cursor Field Relative Offset
    PROC_LIST_REL_OFFSET_DATA = 8 # Process List Data Start Offset
    PROC_LIST_HEADER_SIZE = 8 #Size of the process list header (length + cursor)
    PROC_ENTRY_SIZE = 4 #Number of bytes occupied by each process ID.


class SharedMemoryManager:
    Shared Memory Manager"""
    
    #Abnormal value constant
    PROC_OFFSET_INVALID = -1  #Abnormal value of the process list offset.
    PROC_LEN_INVALID = -1     #Abnormal process list length
    
    def __init__(self, shm_prefix: Optional[str] = None, max_procs: Optional[int] = None):
        """Initializing Shared Memory Manager "" ""
        
    def connect(self, create: bool = True) -> bool:
        Connect to shared memory
        
        When you connect to an existing shared memory, the actual size is automatically fetched and the memory map is adjusted.
        If the sizes do not match, a warning is logged but the actual size continues to be used.
        """
        
    def disconnect(self):
        """Disconnect "" ""
        
    def destroy(self):
        Destroy the shared memory and semaphore (completely deleted)"""
        
    def lock(self):
        """Get semaphore lock (block) "" ""
        
    def unlock(self):
        Release the semaphore lock."""
        
    def semaphore_lock(self):
        """Get semaphore lock (context manager) "" ""
        
    def read_int(self, offset: int) -> int:
        Read int32 from shared memory (unsigned)"""
        
    def write_int(self, offset: int, value: int):
        """Write int32 (unsigned) to shared memory "" ""
        
    def _is_field_available(self, offset: int) -> bool:
        Check whether the field with the specified offset is available (within the valid header length range)"""
        
    def get_state(self) -> int:
        """Gets the current state (STATE_OFF is returned if the field is not available) "" ""
        
    def set_state(self, state: int):
        """ "Setting Status"""
        
    def get_timestamp(self) -> int:
        """Obtain the timestamp (return 0 if the field is not available) "" ""
        
    def set_timestamp(self, timestamp: int):
        Set the timestamp."""
        
    def update_state_and_timestamp(self, state: int):
        """Update both status and timestamp ""
        
    def _get_proc_offset(self) -> int:
        Obtain the process list offset. If the process list is unavailable, PROC_OFFSET_INVALID is returned."""
        
    def get_proc_len(self) -> int:
        """Obtains the process list length (PROC_LEN_INVALID is returned when the process list is unavailable) "" ""
        
    def get_proc_cursor(self) -> int:
        Obtain the cursor of the process list. If the cursor is unavailable, 0 is returned."""
        
    def get_all_procs(self) -> List[int]:
        """Obtain all valid process IDs (deduplicated, empty list returned when unavailable) "" ""
        
    def add_process(self, pid: Optional[int] = None) -> int:
        "" "Add process to list (return - 1 if unavailable)"""
        
    def add_current_process(self) -> int:
        """Add the current process to the list ""
        
    def cleanup_invalid_processes(self) -> int:
        Clear invalid processes. (return the number of purges, -1 if not available)"""
        
    def get_valid_processes(self) -> List[int]:
        """Get all valid process IDs (verify if the process exists) "" ""
        
    def should_destroy(self) -> bool:
        Check whether the shared memory should be destroyed (the status is OFF and there is no valid process)."""
        
    def send_control_command(
        self,
        is_start: bool,
        force: bool = False,
        send_signal: bool = True
    ) -> Tuple[bool, int, int, bool]:
        """Send a control command and return (Whether the operation is successful, the number of signals sent successfully, the number of invalid processes to be cleared, and whether the change is actually performed) ""
        
    def get_status(self) -> dict:
        Obtain the complete status information (including the version_mismatch flag)."""
```

### 3.13 Inject (Bytecode Injection Module)

**Responsibilities:**

 * Insert hook code at function entry and return points through bytecode injection.
 * Accessing the locals variable of the function
 * Handlers of the context manager type are supported (handers of locals are required).
 * Supports Python 3.8+ (different versions use different bytecode instructions)

**Class definition:**

```python
def inject_function(
    ori_func: Callable,
    context_hook_funcs: List[Callable]
) -> Callable:
    """injection function
    
    Insert hook code at the entry and return points of the function through bytecode injection.
    Supports access to the locals variable of the function.
    
    Args:
        ori_func: original function
        context_hook_funcs: Context Manager function list
            Each function signature should be: def handler(ctx, local_values): yield
    
    Returns:
        Function After Injection
    """
```

### 3.14 MetaState (Process Metadata Status Management)

**Responsibilities:**

 * Provides independent metadata storage for each process.
 * Used to provide additional tag information in metrics
 * Supports dynamic update and obtaining, which is used by handlers.
 * The write operation thread is safe. The read operation has no lock (old data can be read).

**Class definition:**

```python
class MetaState:
    """Process metadata status class.
    
    Each process has an independent MetaState instance that stores the metadata information for that process.
    Supports dynamic update and obtaining.
    Note: The get() method does not lock and allows old data to be read for better performance.
    Python GIL guarantees the atomicity of the dict.get() operation.
    """
    
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._lock = threading.Lock()  #For write operations only
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get metadata value (no lock, allow old data to be read) "" ""
        
    def set(self, key: str, value: Any):
        Set metadata values."""
        
    def update(self, data: Dict[str, Any]):
        """Batch update metadata ""
        
    def remove(self, key: str) -> bool:
        Delete metadata."""
        
    def clear(self):
        """Clear all metadata ""
        
    def get_all(self) -> Dict[str, Any]:
        Obtain all metadata."""
        
    def has(self, key: str) -> bool:
        """Check whether a key "" exists.
        
    @property
    def dp_rank(self) -> int:
        Obtain data parallel rank (convenient attribute)."""
        
    @property
    def model_name(self) -> str:
        """Obtain the model name (convenient attribute) "" ""


# Global MetaState instance (singleton)
_meta_state_instance: Optional[MetaState] = None

def get_meta_state() -> MetaState:
    Obtain the global MetaState instance (singleton mode)."""
    
def reset_meta_state():
    """Reset global MetaState instance "" ""
    
def get_dp_rank() -> int:
    Obtain the dp_rank of the current process."""
    
def set_dp_rank(rank: int):
    """Set the dp_rank of the current process"""
    
def get_model_name() -> str:
    Obtain the model name of the current process."""
    
def set_model_name(name: str):
    """Set the model name for the current process ""
```

### 3.15 ExprEval (Expression Evaluator)

**Responsibilities:**

 * Supports secure mathematical expression evaluation
 * Can be used for expression evaluation in the configuration
 * Supports operations such as variable, function call, attribute access, and subscript access.

**Class definition:**

```python
class ExprEval:
    """Expression evaluator
    
    Parses and evaluates mathematical expressions, supporting the following features:
    - Basic math operation: +, -, *, /, //, %, **
    - Variable reference: Obtain variable values from params.
    - Function call: abs, round, len, max, min, etc.
    - Attribute access: obj.attr
    - Subscript access: list[index], dict[key]
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
        """Initializing the expression evaluator ""
        
    def __call__(self, params: Dict[str, Any], *args, **kwargs) -> Any:
        Evaluation expression"""
        
    def register_function(self, name: str, func: Callable):
        """Register the user-defined function ""


def evaluate_expression(expression: str, params: Dict[str, Any]) -> Any:
    "" "Convenience Functions:Evaluation Expressions"""
```

### 3.16 Built-in Handlers (builtin.py)

**Responsibilities:**

 * Provides common built-in handler functions.
 * Can be used directly in configuration.

**Main functions:**

```python
def default_handler(metrics_config: List[MetricConfig], is_async: bool = False, **kwargs) -> Callable:
    """Creating a Default Handler
    
    Determine whether locals is required based on whether the metrics configuration contains the expr field.
    - If expr is available, locals is required and two parameters are created.
    - No expr: locals is not required. The 1 parameter context handler or wrap handler is created.
    
    Supports synchronous and asynchronous functions.
    """
```

### 3.17 CLI Control Tool (cli.py)

**Responsibilities:**

 * Provides a command-line interface to control the metric collection switch in the target process.
 * Communicates with the target process through the shared memory and SIGUSR1 signal.

**How to use:**

```bash
ms-service-metric on      #Enable metric collection.
ms-service-metric off     #Disabling metric collection
ms-service-metric restart #Restart the metric collection (reload the configuration).
ms-service-metric status  #Viewing the status
```

**Environment variables:**

 * `MS_SERVICE_METRIC_SHM_PREFIX`\: shared memory and semaphore name prefix (default: /ms_service_metric)
 * `MS_SERVICE_METRIC_MAX_PROCS`\: Maximum number of processes (1000 by default)

## 4. Configuration format

### 4.1 Array Format (Compatible with Original Configuration)

```yaml
- symbol: module.path:ClassName.method_name
  handler: module.path:function_name  #Optional.
  min_version: "0.1.0"  #Optional.
  max_version: "1.0.0"  #Optional.
  lock_patch: false  #Optional. If the value is true, the handler is not deleted.
  metrics:
    - name: metric_name
      type: timer
      expr: "duration"  #Optional. If expr exists, locals is required.
      buckets: [0.1, 0.5, 1.0]  #Optional.
      labels:
        - name: label_name
          expr: "expression"

- symbol: module.path:ClassName.method_name
  metrics:  #Use the default handler when there is no handler.
    - name: metric_name
      type: timer
```

### 4.2 Dictionary Format

```yaml
module.path:ClassName.method_name:
  - handler: module.path:function_name
    metrics:
      - name: metric_name
        type: timer
```

## 5. Key Processes

### 5.1 Initialization Process

```text
SymbolHandlerManager.initialize()
  ├── 加载配置 (SymbolConfig.load)
  ├── 注册控制回调 (_on_control_state_change)
  ├── 启动控制监视器 (MetricConfigWatch.start)
  └── 启动模块监视器 (SymbolWatcher.start)
```

### 5.2 Module Loading Process

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

### 5.3 Control Command Processing Flow

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

### 5.4 Hook Execution Process

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

## 6. Thread security

### 6.1 Use of locks

| Class                | Locked            | Purpose                                                  |
| -------------------- | ----------------- | -------------------------------------------------------- |
| SymbolHandlerManager | `_lock`           | Protecting the atomicity of _enabled and bulk operations |
| SymbolWatcher        | `_lock`           | Securing callback lists and module collections           |
| HookChain            | `_lock`           | Protection Linked List Operation                         |
| MetricsManager       | None              | Depends on the thread security of the Prometheus client. |
| MetaState            | `_lock`           | Protection Data Dictionary                               |
| SharedMemoryManager  | `_sem`(Semaphore) | Secure shared memory access                              |

### 6.2 Singleton Mode

The following classes use singleton mode:

 * `SymbolWatcher`\: through the`__new__`Ensure globally unique instances
 * `MetricsManager`\: module-level variables`_metrics_manager_instance`Implemented
 * `MetaState`\: module-level variables`_meta_state_instance`achieves

## 7. Troubleshooting

### 7.1 User-defined Exceptions

```python
ServiceMetricError          #Basic Exceptions
├── ConfigError             #Configuration related errors
├── HandlerError            #Handler-related errors.
├── SymbolError             #Symbol related error.
├── HookError               #Hook operation error.
├── MetricsError            #Errors related to metrics
└── SharedMemoryError       #Shared memory error.
```

### 7.2 Exception Handling Policy

1. **Configuration loading failed: Recording error, continue with null configuration**
2. **Failed to create the handler. The handler is skipped because the record is incorrect.**
3. **Hook application failed: Log error, flag_hook_applied=False**
4. **Hook execution exception: The exception protection mechanism ensures that the original function is invoked.**
5. **Shared memory operation failed: Throw SharedMemoryError**
