// documents.cpp -- CPF, CNPJ (numérico e alfanumérico), PIS, título, CNH, placa, RG, cartão, IBAN, EAN-13
// Parte do nini-datagen (kernels C++ com ABI em C; veja datagen.h).
#include "common.hpp"
#include <cmath>
#include <type_traits>

static inline void row_plain(u32* v, u32 b) {
  u32 q = b / 10, d8 = b - q * 10, a = q / 10000, c = q - a * 10000;
  u32 dv = DV3[PA[a] + PB[c] + PC[d8]];
  v[0] = 11; v[1] = T4[a]; v[2] = T4[c];
  v[3] = (u32)('0' + d8) | ((u32)T2[dv] << 8);              // d8, dv1, dv2, 0
}
static inline void row_fmt(u32* v, u32* d, u32 r, u32 b) {
  u32 g0 = b / 1000000u, rem = b - g0 * 1000000u, g1 = rem / 1000u, g2 = rem - g1 * 1000u;
  u32 dv = DV3[PG[0][g0] + PG[1][g1] + PG[2][g2]];
  d[0] = T3dot[g0]; d[1] = T3dot[g1]; d[2] = T3dash[g2]; d[3] = T2[dv];
  v[0] = 14; v[1] = d[0]; v[2] = 0; v[3] = r * 16u;
}
template <class BaseGen>
static inline void fill(i64 m, int formatted, u32* V, u32* D, BaseGen next) {
  if (formatted) for (i64 r = 0; r < m; r++) row_fmt(V + 4 * r, D + 4 * r, (u32)r, next());
  else           for (i64 r = 0; r < m; r++) row_plain(V + 4 * r, next());
}

// bases dadas (testes / entrada externa)
DG_EXPORT void dg_cpf_from_base(const u32* base, i64 m, int formatted, u32* V, u32* D) {
  const u32* p = base; fill(m, formatted, V, D, [&]() { return *p++; });
}
// ===================================================================== permutação com chave (valores sem repetição)
// Cifra de Feistel em base B: x = L*B + R (L, R < B), 6 rodadas de (L, R) <- (R, (L + F(R)) mod B), cada F com sua
// subchave tirada da chave. É uma bijeção de [0, B^2) nela mesma; a linha global i vira perm(i), então valores sem
// repetição, embaralhados e estáveis por prefixo (só dependem de i e da chave). Para um espaço N < B^2, "cycle walking":
// reaplica a cifra até cair em [0, N), o que continua sendo bijeção em [0, N) (com B^2 ~ N, quase nunca repete).
static inline u64 mix64(u64 z) {
  z ^= z >> 30; z *= 0xBF58476D1CE4E5B9ull; z ^= z >> 27; z *= 0x94D049BB133111EBull; return z ^ (z >> 31);
}
// rodada: finalizador do splitmix64 sobre R ^ subchave, levado a [0, B) pela mulhi. Não é criptografia, mas uma rodada
// mais leve (1 multiplicação) deixava estrutura visível (diferenças entre vizinhos repetidas, pares de dígitos com
// qui-quadrado alto); com o splitmix as estatísticas ficam iguais às de uma amostra sem reposição de verdade.
static inline u64 fround(u64 R, u64 k, u64 B) { return mulhi64(mix64(R ^ k), B); }
struct Feistel {
  u64 B, k[6];
  Feistel(u64 base, u64 key) : B(base) { for (int r = 0; r < 6; r++) k[r] = mix64(key + (u64)(r + 1) * 0x9E3779B97F4A7C15ull); }
  inline u64 enc(u64 x) const {
    u64 L = x / B, R = x - L * B;
    for (int r = 0; r < 6; r++) { u64 t = L + fround(R, k[r], B); if (t >= B) t -= B; L = R; R = t; }
    return L * B + R;
  }
  inline u64 perm(u64 x, u64 n) const { x = enc(x); while (x >= n) x = enc(x); return x; }
  // W linhas consecutivas de uma vez: as cadeias de multiplicação de cada linha são independentes, então a CPU as
  // sobrepõe (uma linha sozinha fica esperando a latência de ~18 multiplicações em série)
  static constexpr int W = 16;
  inline void enc_batch(u64 first, u64* out) const {
    u64 L[W], R[W];
    u64 l = first / B, rr = first - l * B;   // uma divisão por lote: as linhas seguintes só somam 1 a (L, R)
    for (int j = 0; j < W; j++) { L[j] = l; R[j] = rr; if (++rr == B) { rr = 0; l++; } }
    for (int r = 0; r < 6; r++)
      for (int j = 0; j < W; j++) { u64 t = L[j] + fround(R[j], k[r], B); t -= (t >= B) ? B : 0; L[j] = R[j]; R[j] = t; }
    for (int j = 0; j < W; j++) out[j] = L[j] * B + R[j];
  }
  // perm(first + j) para j < count (cycle walking só nas raras linhas que caem fora de [0, n))
  inline void perm_run(u64 first, i64 count, u64 n, u64* out) const {
    i64 j = 0;
    for (; j + W <= count; j += W) enc_batch(first + (u64)j, out + j);
    for (; j < count; j++) out[j] = enc(first + (u64)j);
    for (i64 q = 0; q < count; q++) while (out[q] >= n) out[q] = enc(out[q]);
  }
};
static const u64 CPF_B = 31623;   // 31623^2 = 1.000.014.129 >= 10^9

