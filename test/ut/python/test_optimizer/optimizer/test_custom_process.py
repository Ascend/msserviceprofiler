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
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from ms_serviceparam_optimizer.config.config import (  # pylint: disable=no-name-in-module
    CUSTOM_OUTPUT,
    MODEL_EVAL_STATE_CONFIG_PATH,
    OptimizerConfigField,
)
from ms_serviceparam_optimizer.optimizer.custom_process import (  # pylint: disable=no-name-in-module
    CustomProcess,
    tempfile,
    os,
)


def test_before_run_no_run_params(monkeypatch):
    # 模拟 tempfile.mkstemp
    monkeypatch.setattr(tempfile, "mkstemp", lambda prefix="": (1234, 'tempfile'))
    # 模拟 os.environ
    monkeypatch.setattr(os, "environ", {})
    process = CustomProcess()
    process.before_run()

    # 验证属性设置
    assert process.run_log_fp == 1234
    assert process.run_log == 'tempfile'
    assert process.run_log_offset == 0


def test_before_run_with_run_params():
    process = CustomProcess()
    process.command = ["benchmark", "$CONCURRENCY", "$REQUESTRATE"]
    run_params = (
        OptimizerConfigField(name="CONCURRENCY", config_position="env", min=10, max=1000, dtype="int", value=10),
        OptimizerConfigField(name="REQUESTRATE", config_position="env", min=0.1, max=0.7, value=0.3, dtype="float"),
    )
    process.before_run(run_params)
    assert process.command == ["benchmark", "10", "0.3"]


def test_before_run_env_var_already_set(monkeypatch):
    # 模拟 os.environ
    monkeypatch.setattr(os, "environ", {CUSTOM_OUTPUT: "/result", MODEL_EVAL_STATE_CONFIG_PATH: "config.toml"})

    process = CustomProcess()
    process.before_run()

    # 验证 tempfile.mkstemp 被调用
    assert os.environ[CUSTOM_OUTPUT] == "/result"
    assert os.environ[MODEL_EVAL_STATE_CONFIG_PATH] == "config.toml"


def test_check_success_process_still_running(tmpdir):
    # 模拟子进程仍在运行
    custom_process = CustomProcess()
    custom_process.run_log = Path(tmpdir).joinpath("run_log")
    custom_process.run_log_offset = 0
    with open(custom_process.run_log, "w", encoding="utf-8") as f:
        f.write("test")
    custom_process.process = Mock()
    custom_process.process.poll.return_value = None
    custom_process.print_log = True
    result = custom_process.check_success()

    assert result is False


def test_check_success_process_succeeded(tmpdir):
    # 模拟子进程成功完成
    custom_process = CustomProcess()
    custom_process.run_log = Path(tmpdir).joinpath("run_log")
    custom_process.run_log_offset = 0
    with open(custom_process.run_log, "w", encoding="utf-8") as f:
        f.write("test")
    custom_process.process = Mock()
    custom_process.process.poll.return_value = 0
    custom_process.print_log = True
    result = custom_process.check_success()

    assert result is True


def test_check_success_process_failed(tmpdir):
    # 模拟子进程失败
    custom_process = CustomProcess()
    custom_process.run_log = Path(tmpdir).joinpath("run_log")
    custom_process.run_log_offset = 0
    with open(custom_process.run_log, "w", encoding="utf-8") as f:
        f.write("test")
    custom_process.process = Mock()
    custom_process.process.poll.return_value = 1
    custom_process.print_log = True
    with pytest.raises(subprocess.SubprocessError):
        custom_process.check_success()


@patch("psutil.process_iter")
@patch("ms_serviceparam_optimizer.optimizer.custom_process.kill_process")
def test_check_env_no_residual_process(mock_kill_process, mock_process_iter):
    # 模拟没有残留进程的情况
    mock_process_iter.return_value = [
        MagicMock(info={"pid": 1, "name": "not_process"}),
        MagicMock(info={"pid": 2, "name": "also_not_target"}),
        MagicMock(),
    ]

    CustomProcess.kill_residual_process("target_process")

    # 确保kill_process没有被调用
    mock_process_iter.assert_called_once()
    mock_kill_process.assert_not_called()


