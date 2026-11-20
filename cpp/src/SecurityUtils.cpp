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
#include "msServiceProfiler/SecurityUtils.h"

#include <sys/stat.h>
#include <unistd.h>

#include <algorithm>
#include <climits>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <regex>

#include "msServiceProfiler/SecurityUtilsLog.h"

namespace SecurityUtils
{
bool IsExist(const std::string &absPath)
{
    struct stat fileStat;
    if (stat(absPath.c_str(), &fileStat) != 0)
    {
        LogWarn("File not exist: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsReadable(const std::string &absPath)
{
    struct stat fileStat;
    if ((stat(absPath.c_str(), &fileStat) != 0) || (fileStat.st_mode & S_IRUSR) == 0)
    {
        LogWarn("File not readable: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsWritable(const std::string &absPath)
{
    struct stat fileStat;
    if ((stat(absPath.c_str(), &fileStat) != 0) || (fileStat.st_mode & S_IWUSR) == 0)
    {
        LogWarn("File not writable: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsExecutable(const std::string &absPath)
{
    struct stat fileStat;
    if ((stat(absPath.c_str(), &fileStat) != 0) || (fileStat.st_mode & S_IXUSR) == 0)
    {
        LogWarn("File not executable: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsOwner(const std::string &absPath)
{
    struct stat fileStat;
    if ((stat(absPath.c_str(), &fileStat) != 0) || (fileStat.st_uid != getuid()))
    {
        LogWarn("File not owned by current user: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsRootUser()
{
    constexpr __uid_t root = 0;
    return getuid() == root;
}

bool IsSoftLink(const std::string &absPath)
{
    struct stat fileStat;
    if ((lstat(absPath.c_str(), &fileStat) != 0) || ((S_IFMT & fileStat.st_mode) != S_IFLNK))
    {
        return false;
    }
    else
    {
        LogWarn("File is symbol link: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return true;
    }
}

bool IsFile(const std::string &absPath)
{
    struct stat fileStat;
    if ((stat(absPath.c_str(), &fileStat) != 0) || !S_ISREG(fileStat.st_mode))
    {
        LogWarn("Path is not regular file: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsDir(std::string const &absPath)
{
    struct stat fileStat;
    if (stat(absPath.c_str(), &fileStat) != 0 || (fileStat.st_mode & S_IFDIR) == 0)
    {
        LogWarn("Path is not directory: %s", absPath.c_str());  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsPathLenLegal(const std::string &absPath)
{
    if (absPath.empty() || (absPath.size() >= PATH_MAX))
    {
        LogWarn("Path length is ilegal");  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsPathDepthLegal(const std::string &absPath)
{
    if (std::count(absPath.begin(), absPath.end(), PATH_SEPARATOR) > PATH_DEPTH_MAX)
    {
        LogWarn("Path depth exceeds limit");  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

bool IsPathCharactersValid(const std::string &absPath)
{
    if (!std::regex_match(absPath, std::regex(FILE_VALID_PATTERN)))
    {
        LogWarn("File path contain invalid characters");  // LCOV_EXCL_LINE
        return false;
    }
    return true;
}

static std::string GetRealPath(std::string const &path)
{
    char absPath[PATH_MAX + 1] = {0};

    if (realpath(path.c_str(), absPath) == nullptr)
    {
        LogWarn("Cannot GetRealPath: %s", path.c_str());  // LCOV_EXCL_LINE
        return "";
    }

    return std::string(absPath);
}

static std::string GetParentDir(const std::string &path)
{
    if (path.empty() || path == "/")
    {
        LogWarn("Cannot GetParentDir");  // LCOV_EXCL_LINE
    }
    size_t found = path.find_last_of('/');
    if (found != std::string::npos)
    {
        return path.substr(0, found);
    }
    return ".";
}

static void Split(std::string const &str, std::back_insert_iterator<std::vector<std::string>> it,
                  std::string const &seps)
{
    if (!seps.empty() && !str.empty() && str.find_first_of(seps) == 0)
    {
        *it = "";
        ++it;
    }
    std::string::size_type slow = str.find_first_not_of(seps);
    while (slow != std::string::npos && slow < str.length())
    {
        std::string::size_type fast = str.find_first_of(seps, slow);
        if (fast == std::string::npos)
        {
            fast = str.length();
        }
        if (fast != slow)
        {
            *it = str.substr(slow, fast - slow);
            ++it;
        }
        slow = fast + 1;
    }
}

bool CheckPathContainSoftLink(const std::string &path)
{
    constexpr char const *pathSep = "/";
    std::string nonConstPath = path;
    while (!nonConstPath.empty() && nonConstPath.back() == '/')
    {
        nonConstPath.pop_back();
    }
    std::vector<std::string> dirs;
    Split(nonConstPath, std::back_inserter(dirs), pathSep);
    if (dirs.empty())
    {
        return false;
    }
    std::string current;
    for (auto it = dirs.cbegin(); it != dirs.cend(); ++it)
    {
        if (it == dirs.cbegin())
        {
            current = *it;
        }
        else
        {
            current.append(pathSep + *it);
        }
        if (*it == "." || *it == ".." || *it == "")
        {
            continue;
        }
        if (SecurityUtils::IsSoftLink(current))
        {
            return true;
        }
    }
    return false;
}

static mode_t GetFilePermissions(const std::string &path)
{
    struct stat fileStat;
    if (stat(path.c_str(), &fileStat) != 0)
    {
        return 0;
    }
    mode_t permissions = fileStat.st_mode & (S_IRWXU | S_IRWXG | S_IRWXO);
    return permissions;
}

bool CheckFileBeforeWrite(const std::string &path)
{
    if (IsSoftLink(path))
    {
        return false;
    }

    const auto absPath = GetRealPath(path);
    if (!IsPathLenLegal(absPath) || !IsPathCharactersValid(absPath) || !IsFile(absPath) ||
        !IsOwner(GetParentDir(absPath)) || !IsOwner(absPath) || !IsWritable(absPath))
    {
        LogWarn("CheckFileBeforeWrite failed, path: %s", path.c_str());  // LCOV_EXCL_LINE
        return false;
    }

    const mode_t defaultWriteFilePerm = 0640;
    if (GetFilePermissions(absPath) > defaultWriteFilePerm)
    {
        LogWarn("Permission of file to write is over 0640, path: %s", path.c_str());  // LCOV_EXCL_LINE
    }
    return true;
}

}  // namespace SecurityUtils