// sem repetição: a linha r do bloco é a linha global start + r; base = perm(start + r) em [0, 10^9)
DG_EXPORT void dg_cpf_perm(u64 key, u64 start, i64 m, int formatted, u32* V, u32* D) {
  Feistel f(CPF_B, key);
  u64 buf[256]; i64 done = 0, have = 0, pos = 0;
  fill(m, formatted, V, D, [&]() {
    if (pos == have) { have = std::min<i64>(256, m - done); f.perm_run(start + (u64)done, have, MODB, buf); done += have; pos = 0; }
    return (u32)buf[pos++];
  });
}
// i.i.d.: xoshiro256++ (estado de 4 x uint64, atualizado no lugar), 2 bases por uint64 ((x32 * 1e9) >> 32)
DG_EXPORT void dg_cpf_random(u64* s, i64 m, int formatted, u32* V, u32* D) {
  u64 s0 = s[0], s1 = s[1], s2 = s[2], s3 = s[3], pending = 0; bool have = false;
  fill(m, formatted, V, D, [&]() -> u32 {
    if (have) { have = false; return (u32)(((pending >> 32) * (u64)MODB) >> 32); }
    u64 r = rotl(s0 + s3, 23) + s0, t = s1 << 17;
    s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45);
    pending = r; have = true;
    return (u32)((((r & 0xFFFFFFFFULL)) * (u64)MODB) >> 32);
  });
  s[0] = s0; s[1] = s1; s[2] = s2; s[3] = s3;
}

