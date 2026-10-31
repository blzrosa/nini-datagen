cmake_minimum_required(VERSION 3.20)
project(nini_datagen LANGUAGES CXX)

# Biblioteca compartilhada com ABI em C (cpp/datagen.h), carregada pelo Python via ctypes.
# Gera libdatagen.so (Linux), libdatagen.dylib (macOS) ou datagen.dll (Windows) dentro do pacote nini_datagen.

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_CXX_VISIBILITY_PRESET hidden)       # só as funções DG_EXPORT ficam visíveis
set(CMAKE_VISIBILITY_INLINES_HIDDEN ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

# MSVC: runtime do C++ embutido na DLL (/MT). Sem isto, datagen.dll depende do msvcp140.dll, que o Python não traz e
# que só existe em máquinas com o Visual C++ Redistributable instalado.
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

option(DG_NATIVE "Compilar para a CPU desta máquina (-march=native); nunca para wheels publicados" OFF)

file(GLOB DG_SOURCES CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/cpp/*.cpp")
add_library(datagen SHARED ${DG_SOURCES})
target_include_directories(datagen PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/cpp")

if(MSVC)
  # /utf-8: os comentários têm acentos; /O2 já vem do Release; o MSVC não tem __int128 (veja mulhi64 em common.hpp)
  target_compile_options(datagen PRIVATE /utf-8 /W4 /permissive- /Zc:__cplusplus)
  target_compile_definitions(datagen PRIVATE _CRT_SECURE_NO_WARNINGS)
else()
  target_compile_options(datagen PRIVATE -O3 -Wall -Wextra -Wpedantic)
  if(DG_NATIVE)
    target_compile_options(datagen PRIVATE -march=native)
  elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64|AMD64|amd64")
    # base dos wheels: x86-64-v2 (SSE4.2/POPCNT). Medido no MVP: perde no máximo ~2 ns/linha para -march=native.
    target_compile_options(datagen PRIVATE -march=x86-64-v2)
  endif()
endif()

if(WIN32)
  set_target_properties(datagen PROPERTIES PREFIX "")    # datagen.dll
endif()

# scikit-build-core coloca o conteúdo de CMAKE_INSTALL_PREFIX na raiz do wheel
install(TARGETS datagen
        LIBRARY DESTINATION nini_datagen
        RUNTIME DESTINATION nini_datagen)
