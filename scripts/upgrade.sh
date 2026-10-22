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

# Upgrade: overlay ms_service_profiler/, libms_service_profiler.so, include/msServiceProfiler/ to the specified path
# Search for these targets anywhere under upgrade_path (paths may be non-fixed).
# Only replace when target exists; no add or delete of files.
# $1: upgrade_path - target directory to overlay files
# $2: quiet_flag - 1=skip confirmation (from --quiet), 0=require confirmation
upgrade_path=${1}
quiet_flag=${2:-0}
MSSERVICE_RUN_NAME="mindstudio-msserviceprofiler"
INCLUDE_SRC="include"
INCLUDE_MS_SERVICE_PROFILER="msServiceProfiler"

function print_log() {
    if [ ! -f "$log_file" ]; then
        echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [$1]: $2"
    else
        echo "[${MSSERVICE_RUN_NAME}] [$(date +"%Y-%m-%d %H:%M:%S")] [$1]: $2" | tee -a $log_file
    fi
}

# Resolve logical path to real path; if symlink, resolve to real path
# Returns: real_path on stdout, or empty and exit 1 on error
# For broken symlink: use logical_path (we will remove symlink and create there)
function resolve_and_validate() {
    local logical_path=$1
    if [ ! -e "$logical_path" ] && [ ! -L "$logical_path" ]; then
        echo "$logical_path"
        return 0
    fi
    if [ -L "$logical_path" ]; then
        if [ ! -e "$logical_path" ]; then
            echo "$logical_path"
            return 0
        fi
        local real_path
        real_path=$(readlink -f "$logical_path" 2>/dev/null)
        if [ -z "$real_path" ]; then
            print_log "ERROR" "Cannot resolve symlink: $logical_path"
            return 1
        fi
        echo "$real_path"
    else
        echo "$logical_path"
    fi
    return 0
}

# Check if we can write to path (parent dir writable).
# For a directory target, recursively check that all files/dirs under it have writable parent.
function check_writable() {
    local path=$1
    if [ "$(id -u)" -eq 0 ]; then
        return 0
    fi
    if [ -f "$path" ]; then
        local parent
        parent=$(dirname "$path")
        [ -d "$parent" ] || parent="$upgrade_path"
        if [ -d "$parent" ] && [ -w "$parent" ]; then
            return 0
        fi
        print_log "ERROR" "No write permission: $path (directory $parent not writable by current user)"
        return 1
    fi
    if [ -d "$path" ]; then
        local p parent
        while IFS= read -r -d '' p; do
            [ -z "$p" ] && continue
            parent=$(dirname "$p")
            if [ ! -d "$parent" ] || [ ! -w "$parent" ]; then
                print_log "ERROR" "No write permission: $p (directory $parent not writable by current user)"
                return 1
            fi
        done < <(find "$path" -print0 2>/dev/null)
        return 0
    fi
    # Symlink or other: check parent of path
    local parent
    parent=$(dirname "$path")
    [ -d "$parent" ] || parent="$upgrade_path"
    if [ -d "$parent" ] && [ -w "$parent" ]; then
        return 0
    fi
    print_log "ERROR" "No write permission: $path (directory $parent not writable by current user)"
    return 1
}

