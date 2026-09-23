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
Shared Memory Manager - 共享内存管理器

统一管理ms_service_metric的共享内存操作，包括：
- 内存布局定义（支持版本兼容）
- 共享内存创建/连接/断开/释放
- 信号量操作
- 数据读写（状态、时间戳、进程列表）
- 进程管理（添加、清理、验证）

内存布局设计（版本兼容）：
所有偏移量都相对于共享内存起始位置，简化设计

使用方式:
    # 在被控制进程中
    manager = SharedMemoryManager()
    manager.connect()  # 连接或创建共享内存
    manager.add_current_process()  # 添加当前进程到列表

    # 在控制端
    manager = SharedMemoryManager()
    manager.connect()
    manager.send_control_command(is_start=True)  # 发送控制命令
"""

import os
import signal
import time
import mmap
from typing import List, Optional, Tuple

# pylint: disable=logging-fstring-interpolation

from ms_service_metric.utils.exceptions import SharedMemoryError
from ms_service_metric.utils.logger import get_logger

# 仅在Linux平台导入posix_ipc
POSIX_IPC_AVAILABLE = True
try:
    import posix_ipc
except ImportError:
    POSIX_IPC_AVAILABLE = False

logger = get_logger("shm_manager")

# 环境变量名称
ENV_SHM_PREFIX = "MS_SERVICE_METRIC_SHM_PREFIX"
ENV_MAX_PROCS = "MS_SERVICE_METRIC_MAX_PROCS"

# 默认值
DEFAULT_SHM_PREFIX = "/ms_service_metric"
DEFAULT_MAX_PROCS = 1000
IPC_OBJECT_MODE = 0o600

# 状态值
STATE_OFF = 0
STATE_ON = 1

# 内存布局常量
MAGIC_NUMBER = 0x4D534D54  # "MSMT" in hex
HEADER_END_MARKER = 0xDEADBEEF  # 头部结束标记
CURRENT_VERSION = 1  # 当前版本号

# 基础类型大小
INT32_SIZE = 4


class SharedMemoryLayout:
    """共享内存布局定义（版本兼容设计）

    所有偏移量都相对于共享内存起始位置

    内存布局：
    [魔数:4][版本:4][头部长度:4][状态:4][时间戳:4][进程列表偏移:4][头部结束标记:4][进程列表长度:4][进程列表游标:4][PID1:4][PID2:4]...[PIDn:4]

    字段说明（每个都是int32）：
    - 魔数 (0x4D534D54)
    - 版本号
    - 头部长度（从开始到结束标记的总字节数）
    - 状态（STATE_OFF/STATE_ON）
    - 时间戳
    - 进程列表偏移（相对于共享内存起始位置）
    - 头部结束标记 (0xDEADBEEF)
    - 进程列表长度（循环列表长度）
    - 进程列表游标（循环列表当前位置）
    - 进程ID数组...
    """

    # 头部字段偏移量（相对于共享内存起始位置）
    OFFSET_MAGIC = 0  # 魔数（int32）
    OFFSET_VERSION = 4  # 版本号（int32）
    OFFSET_HEADER_LEN = 8  # 头部长度（int32）
    OFFSET_STATE = 12  # 状态（int32）
    OFFSET_TIMESTAMP = 16  # 时间戳（int32）
    OFFSET_PROC_OFFSET = 20  # 进程列表偏移（int32，相对于共享内存起始位置）
    OFFSET_HEADER_END = 24  # 头部结束标记（int32）

    # 头部总大小
    HEADER_SIZE = 28

    # 进程列表字段偏移量（相对于共享内存起始位置）
    # 注意：实际位置 = 进程列表偏移 + 相对偏移
    PROC_LIST_REL_OFFSET_LEN = 0  # 进程列表长度字段相对偏移
    PROC_LIST_REL_OFFSET_CURSOR = 4  # 进程列表游标字段相对偏移
    PROC_LIST_REL_OFFSET_DATA = 8  # 进程列表数据开始相对偏移
    PROC_LIST_HEADER_SIZE = 8  # 进程列表头部大小（长度+游标）
    PROC_ENTRY_SIZE = 4  # 每个进程ID占用的字节数

    @classmethod
    def get_shm_name(cls, prefix: str = DEFAULT_SHM_PREFIX) -> str:
        """获取共享内存完整名称"""
        return f"{prefix}_control"

    @classmethod
    def get_sem_name(cls, prefix: str = DEFAULT_SHM_PREFIX) -> str:
        """获取信号量完整名称"""
        return f"{prefix}_semaphore"

    @classmethod
    def calc_memory_size(cls, max_procs: int) -> int:
        """计算共享内存大小

        总大小 = 头部大小 + 进程列表结构大小
        进程列表结构 = 长度字段 + 游标字段 + max_procs * 每个PID大小
        """
        proc_list_size = cls.PROC_LIST_HEADER_SIZE + max_procs * cls.PROC_ENTRY_SIZE
        return cls.HEADER_SIZE + proc_list_size


class SharedMemoryManager:
    """共享内存管理器

    封装所有共享内存和信号量的操作，支持版本兼容。

    Attributes:
        _shm_prefix: 共享内存名称前缀
        _max_procs: 最大进程数
        _memory_size: 共享内存大小
        _shm: 共享内存对象
        _mmap: 内存映射对象
        _sem: 信号量对象
        _version_mismatch: 版本是否不匹配
        _header_len: 实际头部长度（用于兼容）
    """

    # 进程列表偏移异常值（表示字段不可用）
    PROC_OFFSET_INVALID = -1
    # 进程列表长度异常值（表示进程列表不可用）
    PROC_LEN_INVALID = -1

    def __init__(self, shm_prefix: Optional[str] = None, max_procs: Optional[int] = None):
        """初始化共享内存管理器

        Args:
            shm_prefix: 共享内存前缀（默认从环境变量读取）
            max_procs: 最大进程数（默认从环境变量读取）
        """
        if not POSIX_IPC_AVAILABLE:
            raise SharedMemoryError("posix_ipc not available, requires Linux platform")

        self._shm_prefix = shm_prefix or os.environ.get(ENV_SHM_PREFIX, DEFAULT_SHM_PREFIX)
        self._max_procs = max_procs or int(os.environ.get(ENV_MAX_PROCS, DEFAULT_MAX_PROCS))
        self._memory_size = SharedMemoryLayout.calc_memory_size(self._max_procs)

        self._shm_name = SharedMemoryLayout.get_shm_name(self._shm_prefix)
        self._sem_name = SharedMemoryLayout.get_sem_name(self._shm_prefix)

        self._shm = None
        self._mmap = None
        self._sem = None
        self._version_mismatch = False
        self._header_len = SharedMemoryLayout.HEADER_SIZE  # 实际头部长度（用于兼容）

        logger.debug(f"SharedMemoryManager initialized: shm={self._shm_name}, max_procs={self._max_procs}")

    # ========== 连接管理 ==========

    def connect(self, create: bool = True) -> bool:
        """连接到共享内存

        Args:
            create: 如果不存在是否创建

        Returns:
            是否连接成功
        """
        try:
            # 尝试打开已存在的共享内存
            self._shm = posix_ipc.SharedMemory(self._shm_name)
            # 获取已存在共享内存的实际大小
            actual_size = self._shm.size
            if actual_size != self._memory_size:
                logger.warning(f"Shared memory size mismatch: expected={self._memory_size}, actual={actual_size}")
            # 使用实际大小进行内存映射
            self._mmap = mmap.mmap(self._shm.fd, actual_size)
            # 更新内存大小为实际大小
            self._memory_size = actual_size
            logger.debug(f"Connected to existing shared memory: {self._shm_name}, size={actual_size}")

            # 检查版本兼容性
            self._check_version_compatibility()

        except posix_ipc.ExistentialError:
            if not create:
                logger.debug(f"Shared memory not found: {self._shm_name}")
                return False
            # 创建新的共享内存
            logger.debug(f"Creating new shared memory: {self._shm_name}")
            self._shm = posix_ipc.SharedMemory(
                self._shm_name, flags=posix_ipc.O_CREX, mode=IPC_OBJECT_MODE, size=self._memory_size
            )
            self._mmap = mmap.mmap(self._shm.fd, self._memory_size)
            # 初始化为全0
            self._mmap[:] = b'\x00' * self._memory_size
            # 初始化头部
            self._init_header()

        # 连接或创建信号量
        try:
            self._sem = posix_ipc.Semaphore(self._sem_name)
            logger.debug(f"Connected to existing semaphore: {self._sem_name}")
        except posix_ipc.ExistentialError:
            logger.debug(f"Creating new semaphore: {self._sem_name}")
            self._sem = posix_ipc.Semaphore(
                self._sem_name, flags=posix_ipc.O_CREX, mode=IPC_OBJECT_MODE, initial_value=1
            )

        return True

    def _init_header(self):
        """初始化共享内存头部和进程列表结构"""
        with self.semaphore_lock():
            # 初始化头部
            self.write_int(SharedMemoryLayout.OFFSET_MAGIC, MAGIC_NUMBER)
            self.write_int(SharedMemoryLayout.OFFSET_VERSION, CURRENT_VERSION)
            self.write_int(SharedMemoryLayout.OFFSET_HEADER_LEN, SharedMemoryLayout.HEADER_SIZE)
            self.write_int(SharedMemoryLayout.OFFSET_STATE, STATE_OFF)
            self.write_int(SharedMemoryLayout.OFFSET_TIMESTAMP, 0)
            self.write_int(SharedMemoryLayout.OFFSET_PROC_OFFSET, SharedMemoryLayout.HEADER_SIZE)  # 进程列表紧跟头部
            self.write_int(SharedMemoryLayout.OFFSET_HEADER_END, HEADER_END_MARKER)

            # 初始化进程列表结构
            proc_offset = self._get_proc_offset()
            self.write_int(proc_offset + SharedMemoryLayout.PROC_LIST_REL_OFFSET_LEN, self._max_procs)
            self.write_int(proc_offset + SharedMemoryLayout.PROC_LIST_REL_OFFSET_CURSOR, 0)

        logger.debug(f"Initialized shared memory header with version {CURRENT_VERSION}")

    def _check_version_compatibility(self):
        """检查版本兼容性

        如果头部结束标记不匹配或版本不一致，标记为版本不匹配。
        但即使版本不匹配，也尽量读取能读到的字段（能读多少读多少）。
        """
        try:
            magic = self.read_int(SharedMemoryLayout.OFFSET_MAGIC)
            version = self.read_int(SharedMemoryLayout.OFFSET_VERSION)
            header_len = self.read_int(SharedMemoryLayout.OFFSET_HEADER_LEN)
            header_end = self.read_int(SharedMemoryLayout.OFFSET_HEADER_END)

            # 检查魔数和头部结束标记
            if magic != MAGIC_NUMBER or header_end != HEADER_END_MARKER:
                logger.warning(
                    f"Version mismatch detected: magic={magic:08X}, expected={MAGIC_NUMBER:08X}, "
                    f"header_end={header_end:08X}, expected={HEADER_END_MARKER:08X}"
                )
                self._version_mismatch = True
                return

            # 检查版本号
            if version != CURRENT_VERSION:
                logger.warning(f"Version mismatch: found={version}, expected={CURRENT_VERSION}")
                self._version_mismatch = True

                # 记录实际的头部长度，用于后续读取时判断字段是否存在
                if header_len > 0:
                    self._header_len = min(header_len, SharedMemoryLayout.HEADER_SIZE)
                return

            self._version_mismatch = False
            logger.debug(f"Version check passed: version={version}")

        except Exception as e:
            logger.warning(f"Failed to check version compatibility: {e}")
            self._version_mismatch = True

    def is_control_state_valid(self) -> bool:
        """Validate shared memory header and control state before acting on it."""
        if not self._mmap or self._memory_size < SharedMemoryLayout.HEADER_SIZE:
            logger.warning("Invalid control state: shared memory is not connected or too small")
            return False

        try:
            magic = self.read_int(SharedMemoryLayout.OFFSET_MAGIC)
            version = self.read_int(SharedMemoryLayout.OFFSET_VERSION)
            header_len = self.read_int(SharedMemoryLayout.OFFSET_HEADER_LEN)
            state = self.read_int(SharedMemoryLayout.OFFSET_STATE)
            header_end = self.read_int(SharedMemoryLayout.OFFSET_HEADER_END)
        except Exception as e:
            logger.warning(f"Invalid control state: failed to read shared memory header: {e}")
            return False

        if magic != MAGIC_NUMBER or version != CURRENT_VERSION or header_end != HEADER_END_MARKER:
            logger.warning(
                f"Invalid control state header: magic={magic:08X}, version={version}, header_end={header_end:08X}"
            )
            return False

        if header_len != SharedMemoryLayout.HEADER_SIZE:
            logger.warning(
                f"Invalid control state header length: header_len={header_len}, "
                f"expected={SharedMemoryLayout.HEADER_SIZE}"
            )
            return False

        if state not in (STATE_OFF, STATE_ON):
            logger.warning(f"Invalid control state value: state={state}")
            return False

        return True

    def disconnect(self):
        """断开连接"""
        if self._mmap:
            self._mmap.close()
            self._mmap = None
        if self._shm:
            self._shm.close_fd()
            self._shm = None
        if self._sem:
            self._sem.close()
            self._sem = None
        logger.debug("Disconnected from shared memory")

    def destroy(self):
        """销毁共享内存和信号量

        完全删除共享内存和信号量，释放系统资源。
        应该在确认没有进程使用时调用。
        """
        # 先断开连接
        self.disconnect()

        # 删除共享内存
        try:
            posix_ipc.unlink_shared_memory(self._shm_name)
            logger.info(f"Unlinked shared memory: {self._shm_name}")
        except posix_ipc.ExistentialError:
            logger.debug(f"Shared memory already unlinked: {self._shm_name}")
        except Exception as e:
            logger.warning(f"Failed to unlink shared memory: {e}")

        # 删除信号量
        try:
            posix_ipc.unlink_semaphore(self._sem_name)
            logger.info(f"Unlinked semaphore: {self._sem_name}")
        except posix_ipc.ExistentialError:
            logger.debug(f"Semaphore already unlinked: {self._sem_name}")
        except Exception as e:
            logger.warning(f"Failed to unlink semaphore: {e}")

    # ========== 信号量操作 ==========
    def lock(self):
        """获取信号量锁（阻塞）"""
        if self._sem:
            self._sem.acquire()

    def unlock(self):
        """释放信号量锁"""
        if self._sem:
            self._sem.release()

    def semaphore_lock(self):
        """获取信号量锁（上下文管理器）

        使用方式:
            with manager.semaphore_lock():
                # 临界区代码
                pass
        """

        class SemaphoreLock:
            def __init__(self, sem):
                self._sem = sem

            def __enter__(self):
                if self._sem:
                    self._sem.acquire()

            def __exit__(self, *args):
                if self._sem:
                    self._sem.release()

        return SemaphoreLock(self._sem)

    # ========== 基础读写 ==========

    def read_int(self, offset: int) -> int:
        """从共享内存读取int32"""
        if not self._mmap:
            return 0
        return int.from_bytes(self._mmap[offset : offset + 4], 'little', signed=False)

    def write_int(self, offset: int, value: int):
        """向共享内存写入int32"""
        if not self._mmap:
            return
        self._mmap[offset : offset + 4] = value.to_bytes(4, 'little', signed=False)

    # ========== 状态操作 ==========

    def _is_field_available(self, offset: int) -> bool:
        """检查指定偏移量的字段是否可用（在有效头部长度范围内）"""
        return offset + INT32_SIZE <= self._header_len

    def get_state(self) -> int:
        """获取当前状态

        如果字段不可用，返回默认值 STATE_OFF
        """
        if not self._is_field_available(SharedMemoryLayout.OFFSET_STATE):
            return STATE_OFF
        return self.read_int(SharedMemoryLayout.OFFSET_STATE)

    def set_state(self, state: int):
        """设置状态"""
        if self._is_field_available(SharedMemoryLayout.OFFSET_STATE):
            self.write_int(SharedMemoryLayout.OFFSET_STATE, state)

    def get_timestamp(self) -> int:
        """获取时间戳

        如果字段不可用，返回默认值 0
        """
        if not self._is_field_available(SharedMemoryLayout.OFFSET_TIMESTAMP):
            return 0
        return self.read_int(SharedMemoryLayout.OFFSET_TIMESTAMP)

    def set_timestamp(self, timestamp: int):
        """设置时间戳"""
        if self._is_field_available(SharedMemoryLayout.OFFSET_TIMESTAMP):
            self.write_int(SharedMemoryLayout.OFFSET_TIMESTAMP, timestamp)

    def update_state_and_timestamp(self, state: int):
        """同时更新状态和时间戳"""
        with self.semaphore_lock():
            self.set_state(state)
            self.set_timestamp(int(time.time()))

    def _get_proc_offset(self) -> int:
        """获取进程列表在共享内存中的偏移量

        Returns:
            进程列表起始偏移量（相对于共享内存起始位置）
            如果字段不可用，返回 PROC_OFFSET_INVALID
        """
        if not self._is_field_available(SharedMemoryLayout.OFFSET_PROC_OFFSET):
            return self.PROC_OFFSET_INVALID
        proc_offset = self.read_int(SharedMemoryLayout.OFFSET_PROC_OFFSET)
        if proc_offset <= 0:
            proc_offset = SharedMemoryLayout.HEADER_SIZE
        return proc_offset

    def _is_proc_list_available(self) -> bool:
        """检查进程列表是否可用

        Returns:
            进程列表是否可用（偏移量有效且在内存范围内）
        """
        proc_offset = self._get_proc_offset()
        if proc_offset == self.PROC_OFFSET_INVALID:
            return False
        # 检查进程列表头部是否在内存范围内
        if proc_offset + SharedMemoryLayout.PROC_LIST_REL_OFFSET_DATA > self._memory_size:
            return False
        return True

    def get_proc_len(self) -> int:
        """获取进程列表总长度

        如果进程列表不可用，返回 PROC_LEN_INVALID
        """
        proc_offset = self._get_proc_offset()
        if proc_offset == self.PROC_OFFSET_INVALID:
            return self.PROC_LEN_INVALID
        if proc_offset + SharedMemoryLayout.PROC_LIST_REL_OFFSET_DATA > self._memory_size:
            return self.PROC_LEN_INVALID
        return self.read_int(proc_offset + SharedMemoryLayout.PROC_LIST_REL_OFFSET_LEN)

    def set_proc_len(self, proc_len: int):
        """设置进程列表总长度"""
        proc_offset = self._get_proc_offset()
        if proc_offset == self.PROC_OFFSET_INVALID:
            return
        if proc_offset + SharedMemoryLayout.PROC_LIST_REL_OFFSET_DATA > self._memory_size:
            return
        self.write_int(proc_offset + SharedMemoryLayout.PROC_LIST_REL_OFFSET_LEN, proc_len)

    def get_proc_cursor(self) -> int:
        """获取进程列表游标位置

        如果进程列表不可用，返回默认值 0
        """
        proc_offset = self._get_proc_offset()
        if proc_offset == self.PROC_OFFSET_INVALID:
            return 0
        if proc_offset + SharedMemoryLayout.PROC_LIST_REL_OFFSET_DATA > self._memory_size:
            return 0
        return self.read_int(proc_offset + SharedMemoryLayout.PROC_LIST_REL_OFFSET_CURSOR)

    def set_proc_cursor(self, cursor: int):
        """设置进程列表游标位置"""
        proc_offset = self._get_proc_offset()
        if proc_offset == self.PROC_OFFSET_INVALID:
            return
        if proc_offset + SharedMemoryLayout.PROC_LIST_REL_OFFSET_DATA > self._memory_size:
            return
        self.write_int(proc_offset + SharedMemoryLayout.PROC_LIST_REL_OFFSET_CURSOR, cursor)

    def _get_proc_data_offset(self, index: int) -> int:
        """计算进程ID在内存中的实际偏移量

        Args:
            index: 进程列表索引

        Returns:
            实际内存偏移量，如果进程列表不可用返回 -1
        """
        proc_offset = self._get_proc_offset()
        if proc_offset == self.PROC_OFFSET_INVALID:
            return -1
        return proc_offset + SharedMemoryLayout.PROC_LIST_REL_OFFSET_DATA + index * SharedMemoryLayout.PROC_ENTRY_SIZE

    def get_proc_at(self, index: int) -> int:
        """获取指定索引的进程ID

        如果进程列表不可用，返回 0
        """
        offset = self._get_proc_data_offset(index)
        if offset < 0:
            return 0
        return self.read_int(offset)

    def set_proc_at(self, index: int, pid: int):
        """设置指定索引的进程ID"""
        offset = self._get_proc_data_offset(index)
        if offset < 0:
            return
        self.write_int(offset, pid)

    def get_all_procs(self) -> List[int]:
        """获取所有有效进程ID（去重）

        如果进程列表不可用，返回空列表
        """
        proc_len = self.get_proc_len()
        if proc_len == self.PROC_LEN_INVALID:
            return []
        procs = set()
        for i in range(proc_len):
            pid = self.get_proc_at(i)
            if pid > 0:
                procs.add(pid)
        return list(procs)

    def add_process(self, pid: Optional[int] = None) -> int:
        """添加进程到列表

        Args:
            pid: 进程ID（默认当前进程）

        Returns:
            写入的位置索引，如果进程列表不可用返回 -1
        """
        if pid is None:
            pid = os.getpid()

        with self.semaphore_lock():
            cursor = self.get_proc_cursor()
            proc_len = self.get_proc_len()

            # 如果进程列表不可用，返回 -1
            if proc_len == self.PROC_LEN_INVALID:
                logger.warning(f"Cannot add process {pid}: process list not available")
                return -1

            # 如果进程列表长度为0或负数，无法添加
            if proc_len <= 0:
                logger.warning(f"Cannot add process {pid}: invalid process list length={proc_len}")
                return -1

            # 计算写入位置（循环列表）
            index = cursor % proc_len
            self.set_proc_at(index, pid)

            # 更新游标
            new_cursor = (cursor + 1) % proc_len
            self.set_proc_cursor(new_cursor)

            logger.debug(f"Added process {pid} at index {index}, new_cursor={new_cursor}")
            return index

    def add_current_process(self) -> int:
        """添加当前进程到列表"""
        return self.add_process(os.getpid())

    def cleanup_invalid_processes(self) -> int:
        """清理无效的进程（进程不存在的）

        注意：此方法不自动获取信号量锁，调用方需要确保已持有锁。
        建议在 semaphore_lock() 上下文中调用。

        Returns:
            清理的进程数量，如果进程列表不可用返回 -1
        """
        proc_len = self.get_proc_len()
        if proc_len == self.PROC_LEN_INVALID:
            return -1

        cleaned = 0
        for i in range(proc_len):
            pid = self.get_proc_at(i)
            if pid <= 0:
                continue

            try:
                # 检查进程是否存在（发送信号0）
                os.kill(pid, 0)
            except ProcessLookupError:
                # 进程不存在，清理
                self.set_proc_at(i, 0)
                cleaned += 1
                logger.debug(f"Cleaned invalid process {pid} at index {i}")
            except PermissionError:
                # 进程存在但没有权限，保留
                pass
            except Exception as e:
                logger.debug(f"Failed to check process {pid}: {e}")

        return cleaned

    def get_valid_processes(self) -> List[int]:
        """获取所有有效的进程ID（验证进程是否存在）

        Returns:
            存在的进程ID列表
        """
        all_procs = self.get_all_procs()
        valid_procs = []

        for pid in all_procs:
            try:
                os.kill(pid, 0)
                valid_procs.append(pid)
            except (ProcessLookupError, PermissionError, OSError):
                pass

        return valid_procs

    # ========== 控制命令 ==========

    def send_control_command(
        self, is_start: bool, force: bool = False, send_signal: bool = True
    ) -> Tuple[bool, int, int, bool]:
        """发送控制命令

        Args:
            is_start: 控制状态，True=开启，False=关闭
            force: 是否强制执行
            send_signal: 是否发送SIGUSR1信号

        Returns:
            (是否成功, 成功发送信号数, 清理的无效进程数, 是否实际执行了变更)
        """
        target_state = STATE_ON if is_start else STATE_OFF

        with self.semaphore_lock():
            # 检查当前状态
            current_state = self.get_state()

            # 如果不是强制模式，且状态没有变化，则跳过
            if not force and current_state == target_state:
                action = "START" if is_start else "STOP"
                logger.info(f"State already {action}, no change needed")
                return True, 0, 0, False

            # 1. 先更新状态和时间戳
            self.set_state(target_state)
            self.set_timestamp(int(time.time()))

            # 2. 发送信号并清理无效进程
            if send_signal:
                signaled, cleaned = self._send_signals_and_cleanup()
            else:
                signaled, cleaned = 0, 0

            action = "START" if is_start else "STOP"
            logger.info(f"Sent {action} command to {signaled} processes, cleaned {cleaned}")
            return True, signaled, cleaned, True

    def _send_signals_and_cleanup(self) -> Tuple[int, int]:
        """发送信号并清理无效进程

        Returns:
            (成功发送信号数, 清理的无效进程数)
        """
        proc_len = self.get_proc_len()
        if proc_len == self.PROC_LEN_INVALID:
            return 0, 0

        signaled = 0
        cleaned = 0
        for i in range(proc_len):
            pid = self.get_proc_at(i)

            if pid <= 0:
                continue

            try:
                os.kill(pid, signal.SIGUSR1)
                signaled += 1
                logger.debug(f"Sent SIGUSR1 to process {pid}")
            except ProcessLookupError:
                # 进程不存在，立即清理
                self.set_proc_at(i, 0)
                cleaned += 1
                logger.debug(f"Process {pid} not found, cleaned immediately")
            except PermissionError:
                logger.warning(f"Permission denied to signal process {pid}")
            except Exception as e:
                logger.warning(f"Failed to signal process {pid}: {e}")

        return signaled, cleaned

    # ========== 状态查询 ==========

    def get_status(self) -> dict:
        """获取完整状态信息

        同时清理无效的进程。
        """
        with self.semaphore_lock():
            # 清理无效进程
            cleaned = self.cleanup_invalid_processes()

            valid_procs = self.get_valid_processes()

            return {
                "state": "ON" if self.get_state() == STATE_ON else "OFF",
                "timestamp": self.get_timestamp(),
                "process_cursor": self.get_proc_cursor(),
                "process_list_len": self.get_proc_len(),
                "process_count": len(valid_procs),
                "processes": valid_procs,
                "cleaned": cleaned,
                "version_mismatch": self._version_mismatch,
            }

    def should_destroy(self) -> bool:
        """检查是否应该销毁共享内存

        当状态为OFF且没有有效进程时，应该销毁共享内存。

        Returns:
            是否应该销毁
        """
        state = self.get_state()
        valid_procs = self.get_valid_processes()

        return state == STATE_OFF and len(valid_procs) == 0


# 便捷函数
def get_shm_name(prefix: str = DEFAULT_SHM_PREFIX) -> str:
    """获取共享内存完整名称"""
    return SharedMemoryLayout.get_shm_name(prefix)


def get_sem_name(prefix: str = DEFAULT_SHM_PREFIX) -> str:
    """获取信号量完整名称"""
    return SharedMemoryLayout.get_sem_name(prefix)


__all__ = [
    # 常量
    'ENV_SHM_PREFIX',
    'ENV_MAX_PROCS',
    'DEFAULT_SHM_PREFIX',
    'DEFAULT_MAX_PROCS',
    'IPC_OBJECT_MODE',
    'STATE_OFF',
    'STATE_ON',
    'MAGIC_NUMBER',
    'HEADER_END_MARKER',
    'CURRENT_VERSION',
    # 类
    'SharedMemoryLayout',
    'SharedMemoryManager',
    # 函数
    'get_shm_name',
    'get_sem_name',
]
