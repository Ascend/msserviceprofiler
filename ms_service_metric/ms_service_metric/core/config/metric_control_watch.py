# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------
"""
MetricControlWatch: Metric配置动态监视器

职责：
- 使用posix_ipc共享内存和SIGUSR1信号实现进程间通信
- 支持环境变量配置共享内存和信号量名称前缀
- 简化设计：只需要start标志和时间戳
  - start=False: 关闭metric收集
  - start=True: 开启metric收集
  - 时间戳变化表示需要重启（重新加载配置）

使用示例：
    # 在被控制进程中
    watch = MetricControlWatch()
    watch.register_callback(lambda is_start, ts: logger.info(f"Start: {is_start}, Timestamp: {ts}"))
    watch.start()

    # 在控制端（使用CLI工具）
    ms-service-metric on      # 开启
    ms-service-metric off     # 关闭
    ms-service-metric restart # 重启

环境变量：
    MS_SERVICE_METRIC_SHM_PREFIX: 共享内存和信号量名称前缀（默认: /ms_service_metric）
    MS_SERVICE_METRIC_MAX_PROCS: 最大进程数（默认: 1000）
"""

import os
import signal
import threading
from typing import Callable, List, Optional

# This Linux-only module owns manager disconnect explicitly and keeps existing
# log messages readable while interpolating local control-state values.
# pylint: disable=logging-fstring-interpolation,no-member,consider-using-with

from ms_service_metric.utils.exceptions import SharedMemoryError
from ms_service_metric.utils.logger import get_logger
from ms_service_metric.utils.shm_manager import (
    DEFAULT_MAX_PROCS,
    DEFAULT_SHM_PREFIX,
    ENV_MAX_PROCS,
    ENV_SHM_PREFIX,
    POSIX_IPC_AVAILABLE,
    STATE_OFF,
    STATE_ON,
    SharedMemoryManager,
)

logger = get_logger("metric_control_watch")