# Phase 1: Discover all paths to replace (no modifications)
# Search for libms_service_profiler.so, ms_service_profiler, include/msServiceProfiler anywhere under upgrade_path.
# Only add to targets when both: (1) target exists in upgrade_path, (2) source exists in package.
# Output: lines of "replace_path|content_type" (content_type: pkg, so, include)
# Deduplicated by replace_path
function discover_targets() {
    local has_error=0
    local results=""

    # ms_service_profiler: find directories named ms_service_profiler (anywhere under upgrade_path)
    if [ -n "$(ls ms_service_profiler-*.whl 2>/dev/null | head -1)" ]; then
        while IFS= read -r -d '' logical; do
            [ -z "$logical" ] && continue
            local real_path
            real_path=$(resolve_and_validate "$logical") || { has_error=1; continue; }
            [ -z "$real_path" ] && continue
            check_writable "$real_path" || { has_error=1; continue; }
            results="${results}${real_path}|pkg"$'\n'
        done < <(find "$upgrade_path" -name "ms_service_profiler" \( -type d -o -type l \) -print0 2>/dev/null)
    fi

    # libms_service_profiler.so: find files (anywhere under upgrade_path)
    if [ -f "libms_service_profiler.so" ]; then
        while IFS= read -r -d '' logical; do
            [ -z "$logical" ] && continue
            local real_path
            real_path=$(resolve_and_validate "$logical") || { has_error=1; continue; }
            [ -z "$real_path" ] && continue
            check_writable "$real_path" || { has_error=1; continue; }
            results="${results}${real_path}|so"$'\n'
        done < <(find "$upgrade_path" -name "libms_service_profiler.so" \( -type f -o -type l \) -print0 2>/dev/null)
    fi

    # include/msServiceProfiler: find directories matching path */include/msServiceProfiler
    if [ -d "${INCLUDE_SRC}/${INCLUDE_MS_SERVICE_PROFILER}" ]; then
        while IFS= read -r -d '' logical; do
            [ -z "$logical" ] && continue
            local real_path
            real_path=$(resolve_and_validate "$logical") || { has_error=1; continue; }
            [ -z "$real_path" ] && continue
            check_writable "$real_path" || { has_error=1; continue; }
            results="${results}${real_path}|include"$'\n'
        done < <(find "$upgrade_path" -path "*/include/msServiceProfiler" \( -type d -o -type l \) -print0 2>/dev/null)
    fi

    if [ $has_error -ne 0 ]; then
        return 1
    fi
    # Deduplicate by replace_path (keep first occurrence to avoid conflicts)
    local seen=""
    echo "$results" | sed '/^$/d' | while IFS='|' read -r rp ct; do
        [ -z "$rp" ] && continue
        if ! echo "$seen" | grep -Fxq "$rp"; then
            echo "${rp}|${ct}"
            seen="${seen}${rp}"$'\n'
        fi
    done
}

# Backup target path for rollback. Stores to backup_dir with unique id.
# $1: path to backup, $2: backup_dir
# Appends "path|id" to backup_dir/map. Returns backup id.
function backup_for_rollback() {
    local path=$1
    local backup_dir=$2
    local id
    [ ! -f "${backup_dir}/.nextid" ] && echo 0 > "${backup_dir}/.nextid"
    id=$(cat "${backup_dir}/.nextid")
    echo $((id + 1)) > "${backup_dir}/.nextid"
    if [ -f "$path" ]; then
        cp "$path" "${backup_dir}/${id}" 2>/dev/null || return 1
    elif [ -d "$path" ]; then
        cp -r "$path" "${backup_dir}/${id}" 2>/dev/null || return 1
    elif [ -L "$path" ]; then
        cp -P "$path" "${backup_dir}/${id}" 2>/dev/null || return 1
    else
        return 1
    fi
    echo "${path}|${id}" >> "${backup_dir}/map"
    echo "$id"
}

# Restore ALL backed-up paths from backup_dir. Call on upgrade failure.
# Rollback applies to all targets modified in this upgrade session.
# Records failed restores and prints summary with handling strategy at the end.
function rollback_restore() {
    local backup_dir=$1
    [ ! -f "${backup_dir}/map" ] && return 0
    local count
    count=$(wc -l < "${backup_dir}/map" 2>/dev/null || echo 0)
    print_log "WARN" "Upgrade failed. Rolling back all modified targets (${count} target(s)) to their original state."
    local failed_paths=""
    while IFS='|' read -r path id; do
        [ -z "$path" ] && continue
        [ ! -e "${backup_dir}/${id}" ] && continue
        rm -rf "$path" 2>/dev/null
        rm -f "$path" 2>/dev/null
        if [ -f "${backup_dir}/${id}" ]; then
            if cp "${backup_dir}/${id}" "$path" 2>/dev/null; then
                print_log "INFO" "Restored: $path"
            else
                print_log "WARN" "Failed to restore: $path"
                failed_paths="${failed_paths}  - ${path}"$'\n'
            fi
        elif [ -d "${backup_dir}/${id}" ]; then
            if cp -r "${backup_dir}/${id}" "$path" 2>/dev/null; then
                print_log "INFO" "Restored: $path"
            else
                print_log "WARN" "Failed to restore: $path"
                failed_paths="${failed_paths}  - ${path}"$'\n'
            fi
        elif [ -L "${backup_dir}/${id}" ]; then
            if cp -P "${backup_dir}/${id}" "$path" 2>/dev/null; then
                print_log "INFO" "Restored: $path"
            else
                print_log "WARN" "Failed to restore: $path"
                failed_paths="${failed_paths}  - ${path}"$'\n'
            fi
        fi
    done < "${backup_dir}/map"
    if [ -n "$failed_paths" ]; then
        print_log "ERROR" "Rollback failed for the following paths:"
        while IFS= read -r line; do
            [ -n "$line" ] && print_log "ERROR" "$line"
        done <<< "$failed_paths"
        print_log "ERROR" "Please manually restore these paths or re-run upgrade to retry."
    fi
    print_log "INFO" "Rollback completed."
    rm -rf "$backup_dir"
}

