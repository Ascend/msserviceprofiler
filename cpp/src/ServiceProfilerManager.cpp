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

#include "msServiceProfiler/ServiceProfilerManager.h"

#include <fcntl.h>
#include <semaphore.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <climits>
#include <cmath>
#include <csignal>
#include <cstring>
#include <ctime>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <string>
#include <thread>
#include <unordered_set>
#include <vector>

#include "acl/acl.h"
#include "acl/acl_prof.h"
#include "msServiceProfiler/DBExecutor/DbExecutorMetaData.h"
#include "msServiceProfiler/DBExecutor/DbExecutorServiceData.h"
#include "msServiceProfiler/DBExecutor/DbExecutorSliceData.h"
#include "msServiceProfiler/Log.h"
#include "msServiceProfiler/Profiler.h"
#include "msServiceProfiler/SecurityUtilsLog.h"
#include "msServiceProfiler/ServiceProfilerDbWriter.h"
#include "msServiceProfiler/ServiceProfilerInterface.h"
#include "msServiceProfiler/ServiceProfilerMspti.h"
#include "msServiceProfiler/Utils.h"
#include "mstx/ms_tools_ext.h"
#include "securec.h"

namespace
{
constexpr int MAX_TX_MSG_LEN = 128;
constexpr int MAX_DEVICE_NUM = 128;
constexpr int SPAN_CACHE_LEN = 64;
// 与 libprofapi ProfilerCallbackType 中 PROFILE_DEVICE_STATE_C_CALLBACK 一致（C 风格设备状态回调）
constexpr int32_t kProfileDeviceStateCCallback = 16;
struct DlCloser
{
    void operator()(void *handle) const noexcept
    {
        if (handle)
        {
            dlclose(handle);
        }
    }
};
using LibraryHandle = std::unique_ptr<void, DlCloser>;

std::once_flag &GetProcessRegisteredFlag()
{
    static std::once_flag flag;
    return flag;
}

bool &GetThreadRegisteredRef()
{
    thread_local bool registered = false;
    return registered;
}

std::pair<uint32_t, uint32_t> GetCurrentTidPid()
{
    uint32_t tid = MsUtils::GetTid();
    uint32_t pid = static_cast<uint32_t>(getpid());
    return {tid, pid};
}

void EnsureProcessRegistered(uint32_t pid)
{
    std::call_once(
        GetProcessRegisteredFlag(),
        [pid]()
        {
            msServiceProfiler::DbProcessData procData;
            std::string pidStr = std::to_string(pid);
            procData.pid = std::move(pidStr);
            procData.process_name = procData.pid;
            procData.label = "";
            procData.parentPid = "";

            auto procExecutor = std::make_unique<msServiceProfiler::DbExecutor<msServiceProfiler::PROCESS_INSERT_STMT>>(
                std::move(procData));

            msServiceProfiler::InsertExecutor2Writer<msServiceProfiler::DBFile::SERVICE>(std::move(procExecutor));
        });
}

void EnsureThreadRegistered(uint32_t tid, uint32_t pid, const char *domain)
{
    bool &registered = GetThreadRegisteredRef();
    if (!registered)
    {
        msServiceProfiler::DbThreadData threadData;
        threadData.track_id = tid;
        threadData.tid = std::to_string(tid);
        threadData.pid = std::to_string(pid);
        threadData.thread_name = (domain ? std::string(domain) : "") + "(" + std::to_string(tid) + ")";
        threadData.thread_sort_index = 0;

        auto threadExecutor = std::make_unique<msServiceProfiler::DbExecutor<msServiceProfiler::THREAD_INSERT_STMT>>(
            std::move(threadData));

        msServiceProfiler::InsertExecutor2Writer<msServiceProfiler::DBFile::SERVICE>(std::move(threadExecutor));

        registered = true;
    }
}

void WriteSliceEvent(const char *name, const char *domain, const char *msg, uint64_t timestamp, uint64_t duration,
                     uint32_t tid, uint32_t pid)
{
    msServiceProfiler::DbSliceData sliceData;
    sliceData.timestamp = timestamp;
    sliceData.duration = duration;
    sliceData.name = name ? name : "";
    sliceData.depth = 0;
    sliceData.track_id = tid;
    sliceData.cat = domain ? domain : "";
    sliceData.args = msg ? msg : "";
    sliceData.cname = "";
    sliceData.end_time = timestamp + duration;
    sliceData.flag_id = "";
    sliceData.pid = pid;
    sliceData.tid = tid;

    auto executor =
        std::make_unique<msServiceProfiler::DbExecutor<msServiceProfiler::SLICE_INSERT_STMT>>(std::move(sliceData));

    msServiceProfiler::InsertExecutor2Writer<msServiceProfiler::DBFile::SERVICE>(std::move(executor));
}
}  // end of anonymous namespace

std::atomic<u_int64_t> g_markIndex(0);

std::atomic<int> prof_current_step_num{0};

using DATA_PTR = struct ProfSetDevParaDevice *;

MS_SERVICE_PROFILER_API void SetProfilerCurrentStep(int current_step_num)
{
    prof_current_step_num.store(current_step_num, std::memory_order_relaxed);
}

MS_SERVICE_PROFILER_API int GetProfilerCurrentStep() { return prof_current_step_num.load(std::memory_order_relaxed); }

struct ProfSetDevParaDevice
{
    uint32_t chipId;
    uint32_t deviceId;
    bool isOpen;
};

static uint64_t *GetSpanStartTimeCache()
{
    thread_local u_int64_t cacheSpanStartTime[SPAN_CACHE_LEN + 8];
    return cacheSpanStartTime;
}

