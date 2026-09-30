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
import re
from dataclasses import dataclass, field
from pathlib import Path

from metric.metric_smoke_utils import MetricSmokeError


METRIC_LOG_MARKER = "ms_service_metric"

FATAL_LEVEL_RE = re.compile(r"\b(ERROR|CRITICAL|FATAL)\b")
NON_FATAL_WARNING_RE = re.compile(
    r"Failed to import target for symbol|No target available for symbol|"
    r"Metrics - vLLM metrics module not available|No config file found for vLLM adapter",
    re.I,
)
FATAL_WARNING_RE = re.compile(
    r"Failed to create metric|Metric not found:|Failed to record metric|Failed to register metric|"
    r"Failed to evaluate label expression|Failed to compile expr|Failed to compile label expr|"
    r"Failed to create handler|Failed to import handler module|function enter .* failed|"
    r"function exit .* failed|Failed to apply hook|Failed to recover hook",
    re.I,
)


@dataclass
class LogHealthReport:
    fatal: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    scanned_metric_lines: int = 0

    def write(self, path: Path) -> None:
        path.write_text(json.dumps(self.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")

    def summary(self) -> str:
        lines = [
            "[metric-log-health] "
            f"fatal={len(self.fatal)}, warnings={len(self.warnings)}, "
            f"scanned_metric_lines={self.scanned_metric_lines}"
        ]
        for line in self.fatal[:20]:
            lines.append(f"[metric-log-health] FAIL {line}")
        for line in self.warnings[:20]:
            lines.append(f"[metric-log-health] WARN {line}")
        return "\n".join(lines)


def assert_metric_log_health(service_log: str, report_path: Path | None = None) -> LogHealthReport:
    report = scan_metric_log_health(service_log)
    if report_path:
        report.write(report_path)
    print(report.summary())
    if report.fatal:
        raise MetricSmokeError(
            "ms_service_metric log health check failed:\n" + json.dumps(report.fatal, ensure_ascii=False, indent=2)
        )
    return report


def scan_metric_log_health(service_log: str) -> LogHealthReport:
    report = LogHealthReport()
    for raw_line in service_log.splitlines():
        line = raw_line.strip()
        if METRIC_LOG_MARKER not in line:
            continue
        report.scanned_metric_lines += 1
        if FATAL_LEVEL_RE.search(line) or FATAL_WARNING_RE.search(line):
            report.fatal.append(line)
        elif NON_FATAL_WARNING_RE.search(line):
            report.warnings.append(line)
    return report
