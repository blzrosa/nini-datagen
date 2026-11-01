// common.hpp -- tipos, gerador xoshiro256++, multiplicação 64x64 -> alta, escolha por alias e tabelas compartilhadas.
// Parte do nini-datagen. Todo kernel escreve direto as "views" de 16 bytes do Arrow (formato string_view, o String do
// Polars): {len, 12 bytes inline} se len <= 12, senão {len, prefixo de 4 bytes, índice do buffer, deslocamento}.
#pragma once
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "nini-datagen assume CPU little-endian (x86-64, ARM64): as views do Arrow e os u32 são montados byte a byte"
#endif
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#if defined(_MSC_VER) && !defined(__clang__)
#include <intrin.h>
#endif

// DG_BUILDING: estamos compilando a biblioteca, então datagen.h declara as funções como exportadas (dllexport no
// Windows). A declaração no header e a definição no .cpp precisam ter o mesmo atributo, senão o MSVC acusa C2375.
#define DG_BUILDING 1
#include "datagen.h"

// Na definição: mesmo vínculo (C) e mesmo atributo de exportação da declaração em datagen.h
#define DG_EXPORT extern "C" DG_API

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int32_t i32;
typedef int64_t i64;

static const u32 MODB = 1000000000u;

static inline u64 rotl(u64 x, int k) { return (x << k) | (x >> (64 - k)); }

// parte alta de x * y (64 x 64 -> 128 bits) sem depender de unsigned __int128, que o MSVC não tem
static inline u64 mulhi64(u64 x, u64 y) {
#if defined(_MSC_VER) && !defined(__clang__)
  return __umulh(x, y);
#elif defined(__SIZEOF_INT128__)
  __extension__ typedef unsigned __int128 u128_t;   // __extension__: sem aviso do -Wpedantic
  return (u64)(((u128_t)x * y) >> 64);
#else
  u64 xl = (u32)x, xh = x >> 32, yl = (u32)y, yh = y >> 32;
  u64 ll = xl * yl, lh = xl * yh, hl = xh * yl, hh = xh * yh;
  u64 mid = (ll >> 32) + (u32)lh + (u32)hl;
  return hh + (lh >> 32) + (hl >> 32) + (mid >> 32);
#endif
}

// escolha O(1) por alias: tab[i] = limiar (32 bits baixos) | alias << 32; uma chamada do RNG, sem desvio
static inline u32 alias_pick(u32 k, const u64* tab, u64 y) {
  u32 i = (u32)(((y >> 32) * (u64)k) >> 32);
  u64 e = tab[i];
  u32 al = (u32)(e >> 32), mk = 0u - (u32)((u32)y < (u32)e);
  return al ^ ((i ^ al) & mk);
}

// IPv4 público: faixas reservadas que não podem sair. bad1 depende do 1º e 2º octetos (corrige somando 64 ao 2º:
// 172.16/12 -> 172.80.., 192.168 -> 192.232, 169.254 -> 169.62, 100.64/10 -> 100.128.., 198.18/15 -> 198.82..);
// bad2 depende também do 3º (192.0.0/24, 192.0.2/24, 198.51.100/24, 203.0.113/24; corrige somando 1 ao 3º).
static inline u32 ip_bad1(u32 a, u32 b) {
  return ((a == 172) & (b >= 16) & (b < 32)) | ((a == 192) & (b == 168)) | ((a == 169) & (b == 254)) |
         ((a == 100) & (b >= 64) & (b < 128)) | ((a == 198) & ((b == 18) | (b == 19)));
}
static inline u32 ip_bad2(u32 a, u32 b, u32 c) {
  return ((a == 192) & (b == 0) & ((c == 0) | (c == 2))) | ((a == 198) & (b == 51) & (c == 100)) |
         ((a == 203) & (b == 0) & (c == 113));
}

// ------------------------------------------------------------------ tabelas compartilhadas (tables.cpp)
extern u32 T4[10000], T3[1000], T3dot[1000], T3dash[1000], T2[100];   // dígitos em ASCII, já empacotados
extern u16 PA[10000], PB[10000], PC[10], PG[3][1000];                  // contribuições ao DV do CPF por grupo
extern u8 DV3[(30 << 5) + 31];                                         // soma empacotada -> DV1*10 + DV2
extern u16 H2[256];                                                    // byte -> 2 caracteres hexadecimais
void init_cpf();
void init_h2();
void init_cnpj();   // documents.cpp
void init_ip();     // network.cpp
void init_house_logs();   // address.cpp
void init_simd();         // numbers.cpp