SpanHandle StartSpanWithName(const char *name)
{
    // 对外接口，纯用户线程，无多线程数据交互
    if (name == nullptr)
    {
        return StartSpan();
    }

    auto timestamp = MsUtils::GetCurrentTimeInNanoseconds();
    uint64_t *timeCache = GetSpanStartTimeCache();
    auto threadMarkId = timeCache[0];
    threadMarkId++;
    timeCache[0] = threadMarkId;
    auto location = threadMarkId % SPAN_CACHE_LEN + 1;
    *(timeCache + location) = timestamp;

    return threadMarkId;
}

SpanHandle StartSpan() { return StartSpanWithName(""); }

void MarkSpanAttr(const char *msg, SpanHandle spanHandle)
{
    // 对外接口，用户线程，数据通过 dbBuffer[线程安全] 给到 dbWriter 线程
    if (msg == nullptr)
    {
        return;
    }

    thread_local uint32_t tid = MsUtils::GetTid();  // 每个线程有自己的副本

    uint64_t *timeCache = GetSpanStartTimeCache();
    auto location = spanHandle % SPAN_CACHE_LEN + 1;
    auto stratTimestamp = *(timeCache + location);

    msServiceProfiler::DbActivityMarker marker;
    marker.flag = msServiceProfiler::ActivityFlag::ACTIVITY_FLAG_MARKER_SPAN;
    marker.timestamp = stratTimestamp;
    marker.endTimestamp = MsUtils::GetCurrentTimeInNanoseconds();
    marker.id = g_markIndex.fetch_add(1);
    marker.processId = static_cast<uint32_t>(getpid());
    marker.threadId = tid;
    marker.message = msg;

    auto executor =
        std::make_unique<msServiceProfiler::DbExecutor<msServiceProfiler::SERVICE_INSERT_STMT>>(std::move(marker));
    msServiceProfiler::InsertExecutor2Writer<msServiceProfiler::DBFile::SERVICE>(std::move(executor));
}

void EndSpan(SpanHandle) { return; }

void MarkEvent(const char *msg)
{
    // 对外接口，用户线程，数据通过 dbBuffer[线程安全] 给到 dbWriter 线程
    if (msg == nullptr)
    {
        return;
    }

    thread_local uint32_t tid = MsUtils::GetTid();  // 每个线程有自己的副本
    msServiceProfiler::DbActivityMarker marker;
    marker.flag = msServiceProfiler::ActivityFlag::ACTIVITY_FLAG_MARKER_EVENT;
    marker.timestamp = MsUtils::GetCurrentTimeInNanoseconds();
    marker.endTimestamp = marker.timestamp;
    marker.id = g_markIndex.fetch_add(1);
    marker.processId = static_cast<uint32_t>(getpid());
    marker.threadId = tid;
    marker.message = msg;

    auto executor =
        std::make_unique<msServiceProfiler::DbExecutor<msServiceProfiler::SERVICE_INSERT_STMT>>(std::move(marker));
    msServiceProfiler::InsertExecutor2Writer<msServiceProfiler::DBFile::SERVICE>(std::move(executor));
}

MS_SERVICE_PROFILER_API void SpanEndEx(const char *name, const char *domain, const char *msg, SpanHandle spanHandle)
{
    const auto tidPid = GetCurrentTidPid();
    const uint32_t tid = tidPid.first;
    const uint32_t pid = tidPid.second;

    EnsureProcessRegistered(pid);
    EnsureThreadRegistered(tid, pid, domain);

    uint64_t *timeCache = GetSpanStartTimeCache();
    auto location = spanHandle % SPAN_CACHE_LEN + 1;
    uint64_t startTimestamp = *(timeCache + location);
    uint64_t endTimestamp = MsUtils::GetCurrentTimeInNanoseconds();
    uint64_t duration = endTimestamp - startTimestamp;

    WriteSliceEvent(name, domain, msg, startTimestamp, duration, tid, pid);
}

MS_SERVICE_PROFILER_API void MarkEventEx(const char *name, const char *domain, const char *msg)
{
    const auto tidPid = GetCurrentTidPid();
    const uint32_t tid = tidPid.first;
    const uint32_t pid = tidPid.second;

    EnsureProcessRegistered(pid);
    EnsureThreadRegistered(tid, pid, domain);

    uint64_t timestamp = MsUtils::GetCurrentTimeInNanoseconds();
    WriteSliceEvent(name, domain, msg, timestamp, 0, tid, pid);
}

void StartServerProfiler()
{
    // 对外接口，用户线程，通过原子变量，将开始事件通知到 Manager 工作线程
    msServiceProfiler::ServiceProfilerManager::GetInstance().NotifyStartProfiler();
}

void StopServerProfiler()
{
    // 对外接口，用户线程，通过原子变量，将关闭事件通知到 Manager 工作线程
    msServiceProfiler::ServiceProfilerManager::GetInstance().NotifyStopProfiler();
}

// 显式导出：避免 -fvisibility=hidden 造成符号被隐藏
MS_SERVICE_PROFILER_API void RegisterProfilerStartCallback(void (*callback)())
{
    // 对外接口，用户线程，注册 mstx 启动回调
    msServiceProfiler::ServiceProfilerManager::GetInstance().RegisterStartCallback(callback);
}

// 显式导出：避免 -fvisibility=hidden 造成符号被隐藏
MS_SERVICE_PROFILER_API void RegisterProfilerStopCallback(void (*callback)())
{
    // 对外接口，用户线程，注册 mstx 停止回调
    msServiceProfiler::ServiceProfilerManager::GetInstance().RegisterStopCallback(callback);
}

MS_SERVICE_PROFILER_API void RegisterProfilerStartMetricCallback(void (*callback)())
{
    msServiceProfiler::ServiceProfilerManager::GetInstance().RegisterStartMetricCallback(callback);
}

