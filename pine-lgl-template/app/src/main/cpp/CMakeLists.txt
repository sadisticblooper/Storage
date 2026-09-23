cmake_minimum_required(VERSION 3.22.1)
project(hooktemplate CXX)

# Two modules, one .so.
#   lgl/  the menu layer - swap this to change menu library
#   mod/  your features - the parts you rewrite per game
#
# mod/ consumes only mod/mod_api.h, never anything from lgl/, so the dependency
# points one way and the menu stays replaceable.
#
# lgl/embedded_dex.h, lgl_descriptors.h and lgl_bindings.h are GENERATED. Do not
# hand-edit them; regenerate from the dex you embed:
#   python3 tools/embed_dex.py menu.dex --out app/src/main/cpp/lgl

add_library(hooktemplate SHARED
    lgl/impl.cpp
    lgl/dex_loader.cpp
    mod/native_entry.cpp
    mod/features.cpp)

find_library(log-lib log)
target_link_libraries(hooktemplate ${log-lib})

# 16 KB page size. Required on Android 15+ devices with 16 KB pages, and free
# elsewhere. The reference loader libraries in the wild are built this way;
# stock Pine (libpine.so 0.3.0) is NOT, which is why it fails on newer devices.
# NDK r27+ defaults to this; setting it explicitly keeps the build correct
# regardless of toolchain.
target_link_options(hooktemplate PRIVATE "-Wl,-z,max-page-size=16384")

# C++17: the loader uses std::string, lambdas and constexpr-ish helpers.
set_target_properties(hooktemplate PROPERTIES
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED ON)