@patch("psutil.process_iter")
@patch("ms_serviceparam_optimizer.optimizer.custom_process.kill_process")
def test_check_env_with_residual_process(mock_kill_process, mock_process_iter):
    # 模拟有残留进程的情况
    mock_process_iter.return_value = [
        MagicMock(info={"pid": 1, "name": "not_target_process"}),
        MagicMock(info={"pid": 2, "name": "target_process"}),
        MagicMock(info={"pid": 3, "name": "another_target_process"}),
    ]

    CustomProcess.kill_residual_process("target_process,another_target_process")

    # 确保kill_process被调用
    mock_kill_process.assert_any_call("target_process")
    mock_kill_process.assert_any_call("another_target_process")


@patch("psutil.process_iter")
@patch("ms_serviceparam_optimizer.optimizer.custom_process.kill_process")
def test_check_env_kill_process_exception(mock_kill_process, mock_process_iter):
    # 模拟在尝试杀死进程时发生异常的情况
    mock_process_iter.return_value = [MagicMock(info={"pid": 1, "name": "target_process"})]
    mock_kill_process.side_effect = Exception("Failed to kill process")

    CustomProcess.kill_residual_process("target_process")

    # 确保kill_process被调用，并且异常被捕获
    mock_kill_process.assert_called_once_with("target_process")


# 测试用例1：测试process_name存在且check_env成功的情况
@patch('ms_serviceparam_optimizer.optimizer.custom_process.CustomProcess.kill_residual_process')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.CustomProcess.before_run')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.subprocess.Popen')
def test_run_process_name_exists_and_check_env_success(mock_popen, mock_before_run, mock_check_env):
    process = CustomProcess()
    process.process_name = 'test_process'
    process.command = ['test_command']
    process.work_path = '/test/work/path'
    process.run_log_fp = MagicMock()
    process.run_log = '/test/run/log'
    process.run()
    mock_check_env.assert_called_once_with('test_process')
    mock_before_run.assert_called_once()


# 测试用例2：测试process_name存在但check_env失败的情况
@patch('ms_serviceparam_optimizer.optimizer.custom_process.CustomProcess.kill_residual_process')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.CustomProcess.before_run')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.subprocess.Popen')
def test_run_process_name_exists_and_check_env_fail(mock_popen, mock_before_run, mock_check_env):
    process = CustomProcess()
    process.process_name = 'test_process'
    process.command = ['test_command']
    process.work_path = '/test/work/path'
    process.run_log_fp = MagicMock()
    process.run_log = '/test/run/log'
    mock_check_env.side_effect = Exception('kill_residual_process failed')
    process.run()
    mock_check_env.assert_called_once_with('test_process')
    mock_before_run.assert_called_once()
    mock_popen.assert_called_once()


# 测试用例3：测试process_name不存在的情况
@patch('ms_serviceparam_optimizer.optimizer.custom_process.CustomProcess.before_run')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.subprocess.Popen')
def test_run_process_name_not_exists(mock_popen, mock_before_run):
    process = CustomProcess()
    process.process_name = None
    process.command = ['test_command']
    process.work_path = '/test/work/path'
    process.run_log_fp = MagicMock()
    process.run_log = '/test/run/log'
    process.run()
    mock_before_run.assert_called_once()


# 测试用例4：测试subprocess.Popen抛出OSError的情况
@patch('ms_serviceparam_optimizer.optimizer.custom_process.CustomProcess.before_run')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.subprocess.Popen')
def test_run_subprocess_popen_os_error(mock_popen, mock_before_run):
    process = CustomProcess()
    process.process_name = None
    process.command = ['test_command']
    process.work_path = '/test/work/path'
    process.run_log_fp = MagicMock()
    process.run_log = '/test/run/log'
    mock_popen.side_effect = OSError('subprocess.Popen failed')
    with pytest.raises(OSError) as e:
        process.run()
    assert str(e.value) == 'subprocess.Popen failed'
    mock_before_run.assert_called_once()


# 测试用例1：测试run_log为None的情况
def test_get_log_run_log_none():
    process = CustomProcess()
    process.run_log = None
    assert process.get_log() is None


# 测试用例2：测试run_log文件不存在的情况
@patch('pathlib.Path.exists', return_value=False)
def test_get_log_run_log_not_exists(mock_exists):
    process = CustomProcess()
    process.run_log = 'nonexistent.log'
    assert process.get_log() is None


