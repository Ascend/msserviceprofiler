import pytest

from ms_service_profiler.cli import ROOT_HELP, create_parser, get_version_text, run_parser


def test_root_help_uses_unified_sections(capsys):
    parser = create_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "Description:" in output
    assert "Usage:" in output
    assert "Commands:" in output
    assert "Examples:" in output
    assert "Troubleshooting:" in output
    assert "msserviceprofiler --version" in output


def test_root_version_uses_mindstudio_format():
    version_text = get_version_text()

    assert ">>>>>   MindStudio   <<<<<" in version_text
    assert "msserviceprofiler" in version_text
    assert "Copyright (C) 2026 Huawei Technologies Co., Ltd." in version_text
    assert "License: Mulan PSL v2." in version_text
    assert "Build Info:" in version_text
    assert "Repo : https://gitcode.com/Ascend/msserviceprofiler" in version_text


def test_root_version_action_preserves_multiline_output(capsys):
    parser = create_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "=================================================================\n" in output
    assert "\nBuild Info:\n" in output
    assert "\n  Repo : https://gitcode.com/Ascend/msserviceprofiler" in output


def test_run_parser_without_args_prints_root_help(monkeypatch, capsys):
    parser = create_parser()
    monkeypatch.setattr("sys.argv", ["msserviceprofiler"])

    run_parser(parser)

    assert capsys.readouterr().out == ROOT_HELP
