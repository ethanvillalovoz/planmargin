cmake_minimum_required(VERSION 3.24)

project(planmargin_tensorrt_runner LANGUAGES CXX CUDA)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(CUDAToolkit REQUIRED)

find_path(TENSORRT_INCLUDE_DIR NvInfer.h
  HINTS ${TENSORRT_ROOT} $ENV{TENSORRT_ROOT}
  PATH_SUFFIXES include)
find_library(TENSORRT_LIBRARY
  NAMES nvinfer libnvinfer.so.11
  HINTS ${TENSORRT_ROOT} $ENV{TENSORRT_ROOT}
  PATH_SUFFIXES lib lib64)

if(NOT TENSORRT_INCLUDE_DIR OR NOT TENSORRT_LIBRARY)
  message(FATAL_ERROR "TensorRT headers/library not found; set TENSORRT_ROOT")
endif()

add_executable(planmargin_tensorrt_runner trajectory_runner.cpp)
target_include_directories(planmargin_tensorrt_runner SYSTEM PRIVATE
  ${TENSORRT_INCLUDE_DIR})
target_link_libraries(planmargin_tensorrt_runner PRIVATE
  ${TENSORRT_LIBRARY}
  CUDA::cudart)
target_compile_options(planmargin_tensorrt_runner PRIVATE
  $<$<COMPILE_LANGUAGE:CXX>:-Wall -Wextra -Wpedantic -Werror>)
