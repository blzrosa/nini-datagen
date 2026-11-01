// tables.cpp -- tabelas compartilhadas (dígitos, DV do CPF, hexadecimal) e inicialização
// Parte do nini-datagen (kernels C++ com ABI em C; veja datagen.h).
#include "common.hpp"

u32 T4[10000], T3[1000], T3dot[1000], T3dash[1000], T2[100];
u16 PA[10000], PB[10000], PC[10], PG[3][1000];   // contribuições (A + B<<5) por grupo: (4,4,1) e (3,3,3)
u8 DV3[(30 << 5) + 31];
static bool ready = false;

static u32 dvf(u32 v) { u32 r = v % 11; return r < 2 ? 0 : 11 - r; }
static u16 contrib(int pos, int k, int v) {
  int A = 0, B = 0, dg[4], t = v;
  for (int j = k - 1; j >= 0; j--) { dg[j] = t % 10; t /= 10; }
  for (int j = 0; j < k; j++) { A += dg[j] * (10 - (pos + j)); B += dg[j] * (11 - (pos + j)); }
  return (u16)((A % 11) + ((B % 11) << 5));
}

void init_cpf() {
  if (ready) return;
  for (int i = 0; i < 10000; i++) {
    u32 v = 0; int div[4] = {1000, 100, 10, 1};
    for (int k = 0; k < 4; k++) v |= (u32)('0' + (i / div[k]) % 10) << (8 * k);
    T4[i] = v; PA[i] = contrib(0, 4, i); PB[i] = contrib(4, 4, i);
  }
  for (int i = 0; i < 1000; i++) {
    u32 v = (u32)('0' + i / 100) | ((u32)('0' + (i / 10) % 10) << 8) | ((u32)('0' + i % 10) << 16);
    T3[i] = v; T3dot[i] = v | ((u32)'.' << 24); T3dash[i] = v | ((u32)'-' << 24);
    for (int g = 0; g < 3; g++) PG[g][i] = contrib(3 * g, 3, i);
  }
  for (int i = 0; i < 100; i++) T2[i] = (u32)('0' + i / 10) | ((u32)('0' + i % 10) << 8);
  for (int v = 0; v < 10; v++) PC[v] = contrib(8, 1, v);
  for (int S = 0; S < (int)sizeof(DV3); S++) { u32 d1 = dvf(S & 31); u32 d2 = dvf((S >> 5) + 2 * d1); DV3[S] = (u8)(d1 * 10 + d2); }
  ready = true;
}

static const char HEXD[] = "0123456789abcdef";
u16 H2[256];
static bool h2_ready = false;
void init_h2() { if (h2_ready) return; for (int i = 0; i < 256; i++) H2[i] = (u16)((u8)HEXD[i >> 4] | ((u16)(u8)HEXD[i & 15] << 8)); h2_ready = true; }

// Views longas (len > 12) de um bloco: devolve os bytes usados no buffer de texto (maior deslocamento + len) e, com
// buf >= 0, grava buf como índice do buffer (os kernels escrevem 0; cada bloco tem o seu buffer). Uma passada só; em
// numpy (máscara + atribuição) isto custava ~7 ns por linha, mais que muitos kernels.
DG_EXPORT i64 dg_views_used(u32* V, i64 m, int buf) {
  u64 used = 0;
  for (i64 r = 0; r < m; r++) {
    u32* v = V + 4 * r;
    if (v[0] > 12) {
      u64 end = (u64)v[3] + v[0];
      used = end > used ? end : used;
      if (buf >= 0) v[2] = (u32)buf;
    }
  }
  return (i64)used;
}

// Inicializa TODAS as tabelas de uma vez. O Python chama isto ao carregar a biblioteca, ANTES de usar threads: as
// inicializações preguiçosas dentro dos kernels seriam uma corrida de dados entre threads (e, em CPUs com memória
// fracamente ordenada, outra thread poderia ver a flag "pronto" antes das tabelas).
DG_EXPORT int dg_init() { init_cpf(); init_cnpj(); init_h2(); init_ip(); init_house_logs(); init_simd(); return 1; }
DG_EXPORT int dg_abi_version() { return DG_ABI_VERSION; }

// Linhas nulas (bit 0) entre as m primeiras de um bitmap de validade do Arrow (LSB primeiro), para o null_count da
// interface C do Arrow (core/arrow_c.py). Lê de 8 em 8 bytes; popcount portátil (sem depender de intrínsecos).
static inline u32 popcount64(u64 x) {
  x = x - ((x >> 1) & 0x5555555555555555ull);
  x = (x & 0x3333333333333333ull) + ((x >> 2) & 0x3333333333333333ull);
  x = (x + (x >> 4)) & 0x0F0F0F0F0F0F0F0Full;
  return (u32)((x * 0x0101010101010101ull) >> 56);
}
DG_EXPORT i64 dg_count_unset(const u8* bits, i64 m) {
  i64 set = 0, full = m / 64, r = 0;
  for (; r < full; r++) { u64 w; memcpy(&w, bits + 8 * r, 8); set += popcount64(w); }
  for (i64 i = full * 64; i < m; i++) set += (bits[i >> 3] >> (i & 7)) & 1;
  return m - set;
}
