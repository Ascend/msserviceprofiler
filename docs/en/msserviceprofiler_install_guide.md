# msServiceProfiler Installation Guide

<!-- md-trans-meta sourceCommit=unknown translatedAt=2026-06-24T02:30:55.891Z pushedAt=2026-06-24T10:56:06.401Z -->

## 1. Installation Notes

This tool is integrated into CANN. If CANN is already installed and you do not need to update this tool, you can use it directly without following the installation instructions in this document.

If CANN is not installed in your environment, see the [CANN Quick Installation](https://www.hiascend.com/en/cann/download) guide to install the Ascend NPU driver and CANN software (including Toolkit and the ops package), and configure the environment variables.

If you need to upgrade this tool separately or use the latest version, you can install it in the following three ways: [Online Installation](#21-online-installation), [Offline Installation](#22-offline-installation), [Source Installation](#23-source-installation).

## 2. Installation Methods

### 2.1 Online Installation

If your device has internet access, you can automatically download and install the tool with a single command. Visit the Ascend Community MindStudio [download](https://www.hiascend.com/en/developer/software/mindstudio/download?versionId=152&ids=45%2Cb1e62037594d4e5c9a0fd797ff490006%2C124%2C49%2C) page, select the corresponding CANN version, and choose "Online Installation" as the installation method. The system will guide you through the subsequent steps.

### 2.2 Offline Installation

For devices in environments without external network access, such as enterprise intranets, first download the complete offline installation package on a machine with internet access, then transfer it to the target device for installation. Visit the Ascend Community MindStudio [download](https://www.hiascend.com/en/developer/software/mindstudio/download?versionId=152&ids=45%2Cb1e62037594d4e5c9a0fd797ff490006%2C124%2C50%2C) page, select the corresponding CANN version, and choose "Offline Installation" as the installation method to obtain the corresponding installation package and operation guide.

### 2.3 Source Installation

```shell
# 1. Install build dependencies
apt-get install libsqlite3-dev  # For RHEL/CentOS/Fedora and other systems using yum, run: yum install sqlite sqlite-devel

# 2. Pull the source code
git clone https://gitcode.com/Ascend/msserviceprofiler.git -b 26.1.0
cd msserviceprofiler

# 3. Execute one-click build and upgrade (automatically completes: download third-party dependencies > build run package > execute installation/upgrade)

# Method 1: Use the CANN installation path specified by the environment variable ASCEND_TOOLKIT_HOME
bash scripts/build_and_upgrade.sh

# Method 2: Manually specify the CANN installation path
bash scripts/build_and_upgrade.sh --install-path=/usr/local/Ascend/ascend-toolkit
```

During execution, the files to be overwritten will be listed and confirmation will be required. A sample output is as follows:

```ColdFusion
Verifying archive integrity...  100%   SHA256 checksums are OK. All good.
Uncompressing mindstudio-service-profiler  100%  
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: Upgrade target path: /usr/local/Ascend/cann-x.x.x
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: The following files will be overwritten. To keep the original files, please manually copy or backup them.
  - /usr/local/Ascend/cann-x.x.x/python/site-packages/ms_service_profiler
  - /usr/local/Ascend/cann-x.x.x/python/site-packages/ms_service_profiler/libms_service_profiler.so
Confirm to proceed? [y/N]: 
```

After entering y or Y to confirm, the following information will be displayed upon successful execution.

```ColdFusion
Successfully installed ... ms_service_profiler-x.x.x
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: pip install whl for entry point registration
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: Upgrade completed.
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: mindstudio-msserviceprofiler upgrade completed, the path is: '/usr/local/Ascend/cann-x.x.x'.

[INFO] build and upgrade completed.
```

>[!NOTE]
>
> - Installation or upgrade will automatically overwrite target files such as `ms_service_profiler`, `libms_service_profiler.so`, and `include/msServiceProfiler` in the CANN installation path. If you need to keep the original files, manually back them up in advance according to the file list displayed during execution.
> - If `ASCEND_TOOLKIT_HOME` is not set and `--install-path` is not specified, the execution will fail with a prompt to manually specify the CANN installation path.
> - If the installation is interrupted midway or terminates abnormally due to missing dependencies or other issues, delete the `msserviceprofiler/build` directory before re-executing. Command: `rm -r msserviceprofiler/build`.

## 3. Verifying the Installation

After the installation is complete, run the following command to verify whether the tool is installed successfully:

```shell
  pip list | grep msserviceprofiler
```

If the output contains no errors and displays version information, the installation is successful.

## 4. Uninstallation

You can uninstall the tool by following these steps:

1. Download the script.

   ```bash
   curl -O https://inst.obs.cn-north-4.myhuaweicloud.com/26.1.0/ms_install.py
   ```

   >[!NOTE]
   >
   > - An internet connection is required for downloading. If the environment does not allow internet access or is offline, please download the script in an environment with internet access first and then copy it to the target device.
   > - If the command does not respond or errors such as connection failure or SSL certificate errors occur, please refer to [FAQ](https://www.hiascend.com/developer/blog/details/02176213671719317003).

2. Perform the uninstallation.

   ```bash
   python ms_install.py uninstall {tools_name}
   ```

   Where {tools_name} is configured as the name of the tool to be uninstalled. You can query it using the `python ms_install.py help` command; the tool name is displayed under the Available Tools field in the printed information.

   If the uninstallation is successful, the following information is printed:

   ```ColdFusion
   Successfully uninstalled 1 tool ({tools_name})
   ```

## 5. Upgrade

Upgrading means "uninstall first, then install." Simply run the installation command, and the tool will automatically uninstall the old version and guide you through the overwrite installation.
You can check the version information of the current environment by running the `pip list | grep msserviceprofiler` command, and then select the version you want to upgrade to. When upgrading, pay attention to the version compatibility. For details, see [Release Notes](https://gitcode.com/Ascend/release-management/blob/master/MindStudio/26.1.0/release_notes.md).
