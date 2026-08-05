cmake_minimum_required(VERSION 3.11)

project(ms_service_profiler VERSION 8.5.0 LANGUAGES CXX C)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED True)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -D_GLIBCXX_USE_CXX11_ABI=0")

set(THIRD_PARTY_DIR "${CMAKE_CURRENT_SOURCE_DIR}/3rdparty")
set(CPP_DIR "${CMAKE_CURRENT_SOURCE_DIR}/cpp")

option(ms_service_profiler_BUILD_TESTS "build ms_service_profiler uts and sts" OFF)

find_package(Python3 COMPONENTS Interpreter REQUIRED)
message(STATUS "Checking for conflicting package 'msserviceprofiler'...")

execute_process(
    COMMAND ${Python3_EXECUTABLE} -c "import msserviceprofiler"
    RESULT_VARIABLE CHECK_RESULT
    OUTPUT_QUIET
    ERROR_QUIET
)

if(${CHECK_RESULT} EQUAL 0)
    message(FATAL_ERROR
        "ERROR: Found conflicting package 'msserviceprofiler'\n"
        "This conflicts with the new 'ms_service_profiler'.\n"
        "Please uninstall it first:\n"
        "    ${Python3_EXECUTABLE} -m pip uninstall msserviceprofiler\n"
        "Then retry installation."
    )
else()
    message(WARNING
        "Note: 'ms_service_profiler' conflicts with the legacy 'msserviceprofiler'.\n"
        "If you have multiple Python installations or are using conda/virtual environments,\n"
        "ensure 'msserviceprofiler' is not installed in the target environment."
    )
endif()

add_subdirectory("${THIRD_PARTY_DIR}")
add_subdirectory("${CPP_DIR}")

if(ms_service_profiler_BUILD_TESTS)
    add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/test")
endif()
