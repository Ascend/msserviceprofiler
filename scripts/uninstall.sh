#!/bin/bash
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

CANN_UNINSTALL_SCRIPT="cann_uninstall.sh"
MSSERVICE_RUN_NAME="mindstudio-msserviceprofiler"
LIB_MS_SERVICE_PROFILER="libms_service_profiler.so"
package_arch=$(uname -m)
arch_name="${package_arch}-linux"
right=750

CUR_DIR=$(dirname $(readlink -f $0))
CANN_INSTALL_PATH=$(readlink -f "${CUR_DIR}/../../..")
if [ -z "${1}" ]; then
    install_path=${CANN_INSTALL_PATH}
else
 	  install_path=${1}
fi

function print_log() {
     if [ ! -f "$log_file" ]; then
         echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [$1]: $2"
     else
         echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [$1]: $2" | tee -a $log_file
     fi
}

function delete_register_uninstall() {
    if [ ! -f "${install_path}/${CANN_UNINSTALL_SCRIPT}" ]; then
 	  	  print_log "ERROR" "Failed to delete_register_uninstall, no such file: ${install_path}/${CANN_UNINSTALL_SCRIPT}"
 	  	  return 1
 	  fi
 	  local script_right=$(stat -c '%a' "${install_path}/${CANN_UNINSTALL_SCRIPT}")
 	  chmod u+w "${install_path}/${CANN_UNINSTALL_SCRIPT}"
 	  sed -i "/uninstall_package \"share\/info\/msserviceprofiler\"/d" "${install_path}/${CANN_UNINSTALL_SCRIPT}"
 	  chmod ${script_right} "${install_path}/${CANN_UNINSTALL_SCRIPT}"
}

delete_register_uninstall

rm -rf ${install_path%/}/python/site-packages/ms_service_profiler*
rm -rf ${install_path%/}/python/site-packages/bin/msserviceprofiler*
rm -rf ${install_path%/}/share/info/msserviceprofiler

lib64_right=$(stat -c "%a" ${install_path%/}/${arch_name}/lib64 2>/dev/null)
chmod -R ${right} ${install_path%/}/${arch_name}/lib64
rm -rf ${install_path%/}/${arch_name}/lib64/${LIB_MS_SERVICE_PROFILER}
chmod -R ${lib64_right} ${install_path%/}/${arch_name}/lib64
