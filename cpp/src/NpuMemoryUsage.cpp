/* -------------------------------------------------------------------------
 * This file is part of the MindStudio project.
 * Copyright (c) 2025 Huawei Technologies Co.,Ltd.
 *
 * MindStudio is licensed under Mulan PSL v2.
 * You can use this software according to the terms and conditions of the Mulan PSL v2.
 * You may obtain a copy of Mulan PSL v2 at:
 *
 *          http://license.coscl.org.cn/MulanPSL2
 *
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
 * EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
 * MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
 * See the Mulan PSL v2 for more details.
 * -------------------------------------------------------------------------
 */

#include "msServiceProfiler/NpuMemoryUsage.h"

#include <dlfcn.h>

#include <iostream>
#include <vector>

#include "../include/msServiceProfiler/Log.h"
#include "msServiceProfiler/SecurityUtils.h"

namespace msServiceProfiler
{

NpuMemoryUsage::NpuMemoryUsage()
{
    const std::string soName = "/usr/local/Ascend/driver/lib64/driver/libdcmi.so";  // LCOV_EXCL_LINE
    handleDcmi = dlopen(soName.c_str(), RTLD_LAZY | RTLD_LOCAL);
    if (handleDcmi == nullptr)
    {
        // LCOV_EXCL_START
        PROF_LOGW(
            "Failed to dlopen libdcmi.so. Will be not able to get NPU usage data. "
            "Check whether a NPU server or if NPU driver installed.");
        // LCOV_EXCL_STOP
    }
}

NpuMemoryUsage::~NpuMemoryUsage()
{
    if (handleDcmi != nullptr)
    {
        dlclose(handleDcmi);
        handleDcmi = nullptr;
    }
}

int NpuMemoryUsage::DcmiInit()
{
    using DcmiInitFunc = int (*)();
    if (handleDcmi == nullptr)
    {
        return EXITCODE_EMPTY_DCMI_HANDLER;
    }

    DcmiInitFunc dcmiInit = (DcmiInitFunc)dlsym(handleDcmi, "dcmi_init");
    if (!dcmiInit)
    {
        PROF_LOGW("Error: %s", dlerror());
        dlclose(handleDcmi);
        handleDcmi = nullptr;
        return EXITCODE_EMPTY_DLSYM_ADDR;
    }

    int ret = dcmiInit();
    return ret;
}

int NpuMemoryUsage::DcmiGetCardList(int *paramCardNum, int *paramCardList, int paramListLen) const
{
    using DcmiGetCardListFunc = int (*)(int *, int *, int);
    if (handleDcmi == nullptr)
    {
        return EXITCODE_EMPTY_DCMI_HANDLER;
    }
    DcmiGetCardListFunc dcmiGetCardList = (DcmiGetCardListFunc)dlsym(handleDcmi, "dcmi_get_card_list");
    if (dcmiGetCardList == nullptr)
    {
        PROF_LOGE("ERROR: cannot get dcmi get card list interface.");
        return EXITCODE_EMPTY_DLSYM_ADDR;
    }
    int ret = dcmiGetCardList(paramCardNum, paramCardList, paramListLen);
    return ret;
}

int NpuMemoryUsage::DcmiGetDeviceIdInCard(int cardId, int *deviceIdMax) const
{
    using DcmiGetDeviceIdInCardFunc = int (*)(int, int *, int *, int *);
    if (handleDcmi == nullptr)
    {
        return EXITCODE_EMPTY_DCMI_HANDLER;
    }
    DcmiGetDeviceIdInCardFunc dcmiGetDeviceIdInCard =
        (DcmiGetDeviceIdInCardFunc)dlsym(handleDcmi, "dcmi_get_device_id_in_card");
    if (dcmiGetDeviceIdInCard == nullptr)
    {
        return EXITCODE_EMPTY_DCMI_HANDLER;
    }
    int mcuId = 0;
    int cpuId = 0;
    int ret = dcmiGetDeviceIdInCard(cardId, deviceIdMax, &mcuId, &cpuId);
    return ret;
}

int NpuMemoryUsage::DcmiGetDeviceMemoryInfoV3(int cardId, int deviceId,
                                              struct dcmi_get_memory_info_stru *memoryInfo) const
{
    using DcmiGetDeviceMemoryInfoV3Func = int (*)(int, int, dcmi_get_memory_info_stru *);
    if (handleDcmi == nullptr)
    {
        return EXITCODE_EMPTY_DCMI_HANDLER;
    }
    DcmiGetDeviceMemoryInfoV3Func dcmiGetDeviceMemoryInfoV3 =
        (DcmiGetDeviceMemoryInfoV3Func)dlsym(handleDcmi, "dcmi_get_device_memory_info_v3");
    int ret = dcmiGetDeviceMemoryInfoV3(cardId, deviceId, memoryInfo);
    return ret;
}

int NpuMemoryUsage::DcmiGetDeviceHbmInfo(int cardId, int deviceId, struct dsmi_hbm_info_stru *hbmInfo) const
{
    using DcmiGetDeviceHbmInfoFunc = int (*)(int, int, dsmi_hbm_info_stru *);
    if (handleDcmi == nullptr)
    {
        return EXITCODE_EMPTY_DCMI_HANDLER;
    }
    DcmiGetDeviceHbmInfoFunc dcmiGetDeviceHbmInfo =
        (DcmiGetDeviceHbmInfoFunc)dlsym(handleDcmi, "dcmi_get_device_hbm_info");
    if (dcmiGetDeviceHbmInfo == nullptr)
    {
        return EXITCODE_EMPTY_DCMI_HANDLER;
    }
    int ret = dcmiGetDeviceHbmInfo(cardId, deviceId, hbmInfo);
    return ret;
}

int NpuMemoryUsage::InitDcmiCard()
{
    int ret = DcmiInit();
    if (ret != EXITCODE_SUCCESS)
    {
        return ret;
    }

    ret = DcmiGetCardList(&cardNum, cardList, listLen);
    if (ret != EXITCODE_SUCCESS)
    {
        return ret;
    }

    cardNum = std::min(MAX_CHIP_NUM, cardNum);
    return EXITCODE_SUCCESS;
}

int NpuMemoryUsage::InitDcmiCardAndDevices()
{
    if (isDcmiInited)
    {
        return EXITCODE_SUCCESS;
    }
    isDcmiInited = true;
    int ret = InitDcmiCard();
    if (cardNum == 0)
    {
        return ret;
    }
    for (int cardId = 0; cardId < cardNum; cardId++)
    {
        int deviceIdMax = 0;
        int curRet = DcmiGetDeviceIdInCard(cardList[cardId], &deviceIdMax);
        if (curRet != EXITCODE_SUCCESS)
        {
            ret = ret + curRet;
            continue;
        }
        for (int deviceId = 0; deviceId < deviceIdMax; deviceId++)
        {
            cardDevices.push_back({cardList[cardId], deviceId});
        }
    }

    return ret;
}

int NpuMemoryUsage::GetByDcmi(std::vector<int> &memoryUsed, std::vector<int> &memoryUtiliza)
{
    int ret = EXITCODE_SUCCESS;
    for (const auto &cardDevice : cardDevices)
    {
        int curRet = EXITCODE_SUCCESS;
        // Could either be getting by DcmiGetDeviceMemoryInfoV3 or DcmiGetDeviceHbmInfo
        if (not isHbmDevice)
        {  // Global value
            struct dcmi_get_memory_info_stru memoryInfo;
            curRet = DcmiGetDeviceMemoryInfoV3(cardDevice.cardId, cardDevice.deviceId, &memoryInfo);
            if (curRet != EXITCODE_SUCCESS)
            {
                isHbmDevice = true;  // Will try DcmiGetDeviceHbmInfo later, and skip this next time
            }
            else
            {
                memoryUsed.push_back(memoryInfo.memory_size - memoryInfo.memory_available);
                memoryUtiliza.push_back(memoryInfo.utiliza);
            }
        }

        if (isHbmDevice)
        {
            struct dsmi_hbm_info_stru hbmInfo;
            curRet = DcmiGetDeviceHbmInfo(cardDevice.cardId, cardDevice.deviceId, &hbmInfo);
            if (curRet != EXITCODE_SUCCESS)
            {
                ret = ret + curRet;
                continue;
            }

            const int hbmMemorySize = std::max(HBM_MEMORY_SIZE_FALL_BACK, hbmInfo.memory_size);
            memoryUsed.push_back(hbmInfo.memory_usage);
            memoryUtiliza.push_back(hbmInfo.memory_usage * PERCENTAGE_SCALE / hbmMemorySize);
        }
    }
    return ret;
}
}  // namespace msServiceProfiler
