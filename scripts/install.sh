#!/bin/bash
# install constant
install_path=${1}
package_arch=${2}
install_for_all_flag=${3}
pylocal=y
right=750
root_libmsserviceprofiler_right=444
user_libmsserviceprofiler_right=440
MSSERVICE_RUN_NAME="mindstudio-msserviceprofiler"
SHARE_INFO_DIR="share/info"
BIN_BACKUP="bin_backup"
UNINSTALL_SCRIPT="uninstall.sh"
VERSION_INFO="version.info"
MSSERVICEPROFILER="msserviceprofiler"
CANN_UNINSTALL_SCRIPT="cann_uninstall.sh"
LIB_MS_SERVICE_PROFILER="libms_service_profiler.so"

function print_log() {
    if [ ! -f "$log_file" ]; then
        echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [$1]: $2"
    else
        echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [$1]: $2" | tee -a $log_file
    fi
}

function install_whl_package() {
    local _pylocal=$1
    local _package=$2
    local _pythonlocalpath=$3

    print_log "INFO" "Start to install ${_package}."
    if [ ! -f "${_package}" ]; then
        print_log "ERROR" "Install whl The ${_package} does not exist."
        return 1
    fi
    if [ "-${_pylocal}" = "-y" ]; then
        pip3 install --upgrade --no-deps --force-reinstall --disable-pip-version-check "${_package}" -t "${_pythonlocalpath}" > /dev/null 2>&1
    else
        if [ "$(id -u)" -ne 0 ]; then
            pip3 install --upgrade --no-deps --force-reinstall --disable-pip-version-check "${_package}" --user > /dev/null 2>&1
        else
            pip3 install --upgrade --no-deps --force-reinstall --disable-pip-version-check "${_package}" > /dev/null 2>&1
        fi
    fi
    if [ $? -ne 0 ]; then
        print_log "ERROR" "Install ${_package} failed."
        return 1
    fi
    chmod -R u+rwx,go+rx,go-w "${_pythonlocalpath}"
    print_log "INFO" "Install ${_package} success."
    return 0
}

function implement_install() {
    create_directory ${install_path}/${SHARE_INFO_DIR}/${MSSERVICEPROFILER} ${right}
    copy_file ${UNINSTALL_SCRIPT} ${install_path}/${SHARE_INFO_DIR}/${MSSERVICEPROFILER}/${UNINSTALL_SCRIPT}
    copy_file ${VERSION_INFO} ${install_path}/${SHARE_INFO_DIR}/${MSSERVICEPROFILER}/${VERSION_INFO}
	  # install whl
	  rm -rf ${install_path}/${BIN_BACKUP}
	  create_directory ${install_path}/${BIN_BACKUP} ${right}
	  copy_file ${install_path%/}/python/site-packages/bin ${install_path}/${BIN_BACKUP}
    install_whl_package $pylocal ms_service_profiler-*.whl ${install_path%/}/python/site-packages
    copy_file ${install_path%/}/python/site-packages/bin/msserviceprofiler ${install_path}/${BIN_BACKUP}/msserviceprofiler
    copy_file ${install_path}/${BIN_BACKUP} ${install_path%/}/python/site-packages/bin
    rm -rf ${install_path}/${BIN_BACKUP}
    print_log "INFO" "${install_path%/}/python/site-packages/ms_service_profiler is replaced."
    # libms_service_profiler.so
    lib64_right=$(stat -c "%a" ${install_path}/${arch_name}/lib64 2>/dev/null)
    lib64_right_conf=$(stat -c "%a" ${install_path}/${arch_name}/lib64/plugin/opskernel/config/init.conf 2>/dev/null)
    chmod -R ${right} ${install_path}/${arch_name}/lib64
    copy_file ${install_path%/}/python/site-packages/ms_service_profiler/${LIB_MS_SERVICE_PROFILER} ${install_path}/${arch_name}/lib64/${LIB_MS_SERVICE_PROFILER}
    chmod -R ${lib64_right} ${install_path}/${arch_name}/lib64 && \
    chmod ${lib64_right_conf} ${install_path}/${arch_name}/lib64/plugin/opskernel/config/init.conf
    if [ $? -ne 0 ]; then
        print_log "ERROR" "Install msserviceprofiler whl failed."
        return 1
    fi
}

