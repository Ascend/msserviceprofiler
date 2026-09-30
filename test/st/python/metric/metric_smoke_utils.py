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

import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_METRIC_SOURCE = "https://gitcode.com/Ascend/msserviceprofiler.git"
DEFAULT_METRIC_REF = "master"
GENERATE_COUNT_METRIC = "vllm_profiling_engine:generate:duration_count"


class MetricSmokeError(AssertionError):
    pass


@dataclass
class PreflightReport:
    lines: list[str] = field(default_factory=list)

    def pass_(self, name: str, detail: str) -> None:
        self.lines.append(f"[preflight:{name}] PASS: {detail}")

    def warn(self, name: str, detail: str) -> None:
        self.lines.append(f"[preflight:{name}] WARN: {detail}")

    def fail(self, name: str, detail: str) -> None:
        self.lines.append(f"[preflight:{name}] FAIL: {detail}")
        raise MetricSmokeError(str(self))

    def __str__(self) -> str:
        return "\n".join(self.lines)


def run_command(command: list[str], cwd: Optional[str] = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        check=False,
    )


def require_command(command: str, report: PreflightReport) -> None:
    path = shutil.which(command)
    if not path:
        report.fail("command", f"required command not found: {command}")
    report.pass_("command", f"{command} -> {path}")


def check_model_path(model_path: str, report: PreflightReport) -> None:
    path = Path(model_path)
    if not path.exists():
        report.fail("model", f"model path not found: {model_path}")
    if path.is_dir():
        markers = ("config.json", "tokenizer.json", "tokenizer_config.json")
        if not any((path / marker).exists() for marker in markers):
            report.warn("model", f"{model_path} exists but no common model marker file was found")
        else:
            report.pass_("model", f"{model_path}")
        return
    report.pass_("model", f"{model_path} exists")


def _parse_visible_devices(fallback_devices: Iterable[int]) -> list[int]:
    explicit_devices = [int(device) for device in fallback_devices]
    if explicit_devices:
        return explicit_devices

    visible = os.environ.get("ASCEND_RT_VISIBLE_DEVICES", "").strip()
    if visible and visible.lower() not in ("all", "none"):
        devices = []
        for raw in visible.split(","):
            raw = raw.strip()
            if raw:
                devices.append(int(raw))
        return devices
    return [0]


def _parse_npu_usage(output: str) -> tuple[Optional[int], Optional[int]]:
    capacity_mb = None
    usage_pct = None
    for line in output.splitlines():
        line = line.strip()
        cap_match = re.match(r"^[^M]*M Capacity\(MB\)\s*:\s*(\d+)\s*$", line, re.I)
        if cap_match:
            capacity_mb = int(cap_match.group(1))
            continue
        usage_match = re.match(r"^[^M]*M Usage Rate\(%\)\s*:\s*(\d+)\s*$", line, re.I)
        if usage_match:
            usage_pct = int(usage_match.group(1))
            continue
    return capacity_mb, usage_pct


def check_npu(
    devices: Iterable[int], skip_busy_check: bool, memory_threshold: int, report: PreflightReport
) -> list[int]:
    if not 0 <= memory_threshold <= 100:
        report.fail("npu", f"invalid memory threshold: {memory_threshold}, expected 0..100")
    try:
        selected_devices = _parse_visible_devices(devices)
    except ValueError as exc:
        report.fail("npu", f"invalid ASCEND_RT_VISIBLE_DEVICES: {exc}")
    if not selected_devices:
        report.fail("npu", "no NPU device selected")

    npu_smi = shutil.which("npu-smi")
    if not npu_smi:
        existing = [device for device in selected_devices if Path(f"/dev/davinci{device}").exists()]
        if not existing:
            report.fail("npu", "npu-smi not found and no /dev/davinci device found")
        report.warn("npu", f"npu-smi not found; weak device check passed for {existing}")
        return selected_devices

    for device in selected_devices:
        result = run_command(["npu-smi", "info", "-i", str(device), "-t", "usages"], timeout=10)
        if result.returncode != 0:
            report.fail("npu", f"device {device} is not queryable: {result.stdout.strip()}")
        capacity_mb, usage_pct = _parse_npu_usage(result.stdout)
        if usage_pct is None:
            report.warn("npu", f"device {device} usage parse failed; npu-smi output format may differ")
            continue
        if not skip_busy_check and usage_pct >= memory_threshold:
            report.fail(
                "npu",
                f"device {device} HBM usage rate {usage_pct}% >= threshold {memory_threshold}%",
            )
        capacity_msg = f", capacity={capacity_mb}MB" if capacity_mb is not None else ""
        report.pass_("npu", f"device {device} usage={usage_pct}%{capacity_msg}")

    vllm_proc = run_command(["pgrep", "-af", "vllm serve"], timeout=5) if shutil.which("pgrep") else None
    if vllm_proc and vllm_proc.returncode == 0 and vllm_proc.stdout.strip():
        report.warn("npu", f"existing vllm serve process detected:\n{vllm_proc.stdout.strip()}")
    return selected_devices


