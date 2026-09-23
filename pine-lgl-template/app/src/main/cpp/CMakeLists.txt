cmake_minimum_required(VERSION 3.22.1)
project(hooktemplate CXX)

# Two modules, one .so.
#   lgl/  the menu layer — swap this to change menu library
#   mod/  your features — the parts you rewrite per game
#
# mod/ consumes only lgl/lgl.h, never an LGL header, so the dependency points
# one way and the menu stays replaceable.

add_library(hooktemplate SHARED
    lgl/impl.cpp
    mod/native_entry.cpp
    mod/features.cpp)

find_library(log-lib log)
target_link_libraries(hooktemplate ${log-lib})

# Dobby, for native hooks. Uncomment after vendoring it under cpp/dobby:
#   git submodule add https://github.com/jmpews/Dobby app/src/main/cpp/dobby
#
# add_subdirectory(dobby)
# target_link_libraries(hooktemplate dobby)