# Safely remove path (for real paths only - we've validated symlinks are resolved)
# Returns 0 on success, 1 on failure
function safe_remove() {
    local path=$1
    if [ ! -e "$path" ] && [ ! -L "$path" ]; then
        return 0
    fi
    if [ -L "$path" ]; then
        rm -f "$path" || { print_log "ERROR" "Failed to remove symlink: $path"; return 1; }
    elif [ -d "$path" ]; then
        find "$path" -type d -exec chmod u+w {} \; 2>/dev/null
        find "$path" -type f -exec chmod u+w {} \; 2>/dev/null
        rm -rf "$path" || { print_log "ERROR" "Failed to remove directory: $path"; return 1; }
    else
        chmod u+w "$path" 2>/dev/null
        rm -f "$path" || { print_log "ERROR" "Failed to remove file: $path"; return 1; }
    fi
    return 0
}

# Replace existing target only; never add new files or delete without replacement.
# Logic: 1) remove dst (rm -rf for dir, rm -f for file), 2) copy src to dst
function copy_overlay() {
    local src=$1
    local dst=$2
    if [ ! -e "$src" ]; then
        print_log "WARN" "Source $src does not exist, skip."
        return 0
    fi
    if [ ! -e "$dst" ] && [ ! -L "$dst" ]; then
        print_log "WARN" "Target $dst does not exist, skip (no add)."
        return 0
    fi
    # Step 1: remove dst first (rm -rf for dir, rm -f for file)
    safe_remove "$dst" || return 1
    # Step 2: copy new content to dst
    if [ -f "$src" ]; then
        cp "$src" "$dst" || { print_log "ERROR" "Failed to copy to $dst (disk full or permission denied?)"; return 1; }
    else
        cp -r "$src" "$dst" || { print_log "ERROR" "Failed to copy to $dst (disk full or permission denied?)"; return 1; }
    fi
    chmod -R 555 "$dst" || { print_log "WARN" "chmod failed for $dst"; }
    print_log "INFO" "Overlaid -> $dst"
    return 0
}

function do_overlay_pkg() {
    local dst=$1
    local whl_file
    whl_file=$(ls ms_service_profiler-*.whl 2>/dev/null | head -1)
    if [ -z "$whl_file" ] || [ ! -f "$whl_file" ]; then
        print_log "ERROR" "ms_service_profiler whl not found."
        return 1
    fi
    local tmp_extract
    tmp_extract=$(mktemp -d)
    if unzip -q -o "$whl_file" -d "$tmp_extract" 2>/dev/null; then
        :
    elif python3 -c "
import zipfile
z = zipfile.ZipFile('$whl_file', 'r')
z.extractall('$tmp_extract')
" 2>/dev/null; then
        :
    else
        print_log "ERROR" "Cannot extract whl."
        rm -rf "$tmp_extract"
        return 1
    fi
    local pkg_dir
    if [ -d "${tmp_extract}/ms_service_profiler" ]; then
        pkg_dir="${tmp_extract}/ms_service_profiler"
    else
        pkg_dir=$(find "$tmp_extract" -maxdepth 1 -type d -name "ms_service_profiler*" 2>/dev/null | head -1)
    fi
    if [ -z "$pkg_dir" ] || [ ! -d "$pkg_dir" ]; then
        print_log "ERROR" "Cannot find ms_service_profiler in whl."
        rm -rf "$tmp_extract"
        return 1
    fi
    copy_overlay "$pkg_dir" "$dst" || { rm -rf "$tmp_extract"; return 1; }
    rm -rf "$tmp_extract"
    return 0
}

