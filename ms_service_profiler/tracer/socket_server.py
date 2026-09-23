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

# pylint: disable=logging-fstring-interpolation

import socket
import ctypes
import os
import time
from typing import Optional
import queue
import threading
from ms_service_profiler.utils.log import logger


# Length field size for OTLP protocol
OTEL_Length_Field = 4

# interval of warning log
WARNING_INTERVAL = 3600


# define ucred
class Ucred(ctypes.Structure):
    _fields_ = [("pid", ctypes.c_uint32), ("uid", ctypes.c_uint32), ("gid", ctypes.c_uint32)]


class AbstractSocketServer:
    """Abstract socket server for receiving data."""

    def __init__(
        self,
        socket_name: str,
        buffer_size: int,
        max_listen_num: int,
        socket_timeout: int,
        max_queue_size=1000,
        warning_queue_size=100,
    ):
        """Initialize the socket server."""
        self.socket_name = '\0' + socket_name  # Use abstract namespace
        self.buffer_size = buffer_size
        self.max_listen_num = max_listen_num
        self.socket_timeout = socket_timeout
        self.data_queue = queue.Queue(max_queue_size)
        self.warning_queue_size = warning_queue_size
        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None
        self.last_stack_warning_time = 0
        self.last_full_warning_time = 0

    def _create_socket(self) -> socket.socket:
        """Create and bind the socket."""
        sock = None
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(self.socket_name)
            sock.listen(self.max_listen_num)
            logger.info(f"Start socket server success, listen addr: {self.socket_name}")
            return sock
        except Exception as e:
            if sock and sock.fileno() != -1:
                sock.close()
            logger.warning(f"Socket server {self.socket_name} create error: {str(e)}.", exc_info=True)
            raise

    @staticmethod
    def _get_namespace_inode(pid, ns_type):
        """Get namespace inode by pid."""
        ns_path = f"/proc/{pid}/ns/{ns_type}"
        return os.stat(ns_path).st_ino

    def _validate_peer_cred(self, client_sock):
        """Validate peer cred by uid, pid, gid."""
        cred = Ucred()
        cred_size = ctypes.sizeof(cred)
        try:
            # Get peer cred (SO_PEERCRED 17)
            cred_data = client_sock.getsockopt(socket.SOL_SOCKET, 17, cred_size)
            ctypes.memmove(ctypes.byref(cred), cred_data, cred_size)
        except Exception as e:
            logger.warning(f"Get peer cred failed: {e}")
            return False

        self_uid = os.getuid()
        self_gid = os.getgid()
        self_pid = os.getpid()
        peer_uid = cred.uid
        peer_gid = cred.gid
        peer_pid = cred.pid

        if peer_uid != self_uid or peer_gid != self_gid:
            logger.debug(
                f"Current user {self_uid} group {self_gid}, connect with unexpected user {peer_uid} group {peer_gid}."
            )
            return False

        try:
            if self._get_namespace_inode(self_pid, "pid") != self._get_namespace_inode(
                peer_pid, "pid"
            ) or self._get_namespace_inode(self_pid, "user") != self._get_namespace_inode(peer_pid, "user"):
                logger.debug(f"Connect with unexpected pid {peer_pid}.")
                return False
        except Exception as e:
            logger.debug(f"Validate peer cred failed: {e}")
            return False

        return True

    def _handle_client(self, client_sock: socket.socket, client_addr, length_field_size=OTEL_Length_Field):
        """Handle a client connection."""
        try:
            logger.debug("New connection...")
            if not self._validate_peer_cred(client_sock):
                logger.warning(
                    "Unexpected connection: The user who runs the program must be the same as the user "
                    "who runs the MindIE."
                )
                return

            buffer = self._handle_recv(client_sock, length_field_size)
            if buffer:
                logger.warning(f"Data remaining in buffer: {len(buffer)} bytes.")
        except Exception as e:
            logger.warning(f"Socket server handle error: {str(e)}.", exc_info=True)

    def _handle_recv(self, client_sock, length_field_size):
        buffer = bytearray()
        while True:
            chunk = client_sock.recv(self.buffer_size)
            if not chunk:
                break
            buffer.extend(chunk)

            # Process data frames
            while len(buffer) >= length_field_size:
                data, buffer = self._process_data_frame(buffer, length_field_size)
                if data is not None:
                    self._handle_data(data)
                else:
                    break
        return buffer

    @staticmethod
    def _process_data_frame(buffer, length_field_size):
        """Process a single data frame from the buffer."""
        length = int.from_bytes(buffer[:length_field_size], byteorder='big')
        if len(buffer) >= length_field_size + length:
            data = buffer[length_field_size : length_field_size + length]
            buffer = buffer[length_field_size + length :]
            logger.debug(f"Receive data: {len(data)} bytes.")
            return data, buffer
        return None, buffer

    def _handle_data(self, data):
        """Handle the data by putting it into the queue."""
        try:
            self._check_queue_size()
            self.data_queue.put(data, block=False)
        except queue.Full:
            self._handle_queue_full(data)

    def _check_queue_size(self):
        """Check if the queue size exceeds the warning threshold."""
        if self.data_queue.qsize() > self.warning_queue_size:
            current_time = time.time()
            if current_time - self.last_stack_warning_time >= WARNING_INTERVAL:
                logger.warning(f"Trace data is being stacked: current stacked data count {self.data_queue.qsize()}")
                self.last_stack_warning_time = current_time

    def _handle_queue_full(self, data):
        """Handle the case when the queue is full."""
        current_time = time.time()
        if current_time - self.last_full_warning_time >= WARNING_INTERVAL:
            logger.warning("Trace data queue is full, discarding the oldest data.")
            self.last_full_warning_time = current_time
        self.data_queue.get()
        self.data_queue.put(data, block=False)

    def _server_loop(self):
        """Main server loop."""
        while self.running:
            try:
                self.server_socket.settimeout(self.socket_timeout)
                client_sock, client_addr = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self._handle_client, args=(client_sock, client_addr), daemon=True
                )
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.warning(f"Socket server error: {str(e)}.", exc_info=True)
                break

    def start(self):
        """Start the socket server."""
        if self.running:
            return
        self.running = True
        self.server_socket = self._create_socket()
        self.thread = threading.Thread(target=self._server_loop, daemon=True)
        self.thread.start()

    def get_data(self, timeout=0.5) -> Optional[bytes]:
        """Get data from the queue."""
        try:
            return self.data_queue.get(block=False, timeout=timeout)
        except queue.Empty:
            return None

    def clear_data(self) -> Optional[bytes]:
        """Clear all data from the queue."""
        try:
            return self.data_queue.queue.clear()
        except queue.Empty:
            return None

    def stop(self):
        """Stop the socket server."""
        if not self.running:
            return
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if self.thread and self.thread.is_alive():
            self.thread.join()
        logger.info("Stop socket success.")