MS_SERVICE_PROFILER_API void RegisterProfilerStopMetricCallback(void (*callback)())
{
    msServiceProfiler::ServiceProfilerManager::GetInstance().RegisterStopMetricCallback(callback);
}

bool IsEnable(uint32_t level)
{
    // 对外接口，用户线程，用户线程只读取，工作线程会变更，为了速度，不做保护，判断错了也无所谓
    return msServiceProfiler::ServiceProfilerManager::GetInstance().IsEnable(level);
}

const char *GetProfPath()
{
    // 对外接口，用户线程，用户线程只读取，工作线程会变更，为了速度，不做保护
    return msServiceProfiler::ServiceProfilerManager::GetInstance().GetProfPath().c_str();
}

int GetAclProfAicoreMetrics()
{
    // 对外接口，用户线程，用户线程只读取，工作线程会变更，为了速度，不做保护
    return msServiceProfiler::ServiceProfilerManager::GetInstance().GetAclProfAicoreMetricsValue();
}

bool GetTorchProfStack()
{
    // 对外接口，用户线程只读取，工作线程会变更，为了速度，不做保护
    return msServiceProfiler::ServiceProfilerManager::GetInstance().GetTorchProfStack();
}

bool IsValidDomain(const char *domainName)
{
    // 对外接口，用户线程，用户线程只读取，工作线程会变更，有一定风险，做了部分消减
    const std::set<std::string> &allowNames = msServiceProfiler::ServiceProfilerManager::GetInstance().GetValidDomain();
    return allowNames.empty() || allowNames.find(std::string(domainName)) != allowNames.end();
}

bool GetTorchProfModules()
{
    // 对外接口，用户线程只读取，工作线程会变更，为了速度，不做保护
    return msServiceProfiler::ServiceProfilerManager::GetInstance().GetTorchProfModules();
}

int GetTorchProfStepNum()
{
    // 对外接口，用户线程只读取，工作线程会变更，为了速度，不做保护
    return msServiceProfiler::ServiceProfilerManager::GetInstance().GetTorchProfStepNum();
}

const char *GetAclTaskTimeLevel()
{
    // 对外接口，用户线程只读取，工作线程会变更，为了速度，不做保护
    return msServiceProfiler::ServiceProfilerManager::GetInstance().GetAclTaskTimeLevel().c_str();
}

bool GetTorchProfilerEnable()
{
    // 对外接口，用户线程只读取，工作线程会变更，为了速度，不做保护
    return msServiceProfiler::ServiceProfilerManager::GetInstance().GetTorchProfilerEnable();
}

bool GetEnableDomainFilter()
{
    // 老对外接口，计划兼容一年后日落
    return msServiceProfiler::ServiceProfilerManager::GetInstance().GetEnableDomainFilter();
}

const std::set<std::string> &GetValidDomain()
{
    // 老对外接口，计划兼容一年后日落
    return msServiceProfiler::ServiceProfilerManager::GetInstance().GetValidDomain();
}

void AddMetaInfo(const char *key, const char *value)
{
    // 对外接口，用户线程，数据通过 dbBuffer[线程安全] 给到 dbWriter 线程
    auto executor = std::make_unique<msServiceProfiler::DbExecutor<msServiceProfiler::META_INSERT_STMT>>(key, value);
    msServiceProfiler::InsertExecutor2Writer<msServiceProfiler::DBFile::SERVICE>(std::move(executor));
}

static bool g_usedNewDeviceStateApi = false;

void MsprofSetDeviceCallbackLegacy(DATA_PTR data, uint32_t len)
{
    if (len != sizeof(::ProfSetDevParaDevice))
    {
        return;
    }
    if (data == nullptr)
    {
        return;
    }
    DATA_PTR setCfg = static_cast<DATA_PTR>(data);
    static uint32_t sdeviceID = msServiceProfiler::INVALID_DEVICE_ID;

    if (setCfg->deviceId != sdeviceID)
    {
        sdeviceID = setCfg->deviceId;
        msServiceProfiler::ServiceProfilerManager::GetInstance().NotifyDeviceID(sdeviceID);
    }
    return;
}

int32_t MsprofSetDeviceCallbackImpl(void *data, uint32_t len)
{
    // 不知道什么线程来的，一切皆有可能
    if (len != sizeof(::ProfSetDevParaDevice))
    {
        return -1;
    }
    if (data == nullptr)
    {
        return -1;
    }
    DATA_PTR setCfg = static_cast<DATA_PTR>(data);
    static uint32_t sdeviceID = msServiceProfiler::INVALID_DEVICE_ID;

    if (setCfg->deviceId != sdeviceID)
    {
        sdeviceID = setCfg->deviceId;
        msServiceProfiler::ServiceProfilerManager::GetInstance().NotifyDeviceID(sdeviceID);
    }
    return 0;
}

static void UnregisterDeviceStateCallback(void *profApiHandle)
{
    if (!g_usedNewDeviceStateApi || profApiHandle == nullptr)
    {
        return;
    }
    using MsprofRegisterProfileCallbackFunc = int32_t (*)(int32_t callbackType, void *callback, uint32_t len);
    auto registerFn =
        reinterpret_cast<MsprofRegisterProfileCallbackFunc>(dlsym(profApiHandle, "MsprofRegisterProfileCallback"));
    if (registerFn == nullptr)
    {
        return;
    }
    (void)registerFn(kProfileDeviceStateCCallback, nullptr, sizeof(void *));
    g_usedNewDeviceStateApi = false;
}

