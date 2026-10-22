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

# the params for checking
install_args_num=0
install_path_num=0
upgrade_flag=0
quiet_flag=0
MSSERVICE_RUN_NAME="mindstudio-msserviceprofiler"
PATH_LENGTH=4096
package_arch=$(uname -m)
install_for_all_flag=0
check_flag=0
uninstall_flag=0

function print_log() {
    if [ ! -f "$log_file" ]; then
        echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [$1]: $2"
    else
        echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [$1]: $2" | tee -a $log_file
    fi
}

function get_log_file() {
    local log_dir
    if [ "$UID" = "0" ]; then
		    log_dir="/var/log/ascend_seclog"
	  else
		    log_dir="${HOME}/var/log/ascend_seclog"
	  fi
	  echo "${log_dir}/ascend_install.log"
}


function log_init() {
    local log_dir
    log_dir=$(dirname "$log_file")
    if [ ! -d "$log_dir" ]; then
        mkdir -p "$log_dir" || { echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [ERROR]: Failed to create log directory: $log_dir"; exit 1; }
    fi
    if [ ! -f "$log_file" ]; then
        touch "$log_file" || { echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [ERROR]: Failed to create log file: $log_file"; exit 1; }
    fi
    chmod 640 "$log_file"
}

function check_path() {
    local path_str=${1}
    # check the existence of the path
    if [ ! -e "${path_str}" ]; then
        print_log "ERROR" "The path ${path_str} does not exist, please check."
        exit 1
    fi
    # check the length of path
    if [ ${#path_str} -gt ${PATH_LENGTH} ]; then
        print_log "ERROR" "parameter error $path_str, the length exceeds ${PATH_LENGTH}."
        exit 1
    fi
    # check absolute path
    if [[ ! "${path_str}" =~ ^/.* ]]; then
        print_log "ERROR" "parameter error $path_str, must be an absolute path."
        exit 1
    fi
    # black list
    if echo "${path_str}" | grep -Eq '/{2,}|\.{3,}'; then
        print_log "ERROR" "The path ${path_str} is invalid, cannot contain the following characters: // ...!"
        exit 1
    fi
    # white list
    if echo "${path_str}" | grep -Eq '^~?[a-zA-Z0-9./_-]*$'; then
        return
    else
        print_log "ERROR" "The path ${path_str} is invalid, only [a-z,A-Z,0-9,-,_] is support!"
        exit 1
    fi
}

function check_cann_path() {
    local cann_path=${1}
    local current_user=$(whoami)
    local cann_path_owner=$(stat -c '%U' "$cann_path")

    if [ "$current_user" != "root" ]; then
        # 1. Check the current executing user and the installation user of cann_path.
        if [ "$current_user" != "$cann_path_owner" ]; then
            print_log "ERROR" "Current user ($current_user) is not the same as the owner of cann_path ($cann_path_owner)."
            exit 1
        fi

        # 2. Check whether the current cann_path is writable (except for the root user).
        if [ ! -w "$cann_path" ]; then
            print_log "ERROR" "cann_path ($cann_path) is not writable by the current user ($current_user)."
            exit 1
        fi
    fi
}


function parse_script_args() {
    while true; do
        if [ "$3" = "" ]; then
            break
        fi
        case "$3" in
        --install-path=*)
            let "install_path_num+=1"
            raw_path=${3#--install-path=}
            install_path="${raw_path%/}"
            [ ! -d ${install_path} ] && mkdir -p ${install_path}
            check_path ${install_path}
            install_path=$(readlink -f ${install_path})
            check_path ${install_path}
            check_cann_path ${install_path}
            shift
            continue
            ;;
        --quiet)
            quiet_flag=1
            shift
            continue
            ;;
        --install)
            let "install_args_num+=1"
            shift
            continue
            ;;
        --upgrade)
            upgrade_flag=1
            shift
            continue
            ;;
        --check)
            check_flag=1
            shift
            continue
            ;;
        --uninstall)
 	             uninstall_flag=1
 	             shift
 	             continue
 	             ;;
        --install-for-all)
            install_for_all_flag=1
            shift
            continue
            ;;
        *)
            print_log "ERROR" "Input option is invalid. Please try --help."
            exit 1
            ;;
        esac
    done
}