// ===================================================================== CNPJ (numerico e alfanumerico)
// 14 posicoes: 8 de raiz + 4 de ordem (todas 0-9 ou A-Z no alfanumerico) + 2 DV numericos.
// Valor do caractere = ASCII - 48 ('0'..'9' -> 0..9, 'A'..'Z' -> 17..42). Modulo 11:
//   DV1: pesos 5,4,3,2,9,8,7,6,5,4,3,2 nos 12 primeiros; DV2: pesos 6,5,4,3,2,9,8,7,6,5,4,3,2 nos 12 + DV1.
//   resto < 2 -> DV 0, senao 11 - resto.   (Receita Federal, Manual de Calculo do DV do CNPJ Alfanumerico)
// Como no CPF, trabalhamos com PARES de caracteres: tabelas de contribuicao A (DV1) e B (DV2) por grupo.
static const int CW1[12] = {5,4,3,2,9,8,7,6,5,4,3,2};
static const int CW2[12] = {6,5,4,3,2,9,8,7,6,5,4,3};
static u16 CN_TP[2][1296];       // par -> 2 caracteres ASCII
static u16 CN_CA[2][6][1296];    // [alfabeto][grupo][par] -> A | (B << 6)
static u16 CN_DV[4096];          // (a | b << 6) -> 2 caracteres ASCII dos DV
static bool cn_ready = false;
void init_cnpj() {
  if (cn_ready) return;
  for (int ai = 0; ai < 2; ai++) {
    int K = ai ? 36 : 10;
    auto val = [&](int idx) { return (ai && idx >= 10) ? idx + 7 : idx; };
    auto chr = [&](int idx) { return (u8)(idx < 10 ? '0' + idx : 'A' + idx - 10); };
    for (int p = 0; p < K * K; p++) {
      int i0 = p / K, i1 = p % K;
      CN_TP[ai][p] = (u16)(chr(i0) | (chr(i1) << 8));
      for (int g = 0; g < 6; g++) {
        int A = (CW1[2*g] * val(i0) + CW1[2*g+1] * val(i1)) % 11;
        int B = (CW2[2*g] * val(i0) + CW2[2*g+1] * val(i1)) % 11;
        CN_CA[ai][g][p] = (u16)(A | (B << 6));
      }
    }
  }
  auto f = [](int r) { return r < 2 ? 0 : 11 - r; };
  for (int a = 0; a < 64; a++) for (int b = 0; b < 64; b++) {
    int d1 = f(a % 11), d2 = f((b + 2 * d1) % 11);
    CN_DV[a | (b << 6)] = (u16)(('0' + d1) | (('0' + d2) << 8));
  }
  cn_ready = true;
}

template <int K, bool FMT>
static inline void cn_emit(u32* v, u8* d, u32 r, const u32* pi) {
  const int ai = (K == 36);
  u32 S = 0;
  for (int g = 0; g < 6; g++) S += CN_CA[ai][g][pi[g]];
  u16 dv = CN_DV[(S & 63) | (((S >> 6) & 63) << 6)];
  u16 c[6];
  for (int g = 0; g < 6; g++) c[g] = CN_TP[ai][pi[g]];
  if (FMT) {
    u8* o = d + (size_t)r * 18;
    u8 t[12]; memcpy(t, c, 12);
    o[0]=t[0]; o[1]=t[1]; o[2]='.'; o[3]=t[2]; o[4]=t[3]; o[5]=t[4]; o[6]='.'; o[7]=t[5]; o[8]=t[6]; o[9]=t[7];
    o[10]='/'; o[11]=t[8]; o[12]=t[9]; o[13]=t[10]; o[14]=t[11]; o[15]='-'; o[16]=(u8)dv; o[17]=(u8)(dv >> 8);
    v[0] = 18; memcpy(&v[1], o, 4); v[2] = 0; v[3] = r * 18u;
  } else {
    u8* o = d + (size_t)r * 14;
    memcpy(o, c, 12); memcpy(o + 12, &dv, 2);
    v[0] = 14; v[1] = (u32)c[0] | ((u32)c[1] << 16); v[2] = 0; v[3] = r * 14u;
  }
}