static LibraryHandle RegisterSetDeviceCallback()
{
    const char *ascendHomePathPtr = getenv("ASCEND_HOME_PATH");
    if (ascendHomePathPtr == nullptr || ascendHomePathPtr[0] == '\0')
    {
        PROF_LOGW("ASCEND_HOME_PATH is empty. Will be not able to get device profiling data.");  // LCOV_EXCL_LINE
        return LibraryHandle(nullptr);
    }
    const std::string soName = std::string(ascendHomePathPtr) + "/lib64/libprofapi.so";

    // 在工作线程中执行
    void *handle = dlopen(soName.c_str(), RTLD_LAZY | RTLD_LOCAL);
    if (handle == nullptr)
    {
        PROF_LOGW(
            "Failed to dlopen libprofapi.so. Will be not able to get device profiling data. "  // LCOV_EXCL_LINE
            "Check whether a NPU server or if cann toolkit installed.");                       // LCOV_EXCL_LINE
        return LibraryHandle(nullptr);
    }

    // 优先尝试旧接口 profRegDeviceStateCallback
    using ProfSetDeviceHandle = void (*)(DATA_PTR, uint32_t);
    using ProfRegDeviceStateCallbackFunc = int32_t (*)(ProfSetDeviceHandle);
    auto legacyFn = reinterpret_cast<ProfRegDeviceStateCallbackFunc>(dlsym(handle, "profRegDeviceStateCallback"));
    if (legacyFn != nullptr)
    {
        PROF_LOGD("Using legacy profRegDeviceStateCallback API");  // LCOV_EXCL_LINE
        legacyFn(MsprofSetDeviceCallbackLegacy);
        g_usedNewDeviceStateApi = false;
        return LibraryHandle(handle);
    }

    // 旧接口不存在，回退到新接口 MsprofRegisterProfileCallback
    using MsprofRegisterProfileCallbackFunc = int32_t (*)(int32_t callbackType, void *callback, uint32_t len);
    auto registerFn =
        reinterpret_cast<MsprofRegisterProfileCallbackFunc>(dlsym(handle, "MsprofRegisterProfileCallback"));
    if (registerFn == nullptr)
    {
        PROF_LOGW(
            "Failed to get profRegDeviceStateCallback or MsprofRegisterProfileCallback "  // LCOV_EXCL_LINE
            "from libprofapi.so. Will be not able to get device profiling data. "         // LCOV_EXCL_LINE
            "Check whether a NPU server or if cann toolkit installed.");                  // LCOV_EXCL_LINE
        dlclose(handle);
        return LibraryHandle(nullptr);
    }
    int32_t ret =
        registerFn(kProfileDeviceStateCCallback, reinterpret_cast<void *>(MsprofSetDeviceCallbackImpl), sizeof(void *));
    if (ret != 0)
    {
        PROF_LOGW("MsprofRegisterProfileCallback(PROFILE_DEVICE_STATE_C_CALLBACK) failed: %d", ret);  // LCOV_EXCL_LINE
        dlclose(handle);
        return LibraryHandle(nullptr);
    }
    g_usedNewDeviceStateApi = true;
    return LibraryHandle(handle);
}