def choose_service_port(requested_port: Optional[int], report: PreflightReport) -> int:
    def can_bind(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                return False
            return True

    if requested_port is not None:
        if not can_bind(requested_port):
            report.fail("port", f"requested port is already in use: {requested_port}")
        report.pass_("port", f"using requested port {requested_port}")
        return requested_port

    if can_bind(8000):
        report.pass_("port", "using default port 8000")
        return 8000

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    report.warn("port", f"default port 8000 is busy; using random port {port}")
    return port


def prepare_prometheus_dir(workspace: str, report: PreflightReport) -> str:
    prom_dir = Path(workspace) / "prometheus_multiproc"
    if prom_dir.exists():
        shutil.rmtree(prom_dir)
    prom_dir.mkdir(parents=True, exist_ok=True)
    probe = prom_dir / ".write_probe"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
    report.pass_("prometheus", f"PROMETHEUS_MULTIPROC_DIR={prom_dir}")
    return str(prom_dir)


def _is_git_source(source: str) -> bool:
    return source.startswith(("http://", "https://", "git@")) or source.endswith(".git")


def _resolve_metric_package_dir(source_path: Path) -> Path:
    nested = source_path / "ms_service_metric"
    if (nested / "pyproject.toml").exists() and (nested / "ms_service_metric").exists():
        return nested
    if (source_path / "pyproject.toml").exists() and (source_path / "ms_service_metric").exists():
        return source_path
    raise MetricSmokeError(f"Cannot locate ms_service_metric package under {source_path}")


def install_metric_source(source: str, ref: str, install_mode: str, workspace: str) -> dict:
    if install_mode == "installed" or source == "installed":
        return inspect_metric_installation({"source": source, "ref": ref, "install_mode": "installed"})

    source_dir = None
    source_info = {"source": source, "ref": ref, "install_mode": install_mode}
    if _is_git_source(source):
        require_git = shutil.which("git")
        if not require_git:
            raise MetricSmokeError("git command not found; pass a local --metric-source or install git")
        clone_dir = Path(workspace) / "metric_src" / "msserviceprofiler"
        clone_dir.parent.mkdir(parents=True, exist_ok=True)
        clone = run_command(["git", "clone", source, str(clone_dir)], timeout=600)
        if clone.returncode != 0:
            raise MetricSmokeError(f"git clone failed:\n{clone.stdout}")
        checkout = run_command(["git", "checkout", ref], cwd=str(clone_dir), timeout=120)
        if checkout.returncode != 0:
            raise MetricSmokeError(f"git checkout {ref} failed:\n{checkout.stdout}")
        source_dir = clone_dir
    else:
        local = Path(source).resolve()
        if not local.exists():
            raise MetricSmokeError(f"metric source path not found: {source}")
        if local.suffix == ".whl":
            install = run_command(
                [sys.executable, "-m", "pip", "install", "--force-reinstall", str(local)], timeout=600
            )
            if install.returncode != 0:
                raise MetricSmokeError(f"pip install whl failed:\n{install.stdout}")
            return inspect_metric_installation(source_info)
        source_dir = local

    package_dir = _resolve_metric_package_dir(source_dir)
    install = run_command([sys.executable, "-m", "pip", "install", "-e", str(package_dir)], timeout=600)
    if install.returncode != 0:
        raise MetricSmokeError(f"pip install -e {package_dir} failed:\n{install.stdout}")
    source_info["package_dir"] = str(package_dir)

    if (source_dir / ".git").exists():
        commit = run_command(["git", "rev-parse", "HEAD"], cwd=str(source_dir), timeout=30)
        if commit.returncode == 0:
            source_info["commit"] = commit.stdout.strip()
    return inspect_metric_installation(source_info)


def inspect_metric_installation(source_info: dict) -> dict:
    script = r"""
import json
import shutil
import importlib.metadata as metadata
import ms_service_metric

eps = metadata.entry_points()
if hasattr(eps, "select"):
    plugin_eps = eps.select(group="vllm.general_plugins", name="ms_service_metric")
else:
    plugin_eps = [ep for ep in eps.get("vllm.general_plugins", []) if ep.name == "ms_service_metric"]

print(json.dumps({
    "module_file": getattr(ms_service_metric, "__file__", ""),
    "version": getattr(ms_service_metric, "__version__", ""),
    "cli_path": shutil.which("ms-service-metric"),
    "vllm_entry_point": bool(plugin_eps),
}, ensure_ascii=False))
"""
    result = run_command([sys.executable, "-c", script], timeout=60)
    if result.returncode != 0:
        raise MetricSmokeError(f"ms_service_metric installation inspection failed:\n{result.stdout}")
    info = dict(source_info)
    json_line = next((line for line in reversed(result.stdout.splitlines()) if line.strip().startswith("{")), "")
    info.update(json.loads(json_line))
    if not info.get("vllm_entry_point"):
        raise MetricSmokeError(f"vLLM entry point 'ms_service_metric' is not registered: {info}")
    print("[metric-install]", json.dumps(info, ensure_ascii=False, indent=2))
    return info


def collect_runtime_info() -> dict:
    script = r"""
import importlib.metadata as metadata
import json
import platform
import sys

packages = {}
for package in ("ms-service-metric", "vllm", "vllm-ascend"):
    try:
        packages[package] = metadata.version(package)
    except metadata.PackageNotFoundError:
        packages[package] = None

print(json.dumps({
    "python": sys.version.split()[0],
    "platform": platform.platform(),
    "packages": packages,
}, ensure_ascii=False))
"""
    result = run_command([sys.executable, "-c", script], timeout=60)
    if result.returncode != 0:
        return {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {},
            "inspection_error": result.stdout.strip(),
        }
    json_line = next((line for line in reversed(result.stdout.splitlines()) if line.strip().startswith("{")), "")
    try:
        info = json.loads(json_line)
    except json.JSONDecodeError:
        info = {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {},
            "inspection_error": result.stdout.strip(),
        }
    print("[metric-runtime]", json.dumps(info, ensure_ascii=False, indent=2))
    return info


def wait_http_ok(url: str, timeout: int = 60) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if 200 <= response.status < 500:
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        time.sleep(1)
    raise MetricSmokeError(f"HTTP endpoint not ready: {url}, last_error={last_error}")


def fetch_text(url: str, timeout: int = 30) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def restart_metric_collection() -> None:
    result = run_command([sys.executable, "-m", "ms_service_metric", "restart"], timeout=60)
    if result.returncode != 0:
        raise MetricSmokeError(f"ms-service-metric restart failed:\n{result.stdout}")
    print(result.stdout)


def find_metric_value(metrics_text: str, metric_name: str) -> Optional[float]:
    sample_pattern = re.compile(
        rf"^{re.escape(metric_name)}(?:\{{[^}}]*\}})?\s+([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)$"
    )
    for line in metrics_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = sample_pattern.match(line)
        if match:
            return float(match.group(1))
    return None


def assert_generate_metric(metrics_text: str) -> None:
    value = find_metric_value(metrics_text, GENERATE_COUNT_METRIC)
    if value is None:
        candidates = "\n".join(
            line for line in metrics_text.splitlines() if "vllm_profiling" in line and "generate" in line
        )
        raise MetricSmokeError(
            f"Metric not found: {GENERATE_COUNT_METRIC}\ngenerate-related candidates:\n{candidates or '<none>'}"
        )
    if value <= 0:
        raise MetricSmokeError(f"Metric {GENERATE_COUNT_METRIC} should be > 0, got {value}")