class MetricControlWatch:
    """Metric配置监视器

    使用posix_ipc共享内存和SIGUSR1信号实现动态开关控制。
    支持多进程同时监听，控制端可以同时向所有进程发送信号。

    简化设计：
    - 只需要start标志和时间戳
    - start=False: 关闭metric收集
    - start=True: 开启metric收集
    - 时间戳变化表示需要重启（重新加载配置）

    Attributes:
        STATE_OFF: 关闭状态 (0)
        STATE_ON: 开启状态 (1)
    """

    STATE_OFF = STATE_OFF
    STATE_ON = STATE_ON

    def __init__(self, shm_prefix: Optional[str] = None, max_procs: Optional[int] = None):
        """初始化MetricControlWatch

        Args:
            shm_prefix: 共享内存前缀（默认从环境变量读取）
            max_procs: 最大进程数（默认从环境变量读取）
        """
        if not POSIX_IPC_AVAILABLE:
            raise SharedMemoryError("posix_ipc not available, MetricControlWatch requires Linux platform")

        self._callbacks: List[Callable[[bool, int], None]] = []
        self._running = False
        self._lock = threading.RLock()  # 可重入锁，允许同一线程多次获取
        self._manager: Optional[SharedMemoryManager] = None
        self._current_state = self.STATE_OFF
        self._last_timestamp = 0
        self._original_handler = None
        self._signal_lock = threading.Lock()  # 用于防止信号处理函数重入

        # 配置
        self._shm_prefix = shm_prefix or os.environ.get(ENV_SHM_PREFIX, DEFAULT_SHM_PREFIX)
        self._max_procs = max_procs or int(os.environ.get(ENV_MAX_PROCS, DEFAULT_MAX_PROCS))

        logger.debug(f"MetricControlWatch initialized: shm_prefix={self._shm_prefix}, max_procs={self._max_procs}")

    def register_callback(self, callback: Callable[[bool, int], None]):
        """注册状态变化回调

        Args:
            callback: 回调函数，参数为(is_start, timestamp)
                     is_start: True=开启/重启, False=关闭
                     timestamp: 命令修改时间戳

        Note:
            如果当前已经是开启状态，回调会立即被调用一次
        """
        with self._lock:
            self._callbacks.append(callback)
            # 如果当前是开启状态，立即调用
            if self._current_state == self.STATE_ON:
                try:
                    callback(True, self._last_timestamp)
                except Exception as e:
                    logger.error(f"Callback error during registration: {e}")

        logger.debug(f"Callback registered: {callback}")

    def unregister_callback(self, callback: Callable[[bool, int], None]):
        """注销状态变化回调

        Args:
            callback: 要注销的回调函数
        """
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
                logger.debug(f"Callback unregistered: {callback}")

    def start(self):
        """启动监视器（在被控制进程中调用）

        初始化共享内存、信号量，注册信号处理函数，添加当前进程到列表。
        """
        with self._lock:
            if self._running:
                logger.debug("MetricControlWatch already running")
                return
            self._running = True

        try:
            # 初始化共享内存管理器
            self._manager = SharedMemoryManager(shm_prefix=self._shm_prefix, max_procs=self._max_procs)
            self._manager.connect(create=True)

            # 注册SIGUSR1信号处理
            self._register_signal_handler()

            # 添加当前进程到进程列表
            self._manager.add_current_process()

            # 读取初始状态
            self._check_control_state()

            logger.info("MetricControlWatch started")

        except Exception as e:
            self._running = False
            logger.error(f"Failed to start MetricControlWatch: {e}")
            raise

    def stop(self):
        """停止监视器

        恢复信号处理，关闭共享内存和信号量。
        """
        with self._lock:
            if not self._running:
                return
            self._running = False

        try:
            # 恢复信号处理
            if self._original_handler is not None:
                signal.signal(signal.SIGUSR1, self._original_handler)
                logger.debug("Restored original SIGUSR1 handler")
            else:
                signal.signal(signal.SIGUSR1, signal.SIG_DFL)

            # 关闭共享内存管理器
            if self._manager:
                self._manager.disconnect()
                self._manager = None

            logger.info("MetricControlWatch stopped")

        except Exception as e:
            logger.error(f"Error stopping MetricControlWatch: {e}")

    def _register_signal_handler(self):
        """注册SIGUSR1信号处理"""
        self._original_handler = signal.signal(signal.SIGUSR1, self._signal_handler)
        logger.debug("Registered SIGUSR1 handler")

    def _signal_handler(self, signum, frame):
        """SIGUSR1信号处理函数

        收到信号后检查控制状态并触发相应回调。
        使用锁防止重入，同时链式调用原始handler（如果存在）。
        """
        # 非阻塞尝试获取锁，如果获取不到说明已经在处理中
        if not self._signal_lock.acquire(blocking=False):
            logger.warning("Signal handler already running, skipping...")
            return

        try:
            if signum == signal.SIGUSR1:
                logger.debug("Received SIGUSR1 signal")
                self._check_control_state()

            # 调用原始handler（如果存在且不是默认handler）
            if self._original_handler is not None and self._original_handler not in (signal.SIG_DFL, signal.SIG_IGN):
                self._original_handler(signum, frame)
        finally:
            self._signal_lock.release()

    def _read_control_state(self):
        """从共享内存读取控制状态

        Returns:
            Tuple[int, int]: (状态, 时间戳)
        """
        if not self._manager:
            return self.STATE_OFF, 0

        return self._manager.get_state(), self._manager.get_timestamp()

    def _check_control_state(self):
        """检查控制状态

        从共享内存读取控制命令，根据状态和时间戳判断是否触发回调。

        处理逻辑：
        - 状态变化时触发回调
        - 时间戳变化时触发回调（用于重启检测）
        - 回调执行后更新本地状态，避免失败回调被信号重复触发
        """
        state, timestamp = self._read_control_state()

        # 转换为is_start标志
        is_start = state == self.STATE_ON

        # 检查是否需要触发回调
        state_changed = state != self._current_state
        timestamp_changed = timestamp != self._last_timestamp

        if state_changed or (is_start and timestamp_changed):
            if state_changed:
                logger.info(f"Control state changed: {self._current_state} -> {state}")
            else:
                logger.info(f"Control timestamp changed: {self._last_timestamp} -> {timestamp} (restart)")

            # 通知所有回调后确认本次命令。失败由回调自身记录，后续通过
            # restart 发送新时间戳显式重试，避免重复信号造成重试风暴。
            callbacks_succeeded = self._notify_callbacks(is_start, timestamp)
            self._current_state = state
            self._last_timestamp = timestamp
            if not callbacks_succeeded:
                logger.error("Control state callback failed; use metric restart to retry")

    def _notify_callbacks(self, is_start: bool, timestamp: int) -> bool:
        """通知所有回调函数

        Args:
            is_start: 是否开启
            timestamp: 时间戳
        """
        action = "START" if is_start else "STOP"
        logger.info(f"Notifying callbacks: action={action}, timestamp={timestamp}")

        with self._lock:
            callbacks = self._callbacks.copy()

        succeeded = True
        for callback in callbacks:
            try:
                callback(is_start, timestamp)
            except Exception as e:
                succeeded = False
                logger.error(f"Error in callback: {e}")
        return succeeded

    def get_last_timestamp(self) -> int:
        """获取上次处理的时间戳

        Returns:
            上次处理的时间戳
        """
        with self._lock:
            return self._last_timestamp

    def is_enabled(self) -> bool:
        """检查当前是否处于开启状态

        Returns:
            如果当前状态为开启返回True
        """
        with self._lock:
            return self._current_state == self.STATE_ON

    # ========== 类方法：控制端接口（可选，推荐使用CLI工具） ==========

    @classmethod
    def set_control_state(cls, is_start: bool, shm_prefix: Optional[str] = None, force: bool = False):
        """设置控制状态（控制端调用）

        注意：推荐使用CLI工具（ms-service-metric）代替此方法。

        Args:
            is_start: 控制状态，True=开启，False=关闭
            shm_prefix: 共享内存前缀（默认从环境变量读取）
            force: 是否强制执行

        Raises:
            SharedMemoryError: 共享内存操作失败
        """
        if not POSIX_IPC_AVAILABLE:
            raise SharedMemoryError("posix_ipc not available")

        manager = SharedMemoryManager(shm_prefix=shm_prefix)

        try:
            if not manager.connect(create=False):
                raise SharedMemoryError("Failed to connect to shared memory")

            success, signaled, cleaned, changed = manager.send_control_command(
                is_start=is_start, force=force, send_signal=True
            )

            if not success:
                raise SharedMemoryError("Failed to send control command")

            action = "START" if is_start else "STOP"
            if changed:
                logger.info(f"Set control state to {action}, signaled={signaled}, cleaned={cleaned}")
            else:
                logger.info(f"State already {action}, no change needed")

        finally:
            manager.disconnect()