namespace msServiceProfiler
{

ServiceProfilerManager &ServiceProfilerManager::GetInstance()
{
    static ServiceProfilerManager manager;
    return manager;
}

ServiceProfilerManager::ServiceProfilerManager()
    : configHandle_(nullptr), config_(std::make_shared<Config>()), msptiHandle_(nullptr)
{
    ProfLogInit();
    MarkFirstProcessAsMain();
    config_->ReadAndSaveConfig();
    if (config_->GetEnable())
    {
        // 只有这一个地方是用户线程调用初始化，其他的都放到 manager 工作线程中
        StartProfiler(true);
    }
    notifyStarted = started_;  // 在构造的时候同步一次，其他都在工作线程中。如果值不一样，在工作线程中启动或关闭prof
    LaunchThread();
    PROF_LOGD("ServiceProfilerManager Init Finished");
}

ServiceProfilerManager::~ServiceProfilerManager()
{
    const std::string &exitSemName = GetConfigPath();
    if (!exitSemName.empty())
    {
        shm_unlink(ServiceProfilerManager::ToSemName(exitSemName).c_str());
    }

    if (this->thread_.joinable())
    {
        threadRunFlag_ = false;
        this->thread_.join();
    }
}

std::string ServiceProfilerManager::ToSemName(const std::string &oriSemName)
{
    std::string semName = "/";
    semName.append(oriSemName);
    std::replace(++semName.begin(), semName.end(), '/', '#');
    return semName;
}

void ServiceProfilerManager::MarkFirstProcessAsMain()
{
    // 在用户线程调用，只在初始化中调用一次，不涉及其他模块

    const size_t mmapSize = 1024;     // 共享内存对象的大小
    const size_t infoMaxSize = 1000;  // 内存中信息的最大大小

    const std::string &semNameTouchTime = config_->GetConfigPath();

    if (semNameTouchTime.empty())
    {
        return;
    }

    int shmFd = shm_open(ToSemName(semNameTouchTime).c_str(), O_CREAT | O_RDWR, 0640);
    if (shmFd == -1)
    {
        PROF_LOGW("shm_open failed");  // LCOV_EXCL_LINE
        return;
    }

    // 设置共享内存对象的大小
    if (ftruncate(shmFd, mmapSize) == -1)
    {
        PROF_LOGW("ftruncate failed");  // LCOV_EXCL_LINE
        close(shmFd);
        return;
    }

    // 将共享内存对象映射到进程地址空间
    void *mmapPtr = mmap(nullptr, mmapSize, PROT_READ | PROT_WRITE, MAP_SHARED, shmFd, 0);
    if (mmapPtr == MAP_FAILED)
    {
        PROF_LOGW("mmap failed");  // LCOV_EXCL_LINE
        close(shmFd);
        return;
    }
    char *pInfoStr = static_cast<char *>(mmapPtr);
    std::string infoStr(pInfoStr, infoMaxSize);

    auto splitInfo = MsUtils::SplitStr(infoStr, ',');  // 格式为： pid,目录。所以使用逗号分隔开
    if (!splitInfo.second.empty())
    {
        pid_t pid =
            static_cast<pid_t>(MsUtils::Str2Uint(splitInfo.first));  // 检查的进程 PID, 如果存在，就将和它放到一个目录中
        if (kill(pid, 0) == 0)
        {
            isMaster_ = false;
            config_->SetProfPathDateTail(std::string(splitInfo.second.c_str()));
        }
    }

    if (isMaster_)
    {
        std::string infoOut;
        config_->InitProfPathDateTail(true);
        infoOut.append(std::to_string(getpid())).append(",").append(config_->GetProfPathDateTail());
        if (sprintf_s(pInfoStr, infoMaxSize, "%s", infoOut.c_str()) == -1)
        {
            PROF_LOGW("cannot write to mmap");  // LCOV_EXCL_LINE
        }
    }

    if (munmap(mmapPtr, mmapSize) == -1)
    {
        PROF_LOGW("munmap failed");  // LCOV_EXCL_LINE
    }

    close(shmFd);
}

void ServiceProfilerManager::LaunchThread()
{
    this->thread_ = std::thread(&ServiceProfilerManager::ThreadFunction, this);
}

// Dynamic Control according to config file modification
void ServiceProfilerManager::DynamicControl()
{
    // 只在 Manager 的工作线程中执行，会启动或者关停服务

    auto configPath = config_->GetConfigPath();
    if (configPath.empty())
    {
        return;
    }
    struct stat configFileStat;
    if (stat(configPath.c_str(), &configFileStat) == 0)
    {
        if (configFileStat.st_mtime == lastUpdate_)
        {
            return;
        }
        else
        {
            lastUpdate_ = configFileStat.st_mtime;
        }
    }
    else
    {
        LOG_ONCE_E("fail to get stat of %s", SecurityUtils::ToSafeString(configPath).c_str());  // LCOV_EXCL_LINE
        return;
    }

    auto configJson = config_->ReadConfigFile();
    bool enableFromConfig = config_->ParseEnable(configJson, true);
    bool prevMetricEnable = config_->GetMetricEnable();

    if (enableFromConfig && !config_->GetEnable())
    {
        PROF_LOGI("Profiler Enabled...");  // LCOV_EXCL_LINE
        config_->ParseConfig(configJson);
        StartProfiler();
        PROF_LOGI("Profiler Enabled Successfully!");  // LCOV_EXCL_LINE
    }
    else if (!enableFromConfig && config_->GetEnable())
    {
        PROF_LOGI("Profiler Disabled...");  // LCOV_EXCL_LINE
        StopProfiler();
        PROF_LOGI("Profiler Disabled Successfully!");  // LCOV_EXCL_LINE
    }

    // metric_enable 与 enable 独立：变化时触发回调；且若配置已为 1 但从未发起过 start（如启动时即
    // metric_enable=1），也触发一次
    bool metricEnableFromConfig = config_->ParseMetricEnable(configJson, true);
    bool needStart =
        metricEnableFromConfig && (prevMetricEnable != metricEnableFromConfig || !metricStartCallbackInvoked_);
    bool needStop =
        !metricEnableFromConfig && (prevMetricEnable != metricEnableFromConfig || metricStartCallbackInvoked_);
    if (needStart)
    {
        config_->ParseMetricEnable(configJson, false);
        if (startMetricCallback_ != nullptr)
        {
            PROF_LOGI("Metric collection enabled, calling start metric callback");  // LCOV_EXCL_LINE
            try
            {
                startMetricCallback_();
                metricStartCallbackInvoked_ = true;
            }
            catch (...)
            {
                PROF_LOGE("Python start metric callback threw an exception");  // LCOV_EXCL_LINE
            }
        }
    }
    else if (needStop)
    {
        config_->ParseMetricEnable(configJson, false);
        if (stopMetricCallback_ != nullptr)
        {
            PROF_LOGI("Metric collection disabled, calling stop metric callback");  // LCOV_EXCL_LINE
            try
            {
                stopMetricCallback_();
                metricStartCallbackInvoked_ = false;
            }
            catch (...)
            {
                PROF_LOGE("Python stop metric callback threw an exception");  // LCOV_EXCL_LINE
            }
        }
    }
}

// 线程函数：npu usage and dynamic monitor
void ServiceProfilerManager::ThreadFunction()
{
    PROF_LOGD("profiler thread launched");             // LCOV_EXCL_LINE
    auto profApiHandle = RegisterSetDeviceCallback();  // 获取device id , 变化  deviceID_
    uint32_t deviceID = deviceID_.load();
    PROF_LOGD("start prof device id is %u", deviceID);  // LCOV_EXCL_LINE
    if (config_->GetEnable())
    {
        StartAclProfiler(config_->GetProfPath(), deviceID);
    }

    NpuMemoryUsage npuMemoryUsage = NpuMemoryUsage();

    AddMetaInfo("hostname", MsUtils::GetHostName().c_str());
    AddMetaInfo("ppid", std::to_string(getppid()).c_str());

    int heartbeat = 0;
    while (threadRunFlag_)
    {
        // dynamic start_and_stop
        if (heartbeat++ % (60000 / config_->GetNpuMemorySleepMilliseconds()) == 0)
        {
            PROF_LOGD("manager thread heartbeat");  // LCOV_EXCL_LINE
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(config_->GetNpuMemorySleepMilliseconds()));

        DynamicControl();

        bool startFlagFromNotify = notifyStarted.load();
        if (startFlagFromNotify != started_)
        {
            if (startFlagFromNotify)
            {
                StartProfiler();
                deviceID = deviceID_.load();
            }
            else
            {
                StopProfiler();
            }
        }

        uint32_t nowDeviceID = deviceID_.load();
        if (nowDeviceID != deviceID && started_ && config_->IsAclProf())
        {
            StopAclProf();
            StartAclProf(config_->GetProfPath(), nowDeviceID);
        }
        deviceID = nowDeviceID;

        ProfTimerCtrl();
        ProfStepCtrl();

        RecordMemoryUsage(npuMemoryUsage);

        if (msptiStarted_)
        {
            FlushBufferByTime();
        }
    }
    UnregisterDeviceStateCallback(profApiHandle.get());
    PROF_LOGD("profiler thread stop loop");  // LCOV_EXCL_LINE
    StopProfiler();
}

void ServiceProfilerManager::ProfStepCtrl()
{
    int stepLimit = config_->GetProfilerStepNum();

    if (profilerStoppedByLimit_)
    {
        return;
    }

    if (!started_ || stepLimit < 0)
    {
        return;
    }

    int currentStep = GetProfilerCurrentStep();

    if (stepLimit >= 0)
    {
        if (stopTargetStep_ < 0)
        {
            stopTargetStep_ = currentStep + stepLimit;
        }
        if (currentStep >= stopTargetStep_)
        {
            PROF_LOGI("Profiler Step Limit Reached! Current=%d, Target=%d. Stopping...",  // LCOV_EXCL_LINE
                      currentStep, stopTargetStep_);                                      // LCOV_EXCL_LINE

            StopProfiler();
            stopTargetStep_ = -1;
            PROF_LOGI("Profiler Disabled Successfully!");  // LCOV_EXCL_LINE
            config_->SetFileEnable(0);

            profilerStoppedByLimit_ = true;
        }
    }
    else
    {
        if (stopTargetStep_ != -1)
        {
            stopTargetStep_ = -1;
        }
    }
}

void ServiceProfilerManager::ProfTimerCtrl()
{
    {
        if (config_->GetTimeLimit() > 0 && started_)
        {
            auto terminate = std::chrono::high_resolution_clock::now();  // 记录结束时间

            auto duration = std::chrono::duration_cast<std::chrono::seconds>(terminate - initiate);

            if (duration.count() >= config_->GetTimeLimit())
            {
                StopProfiler();
                PROF_LOGI(
                    "Profiler Timelimit %u Seconds Is Reached,"  // LCOV_EXCL_LINE
                    " Profiler Disabled Successfully!",
                    config_->GetTimeLimit());  // LCOV_EXCL_LINE
                config_->SetFileEnable(0);
            }
        }
        // 单独控制算子采集
        if (config_->GetAclTaskTimeDuration() > 0 && aclProfStarted_)
        {
            auto terminate = std::chrono::high_resolution_clock::now();  // 记录结束时间

            auto duration = std::chrono::duration_cast<std::chrono::seconds>(terminate - initiate);

            if (duration.count() >= config_->GetAclTaskTimeDuration())
            {
                StopAclProf();
                PROF_LOGI(
                    "Profiler AclTaskTimeDuration %d Seconds Is Reached, "  // LCOV_EXCL_LINE
                    "AclTaskTime Disabled Successfully!",
                    config_->GetAclTaskTimeDuration());  // LCOV_EXCL_LINE
                config_->SetAclTaskTimeDuration(0);
            }
        }
    }
}

// Funtion that write info to tx
void DeviceMemoryWrite2Tx(const std::vector<int> &memoryInfo, const std::string &metricName)
{
    for (long unsigned int i = 0; i < memoryInfo.size(); i++)
    {
        msServiceProfiler::Profiler<msServiceProfiler::INFO>()
            .Domain("npu")
            .Metric(metricName.c_str(), memoryInfo[i])
            .MetricScope("device", i)
            .Launch();
    }
}

void ServiceProfilerManager::RecordMemoryUsage(NpuMemoryUsage &npuMemoryUsage)
{
    try
    {
        if (!(config_->GetEnable() && config_->GetNpuMemoryUsage() && isMaster_))
        {
            return;
        }
        int ret = npuMemoryUsage.InitDcmiCardAndDevices();
        if (ret != EXITCODE_SUCCESS)
        {
            PROF_LOGE(
                "InitDcmiCardAndDevices failed."                             // LCOV_EXCL_LINE
                " Check whether a NPU server or if NPU driver installed.");  // LCOV_EXCL_LINE
            return;
        }
        std::vector<int> memoryUsed;
        std::vector<int> memoryUtiliza;
        if (npuMemoryUsage.GetByDcmi(memoryUsed, memoryUtiliza) == EXITCODE_SUCCESS)
        {
            DeviceMemoryWrite2Tx(memoryUsed, "usage");
            DeviceMemoryWrite2Tx(memoryUtiliza, "utiliza");
        }
    }
    catch (std::exception &e)
    {
        PROF_LOGD("get npu memory usage failed");  // LCOV_EXCL_LINE
    }
}

void ServiceProfilerManager::SetAclProfHostSysConfig() const
{
    std::string hostProfString = "";

    // 根据条件设置 hostProfString 的值
    if (config_->GetHostCpuUsage() && config_->GetHostMemoryUsage())
    {
        hostProfString = "cpu,mem";
    }
    else if (config_->GetHostCpuUsage())
    {
        hostProfString = "cpu";
    }
    else if (config_->GetHostMemoryUsage())
    {
        hostProfString = "mem";
    }

    aclprofSetConfig(ACL_PROF_HOST_SYS, hostProfString.c_str(), strlen(hostProfString.c_str()));
    aclprofSetConfig(ACL_PROF_HOST_SYS_USAGE, hostProfString.c_str(), strlen(hostProfString.c_str()));
    aclprofSetConfig(ACL_PROF_HOST_SYS_USAGE_FREQ, std::to_string(config_->GetHostFreq()).c_str(),
                     strlen(std::to_string(config_->GetHostFreq()).c_str()));
}

AclprofConfig *ServiceProfilerManager::ProfCreateConfig(uint32_t deviceID)
{
    uint32_t profSwitch = ACL_PROF_MSPROFTX;
    uint32_t deviceIdList[MAX_DEVICE_NUM] = {0};
    uint32_t deviceNums = deviceID == INVALID_DEVICE_ID ? 0 : 1;
    if (deviceNums > 0)
    {
        deviceIdList[0] = deviceID;

        if (config_->GetEnableAclTaskTime())
        {
            profSwitch = config_->GetProfilingSwitch();
        }
    }
    // 创建性能采集配置
    aclprofAicoreMetrics aicoreMetricsEnum = config_->GetAclProfAicoreMetrics();
    PROF_LOGD("Current profSwitch configuration: Hex: 0x%x", profSwitch);
    PROF_LOGD("Current aicoreMetricsEnum configuration: %u", aicoreMetricsEnum);
    PROF_LOGD("Current deviceID configuration: %u, %u", deviceNums, deviceIdList[0]);
    auto profConfig = aclprofCreateConfig(deviceIdList, deviceNums, aicoreMetricsEnum, nullptr, profSwitch);
    if (profConfig == nullptr)
    {
        PROF_LOGE("acl prof create config failed.");  // LCOV_EXCL_LINE
    }
    else
    {
        this->configHandle_ = profConfig;
    }
    return profConfig;
}

void ServiceProfilerManager::StartProfiler(bool isInit)
{
    if (started_)
    {
        return;
    }

    stopTargetStep_ = -1;
    profilerStoppedByLimit_ = false;
    initiate = std::chrono::high_resolution_clock::now();  // 记录开始时间

    auto profPath = config_->GetProfPath();
    if (!MsUtils::MakeDirs(profPath))
    {
        PROF_LOGE("Failed to create directory(%s), possibly due to lack of permission",
                  profPath.c_str());  // LCOV_EXCL_LINE
        // 无法创建目录，就直接返回
        config_->SetEnable(false);
        return;
    }
    PROF_LOGI("prof path: %s", profPath.c_str());  // LCOV_EXCL_LINE
    // 服务化数据开始采集，到写入线程去执行，这样不用管多线程安全
    auto executor = std::make_unique<DbFuncExec>([profPath](ServiceProfilerDbWriter &writer, sqlite3 *) -> void
                                                 { writer.StartDump(profPath); }, PRIORITY_START_PROF);
    msServiceProfiler::InsertExecutor2Writer<DBFile::SERVICE>(std::move(executor));

    if (!isInit)
    {
        // 在构造的时候，不初始化这些不重要的，在工作线程中初始化一次
        StartAclProfiler(profPath, deviceID_.load());
    }

    // 设置标志位
    config_->SetEnable(true);
    started_ = true;
    notifyStarted = true;  // 处理完同步一次状态, 等待下一次通知

    // 调用 Python 回调以启用 hooks
    if (startCallback_ != nullptr)
    {
        PROF_LOGD("Calling Python start callback");  // LCOV_EXCL_LINE
        try
        {
            startCallback_();
        }
        catch (...)
        {
            PROF_LOGE("Python start callback threw an exception");  // LCOV_EXCL_LINE
        }
    }
}

void ServiceProfilerManager::StartAclProfiler(const std::string &profPath, uint32_t deviceID)
{
    if (config_->GetMsptiEnable())
    {
        // mspti 数据开始采集
        StartMsptiProf(profPath);
    }
    else if (config_->GetTorchProfilerEnable())
    {
        // torch profiler 不开启算子采集 在python侧打点开始采集
    }
    else if (config_->IsAclProf())
    {
        // msprof 数据开始采集
        StartAclProf(profPath, deviceID);
    }
    else
    {
        // 无算子采集
    }
}

void ServiceProfilerManager::StartMsptiProf(const std::string &profPath)
{
    auto ret = InitMspti(profPath, msptiHandle_);
    if (ret != 0)
    {
        PROF_LOGE("Mspti init failed.");  // LCOV_EXCL_LINE
        msptiStarted_ = false;
    }
    else
    {
        InitMsptiActivity(config_->GetMsptiEnable());
        const auto apiFilter_ = config_->GetApiFilter();
        const auto kernelFilter_ = config_->GetKernelFilter();
        InitMsptiFilter(apiFilter_, kernelFilter_);
        msptiStarted_ = true;
    }
}

void ServiceProfilerManager::StartAclProf(const std::string &profPath, uint32_t deviceID)
{
    if (aclProfStarted_)
    {
        PROF_LOGD("StartAclProf aclProf is Started: %d", aclProfStarted_);  // LCOV_EXCL_LINE
        return;
    }

    PROF_LOGD("StartAclProf device_id: %u, is Master: %d", deviceID, isMaster_);  // LCOV_EXCL_LINE
    if (deviceID == INVALID_DEVICE_ID && !(isMaster_ && (config_->GetHostCpuUsage() || config_->GetHostMemoryUsage())))
    {
        // 不知道为啥，如果没有 device，就会卡死。算了，反正不设置 device 也没有什么意义。
        return;
    }
    PROF_LOGD("StartAclProf starting");  // LCOV_EXCL_LINE
    aclError ret = aclprofInit(profPath.c_str(), profPath.size());
    if (ret != ACL_ERROR_NONE)
    {
        PROF_LOGE("acl prof init failed, ret = %d", ret);  // LCOV_EXCL_LINE
        return;
    }

    MsUtils::FailAutoFree autoFree;
    autoFree.AddFreeFunction(
        []()
        {
            if (aclprofFinalize() != ACL_ERROR_NONE)
            {
                PROF_LOGE("acl prof finalize failed");  // LCOV_EXCL_LINE
            }
        },
        "auto call finalize after acl prof init when start failed.");

    if (ret == ACL_ERROR_NONE && isMaster_)
    {
        SetAclProfHostSysConfig();
    }

    auto profConfig = ProfCreateConfig(deviceID);
    if (profConfig == nullptr)
    {
        config_->SetEnable(false);
        return;
    }

    autoFree.AddFreeFunction(
        [this, profConfig]()
        {
            if (aclprofDestroyConfig(profConfig) != ACL_ERROR_NONE)
            {
                PROF_LOGE("acl prof destroy config failed");  // LCOV_EXCL_LINE
            }
            configHandle_ = nullptr;
        },
        "auto call destroy after acl prof create config when start failed.");

    PROF_LOGD("begin to start profiling");  // LCOV_EXCL_LINE
    ret = aclprofStart(profConfig);
    if (ret != ACL_ERROR_NONE)
    {
        PROF_LOGE("acl prof start failed, ret = %d", ret);  // LCOV_EXCL_LINE
        config_->SetEnable(false);
        return;
    }

    autoFree.SetSuccess();
    aclProfStarted_ = true;
}

void ServiceProfilerManager::StopAclProf()
{
    if (!aclProfStarted_)
    {
        return;
    }
    auto profConfig = (AclprofConfig *)this->configHandle_;

    PROF_LOGD("StopAclProf calling aclprofStop");  // LCOV_EXCL_LINE
    auto ret = aclprofStop(profConfig);
    aclProfStarted_ = false;
    if (ret != ACL_ERROR_NONE)
    {
        PROF_LOGE("acl prof stop failed, ret = %d", ret);  // LCOV_EXCL_LINE
        return;
    }
    ret = aclprofDestroyConfig(profConfig);
    if (ret != ACL_ERROR_NONE)
    {
        PROF_LOGE("acl prof destroy config failed, ret = %d", ret);  // LCOV_EXCL_LINE
    }
    this->configHandle_ = nullptr;
    ret = aclprofFinalize();
    if (ret != ACL_ERROR_NONE)
    {
        PROF_LOGE("acl prof finalize failed, ret = %d", ret);  // LCOV_EXCL_LINE
        return;
    }
}

void ServiceProfilerManager::NotifyDeviceID(uint32_t deviceID)
{
    PROF_LOGD("device id set to %u", deviceID);  // LCOV_EXCL_LINE
    deviceID_ = deviceID;
}

void ServiceProfilerManager::RegisterStartCallback(void (*callback)())
{
    // 注册 mstx 启动回调
    startCallback_ = callback;
    PROF_LOGD("Profiler start callback registered");  // LCOV_EXCL_LINE

    // 如果 profiler 已经启动，立即调用回调（解决时序问题）
    if (started_ && callback != nullptr)
    {
        PROF_LOGI("Profiler already started, calling start callback immediately");  // LCOV_EXCL_LINE
        try
        {
            callback();
        }
        catch (...)
        {
            PROF_LOGE("Start callback threw an exception");  // LCOV_EXCL_LINE
        }
    }
}

void ServiceProfilerManager::RegisterStopCallback(void (*callback)())
{
    // 注册 mstx 停止回调
    stopCallback_ = callback;
    PROF_LOGD("Profiler stop callback registered");  // LCOV_EXCL_LINE
}

void ServiceProfilerManager::RegisterStartMetricCallback(void (*callback)())
{
    startMetricCallback_ = callback;
    PROF_LOGD("Profiler start metric callback registered");  // LCOV_EXCL_LINE
}

void ServiceProfilerManager::RegisterStopMetricCallback(void (*callback)())
{
    stopMetricCallback_ = callback;
    PROF_LOGD("Profiler stop metric callback registered");  // LCOV_EXCL_LINE
}

void ServiceProfilerManager::StopProfiler()
{
    // 只 Manager 的工作线程
    PROF_LOGD("StopProfiler started_=%d, aclProfStarted_=%d", started_, aclProfStarted_);  // LCOV_EXCL_LINE
    if (!started_)
    {
        return;
    }

    config_->SetEnable(false);
    if (msptiStarted_)
    {
        // mspti 数据结束采集
        msptiStarted_ = false;
        UninitMspti(msptiHandle_);
    }
    else if (aclProfStarted_)
    {
        // msprof 数据结束采集
        StopAclProf();
    }
    else
    {
        // 无算子采集
    }

    // 服务化数据结束采集，到写入线程去执行，这样不用管多线程安全
    auto executor = std::make_unique<DbFuncExec>(
        [](ServiceProfilerDbWriter &writer, sqlite3 *) -> void { writer.StopDump(); }, PRIORITY_STOP_PROF);
    msServiceProfiler::InsertExecutor2Writer<DBFile::SERVICE>(std::move(executor));

    started_ = false;
    notifyStarted = false;  // 处理完同步一次状态, 等待下一次通知

    // 调用 Python 回调
    if (stopCallback_ != nullptr)
    {
        PROF_LOGD("Calling Python stop callback");  // LCOV_EXCL_LINE
        try
        {
            stopCallback_();
        }
        catch (...)
        {
            PROF_LOGE("Python stop callback threw an exception");  // LCOV_EXCL_LINE
        }
    }
}
}  // namespace msServiceProfiler
