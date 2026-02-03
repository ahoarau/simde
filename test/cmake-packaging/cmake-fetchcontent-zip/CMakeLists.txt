cmake_minimum_required(VERSION 3.22)

# SIMDE_ZIP_PATH must be passed to CMake
if(NOT DEFINED SIMDE_ZIP_PATH)
    message(FATAL_ERROR "SIMDE_ZIP_PATH must be defined")
endif()

project(simde-fetchcontent-zip-consumer LANGUAGES C CXX)

include(FetchContent)
FetchContent_Declare(simde URL ${SIMDE_ZIP_PATH})
FetchContent_MakeAvailable(simde)

# The zip file does not contain a CMakeLists.txt, so FetchContent_MakeAvailable won't import the target.
# We need to define it manually pointing to the source directory.
if(NOT TARGET simde::simde)
    add_library(simde::simde INTERFACE IMPORTED)
    set_target_properties(simde::simde PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES ${simde_SOURCE_DIR})
endif()


add_executable(consumer-zip-c ../sources/main.c)
target_link_libraries(consumer-zip-c PRIVATE simde::simde)

add_executable(consumer-zip-cpp ../sources/main.cpp)
target_link_libraries(consumer-zip-cpp PRIVATE simde::simde)

enable_testing()
add_test(NAME consumer-zip-c COMMAND consumer-zip-c)
add_test(NAME consumer-zip-cpp COMMAND consumer-zip-cpp)
