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

import os
import stat
import sys
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from ms_service_profiler.utils.file_open_check import (
    FileStat,
    OpenException,
    UmaskWrapper,
    check_file_exists_and_type,
    check_file_owner,
    check_file_size,
    is_legal_args_path_string,
    is_legal_path_length,
    is_match_path_white_list,
    ms_open,
    sanitize_csv_value,
    solution_log,
    solution_log_win,
)
from ms_service_profiler.utils.log import logger

MAX_SIZE_UNLIMITE = -1


class TestPathValidation:
    @pytest.mark.parametrize(
        "platform,path,expected",
        [
            ("linux", os.path.join("/", *["a" * 255 for _ in range(16)]), True),
            ("linux", os.path.join("/", "a" * 256), True),
            ("linux", os.path.join("/", "a" * 4097), True),
            ("linux", os.path.join("/", *["a" * 255 for _ in range(17)]), True),
            ("win32", os.path.join("C:\\", "a" * 256), True),
            ("win32", os.path.join("C:\\", "a" * 252), True),
            ("win32", os.path.join("C:\\", "a" * 258), True),
        ],
    )
    def test_legal_path_length(self, platform, path, expected, monkeypatch):
        monkeypatch.setattr(sys, "platform", platform)
        assert is_legal_path_length(path) == expected

    @pytest.mark.parametrize(
        "platform,path,expected",
        [
            ("linux", "bad$path", False),
            ("win32", "bad:path", False),
        ],
    )
    @patch("ms_service_profiler.utils.file_open_check.PATH_WHITE_LIST_REGEX_WIN")
    @patch("ms_service_profiler.utils.constants.PATH_WHITE_LIST_REGEX")
    def test_is_match_path_white_list(self, mock_linux_regex, mock_win_regex, platform, path, expected, monkeypatch):
        monkeypatch.setattr(sys, "platform", platform)
        if platform == "linux":
            mock_linux_regex.search.return_value = True
        else:
            mock_win_regex.search.return_value = True
        assert is_match_path_white_list(path) == expected


class TestFileStat:
    @patch("os.readlink")
    @patch("os.path.islink")
    @patch("os.stat")
    @patch.dict(os.environ, {"RAW_INPUT_PATH": "/valid/path"})
    def test_softlink_validation(self, mock_stat, mock_islink, mock_readlink):
        mock_readlink.return_value = "/valid/path/target"
        mock_islink.return_value = True
        mock_stat_result = MagicMock()
        mock_stat_result.st_mode = stat.S_IFLNK
        mock_stat.return_value = mock_stat_result

        fs_stat = FileStat("/test/link")
        assert fs_stat.check_basic_permission() is True


class TestCSVSanitization:
    @pytest.mark.parametrize(
        "value,error_mode,expected",
        [
            ("=cmd|", "strict", ValueError),
            ("=cmd|", "replace", " =cmd|"),
            (123, "ignore", 123),
        ],
    )
    @patch("ms_service_profiler.utils.file_open_check.MALICIOUS_CSV_PATTERN")
    def test_sanitize_csv_value(self, mock_pattern, value, error_mode, expected):
        mock_pattern.search.return_value = True

        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                sanitize_csv_value(value, error_mode)
        else:
            assert sanitize_csv_value(value, error_mode) == expected


class TestMsOpen:
    @staticmethod
    def test_read_mode_file_size_exceeded():
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isfile", return_value=True),
            patch("os.path.isdir", return_value=False),
            patch("ms_service_profiler.utils.file_open_check.FileStat") as mock_filestat,
        ):
            mock_filestat.return_value = Mock(is_exists=True, is_file=True, is_dir=False, file_size=150, is_owner=True)
            with pytest.raises(OpenException) as exc:
                with ms_open("/test/file", "r", max_size=100):
                    pass
            assert "exceeded" in str(exc.value).lower()

    @staticmethod
    def test_write_mode_permission_denied():
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isfile", return_value=True),
            patch("os.path.isdir", return_value=False),
            patch("ms_service_profiler.utils.file_open_check.FileStat") as mock_filestat,
        ):
            mock_filestat.return_value = Mock(is_exists=True, is_file=True, is_dir=False, is_owner=False)
            with pytest.raises(OpenException) as exc:
                with ms_open("/test/file", "w"):
                    pass
            assert "owner is inconsistent" in str(exc.value).lower()

    @staticmethod
    def test_append_mode_directory_path():
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isfile", return_value=False),
            patch("os.path.isdir", return_value=True),
            patch("ms_service_profiler.utils.file_open_check.FileStat") as mock_filestat,
        ):
            mock_filestat.return_value = Mock(is_exists=True, is_file=False, is_dir=True)
            with pytest.raises(OpenException) as exc:
                with ms_open("/test/file", "a"):
                    pass
            assert "but it's a folder" in str(exc.value).lower()

    @pytest.mark.parametrize("mode,exists", [("r", False)])
    @patch("os.path.exists", return_value=False)
    def test_open_exceptions(self, mock_exists, mode, exists):
        with pytest.raises(OpenException):
            with ms_open("/test/file", mode):
                pass