function do_overlay_so() {
    local dst=$1
    local so_file
    so_file=$(ls libms_service_profiler.so 2>/dev/null | head -1)
    if [ -z "$so_file" ] || [ ! -f "$so_file" ]; then
        print_log "WARN" "libms_service_profiler.so not found, skip."
        return 0
    fi
    copy_overlay "$so_file" "$dst" || return 1
    return 0
}

function do_overlay_include() {
    local dst=$1
    if [ ! -d "${INCLUDE_SRC}/${INCLUDE_MS_SERVICE_PROFILER}" ]; then
        print_log "WARN" "include/msServiceProfiler/ not found, skip."
        return 0
    fi
    copy_overlay "${INCLUDE_SRC}/${INCLUDE_MS_SERVICE_PROFILER}" "$dst" || return 1
    return 0
}

# Main
if [ -z "$upgrade_path" ]; then
    print_log "ERROR" "upgrade_path is required."
    exit 1
fi

upgrade_path=$(readlink -f "${upgrade_path}")
if [ ! -d "$upgrade_path" ]; then
    print_log "WARN" "Upgrade path does not exist: $upgrade_path."
    exit 1
fi

print_log "INFO" "Upgrade target path: ${upgrade_path}"

# Phase 1: Discover targets (no modifications)
targets=$(discover_targets) || exit 1
targets=$(echo "$targets" | sed '/^$/d')

if [ -z "$targets" ]; then
    print_log "WARN" "No targets to upgrade (whl/so/include may be missing in package)."
fi

# Phase 2: List all paths to replace
print_log "INFO" "The following files will be overwritten. To keep the original files, please manually copy and backup them."
echo "$targets" | while IFS='|' read -r rp ct; do
    [ -n "$rp" ] && echo "  - $rp"
done

# Phase 3: User confirmation (skip if --quiet)
if [ "$quiet_flag" != "1" ]; then
    if [ ! -t 0 ]; then
        print_log "ERROR" "Non-interactive mode. Use --quiet to skip confirmation."
        exit 1
    fi
    echo -n "Confirm to proceed? [y/N]: "
    read -r confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        print_log "INFO" "Upgrade cancelled by user."
        exit 0
    fi
fi

# Phase 4: Execute overlay (only after confirmation), with rollback on failure
BACKUP_DIR=$(mktemp -d) || { print_log "ERROR" "Failed to create backup directory."; exit 1; }
trap 'rm -rf "$BACKUP_DIR" 2>/dev/null' EXIT

while IFS='|' read -r replace_path content_type; do
    [ -z "$replace_path" ] && continue
    if ! backup_for_rollback "$replace_path" "$BACKUP_DIR" >/dev/null 2>&1; then
        print_log "ERROR" "Failed to backup $replace_path for rollback."
        rollback_restore "$BACKUP_DIR"
        exit 1
    fi
    case "$content_type" in
        pkg)   do_overlay_pkg "$replace_path" || { rollback_restore "$BACKUP_DIR"; exit 1; } ;;
        so)    do_overlay_so "$replace_path" || { rollback_restore "$BACKUP_DIR"; exit 1; } ;;
        include) do_overlay_include "$replace_path" || { rollback_restore "$BACKUP_DIR"; exit 1; } ;;
    esac
done <<< "$targets"

# Phase 5: pip install whl for entry point registration (vllm.general_plugins etc.)
whl_file=$(ls ms_service_profiler-*.whl 2>/dev/null | head -1)
if [ -n "$whl_file" ] && [ -f "$whl_file" ]; then
    whl_abs=$(readlink -f "$whl_file" 2>/dev/null || realpath "$whl_file" 2>/dev/null || echo "${PWD}/${whl_file}")
    if python3 -m pip install "$whl_abs" 2>/dev/null; then
        print_log "INFO" "pip install whl for entry point registration"
    elif pip install "$whl_abs" 2>/dev/null; then
        print_log "INFO" "pip install whl for entry point registration"
    else
        print_log "WARN" "pip install failed (entry points may not work)"
    fi
fi

print_log "INFO" "Upgrade completed."