function copy_file() {
  local filename=${1}
  local target_file=$(readlink -f ${2})

  if [ ! -f "$filename" ] && [ ! -d "$filename" ]; then
    return
  fi

  if [ -f "$target_file" ] || [ -d "$target_file" ]; then
    local parent_dir=$(dirname ${target_file})
    local parent_right=$(stat -c '%a' ${parent_dir})

    chmod u+w ${parent_dir}
    chmod -R u+w ${target_file}
    rm -r ${target_file}

    cp -r ${filename} ${target_file}
    chmod -R ${parent_right} ${target_file}
    chmod ${parent_right} ${parent_dir}
  else
    cp -r ${filename} ${target_file}
    chmod -R ${right} ${target_file}
  fi
  print_log "INFO" "$target_file is replaced."
}

function create_directory() {
    local _dir=${1}
    local _right=${2}
  	if [ ! -d "${_dir}" ]; then
  	    mkdir -p ${_dir}
  	    chmod ${_right} ${_dir}
  	fi
}

function delete_msserviceprofiler() {
    rm -rf ${install_path%/}/python/site-packages/ms_service_profiler*
}

function set_libmsserviceprofiler_right() {
	libmsserviceprofiler_right=${user_libmsserviceprofiler_right}
	if [ "$install_for_all_flag" = "1" ] || [ "$UID" = "0" ]; then
		libmsserviceprofiler_right=${root_libmsserviceprofiler_right}
	fi
}

function chmod_libmsserviceprofiler() {

	if [ -f "${install_path}/${arch_name}/lib64/${LIB_MS_SERVICE_PROFILER}" ]; then
		chmod ${libmsserviceprofiler_right} "${install_path}/${arch_name}/lib64/${LIB_MS_SERVICE_PROFILER}"
	fi
}

function register_uninstall() {
       local target_line='uninstall_package "share/info/msserviceprofiler"'
 	   if [ ! -f "${install_path}/${SHARE_INFO_DIR}/${MSSERVICEPROFILER}/${UNINSTALL_SCRIPT}" ]; then
 	       print_log "ERROR" "No such file: ${install_path}/${SHARE_INFO_DIR}/${MSSERVICEPROFILER}/${UNINSTALL_SCRIPT}"
 	   fi
 	   if [ ! -x "${install_path}/${SHARE_INFO_DIR}/${MSSERVICEPROFILER}/${UNINSTALL_SCRIPT}" ]; then
 	       print_log "ERROR" "The file ${install_path}/${SHARE_INFO_DIR}/${MSSERVICEPROFILER}/${UNINSTALL_SCRIPT} is not executable."
 	       return 1
 	   fi
 	   if [ ! -f "${install_path}/${CANN_UNINSTALL_SCRIPT}" ]; then
 	       print_log "ERROR" "Failed to register uninstall script, no such file: ${install_path}/${CANN_UNINSTALL_SCRIPT}"
 	       return 1
 	   fi
 	   if grep -qxF "${target_line}" "${install_path}/${CANN_UNINSTALL_SCRIPT}"; then
 	         return 0
 	   fi
 	   local script_right=$(stat -c '%a' "${install_path}/${CANN_UNINSTALL_SCRIPT}")
 	   chmod u+w "${install_path}/${CANN_UNINSTALL_SCRIPT}"
 	   sed -i "/^exit /i uninstall_package \"share\/info\/msserviceprofiler\"" "${install_path}/${CANN_UNINSTALL_SCRIPT}"
 	   chmod ${script_right} "${install_path}/${CANN_UNINSTALL_SCRIPT}"
}

arch_name="${package_arch}-linux"
delete_msserviceprofiler
implement_install
if [ $? -eq 0 ]; then
 	  register_uninstall
fi
set_libmsserviceprofiler_right
chmod_libmsserviceprofiler