class TestUmaskWrapper:
    @staticmethod
    def test_umask_behavior():
        original = os.umask(0o022)
        try:
            with UmaskWrapper(umask=0o027):
                current = os.umask(0o077)
                assert current == 0o027
            final = os.umask(original)
            assert final == 0o022
        finally:
            os.umask(original)


class TestHelpers:
    @staticmethod
    def test_solution_logging():
        handlers = logger.handlers[:]
        for handler in handlers:
            logger.removeHandler(handler)

        with patch.object(logger, "log") as mock_log:
            solution_level = 35
            solution_level_win = 45

            solution_log("test_path")
            solution_log_win("test_win_path")

            expected_calls = [
                call(solution_level, "visit %s for detailed solution", "test_path"),
                call(solution_level_win, "visit %s for detailed solution", "test_win_path"),
            ]

            mock_log.assert_has_calls(expected_calls, any_order=True)
            assert mock_log.call_count == 2


class TestFileStatProperties:
    @pytest.fixture
    def mock_file_stat(self):
        return MagicMock(st_mode=stat.S_IFREG, st_size=1024, st_uid=1000, st_gid=1000)

    @patch("ms_service_profiler.utils.file_open_check.is_legal_path_length", return_value=True)
    @patch("ms_service_profiler.utils.file_open_check.is_match_path_white_list", return_value=True)
    def test_properties_with_file_stat(self, mock_white, mock_legal, mock_file_stat):
        fs = FileStat("/valid/path")
        fs.file_stat = mock_file_stat

        assert fs.is_file is True
        assert fs.is_dir is False
        assert fs.file_size == 1024
        assert fs.permission == stat.S_IMODE(mock_file_stat.st_mode)
        assert fs.owner == 1000
        assert fs.group_owner == 1000

    @patch("ms_service_profiler.utils.file_open_check.is_legal_path_length", return_value=True)
    @patch("ms_service_profiler.utils.file_open_check.is_match_path_white_list", return_value=True)
    def test_properties_without_file_stat(self, mock_white, mock_legal):
        fs = FileStat("/valid/not_exist")
        fs.file_stat = None

        assert fs.is_file is False
        assert fs.is_dir is False
        assert fs.file_size == 0
        assert fs.permission == 0o777
        assert fs.owner == -1
        assert fs.group_owner == -1

    @patch("ms_service_profiler.utils.file_open_check.is_legal_path_length", return_value=True)
    @patch("ms_service_profiler.utils.file_open_check.is_match_path_white_list", return_value=True)
    @patch("os.geteuid")
    @patch("os.getgroups")
    def test_ownership_properties(self, mock_getgroups, mock_geteuid, mock_white, mock_legal):
        fs = FileStat("/valid/path")
        fs.file_stat = MagicMock(st_uid=1000, st_gid=1000)
        mock_geteuid.return_value = 1000
        mock_getgroups.return_value = [1000, 2000]

        assert fs.is_owner is True
        assert fs.is_group_owner is True
        assert fs.is_user_or_group_owner is True
        assert fs.is_user_and_group_owner is True


class TestFileStatInit:
    @staticmethod
    def test_stat_permission_error(monkeypatch):
        monkeypatch.setattr("ms_service_profiler.utils.file_open_check.is_legal_path_length", lambda x: True)
        monkeypatch.setattr("ms_service_profiler.utils.file_open_check.is_match_path_white_list", lambda x: True)
        monkeypatch.setattr(os.path, "exists", lambda x: True)

        def mock_stat(path):
            raise PermissionError("Permission denied")

        monkeypatch.setattr(os, "stat", mock_stat)

        with pytest.raises(PermissionError):
            FileStat("/no/permission/path")

    @pytest.fixture
    def mock_os_functions(self, monkeypatch):
        monkeypatch.setattr(os.path, "exists", lambda x: True)
        mock_stat = MagicMock(st_mode=0o777, st_uid=1000, st_gid=1000)
        monkeypatch.setattr(os, "stat", lambda x: mock_stat)
        monkeypatch.setattr(os.path, "realpath", lambda x: x)
        return mock_stat

    @patch("ms_service_profiler.utils.file_open_check.is_legal_path_length", return_value=True)
    @patch("ms_service_profiler.utils.file_open_check.is_match_path_white_list", return_value=True)
    def test_path_with_spaces(self, mock_white, mock_legal):
        fs = FileStat("/path with spaces/file.txt")
        assert fs.file == "/path with spaces/file.txt"


