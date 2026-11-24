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

#ifndef MS_STANDARD_SECYRUTY_UTILS_H
#define MS_STANDARD_SECYRUTY_UTILS_H

#include <string>

#include "SecurityConstants.h"

namespace SecurityUtils
{
bool IsExist(const std::string &absPath);                // 检查文件是否存在
bool IsReadable(const std::string &absPath);             // 检查文件是否可读
bool IsWritable(const std::string &absPath);             // 检查文件是否可写
bool IsExecutable(const std::string &absPath);           // 检查文件是否可执行
bool IsOwner(const std::string &absPath);                // 检查是否为文件属主
bool IsSoftLink(const std::string &absPath);             // 检查是否为软链接
bool IsFile(const std::string &absPath);                 // 检查是否为文件
bool IsDir(std::string const &absPath);                  // 检查是否为文件夹
bool IsPathLenLegal(const std::string &absPath);         // 检查路径长度是否合法
bool IsPathDepthLegal(const std::string &absPath);       // 检查路径深度是否合法
bool IsPathCharactersValid(const std::string &absPath);  // 检查路径中是否有非法字符

bool CheckPathContainSoftLink(const std::string &path);  // 检查路径中各层级是否为软链接
bool CheckFileBeforeWrite(const std::string &path);      // 写入前综合检查
};  // namespace SecurityUtils

#endif  // MS_STANDARD_SECYRUTY_UTILS_H
