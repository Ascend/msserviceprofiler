#!/bin/bash
#
# readthedocs资料构建 检查 mkdocs.yml 与 docs 目录一致性：
# 1. mkdocs.yml 中配置的文件不存在 -> 报错退出 1
# 2. docs 目录下的 .md 文件未配置到 mkdocs.yml 且不在排除表EXCLUDED_MD中 -> 报错退出 1
#
# 用法: ./scripts/check-mkdocs.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

MKDOCS="${1:-mkdocs.yml}"
DOCS_DIR="docs"

# 确认不应添加到 mkdocs.yml 的 .md 文件（相对 docs 的路径）
# 确认下述文件将不在readthedocs显示
EXCLUDED_MD=(
  zh/cpp_api/trace_data_monitoring/Span_1.md
  zh/overview.md
  en/cpp_api/serving_tuning/ArrayAttr.md
  en/cpp_api/serving_tuning/ArrayResource.md
  en/cpp_api/serving_tuning/Attr.md
  en/cpp_api/serving_tuning/Domain.md
  en/cpp_api/serving_tuning/Event.md
  en/cpp_api/serving_tuning/GetMsg.md
  en/cpp_api/serving_tuning/IsEnable.md
  en/cpp_api/serving_tuning/Launch.md
  en/cpp_api/serving_tuning/Link.md
  en/cpp_api/serving_tuning/macro_definitions.md
  en/cpp_api/serving_tuning/MetricInc.md
  en/cpp_api/serving_tuning/Metric.md
  en/cpp_api/serving_tuning/MetricScopeAsGlobal.md
  en/cpp_api/serving_tuning/MetricScopeAsReqID.md
  en/cpp_api/serving_tuning/MetricScope.md
  en/cpp_api/serving_tuning/NumArrayAttr.md
  en/cpp_api/serving_tuning/README.md
  en/cpp_api/serving_tuning/Resource.md
  en/cpp_api/serving_tuning/SpanEnd.md
  en/cpp_api/serving_tuning/SpanStart.md
  en/cpp_api/trace_data_monitoring/Activate.md
  en/cpp_api/trace_data_monitoring/addResAttribute.md
  en/cpp_api/trace_data_monitoring/Attach.md
  en/cpp_api/trace_data_monitoring/End.md
  en/cpp_api/trace_data_monitoring/ExtractAndAttach.md
  en/cpp_api/trace_data_monitoring/GetCurrent.md
  en/cpp_api/trace_data_monitoring/GetTraceCtx.md
  en/cpp_api/trace_data_monitoring/IsEnable.md
  en/cpp_api/trace_data_monitoring/README.md
  en/cpp_api/trace_data_monitoring/SetAttribute.md
  en/cpp_api/trace_data_monitoring/SetStatus.md
  en/cpp_api/trace_data_monitoring/Span_1.md
  en/cpp_api/trace_data_monitoring/Span.md
  en/cpp_api/trace_data_monitoring/StartSpanAsActive.md
  en/cpp_api/trace_data_monitoring/TraceContext.md
  en/cpp_api/trace_data_monitoring/Tracer.md
  en/cpp_api/trace_data_monitoring/Unattach.md
  en/developer_guide/development_guide.md
  en/dir_structure.md
  en/legal/disclaimer.md
  en/legal/license_notice.md
  en/ms_service_profiler_compare_tool_instruct.md
  en/msserviceprofiler_install_guide.md
  en/msserviceprofiler_multi_analyze_instruct.md
  en/msserviceprofiler_serving_tuning_instruct.md
  en/msserviceprofiler_trace_data_monitoring_instruct.md
  en/public_ip_address.md
  en/python_api/context/attr.md
  en/python_api/context/domain.md
  en/python_api/context/__enter__-__exit__.md
  en/python_api/context/event.md
  en/python_api/context/get_msg.md
  en/python_api/context/init.md
  en/python_api/context/launch.md
  en/python_api/context/link.md
  en/python_api/context/metric_inc.md
  en/python_api/context/metric.md
  en/python_api/context/metric_scope_as_req_id.md
  en/python_api/context/metric_scope.md
  en/python_api/context/res.md
  en/python_api/context/span_end.md
  en/python_api/context/span_start.md
  en/python_api/README.md
  en/quick_start.md
  en/security_statement.md
  en/serviceparam_optimizer_instruct.md
  en/serviceparam_optimizer_plugin_instruct.md
  en/service_performance_split_tool_instruct.md
  en/service_profiling_advisor_instruct.md
  en/SGLang_service_oriented_performance_collection_tool.md
  en/vLLM_metrics_tool_instruct.md
  en/vLLM_service_oriented_performance_collection_tool.md
  en/vulnerability_handling_procedure.md
  en/overview.md
  design/Ternary_Relationship_Detailed_Design.md
)

if [[ ! -f "$MKDOCS" ]]; then
  echo "错误: 未找到 $MKDOCS"
  exit 1
fi

# 判断路径是否在排除表中
is_excluded() {
  local f="$1"
  for e in "${EXCLUDED_MD[@]}"; do
    [[ "$e" == "$f" ]] && return 0
  done
  return 1
}

# 从 mkdocs.yml 抽取所有 .md 路径（相对 docs）
get_nav_paths() {
  sed -n '/^nav:/,/^[a-z_]/p' "$MKDOCS" | \
    grep '\.md' | \
    sed -E 's/^[^:]*:[[:space:]]+(.+\.md)[[:space:]]*$/\1/' | \
    sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | \
    grep -E '\.md$' | \
    sort -u
}

# 获取 docs 目录下所有 .md 文件（相对 docs 的路径）
get_all_docs_md() {
  if [[ ! -d "$DOCS_DIR" ]]; then
    return
  fi
  (cd "$DOCS_DIR" && find . -type f -name "*.md") | sed 's|^\./||' | sort -u
}

NAV_PATHS=$(get_nav_paths)
ERRORS=""

# 1. 检查 mkdocs.yml 中配置的文档是否存在
while IFS= read -r p; do
  [[ -z "$p" ]] && continue
  if [[ ! -f "$DOCS_DIR/$p" ]]; then
    ERRORS="${ERRORS}  - $p\n"
  fi
done <<< "$NAV_PATHS"

if [[ -n "$ERRORS" ]]; then
  echo "错误: 以下文档链接已失效:"
  echo -e "$ERRORS"
  exit 1
fi

# 2. 检查 docs 下 .md 文件是否已配置到 mkdocs.yml 或在排除表中
UNCGF=""
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  if echo "$NAV_PATHS" | grep -qxF "$f"; then
    continue
  fi
  if is_excluded "$f"; then
    continue
  fi
  UNCGF="${UNCGF}  - $f\n"
done <<< "$(get_all_docs_md)"

if [[ -n "$UNCGF" ]]; then
  echo "错误: docs 目录下以下 .md 文件尚未配置到 mkdocs.yml:"
  echo -e "$UNCGF"
  echo "请将上述文件添加到 mkdocs.yml 配置，或加入本脚本的 EXCLUDED_MD 排除表。"
  exit 1
fi

exit 0