class TestLegalArgsPathString:
    @patch("ms_service_profiler.utils.file_open_check.is_legal_path_length")
    @patch("ms_service_profiler.utils.file_open_check.is_match_path_white_list")
    def test_path_validation(self, mock_white, mock_legal):
        assert is_legal_args_path_string("") is True

        mock_legal.return_value = False
        assert is_legal_args_path_string("path") is False

        mock_legal.return_value = True
        mock_white.return_value = False
        assert is_legal_args_path_string("path") is False

        mock_white.return_value = True
        assert is_legal_args_path_string("path") is True


class TestIsBasicallyLegal:
    @patch("ms_service_profiler.utils.file_open_check.is_legal_path_length", return_value=True)
    @patch("ms_service_profiler.utils.file_open_check.is_match_path_white_list", return_value=True)
    @patch.object(FileStat, "check_windows_permission")
    @patch.object(FileStat, "check_linux_permission")
    def test_platform_specific(self, mock_linux, mock_win, mock_white, mock_legal, monkeypatch):
        fs = FileStat("/valid/path")
        monkeypatch.setattr(sys, "platform", "win32")
        fs.is_basically_legal(perm="read")
        mock_win.assert_called_once_with("read")

        monkeypatch.setattr(sys, "platform", "linux")
        fs.is_basically_legal(perm="write", strict_permission=False)
        mock_linux.assert_called_once_with("write", strict_permission=False)


class TestCheckBasicPermission:
    @staticmethod
    def test_softlink_validation(setup_softlink, monkeypatch):
        monkeypatch.setattr("ms_service_profiler.utils.file_open_check.is_legal_path_length", lambda x: True)
        monkeypatch.setattr("ms_service_profiler.utils.file_open_check.is_match_path_white_list", lambda x: True)

        fs = FileStat("/symlink/path")
        monkeypatch.delenv("RAW_INPUT_PATH", raising=False)
        with (
            patch("ms_service_profiler.utils.file_open_check.logger.error") as mock_logger,
            patch("ms_service_profiler.utils.file_open_check.solution_log") as mock_solution,
        ):
            assert fs.check_basic_permission() is True
            mock_logger.assert_not_called()
            mock_solution.assert_not_called()

    @staticmethod
    def test_nonexistent_file(monkeypatch):
        monkeypatch.setattr("ms_service_profiler.utils.file_open_check.is_legal_path_length", lambda x: True)
        monkeypatch.setattr("ms_service_profiler.utils.file_open_check.is_match_path_white_list", lambda x: True)
        monkeypatch.setattr(os.path, "exists", lambda x: False)

        fs = FileStat("/non/existent/path")

        with patch("ms_service_profiler.utils.file_open_check.logger.error") as mock_logger:
            assert fs.check_basic_permission(perm="read") is False
            mock_logger.assert_called_once_with(
                "path: %s not exist, please check if file or dir is exist", "/non/existent/path"
            )

    @pytest.fixture
    def setup_softlink(self, monkeypatch):
        monkeypatch.setattr(os.path, "exists", lambda x: True)
        monkeypatch.setattr(os.path, "islink", lambda x: True)
        mock_stat = MagicMock(st_mode=stat.S_IFLNK)
        monkeypatch.setattr(os, "stat", lambda x: mock_stat)
        monkeypatch.setattr(os, "readlink", lambda x: "/fake/target")
        monkeypatch.setattr(os.path, "abspath", lambda x: x)
        monkeypatch.setattr(os.path, "normpath", lambda x: x)