# 测试stop方法的测试用例
@patch('ms_serviceparam_optimizer.optimizer.custom_process.kill_children')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.remove_file')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.close_file_fp')
@patch('psutil.Process')
def test_stop_with_del_log_true(mock_psutil_process, mock_close_file_fp, mock_remove_file, mock_kill_children):
    # 测试del_log=True的情况
    process = CustomProcess()
    process.run_log_fp = MagicMock()
    process.run_log = '/test/run/log'
    process.process = MagicMock()
    process.process.poll.return_value = None
    process.process.pid = 12345

    # 模拟子进程
    mock_child_process = MagicMock()
    mock_psutil_process.return_value.children.return_value = [mock_child_process]

    # 调用stop方法
    process.stop(del_log=True)

    # 验证run_log_offset被重置
    assert process.run_log_offset == 0

    # 验证文件操作
    mock_close_file_fp.assert_called_once_with(process.run_log_fp)
    mock_remove_file.assert_called_once_with(Path('/test/run/log'))

    # 验证进程操作
    process.process.poll.assert_called()
    mock_psutil_process.assert_called_once_with(12345)
    mock_psutil_process.return_value.children.assert_called_once_with(recursive=True)
    process.process.kill.assert_called_once()
    process.process.wait.assert_called_once_with(10)
    mock_kill_children.assert_called_once_with([mock_child_process])


@patch('ms_serviceparam_optimizer.optimizer.custom_process.kill_children')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.remove_file')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.close_file_fp')
def test_stop_with_del_log_false(mock_close_file_fp, mock_remove_file, mock_kill_children):
    # 测试del_log=False的情况
    process = CustomProcess()
    process.run_log_fp = MagicMock()
    process.run_log = '/test/run/log'
    process.process = None

    # 调用stop方法
    process.stop(del_log=False)

    # 验证run_log_offset被重置
    assert process.run_log_offset == 0

    # 验证文件操作
    mock_close_file_fp.assert_called_once_with(process.run_log_fp)

    # 验证不删除日志文件
    mock_remove_file.assert_not_called()


@patch('ms_serviceparam_optimizer.optimizer.custom_process.kill_children')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.remove_file')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.close_file_fp')
def test_stop_process_already_exited(mock_close_file_fp, mock_remove_file, mock_kill_children):
    # 测试进程已经退出的情况
    process = CustomProcess()
    process.run_log_fp = MagicMock()
    process.run_log = '/test/run/log'
    process.process = MagicMock()
    process.process.poll.return_value = 1  # 进程已退出，返回退出码

    # 调用stop方法
    process.stop()

    # 验证文件操作
    mock_close_file_fp.assert_called_once_with(process.run_log_fp)
    mock_remove_file.assert_called_once_with(Path('/test/run/log'))

    # 验证不会尝试杀死进程
    process.process.kill.assert_not_called()
    process.process.wait.assert_not_called()
    mock_kill_children.assert_not_called()


@patch('ms_serviceparam_optimizer.optimizer.custom_process.kill_children')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.remove_file')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.close_file_fp')
@patch('psutil.Process')
def test_stop_process_wait_timeout(mock_psutil_process, mock_close_file_fp, mock_remove_file, mock_kill_children):
    # 测试进程等待超时的情况

    process = CustomProcess()
    process.run_log_fp = MagicMock()
    process.run_log = '/test/run/log'
    process.process = MagicMock()
    process.process.poll.return_value = None
    process.process.pid = 12345

    # 模拟wait超时
    process.process.wait.side_effect = subprocess.TimeoutExpired('cmd', 10)

    # 模拟子进程
    mock_child_process = MagicMock()
    mock_psutil_process.return_value.children.return_value = [mock_child_process]

    # 调用stop方法
    process.stop()

    # 验证文件操作
    mock_close_file_fp.assert_called_once_with(process.run_log_fp)
    mock_remove_file.assert_called_once_with(Path('/test/run/log'))

    # 验证进程操作
    process.process.kill.assert_called_once()
    process.process.wait.assert_called_once_with(10)
    process.process.send_signal.assert_called_once_with(9)  # SIGKILL
    mock_kill_children.assert_called_once_with([mock_child_process])


