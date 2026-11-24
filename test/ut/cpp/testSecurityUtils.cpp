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
#include <dlfcn.h>
#include <gmock/gmock.h>
#include <gtest/gtest.h>
#include <sys/stat.h>
#include <unistd.h>

#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

#include "msServiceProfiler/SecurityUtils.h"
#include "msServiceProfiler/SecurityUtilsLog.h"

using namespace SecurityUtils;
using namespace testing;

// 原始函数指针
static int (*real_stat)(const char*, struct stat*) = nullptr;

// Mock 控制
struct MockControl
{
    bool real_func = true;
    bool bool_return = false;
    int int_return = 0;
    int call_count = 0;
};
static MockControl mock_control;

// Mock 实现
extern "C" int stat(const char* path, struct stat* buf)
{
    mock_control.call_count++;
    if (mock_control.real_func)
    {
        real_stat = reinterpret_cast<decltype(real_stat)>(dlsym(RTLD_NEXT, "stat"));
        return real_stat(path, buf);
    }
    return mock_control.int_return;
}

class SecurityUtilsTest : public Test
{
   protected:
    void SetUp() override
    {
        // 创建临时文件和目录
        const char* tempFile = "testfile.txt";
        const char* tempDir = "testdir";
        const char* tempLink = "testlink";

        // 创建临时文件
        FILE* file = fopen(tempFile, "w");
        if (file)
        {
            fclose(file);
        }
        // 创建临时目录
        mkdir(tempDir, 0755);
        // 创建符号链接
        symlink(tempFile, tempLink);
        mock_control = MockControl{};  // 重置stat状态
    }

    void TearDown() override
    {
        // 清理临时文件和目录
        const char* tempFile = "testfile.txt";
        const char* tempDir = "testdir";
        const char* tempLink = "testlink";

        // 删除文件
        unlink(tempFile);
        // 删除目录
        rmdir(tempDir);
        // 删除符号链接
        unlink(tempLink);
        mock_control.real_func = true;
        mock_control.bool_return = false;
        mock_control.int_return = 0;
        mock_control.call_count = 0;
    }
};

TEST_F(SecurityUtilsTest, TestIsExist)
{
    // 测试文件存在的情况
    const std::string existingFile = "testfile.txt";
    EXPECT_TRUE(IsExist(existingFile));

    // 测试文件不存在的情况
    const std::string nonExistingFile = "nonexistent.txt";
    EXPECT_FALSE(IsExist(nonExistingFile));
}

TEST_F(SecurityUtilsTest, TestIsReadable)
{
    // 测试可读文件
    const std::string readableFile = "testfile.txt";
    EXPECT_TRUE(IsReadable(readableFile));

    // 测试不可读文件（需要修改权限）
    const std::string unreadableFile = "testfile.txt";
    chmod(unreadableFile.c_str(), 0000);
    EXPECT_FALSE(IsReadable(unreadableFile));
    // 恢复权限
    chmod(unreadableFile.c_str(), 0644);
}

TEST_F(SecurityUtilsTest, TestIsReadable_001)
{
    mock_control.real_func = false;
    mock_control.int_return = 1;
    // 测试可读文件
    const std::string readableFile = "testfile.txt";
}

TEST_F(SecurityUtilsTest, TestIsWritable)
{
    // 测试可写文件
    const std::string writableFile = "testfile.txt";
    EXPECT_TRUE(IsWritable(writableFile));

    // 测试不可写文件（需要修改权限）
    const std::string unwritableFile = "testfile.txt";
    chmod(unwritableFile.c_str(), 0444);
    EXPECT_FALSE(IsWritable(unwritableFile));
    // 恢复权限
    chmod(unwritableFile.c_str(), 0644);
}

TEST_F(SecurityUtilsTest, TestIsWritable_002)
{
    mock_control.real_func = false;
    mock_control.int_return = 1;

    // 测试可写文件
    const std::string writableFile = "testfile.txt";
}

TEST_F(SecurityUtilsTest, TestIsExecutable)
{
    // 测试可执行文件（假设testfile.txt不可执行）
    const std::string nonExecutableFile = "testfile.txt";
    EXPECT_FALSE(IsExecutable(nonExecutableFile));

    // 测试可执行文件（需要一个可执行文件）
    const std::string executableFile = "test.sh";
    FILE* file = fopen(executableFile.c_str(), "w");
    if (file)
    {
        fclose(file);
        chmod(executableFile.c_str(), 0755);
        EXPECT_TRUE(IsExecutable(executableFile));
        // 清理
        unlink(executableFile.c_str());
    }
}

TEST_F(SecurityUtilsTest, TestIsExecutable_002)
{
    mock_control.real_func = false;
    mock_control.int_return = 1;

    // 测试可执行文件（假设testfile.txt不可执行）
    const std::string nonExecutableFile = "testfile.txt";
    EXPECT_FALSE(IsExecutable(nonExecutableFile));
}

TEST_F(SecurityUtilsTest, TestIsOwner_001)
{
    mock_control.real_func = false;
    mock_control.int_return = 1;

    // 测试可执行文件（假设testfile.txt不可执行）
    const std::string normalFile = "testfile.txt";
}

TEST_F(SecurityUtilsTest, TestIsSoftLink)
{
    // 测试符号链接
    const std::string softLink = "testlink";
    EXPECT_TRUE(IsSoftLink(softLink));

    // 测试非符号链接
    const std::string nonSoftLink = "testfile.txt";
    EXPECT_FALSE(IsSoftLink(nonSoftLink));
}

TEST_F(SecurityUtilsTest, TestIsSoftLink_001)
{
    mock_control.real_func = false;
    mock_control.int_return = 1;
    // 测试符号链接
    const std::string softLink = "testlink";
    EXPECT_TRUE(IsSoftLink(softLink));
}

