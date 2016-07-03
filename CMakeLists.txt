cmake_minimum_required(VERSION 2.8)

project(blah)

find_package(PCL REQUIRED)

include_directories(
    SYSTEM ${EIGEN3_INCLUDE_DIR}
    SYSTEM ${PCL_INCLUDE_DIRS})

add_executable(main test.cpp)