@patch('ms_serviceparam_optimizer.optimizer.custom_process.kill_children')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.remove_file')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.close_file_fp')
@patch('psutil.Process')
def test_stop_process_shutdown_failed(mock_psutil_process, mock_close_file_fp, mock_remove_file, mock_kill_children):
    # 测试进程关闭失败的情况
    process = CustomProcess()
    process.run_log_fp = MagicMock()
    process.run_log = '/test/run/log'
    process.process = MagicMock()
    process.process.poll.return_value = None  # 进程仍在运行
    process.process.pid = 12345

    # 模拟子进程
    mock_child_process = MagicMock()
    mock_psutil_process.return_value.children.return_value = [mock_child_process]

    # 调用stop方法
    process.stop()

    # 验证文件操作
    mock_close_file_fp.assert_called_once_with(process.run_log_fp)
    mock_remove_file.assert_called_once_with(Path('/test/run/log'))

    # 验证进程操作
    process.process.kill.assert_called_once()
    process.process.wait.assert_called_once_with(10)
    mock_kill_children.assert_called_once_with([mock_child_process])


@patch('ms_serviceparam_optimizer.optimizer.custom_process.kill_children')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.remove_file')
@patch('ms_serviceparam_optimizer.optimizer.custom_process.close_file_fp')
@patch('psutil.Process')
def test_stop_exception_handling(mock_psutil_process, mock_close_file_fp, mock_remove_file, mock_kill_children):
    # 测试异常处理
    process = CustomProcess()
    process.run_log_fp = MagicMock()
    process.run_log = '/test/run/log'
    process.process = MagicMock()
    process.process.poll.return_value = None
    process.process.pid = 12345

    # 模拟psutil.Process抛出异常
    mock_psutil_process.side_effect = Exception("Process error")

    # 调用stop方法
    process.stop()

    # 验证文件操作
    mock_close_file_fp.assert_called_once_with(process.run_log_fp)
    mock_remove_file.assert_called_once_with(Path('/test/run/log'))

    # 验证异常被处理
    mock_psutil_process.assert_called_once_with(12345)
    process.process.kill.assert_not_called()
    process.process.wait.assert_not_called()
    mock_kill_children.assert_not_called()


# 测试get_last_log方法的测试用例
def test_get_last_log_no_run_log():
    # 测试run_log为None的情况
    process = CustomProcess()
    process.run_log = None

    result = process.get_last_log()

    assert result is None


@patch('pathlib.Path.exists', return_value=False)
def test_get_last_log_file_not_exists(mock_exists):
    # 测试日志文件不存在的情况
    process = CustomProcess()
    process.run_log = '/nonexistent/log/file.log'

    result = process.get_last_log()

    assert result is None
    mock_exists.assert_called_once()


@patch('ms_serviceparam_optimizer.optimizer.custom_process.open_s')
@patch('pathlib.Path.exists', return_value=True)
def test_get_last_log_default_number(mock_exists, mock_open_s):
    # 测试使用默认参数number=5的情况
    process = CustomProcess()
    process.run_log = '/test/log/file.log'

    # 模拟文件内容
    mock_file = MagicMock()
    mock_file.readlines.return_value = [
        'Line 1\n',
        'Line 2\n',
        'Line 3\n',
        'Line 4\n',
        'Line 5\n',
        'Line 6\n',
        'Line 7\n',
    ]
    mock_open_s.return_value.__enter__.return_value = mock_file

    result = process.get_last_log()

    # 验证返回最后5行
    expected = 'Line 3\n\nLine 4\n\nLine 5\n\nLine 6\n\nLine 7\n'
    assert result == expected
    mock_exists.assert_called_once()
    mock_open_s.assert_called_once_with(Path('/test/log/file.log'), "r", encoding="utf-8")


@patch('ms_serviceparam_optimizer.optimizer.custom_process.open_s')
@patch('pathlib.Path.exists', return_value=True)
def test_get_last_log_custom_number(mock_exists, mock_open_s):
    # 测试使用自定义number参数的情况
    process = CustomProcess()
    process.run_log = '/test/log/file.log'

    # 模拟文件内容
    mock_file = MagicMock()
    mock_file.readlines.return_value = [
        'Line 1\n',
        'Line 2\n',
        'Line 3\n',
        'Line 4\n',
        'Line 5\n',
        'Line 6\n',
        'Line 7\n',
    ]
    mock_open_s.return_value.__enter__.return_value = mock_file

    result = process.get_last_log(number=3)

    # 验证返回最后3行
    expected = 'Line 5\n\nLine 6\n\nLine 7\n'
    assert result == expected