TEST_F(SecurityUtilsTest, TestIsFile)
{
    // 测试普通文件
    const std::string regularFile = "testfile.txt";
    EXPECT_TRUE(IsFile(regularFile));

    // 测试目录
    const std::string directory = "testdir";
    EXPECT_FALSE(IsFile(directory));
}

TEST_F(SecurityUtilsTest, TestIsFile_001)
{
    mock_control.real_func = false;
    mock_control.int_return = 1;
    // 测试普通文件
    const std::string regularFile = "testfile.txt";
}

TEST_F(SecurityUtilsTest, TestIsDir)
{
    // 测试目录
    const std::string directory = "testdir";
    EXPECT_TRUE(IsDir(directory));

    // 测试普通文件
    const std::string regularFile = "testfile.txt";
    EXPECT_FALSE(IsDir(regularFile));
}

TEST_F(SecurityUtilsTest, TestIsDir_001)
{
    mock_control.real_func = false;
    mock_control.int_return = 1;
    // 测试目录
    const std::string directory = "testdir";
}

TEST_F(SecurityUtilsTest, TestIsPathLenLegal)
{
    // 测试路径长度合法
    const std::string shortPath = "testfile.txt";
    EXPECT_TRUE(IsPathLenLegal(shortPath));

    // 测试路径长度超过限制
    std::string longPath(PATH_MAX, 'a');
    EXPECT_FALSE(IsPathLenLegal(longPath));
}

TEST_F(SecurityUtilsTest, TestIsPathDepthLegal)
{
    // 测试路径深度合法
    const std::string shallowPath = "testdir/testfile.txt";
    EXPECT_TRUE(IsPathDepthLegal(shallowPath));

    // 测试路径深度超过限制
    std::string deepPath;
    for (int i = 0; i < PATH_DEPTH_MAX + 1; ++i)
    {
        deepPath += "/testdir";
    }
    EXPECT_FALSE(IsPathDepthLegal(deepPath));
}

TEST_F(SecurityUtilsTest, TestIsPathLenLegal_001)
{
    // 测试路径长度合法
    const std::string shortPath = "";
    EXPECT_FALSE(IsPathLenLegal(shortPath));
}

TEST_F(SecurityUtilsTest, TestIsPathCharactersValid)
{
    // 测试有效路径
    const std::string validPath = "testfile.txt";
    EXPECT_TRUE(IsPathCharactersValid(validPath));

    // 测试无效路径（包含非法字符）
    const std::string invalidPath = "test?file.txt";
    EXPECT_FALSE(IsPathCharactersValid(invalidPath));
}

TEST_F(SecurityUtilsTest, TestIsPathCharactersValid_001)
{
    // 测试有效路径
    const std::string validPath = "testfile";
    EXPECT_TRUE(IsPathCharactersValid(validPath));
}

TEST_F(SecurityUtilsTest, TestCheckPathContainSoftLink)
{
    // 测试包含符号链接的路径
    const std::string pathWithLink = "testlink";
    EXPECT_TRUE(CheckPathContainSoftLink(pathWithLink));

    // 测试不包含符号链接的路径
    const std::string pathWithoutLink = "testfile.txt";
    EXPECT_FALSE(CheckPathContainSoftLink(pathWithoutLink));
}

TEST_F(SecurityUtilsTest, TestCheckFileBeforeWrite)
{
    // 测试文件写入检查
    const std::string validFile = "testfile.txt";
    CheckFileBeforeWrite(validFile);

    // 测试符号链接
    const std::string link = "testlink";
    EXPECT_FALSE(CheckFileBeforeWrite(link));
}

TEST_F(SecurityUtilsTest, TestCheckFileBeforeWrite_001)
{
    // 测试文件写入检查
    const std::string fileName = "";
    EXPECT_FALSE(CheckFileBeforeWrite(fileName));

    fileName = "test;file";
    EXPECT_FALSE(CheckFileBeforeWrite(fileName));
}

TEST_F(SecurityUtilsTest, TestSetLogLevelByEnvVar)
{
    SecurityUtilsLog::GetLog().SetLogLevelByEnvVar();
    setenv("SECURITY_UTILS_LOG_LEVEL", "1", 1);
    SecurityUtilsLog::GetLog().SetLogLevelByEnvVar();
    setenv("SECURITY_UTILS_LOG_LEVEL", "9", 1);
    SecurityUtilsLog::GetLog().SetLogLevelByEnvVar();

    ToSafeString("\n");

    const auto& map = GetInvalidChar();
    EXPECT_EQ(map.at("\n"), "\\n");
    EXPECT_EQ(map.at("\f"), "\\f");
    EXPECT_EQ(map.at("\r"), "\\r");
    EXPECT_EQ(map.at("\b"), "\\b");
    EXPECT_EQ(map.at("\t"), "\\t");
    EXPECT_EQ(map.at("\v"), "\\v");
    EXPECT_EQ(map.at("\u007F"), "\\u007F");

    // 测试不存在的键
    EXPECT_THROW(map.at("not_exist"), std::out_of_range);
}

// 原始函数指针
static struct tm* (*real_localtime)(const time_t*, struct tm*) = nullptr;

// Mock 控制
struct TimeMockControl
{
    bool real_func = true;
    struct tm mock_return;
};
static TimeMockControl time_mock_control;

TEST_F(SecurityUtilsTest, TestAddPrefixInfo)
{
    time_mock_control.real_func = false;
    std::string lengthLimit = "Log length reach limit,only show part message";
    SecurityUtilsLog::GetLog().AddPrefixInfo(lengthLimit, LogLv::INFO);
}