class TestCheckLinuxPermission:
    @staticmethod
    def test_not_owner_or_group(mock_file_stat, mock_non_owner, monkeypatch):
        monkeypatch.setattr("ms_service_profiler.utils.file_open_check.is_legal_path_length", lambda x: True)
        monkeypatch.setattr("ms_service_profiler.utils.file_open_check.is_match_path_white_list", lambda x: True)

        fs = FileStat("/valid/path")
        with (
            patch("ms_service_profiler.utils.file_open_check.logger.error") as mock_logger,
            patch("ms_service_profiler.utils.file_open_check.solution_log") as mock_solution,
        ):
            assert fs.check_linux_permission() is True
            mock_logger.assert_not_called()
            mock_solution.assert_not_called()

    @pytest.fixture
    def mock_file_stat(self, monkeypatch):
        mock_stat = MagicMock(st_mode=stat.S_IFREG | 0o755, st_uid=1000, st_gid=1000)
        monkeypatch.setattr(os, "stat", lambda x: mock_stat)
        monkeypatch.setattr(os.path, "exists", lambda x: True)
        return mock_stat

    @pytest.fixture
    def mock_owner(self, monkeypatch):
        monkeypatch.setattr(os, "geteuid", lambda: 1000)
        monkeypatch.setattr(os, "getgroups", lambda: [1000])

    @pytest.fixture
    def mock_non_owner(self, monkeypatch):
        monkeypatch.setattr(os, "geteuid", lambda: 2000)
        monkeypatch.setattr(os, "getgroups", lambda: [2000])

    @pytest.mark.parametrize("perm_mode,strict", [("read", True), ("read", False)])
    def test_read_permission_violation(self, mock_file_stat, mock_owner, perm_mode, strict, monkeypatch):
        monkeypatch.setattr("ms_service_profiler.utils.file_open_check.is_legal_path_length", lambda x: True)
        monkeypatch.setattr("ms_service_profiler.utils.file_open_check.is_match_path_white_list", lambda x: True)

        mock_file_stat.st_mode = stat.S_IFREG | 0o777
        fs = FileStat("/valid/path")

        with (
            patch("ms_service_profiler.utils.file_open_check.logger.error") as mock_logger,
            patch("ms_service_profiler.utils.file_open_check.solution_log") as mock_solution,
        ):
            assert fs.check_linux_permission(perm=perm_mode, strict_permission=strict) is True
            mock_logger.assert_not_called()
            mock_solution.assert_not_called()

    @pytest.mark.parametrize("is_file,strict", [(True, True), (False, False)])
    def test_write_permission_violation(self, mock_file_stat, mock_owner, is_file, strict, monkeypatch):
        monkeypatch.setattr("ms_service_profiler.utils.file_open_check.is_legal_path_length", lambda x: True)
        monkeypatch.setattr("ms_service_profiler.utils.file_open_check.is_match_path_white_list", lambda x: True)

        mode = stat.S_IFREG | 0o755 if is_file else stat.S_IFDIR | 0o755
        mock_file_stat.st_mode = mode
        fs = FileStat("/valid/path")

        with (
            patch("ms_service_profiler.utils.file_open_check.logger.error") as mock_logger,
            patch("ms_service_profiler.utils.file_open_check.solution_log") as mock_solution,
        ):
            assert fs.check_linux_permission(perm="write", strict_permission=strict) is True
            mock_logger.assert_not_called()
            mock_solution.assert_not_called()


class MockFileStat:
    def __init__(self, is_exists=False, is_dir=False, file_size=0, is_owner=False):
        self.is_exists = is_exists
        self.is_dir = is_dir
        self.file_size = file_size
        self.is_owner = is_owner


def test_check_file_exists_and_type_directory():
    file_stat = MockFileStat(is_exists=True, is_dir=True)
    with pytest.raises(OpenException) as excinfo:
        check_file_exists_and_type(file_stat, "/test/path")
    assert "Expecting a file, but it's a folder" in str(excinfo.value)


def test_check_file_exists_and_type_not_exist():
    file_stat = MockFileStat(is_exists=False)
    check_file_exists_and_type(file_stat, "/test/path")


def test_check_file_exists_and_type_valid_file():
    file_stat = MockFileStat(is_exists=True, is_dir=False)
    check_file_exists_and_type(file_stat, "/test/path")


def test_check_file_size_null_max_size():
    file_stat = MockFileStat()
    with pytest.raises(OpenException) as excinfo:
        check_file_size(file_stat, "/test/path", max_size=None)
    assert "must have a size limit control" in str(excinfo.value)


def test_check_file_size_unlimited():
    file_stat = MockFileStat(file_size=999999)
    check_file_size(file_stat, "/test/path", max_size=MAX_SIZE_UNLIMITE)


def test_check_file_size_exceed_limit():
    file_stat = MockFileStat(file_size=100)
    with pytest.raises(OpenException) as excinfo:
        check_file_size(file_stat, "/test/path", max_size=50)
    assert "exceeded the specifications" in str(excinfo.value)


def test_check_file_size_valid():
    file_stat = MockFileStat(file_size=100)
    check_file_size(file_stat, "/test/path", max_size=100)


def test_check_file_owner_invalid():
    file_stat = MockFileStat(is_owner=False)
    with pytest.raises(OpenException) as excinfo:
        check_file_owner(file_stat, "/test/path")
    assert "inconsistent with the current process user" in str(excinfo.value)


def test_check_file_owner_valid():
    file_stat = MockFileStat(is_owner=True)
    check_file_owner(file_stat, "/test/path")
