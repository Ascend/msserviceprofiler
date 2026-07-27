# msServiceProfiler 工具安装指南

## 1. 安装说明

本工具已集成于CANN中，若已安装CANN且无需更新此工具，可直接使用，无需按本文档安装。

若您的环境尚未安装CANN，请参见《[CANN 快速安装](https://www.hiascend.com/cann/download)》安装昇腾NPU驱动和CANN软件（包含Toolkit和ops包），并配置环境变量。

如需单独升级本工具或使用最新版本，您可通过以下三种方式进行安装：[在线安装](#21-在线安装)、[离线安装](#22-离线安装)、[源码安装](#23-源码安装)。

## 2. 安装方式

### 2.1 在线安装

若您的设备具备互联网访问能力，可通过一条命令自动完成工具的下载与安装。请参见昇腾社区MindStudio[下载](https://www.hiascend.com/developer/software/mindstudio/download)页面，选择对应的CANN版本，并在安装方式中选择“在线安装”，系统将引导您完成后续操作。

### 2.2 离线安装

对处于企业内网等无外网环境的设备，请先在可联网的机器上下载完整的离线安装包，再将其传输至目标设备进行安装。请参见昇腾社区MindStudio[下载](https://www.hiascend.com/developer/software/mindstudio/download)页面，选择对应的CANN版本，并在安装方式中选择“离线安装”，获取对应的安装包及操作指引。

### 2.3 源码安装

```shell
# 1. 安装构建依赖
apt-get install libsqlite3-dev  # RHEL/CentOS/Fedora 等使用 yum 的系统请执行：yum install sqlite sqlite-devel

# 2. 拉取源码
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler

# 3. 执行一键构建并升级（自动完成：下载第三方依赖 > 构建 run 包 > 执行安装/升级）

# 方式一：使用环境变量 ASCEND_TOOLKIT_HOME 指定的 CANN 安装路径
bash scripts/build_and_upgrade.sh

# 方式二：手动指定 CANN 安装路径
bash scripts/build_and_upgrade.sh --install-path=/usr/local/Ascend/ascend-toolkit
```

执行时将列出将被覆盖的文件并等待确认，示例回显如下：

```ColdFusion
Verifying archive integrity...  100%   SHA256 checksums are OK. All good.
Uncompressing mindstudio-service-profiler  100%  
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: Upgrade target path: /usr/local/Ascend/cann-x.x.x
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: The following files will be overwritten. To keep the original files, please manually copy or backup them.
  - /usr/local/Ascend/cann-x.x.x/python/site-packages/ms_service_profiler
  - /usr/local/Ascend/cann-x.x.x/python/site-packages/ms_service_profiler/libms_service_profiler.so
Confirm to proceed? [y/N]: 
```

输入 y 或 Y 确认后，执行成功将有以下回显信息。

```ColdFusion
Successfully installed ... ms_service_profiler-x.x.x
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: pip install whl for entry point registration
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: Upgrade completed.
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: mindstudio-msserviceprofiler upgrade completed, the path is: '/usr/local/Ascend/cann-x.x.x'.

[INFO] 构建并升级完成。
```

> [!NOTE]
>
> - 安装或升级将自动覆盖 CANN 安装路径下的 `ms_service_profiler`、`libms_service_profiler.so`、`include/msServiceProfiler` 等目标文件。如需保留原文件，请根据执行时列出的文件清单提前手动备份。
> - 若未设置 `ASCEND_TOOLKIT_HOME` 且未指定 `--install-path`，将执行失败并提示需手动指定 CANN 安装路径。
> - 若安装中途终止或因依赖缺失等异常终止，请先删除 `msserviceprofiler/build` 目录后再重新执行，命令：`rm -r msserviceprofiler/build`。

## 3. 验证安装

安装完成后，执行以下命令验证工具是否安装成功：

```shell
  pip list | grep msserviceprofiler
```

若输出不报错，且能显示版本信息，则表明安装成功。

## 4. 卸载

可通过如下步骤卸载：

1. 下载脚本。

   ```bash
   curl -O https://inst.obs.cn-north-4.myhuaweicloud.com/26.1.0/ms_install.py
   ```

   > [!NOTE]
   >
   > - 需要联网环境才能下载，若环境不允许联网或离线状态，请先在可联网的环境下载该脚本后拷贝到目标设备。
   > - 若执行命令无响应或出现连接失败、SSL证书错误等问题，请参见[FAQ](https://www.hiascend.com/developer/blog/details/02176213671719317003)。

2. 执行卸载。

   ```bash
   python ms_install.py uninstall {tools_name}
   ```

   其中{tools_name}配置为需要卸载的工具名称，可通过`python ms_install.py help`命令查询，在打印信息中的Available Tools字段下显示工具名称。

   卸载成功打印如下信息：

   ```ColdFusion
   Successfully uninstalled 1 tool ({tools_name})
   ```

## 5. 升级

升级即“先卸后装”。直接执行安装命令，工具将自动卸载旧版本，并引导您完成覆盖安装。<br>
可通过`pip list | grep msserviceprofiler`命令查看当前环境的版本信息，再选择需要升级的版本。升级版本时需要关注版本配套关系，请参见《[版本说明](https://gitcode.com/Ascend/release-management/blob/master/MindStudio/26.1.0/release_notes.md)》。