// tp4/tp5: indices de par (0..K*K-1) dos grupos 4 e 5 (ordem fixa, FIXED=true); com FIXED=false a ordem e sorteada.
template <int K, bool UNIQ, bool FMT, bool FIXED>
// UNIQ: linha r = perm(start + r) na cifra de Feistel de base K2^(NP/2) (o espaço K2^NP é exatamente B^2).
static void cn_run(u64* s, u32 tp4, u32 tp5, u64 start, u64 key, i64 m, u32* V, u8* D) {
  constexpr u32 K2 = K * K;
  constexpr int NP = FIXED ? 4 : 6;
  constexpr u64 B = FIXED ? (u64)K2 * K2 : (u64)K2 * K2 * K2;
  Feistel f(B, key);
  u64 s0 = s[0], s1 = s[1], s2 = s[2], s3 = s[3];
  u32 pi[6]; pi[4] = tp4; pi[5] = tp5;
  u64 buf[256];
  for (i64 r = 0; r < m; r++) {
    if (UNIQ) {
      if ((r & 255) == 0) f.perm_run(start + (u64)r, std::min<i64>(256, m - r), B * B, buf);
      u64 y = buf[r & 255];
      for (int g = NP - 1; g >= 0; g--) { pi[g] = (u32)(y % K2); y /= K2; }
    } else {
      for (int g = 0; g < NP; g += 2) {
        u64 z = rotl(s0 + s3, 23) + s0, t = s1 << 17;
        s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45);
        pi[g] = (u32)(((z & 0xFFFFFFFFull) * K2) >> 32);
        pi[g + 1] = (u32)(((z >> 32) * K2) >> 32);
      }
    }
    cn_emit<K, FMT>(V + 4 * r, D, (u32)r, pi);
  }
  s[0] = s0; s[1] = s1; s[2] = s2; s[3] = s3;
}
template <int K, bool U, bool F>
static void cn_disp(u64* s, u32 tp4, u32 tp5, u64 start, u64 key, i64 m, u32* V, u8* D) {
  if (tp4 != 0xFFFFFFFFu) cn_run<K, U, F, true>(s, tp4, tp5, start, key, m, V, D);
  else cn_run<K, U, F, false>(s, tp4, tp5, start, key, m, V, D);
}
// unique: start = linha global da primeira linha, key = chave da permutação (ignorados sem unique)
DG_EXPORT void dg_cnpj_gen(u64* s, int alpha, u32 tp4, u32 tp5, int formatted, int unique, u64 start, u64 key, i64 m, u32* V, u8* D) {
  init_cnpj();
  #define CN_CALL(K, U, F) cn_disp<K, U, F>(s, tp4, tp5, start, key, m, V, D)
  if (alpha == 36) {
    if (unique) { if (formatted) CN_CALL(36, true, true); else CN_CALL(36, true, false); }
    else        { if (formatted) CN_CALL(36, false, true); else CN_CALL(36, false, false); }
  } else {
    if (unique) { if (formatted) CN_CALL(10, true, true); else CN_CALL(10, true, false); }
    else        { if (formatted) CN_CALL(10, false, true); else CN_CALL(10, false, false); }
  }
}