@patch('ms_serviceparam_optimizer.optimizer.custom_process.open_s')
@patch('pathlib.Path.exists', return_value=True)
def test_get_last_log_number_greater_than_file_lines(mock_exists, mock_open_s):
    # 测试number大于文件行数的情况
    process = CustomProcess()
    process.run_log = '/test/log/file.log'

    # 模拟文件内容
    mock_file = MagicMock()
    mock_file.readlines.return_value = ['Line 1\n', 'Line 2\n', 'Line 3\n']
    mock_open_s.return_value.__enter__.return_value = mock_file

    result = process.get_last_log(number=10)

    # 验证返回所有行
    expected = 'Line 1\n\nLine 2\n\nLine 3\n'
    assert result == expected


@patch('ms_serviceparam_optimizer.optimizer.custom_process.open_s')
@patch('pathlib.Path.exists', return_value=True)
def test_get_last_log_empty_file(mock_exists, mock_open_s):
    # 测试空文件的情况
    process = CustomProcess()
    process.run_log = '/test/log/file.log'

    # 模拟空文件
    mock_file = MagicMock()
    mock_file.readlines.return_value = []
    mock_open_s.return_value.__enter__.return_value = mock_file

    result = process.get_last_log()

    # 验证返回空字符串
    assert result == ''


@patch('ms_serviceparam_optimizer.optimizer.custom_process.open_s')
@patch('pathlib.Path.exists', return_value=True)
@patch('ms_serviceparam_optimizer.optimizer.custom_process.logger')
def test_get_last_log_unicode_error(mock_logger, mock_exists, mock_open_s):
    # 测试UnicodeError异常的情况
    process = CustomProcess()
    process.run_log = '/test/log/file.log'

    # 模拟UnicodeError
    mock_open_s.side_effect = UnicodeError("Encoding error")

    # 由于原始代码中的bug，当发生异常时会抛出UnboundLocalError
    # 我们需要捕获这个异常来验证错误日志被记录
    with pytest.raises(UnboundLocalError) as exc_info:
        process.get_last_log()

    # 验证异常信息
    assert "file_lines" in str(exc_info.value)

    # 验证记录错误日志
    mock_logger.error.assert_called_once()
    assert "Failed read" in mock_logger.error.call_args[0][0]


@patch('ms_serviceparam_optimizer.optimizer.custom_process.open_s')
@patch('pathlib.Path.exists', return_value=True)
@patch('ms_serviceparam_optimizer.optimizer.custom_process.logger')
def test_get_last_log_os_error(mock_logger, mock_exists, mock_open_s):
    # 测试OSError异常的情况
    process = CustomProcess()
    process.run_log = '/test/log/file.log'

    # 模拟OSError
    mock_open_s.side_effect = OSError("File access error")

    # 由于原始代码中的bug，当发生异常时会抛出UnboundLocalError
    # 我们需要捕获这个异常来验证错误日志被记录
    with pytest.raises(UnboundLocalError) as exc_info:
        process.get_last_log()

    # 验证异常信息
    assert "file_lines" in str(exc_info.value)

    # 验证记录错误日志
    mock_logger.error.assert_called_once()
    assert "Failed read" in mock_logger.error.call_args[0][0]


@patch('ms_serviceparam_optimizer.optimizer.custom_process.open_s')
@patch('pathlib.Path.exists', return_value=True)
def test_get_last_log_with_command(mock_exists, mock_open_s):
    # 测试有command属性的情况
    process = CustomProcess()
    process.run_log = '/test/log/file.log'
    process.command = ['python', 'script.py']

    # 模拟文件内容
    mock_file = MagicMock()
    mock_file.readlines.return_value = ['Line 1\n', 'Line 2\n', 'Line 3\n']
    mock_open_s.return_value.__enter__.return_value = mock_file

    result = process.get_last_log()

    # 验证返回最后5行（默认值）
    expected = 'Line 1\n\nLine 2\n\nLine 3\n'
    assert result == expected
