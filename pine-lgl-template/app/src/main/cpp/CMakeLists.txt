cmake_minimum_required(VERSION 3.22.1)
project(hooktemplate CXX)

add_library(hooktemplate SHARED
    native_entry.cpp
    lgl_features.cpp)

find_library(log-lib log)
target_link_libraries(hooktemplate ${log-lib})

# Dobby, for native hooks. Uncomment after vendoring it under cpp/dobby:
#   git submodule add https://github.com/jmpews/Dobby app/src/main/cpp/dobby
#
# add_subdirectory(dobby)
# target_link_libraries(hooktemplate dobby)
