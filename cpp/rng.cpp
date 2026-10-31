// rng.cpp -- estados independentes do xoshiro256++ para os blocos de linhas.
// Parte do nini-datagen (kernels C++ com ABI em C; veja datagen.h).
#include "common.hpp"

// O bloco i usa o estado inicial avançado i vezes por jump() (2^128 passos do gerador): os blocos nunca se sobrepõem e
// o estado de um bloco depende só de (seed, fluxo, índice do bloco). Por isso o resultado não muda com o número de
// threads nem com n: gerar 1.000 linhas dá o começo exato de gerar 1 milhão.
static void jump(u64* s) {
  static const u64 J[4] = {0x180ec6d33cfd0abaULL, 0xd5a61266f0c9392cULL, 0xa9582618e03fc9aaULL, 0x39abdc4529b1661cULL};
  u64 s0 = 0, s1 = 0, s2 = 0, s3 = 0;
  for (int i = 0; i < 4; i++)
    for (int b = 0; b < 64; b++) {
      if (J[i] & (1ULL << b)) { s0 ^= s[0]; s1 ^= s[1]; s2 ^= s[2]; s3 ^= s[3]; }
      u64 t = s[1] << 17;   // um passo do xoshiro256++ (a saída não importa aqui)
      s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3]; s[2] ^= t; s[3] = rotl(s[3], 45);
    }
  s[0] = s0; s[1] = s1; s[2] = s2; s[3] = s3;
}

// out[4*i .. 4*i+3] = estado do bloco first+i, a partir do estado-semente seed[4] (não pode ser todo zero).
DG_EXPORT void dg_xoshiro_streams(const u64* seed, i64 first, i64 count, u64* out) {
  u64 s[4] = {seed[0], seed[1], seed[2], seed[3]};
  for (i64 i = 0; i < first; i++) jump(s);
  for (i64 i = 0; i < count; i++) {
    memcpy(out + 4 * i, s, 32);
    jump(s);
  }
}
