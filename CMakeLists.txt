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

set(DG_X86 OFF)
if(CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64|AMD64|amd64|x64")
  set(DG_X86 ON)
endif()

# Determinismo: a mesma semente tem que dar os mesmos bits em qualquer sistema. Sem fusão de multiplicação e soma
# (-ffp-contract=off: FMA arredonda diferente, e o ARM e as CPUs com FMA fundiriam a*b + c por conta própria) e sem
# matemática "rápida". -fno-math-errno e -fno-trapping-math não mudam nenhum resultado (só dizem que ninguém lê errno
# nem captura exceções de ponto flutuante) e deixam os laços de exp/log vetorizar.
if(MSVC AND CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
  # clang-cl (DG_CLANGCL=1 no Windows): opções do clang passadas com /clang:
  target_compile_options(datagen PRIVATE /utf-8 /W4 /clang:-O3 /clang:-ffp-contract=off /clang:-fno-math-errno /clang:-fno-trapping-math)
  if(DG_NATIVE)
    target_compile_options(datagen PRIVATE /clang:-march=native)
  elseif(DG_X86)
    target_compile_options(datagen PRIVATE /clang:-march=x86-64-v2)
  endif()
  target_compile_definitions(datagen PRIVATE _CRT_SECURE_NO_WARNINGS)
elseif(MSVC)
  # /utf-8: os comentários têm acentos; /O2 já vem do Release; o MSVC não tem __int128 (veja mulhi64 em common.hpp).
  # /fp:precise (padrão desde o VS 2022) não funde multiplicação e soma.
  target_compile_options(datagen PRIVATE /utf-8 /W4 /permissive- /Zc:__cplusplus /fp:precise)
  target_compile_definitions(datagen PRIVATE _CRT_SECURE_NO_WARNINGS)
else()
  target_compile_options(datagen PRIVATE -O3 -Wall -Wextra -Wpedantic -ffp-contract=off -fno-math-errno -fno-trapping-math)
  if(DG_NATIVE)
    target_compile_options(datagen PRIVATE -march=native)
  elseif(DG_X86)
    # base dos wheels: x86-64-v2 (SSE4.2/POPCNT). AVX2 e FMA ficam de fora de propósito: FMA mudaria os bits (veja
    # acima) e, sem ela, uma versão AVX2 do normal medida aqui não ganhou da escalar.
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