function check_args() {
    local op_count=0
    if [ ${check_flag} -eq 1 ]; then
 	         return 0
 	  fi
    [ ${install_args_num} -gt 0 ] && op_count=$((op_count + 1))
    [ ${upgrade_flag} -eq 1 ] && op_count=$((op_count + 1))
    [ ${uninstall_flag} -eq 1 ] && op_count=$((op_count + 1))
    if [ ${op_count} -ne 1 ]; then
        print_log "ERROR" "Must specify exactly one of --install, or --uninstall. Please try --help."
        exit 1
    fi
    if [ ${install_path_num} -gt 1 ]; then
        print_log "ERROR" "Do not input --install-path many times. Please try --help."
        exit 1
    fi
}

function execute_run() {
    if [ ${uninstall_flag} -eq 1 ]; then
        bash uninstall.sh ${install_path}
        if [ $? -ne 0 ]; then
            print_log "ERROR" "${MSSERVICE_RUN_NAME} package uninstall failed."
            exit 1
        fi
        print_log "INFO" "${MSSERVICE_RUN_NAME} package uninstall success."
    elif [ ${install_args_num} -gt 0 ]; then
        bash install.sh ${install_path} ${package_arch} ${install_for_all_flag} 0
        if [ $? -ne 0 ]; then
            print_log "ERROR" "${MSSERVICE_RUN_NAME} package install failed."
            exit 1
        fi
        print_log "INFO" "${MSSERVICE_RUN_NAME} package install success, the path is: '${install_path}'."
    elif [ ${upgrade_flag} -eq 1 ]; then
        bash upgrade.sh ${upgrade_path} ${quiet_flag}
        if [ $? -ne 0 ]; then
            print_log "ERROR" "${MSSERVICE_RUN_NAME} package upgrade failed."
            exit 1
        fi
        print_log "INFO" "${MSSERVICE_RUN_NAME} upgrade completed, the path is: '${upgrade_path}'."
    fi
}

function get_default_install_path() {
    if [ "$UID" = "0" ]; then
        echo "/usr/local/Ascend/cann"
    else
        echo "${HOME}/Ascend/cann"
    fi
}


# init log file
log_file=$(get_log_file)
log_init
# use utils function and constant
install_path=$(get_default_install_path)
#0, this footnote path;1, path for executing run;2, parents' dir for run package;3, run params
parse_script_args $*
check_args
# Create install path when --install (default path may not exist)
if [ ${install_args_num} -gt 0 ]; then
    [ ! -d "${install_path}" ] && mkdir -p "${install_path}"
fi
# Set upgrade path when --upgrade: use --install-path if specified, else ASCEND_TOOLKIT_HOME (must be set)
if [ ${upgrade_flag} -eq 1 ]; then
    if [ ${install_path_num} -gt 0 ]; then
        upgrade_path="${install_path}"
    else
        if [ -z "${ASCEND_TOOLKIT_HOME}" ]; then
            print_log "ERROR" "ASCEND_TOOLKIT_HOME is not set. Please specify --install-path to set the upgrade path."
            exit 1
        fi
        upgrade_path="${ASCEND_TOOLKIT_HOME}"
    fi
    upgrade_path="${upgrade_path%/}"
    if [ ! -e "${upgrade_path}" ]; then
        print_log "WARN" "Upgrade path does not exist: ${upgrade_path}."
        exit 1
    fi
    check_path "${upgrade_path}"
    upgrade_path=$(readlink -f "${upgrade_path}")
fi
execute_run
