# msServiceProfiler Installation Guide

<br>

## 1. Installation Notes

This tool is integrated into CANN. If CANN is already installed and you do not need to update this tool, you can use it directly without following the installation instructions in this document.

If CANN is not installed in your environment, see the [CANN Quick Installation](https://www.hiascend.com/en/cann/download) guide to install the Ascend NPU driver and CANN software (including Toolkit and the ops package), and configure the environment variables.

If you need to upgrade this tool separately or use the latest version, you can install it in the following three ways: [Online Installation](#21-online-installation), [Offline Installation](#22-offline-installation), [Source Installation](#23-source-installation).

## 2. Installation Methods

### 2.1 Online Installation

If your device can access the Internet, you can download and install the tool automatically with a single command. Go to the MindStudio [download](https://www.hiascend.com/developer/software/mindstudio/download) page on the Ascend community, select the corresponding CANN version, and choose **Online installation** as the installation method; the system will guide you through the remaining steps.

### 2.2 Offline Installation

For devices on an enterprise intranet or in other environments without external network access, first download the complete offline installation package on a machine with network access, then transfer it to the target device for installation. Go to the MindStudio [download](https://www.hiascend.com/developer/software/mindstudio/download) page on the Ascend community, select the corresponding CANN version, and choose **Offline installation** as the installation method to obtain the package and the installation instructions.

### 2.3 Source Installation

To use the features of the latest code, or to modify the source code to enhance functionality, you can download the code of this repository, compile and package the tool yourself, and complete the installation.

#### 2.3.1 Environment Setup

Source code compilation uses the standard MindStudio build environment.

- For daily development or when using a released image, see *[MindStudio Tool Development Environment Setup Guide](https://gitcode.com/Ascend/msot/blob/master/docs/en/common/dev_env_setup.md)*.
- When you need to reproduce the environment from a base OS, or to run source build verification or unit test verification, you must see *[MindStudio Unified Build Image Creation Guide](https://gitcode.com/Ascend/msot/blob/master/docs/en/common/docker_image_build_guide.md)* and build the environment image on site from the openEuler base image.

The source compilation and unit test commands later in this document are all executed in the container of the specified image above or of the on-site built environment image. The CANN, GCC, and Python versions are subject to the unified image creation guide and are not duplicated in this repository.

After the image is built, you must use the `ctr_in.py` command provided in Chapter 7 of the unified image creation guide to start and enter the container in an interactive terminal. Do not create containers with a plain `docker run`, and do not use `docker exec <container name> bash -c '<command>'` instead of an interactive environment; otherwise the initialization of the Python, GCC, and CANN environments may be skipped.

After entering the interactive container shell opened by `ctr_in.py`, run the following command to clone this repository:

```bash
cd ~
git clone https://gitcode.com/Ascend/msserviceprofiler.git
```

#### 2.3.2 Building

Staying in the same interactive container shell opened by `ctr_in.py`, run the following commands in the repository root directory to download the dependencies and build the project automatically:

```bash
cd ~/msserviceprofiler
python3 build.py
```

After a successful build, the installation package is generated in the `artifacts/` directory.

#### 2.3.3 Running Unit Tests (Optional)

This step is not required for installation. To verify the basic functionality of the code, you can run the unit tests:

```bash
cd ~/msserviceprofiler
python3 build.py test
```

If the command returns 0 and no test case fails, the unit tests have passed.

#### 2.3.4 Installation

##### 2.3.4.1 Preparing the run Package

Before installing the software package, add the executable permission to the run package. Go to the directory where the run package is stored and run the following command to add the executable permission.

```bash
cd ~/msserviceprofiler/artifacts
chmod +x mindstudio-service-profiler_<version>_<arch>.run
```

##### 2.3.4.2 Installation

Copy the run package to the runtime environment and run the following command to install it.

```bash
./mindstudio-service-profiler_<version>_<arch>.run --install
```

The software package is installed successfully when the output contains the following information.

```ColdFusion
mindstudio-msserviceprofiler package install success, the path is: '<install_path>'.
```

>[!NOTE]
>
> - Default installation path: `/usr/local/Ascend/cann` for the root user, and `${HOME}/Ascend/cann` for non-root users.
>
> - To install to a specified path, add `--install-path`, for example `./mindstudio-service-profiler_<version>_<arch>.run --install --install-path=<install_path>`.
>
> - If an earlier version of the tool is already installed, use `--upgrade` to perform an overwrite upgrade, and specify the installation path with `--install-path` or the `ASCEND_TOOLKIT_HOME` environment variable.

## 3. Verifying the Installation

After the installation is complete, run the following command to verify whether the tool is installed successfully:

```bash
pip list | grep ms_service_profiler
```

If the output contains no errors and displays version information, the installation is successful.

## 4. Uninstallation

You can uninstall the tool by following these steps:

1. Download the script.

   ```bash
   curl -O https://inst.obs.cn-north-4.myhuaweicloud.com/26.2.0/ms_install.py
   ```

   >[!NOTE]
   >
   > - An internet connection is required for downloading. If the environment does not allow internet access or is offline, please download the script in an environment with internet access first and then copy it to the target device.
   > - If the command does not respond or errors such as connection failure or SSL certificate errors occur, please refer to [FAQ](https://www.hiascend.com/developer/blog/details/02176213671719317003).

2. Perform the uninstallation.

   ```bash
   python3 ms_install.py uninstall {tools_name}
   ```

   Where {tools_name} is configured as the name of the tool to be uninstalled. You can query it using the `python3 ms_install.py help` command; the tool name is displayed under the Available Tools field in the printed information.

   If the uninstallation is successful, the following information is printed:

   ```ColdFusion
   Successfully uninstalled 1 tool ({tools_name})
   ```

## 5. Upgrade

Upgrading means "uninstall first, then install." Simply run the installation command, and the tool will automatically uninstall the old version and guide you through the overwrite installation.
You can check the version information of the current environment by running the `pip list | grep ms_service_profiler` command, and then select the version you want to upgrade to. When upgrading, pay attention to the version compatibility. For details, see [Release Notes](https://gitcode.com/Ascend/release-management/blob/master/MindStudio/26.2.0/release_notes.md).
