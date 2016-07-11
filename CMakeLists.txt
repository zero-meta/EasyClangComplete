cmake_minimum_required(VERSION 2.8)

project(blah)

find_package(OpenCV)

include_directories(${PROJECT_SOURCE_DIR}
                    SYSTEM ${OpenCV_DIRS},
                    "src blah")

add_executable(main test.cpp)