// ===================================================================== outros documentos
// kind: 0 PIS/NIS (11 digitos; style 1 = "123.45678.90-1")        DV: pesos 3,2,9,8,7,6,5,4,3,2; 11-resto, 10/11 -> 0
//       1 Titulo de eleitor (12 digitos 8+UF+2DV; style 1 = "1234 5678 0101")   pesos 2..9 e 7,8,9; resto 10 -> 0; SP/MG: 0 -> 1
//       2 CNH (11 digitos, 9 + 2 DV)
//       3 Placa Mercosul "ABC1D23"      4 Placa antiga "ABC-1234"
//       5 RG estilo SP (8 digitos + DV 0-9/X; style 1 = "12.345.678-9")  DV: pesos 2..9, 11-resto (10 -> X, 11 -> 0)
//       6 UUID v4 (36 caracteres)
//       7 IPv4 publico  8 IPv4 privado (10/8, 172.16/12, 192.168/16)  9 IPv6 (8 grupos de 4 hex)  10 MAC (aa:bb:cc:dd:ee:ff)
template <int KIND>
static void id_run(u64* st, int style, i64 m, u32* V, u8* D, int stride) {
  init_cpf(); init_h2();
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  auto next = [&]() -> u64 { u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45); return x; };
  auto put = [&](u32 r, const u8* o, int n) {   // o: ate 48 bytes validos; escreve a view (inline se n <= 12)
    u32* v = V + 4 * (size_t)r; v[0] = (u32)n;
    if (n <= 12) { u8 t[12] = {0}; memcpy(t, o, (size_t)n); memcpy(&v[1], t, 12); }
    else { memcpy(D + (size_t)r * stride, o, (size_t)n); memcpy(&v[1], o, 4); v[2] = 0; v[3] = r * (u32)stride; }
  };
  for (i64 r = 0; r < m; r++) {
    u8 o[48]; int n = 0;
    if (KIND == 0) {
      u64 x = next(); u32 a = (u32)(((x & 0xFFFFFFFFull) * 100000ull) >> 32), b = (u32)(((x >> 32) * 100000ull) >> 32);
      u8 d[11]; memcpy(d, &T4[a / 10], 4); d[4] = (u8)('0' + a % 10); memcpy(d + 5, &T4[b / 10], 4); d[9] = (u8)('0' + b % 10);
      static const int W[10] = {3,2,9,8,7,6,5,4,3,2}; int sum = 0; for (int i = 0; i < 10; i++) sum += (d[i] - '0') * W[i];
      int dv = 11 - sum % 11; if (dv >= 10) dv = 0; d[10] = (u8)('0' + dv);
      if (style == 0) { memcpy(o, d, 11); n = 11; }
      else { memcpy(o, d, 3); o[3] = '.'; memcpy(o + 4, d + 3, 5); o[9] = '.'; memcpy(o + 10, d + 8, 2); o[12] = '-'; o[13] = d[10]; n = 14; }
    } else if (KIND == 1) {
      u64 x = next(); u32 a = (u32)(((x & 0xFFFFFFFFull) * 100000000ull) >> 32), uf = 1 + (u32)(((x >> 32) * 28ull) >> 32);
      u8 d[12]; memcpy(d, &T4[a / 10000], 4); memcpy(d + 4, &T4[a % 10000], 4); d[8] = (u8)('0' + uf / 10); d[9] = (u8)('0' + uf % 10);
      // DV1: resto 10 -> 0. SP/MG (uf 1, 2): a regra "resto 0 -> DV 1" e controversa (Wikipedia/brutils a aplicam; a Resolucao
      // TSE 23.659 e o validate-docbr nao). Para o valor ser valido nas DUAS leituras, essas linhas ambiguas (resto 0 no DV1 ou
      // no DV2 com uf <= 2) mudam o ultimo digito da sequencia ate sairem da ambiguidade (sempre ha saida em <= 10 passos).
      int dv1, dv2;
      for (;;) {
        int s1_ = 0; for (int i = 0; i < 8; i++) s1_ += (d[i] - '0') * (i + 2);
        int r1 = s1_ % 11; dv1 = r1 == 10 ? 0 : r1;
        int r2 = ((d[8] - '0') * 7 + (d[9] - '0') * 8 + dv1 * 9) % 11; dv2 = r2 == 10 ? 0 : r2;
        if (!(uf <= 2 && (r1 == 0 || r2 == 0))) break;
        d[7] = (u8)('0' + (d[7] - '0' + 1) % 10);
      }
      d[10] = (u8)('0' + dv1); d[11] = (u8)('0' + dv2);
      if (style == 0) { memcpy(o, d, 12); n = 12; }
      else { memcpy(o, d, 4); o[4] = ' '; memcpy(o + 5, d + 4, 4); o[9] = ' '; memcpy(o + 10, d + 8, 4); n = 14; }
    } else if (KIND == 2) {
      u64 x = next(); u32 a = (u32)(((x & 0xFFFFFFFFull) * 1000000000ull) >> 32);
      u8 d[11]; memcpy(d, &T4[a / 100000], 4); memcpy(d + 4, &T4[(a % 100000) / 10], 4); d[8] = (u8)('0' + a % 10);
      int v1 = 0, v2 = 0; for (int i = 0; i < 9; i++) { v1 += (d[i] - '0') * (9 - i); v2 += (d[i] - '0') * (1 + i); }
      int dsc = 0, d1 = v1 % 11; if (d1 >= 10) { d1 = 0; dsc = 2; }
      int d2 = v2 % 11 - dsc; if (d2 < 0) d2 += 11; if (d2 >= 10) d2 = 0;
      d[9] = (u8)('0' + d1); d[10] = (u8)('0' + d2); memcpy(o, d, 11); n = 11;
    } else if (KIND == 3 || KIND == 4) {
      u64 x = next(); u32 lo = (u32)x, hi = (u32)(x >> 32);
      auto sym = [](u32& f, u32 k) -> u32 { u64 t = (u64)f * k; f = (u32)t; return (u32)(t >> 32); };   // simbolo + fracao restante
      u32 fl = lo, fh = hi;
      o[0] = (u8)('A' + sym(fl, 26)); o[1] = (u8)('A' + sym(fl, 26)); o[2] = (u8)('A' + sym(fl, 26));
      if (KIND == 3) { o[3] = (u8)('0' + sym(fh, 10)); o[4] = (u8)('A' + sym(fh, 26)); o[5] = (u8)('0' + sym(fh, 10)); o[6] = (u8)('0' + sym(fh, 10)); n = 7; }
      else { o[3] = '-'; o[4] = (u8)('0' + sym(fh, 10)); o[5] = (u8)('0' + sym(fh, 10)); o[6] = (u8)('0' + sym(fh, 10)); o[7] = (u8)('0' + sym(fh, 10)); n = 8; }
    } else if (KIND == 5) {
      u64 x = next(); u32 a = (u32)(((x & 0xFFFFFFFFull) * 100000000ull) >> 32);
      u8 d[9]; memcpy(d, &T4[a / 10000], 4); memcpy(d + 4, &T4[a % 10000], 4);
      int sum = 0; for (int i = 0; i < 8; i++) sum += (d[i] - '0') * (i + 2);
      int dv = 11 - sum % 11; d[8] = dv == 10 ? 'X' : (dv == 11 ? '0' : (u8)('0' + dv));
      if (style == 0) { memcpy(o, d, 9); n = 9; }
      else { memcpy(o, d, 2); o[2] = '.'; memcpy(o + 3, d + 2, 3); o[6] = '.'; memcpy(o + 7, d + 5, 3); o[10] = '-'; o[11] = d[8]; n = 12; }
    } else if (KIND == 11) {   // cartao: style = marca (0 visa, 1 master, 2 amex, 3 mistura) + 4 * formatado
      u64 x = next(), y = next();
      u32 g0 = (u32)(((x & 0xFFFFFFFFull) * 10000ull) >> 32), g1 = (u32)(((x >> 32) * 10000ull) >> 32);
      u32 g2 = (u32)(((y & 0xFFFFFFFFull) * 10000ull) >> 32), g3 = (u32)(((y >> 32) * 10000ull) >> 32);
      u32 brand = (u32)style & 3, fmt = (u32)style >> 2;
      if (brand == 3) { u32 q = (u32)(((x >> 20) & 0xFFFFull) * 100ull >> 16); brand = q < 55 ? 0 : (q < 93 ? 1 : 2); }
      u8 d[16]; memcpy(d, &T4[g0], 4); memcpy(d + 4, &T4[g1], 4); memcpy(d + 8, &T4[g2], 4); memcpy(d + 12, &T4[g3], 4);
      int L = brand == 2 ? 15 : 16;
      if (brand == 0) d[0] = '4';
      else if (brand == 1) { d[0] = '5'; d[1] = (u8)('1' + (d[1] - '0') % 5); }
      else { d[0] = '3'; d[1] = (d[1] - '0') & 1 ? '7' : '4'; }
      // Luhn: dobra os dígitos em posição par contando da direita (sem o DV); tabela em vez de desvio, laço de
      // tamanho fixo (15 ou 16) para o compilador desenrolar
      static const u8 DBL[10] = {0, 2, 4, 6, 8, 1, 3, 5, 7, 9};
      auto luhn = [&](auto len) { constexpr int N = decltype(len)::value; int sum = 0;
        for (int i = 0; i < N - 1; i++) { int t = d[i] - '0'; sum += ((N - 2 - i) & 1) ? t : DBL[t]; } return sum; };
      int sum = L == 16 ? luhn(std::integral_constant<int, 16>{}) : luhn(std::integral_constant<int, 15>{});
      d[L - 1] = (u8)('0' + (10 - sum % 10) % 10);
      if (!fmt) { memcpy(o, d, (size_t)L); n = L; }
      else if (L == 16) { for (int k = 0; k < 4; k++) { memcpy(o + 5 * k, d + 4 * k, 4); o[5 * k + 4] = ' '; } n = 19; }
      else { memcpy(o, d, 4); o[4] = ' '; memcpy(o + 5, d + 4, 6); o[11] = ' '; memcpy(o + 12, d + 10, 5); n = 17; }
    } else if (KIND == 12) {   // IBAN do Brasil (29): BR kk banco(8) agencia(5) conta(10) tipo(C|P) titular(1)
      // DV: 98 - (numero "banco agencia conta tipo titular BR00" com letras -> 2 digitos) mod 97. O numero tem 32
      // digitos: a(8) b(5) c1(5) c2(5) tipo(2: C=12, P=25) titular(1) "1127" "00"; em vez de percorrer os digitos,
      // soma cada parte vezes 10^posicao mod 97 (tudo cabe em 64 bits) e tira um modulo so.
      u64 x = next(), y = next(), z = next();
      u32 a = (u32)(((x & 0xFFFFFFFFull) * 100000000ull) >> 32), b = (u32)(((x >> 32) * 100000ull) >> 32);
      u32 c1 = (u32)(((y & 0xFFFFFFFFull) * 100000ull) >> 32), c2 = (u32)(((y >> 32) * 100000ull) >> 32);
      bool poup = (z & 0xFFFF) < 19660;   // ~30% poupanca
      // 10^k mod 97 para k = 24, 19, 14, 9, 7, 6
      const u64 P24 = 75, P19 = 17, P14 = 53, P9 = 34, P7 = 76, P6 = 27;
      u64 sum = a * P24 + b * P19 + c1 * P14 + c2 * P9 + (poup ? 25u : 12u) * P7 + 1 * P6 + 112700ull;
      u32 chk = (u32)(98 - sum % 97);
      o[0] = 'B'; o[1] = 'R'; o[2] = (u8)('0' + chk / 10); o[3] = (u8)('0' + chk % 10);
      memcpy(o + 4, &T4[a / 10000], 4); memcpy(o + 8, &T4[a % 10000], 4);
      memcpy(o + 12, &T4[b / 10], 4); o[16] = (u8)('0' + b % 10);
      memcpy(o + 17, &T4[c1 / 10], 4); o[21] = (u8)('0' + c1 % 10); memcpy(o + 22, &T4[c2 / 10], 4); o[26] = (u8)('0' + c2 % 10);
      o[27] = poup ? 'P' : 'C'; o[28] = '1'; n = 29;
    } else if (KIND == 13) {   // EAN-13 brasileiro (prefixo 789)
      u64 x = next(); u32 a = (u32)(((x & 0xFFFFFFFFull) * 100000ull) >> 32), b = (u32)(((x >> 32) * 10000ull) >> 32);
      u8 d[13]; d[0] = '7'; d[1] = '8'; d[2] = '9'; memcpy(d + 3, &T4[a / 10], 4); d[7] = (u8)('0' + a % 10); memcpy(d + 8, &T4[b], 4);
      int sum = 0; for (int i = 0; i < 12; i++) sum += (d[i] - '0') * ((i & 1) ? 3 : 1);
      d[12] = (u8)('0' + (10 - sum % 10) % 10); memcpy(o, d, 13); n = 13;
    } else if (KIND >= 7 && KIND <= 8) {
      u64 x = next(); u32 b[4]; for (int i = 0; i < 4; i++) b[i] = (u32)(x >> (8 * i)) & 255u;
      if (KIND == 7) {   // publico: mesmas exclusoes de ipv4_run<false>
        u32 a = 1 + ((u32)(x >> 32) * 222ull >> 32) ; a = (a == 10 || a == 127) ? a + 1 : a;
        b[0] = a; if (ip_bad1(a, b[1])) b[1] = (b[1] + 64) & 255u;
        if (ip_bad2(a, b[1], b[2])) b[2] = b[2] + 1;
      } else {
        u32 c = (u32)(((x >> 32) * 3ull) >> 32);
        if (c == 0) { b[0] = 10; } else if (c == 1) { b[0] = 172; b[1] = 16 + (b[1] & 15); } else { b[0] = 192; b[1] = 168; }
      }
      int p = 0; for (int i = 0; i < 4; i++) { u32 v = b[i]; if (v >= 100) o[p++] = (u8)('0' + v / 100); if (v >= 10) o[p++] = (u8)('0' + (v / 10) % 10); o[p++] = (u8)('0' + v % 10); if (i < 3) o[p++] = '.'; }
      n = p;
    } else if (KIND == 9) {
      u64 a = next(), b = next(); u16 g[8]; memcpy(g, &a, 8); memcpy(g + 4, &b, 8);
      int p = 0; for (int i = 0; i < 8; i++) { memcpy(o + p, &H2[g[i] >> 8], 2); memcpy(o + p + 2, &H2[g[i] & 255], 2); p += 4; if (i < 7) o[p++] = ':'; }
      n = p;
    } else if (KIND == 10) {
      u64 a = next(); u8 by[8]; memcpy(by, &a, 8); by[0] = (u8)(by[0] & 0xFE);   // unicast
      int p = 0; for (int i = 0; i < 6; i++) { memcpy(o + p, &H2[by[i]], 2); p += 2; if (i < 5) o[p++] = ':'; }
      n = p;
    } else {  // UUID v4
      u64 a = next(), b = next();
      u8 by[16]; memcpy(by, &a, 8); memcpy(by + 8, &b, 8);
      by[6] = (u8)((by[6] & 0x0F) | 0x40); by[8] = (u8)((by[8] & 0x3F) | 0x80);
      int p = 0; for (int i = 0; i < 16; i++) { if (i == 4 || i == 6 || i == 8 || i == 10) o[p++] = '-'; memcpy(o + p, &H2[by[i]], 2); p += 2; }
      n = 36;
    }
    put((u32)r, o, n);
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
}
DG_EXPORT void dg_id_views(u64* st, int kind, int style, i64 m, u32* V, u8* D, int stride) {
  switch (kind) {
    case 0: id_run<0>(st, style, m, V, D, stride); break;
    case 1: id_run<1>(st, style, m, V, D, stride); break;
    case 2: id_run<2>(st, style, m, V, D, stride); break;
    case 3: id_run<3>(st, style, m, V, D, stride); break;
    case 4: id_run<4>(st, style, m, V, D, stride); break;
    case 5: id_run<5>(st, style, m, V, D, stride); break;
    case 7: id_run<7>(st, style, m, V, D, stride); break;
    case 8: id_run<8>(st, style, m, V, D, stride); break;
    case 9: id_run<9>(st, style, m, V, D, stride); break;
    case 10: id_run<10>(st, style, m, V, D, stride); break;
    case 11: id_run<11>(st, style, m, V, D, stride); break;
    case 12: id_run<12>(st, style, m, V, D, stride); break;
    case 13: id_run<13>(st, style, m, V, D, stride); break;
    default: id_run<6>(st, style, m, V, D, stride); break;
  }
}
