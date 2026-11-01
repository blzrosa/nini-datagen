// numbers.cpp -- alias (Vose), booleanos, inteiros, floats, normal/lognormal, índices ponderados
// Parte do nini-datagen (kernels C++ com ABI em C; veja datagen.h).
#include "common.hpp"
#include <vector>

// Constroi a tabela alias de Vose (uint64 = thr | alias<<32) a partir de pesos ja validados. O(k).
DG_EXPORT void dg_alias_build(const double* w, u32 k, u64* tab) {
  double sum = 0; for (u32 i = 0; i < k; i++) sum += w[i];
  std::vector<double> p(k); std::vector<u32> alias(k), small, large;
  small.reserve(k); large.reserve(k);
  for (u32 i = 0; i < k; i++) { p[i] = w[i] / sum * k; alias[i] = i; (p[i] < 1.0 ? small : large).push_back(i); }
  std::vector<double> prob(k, 1.0);
  while (!small.empty() && !large.empty()) {
    u32 sm = small.back(); small.pop_back(); u32 lg = large.back(); large.pop_back();
    prob[sm] = p[sm]; alias[sm] = lg;
    p[lg] = p[lg] + p[sm] - 1.0;
    (p[lg] < 1.0 ? small : large).push_back(lg);
  }
  for (u32 i = 0; i < k; i++) {
    double t = prob[i] * 4294967296.0; if (t > 4294967295.0) t = 4294967295.0;
    tab[i] = (u64)(u32)(t + 0.5) | ((u64)alias[i] << 32);
  }
}

// m bits aleatorios (little-endian por palavra, como o Arrow), cada um 1 com probabilidade thr/2^32 (thr em [0, 2^32]).
// thr == 2^31 usa a palavra crua do RNG (64 bits por sorteio). Os bits alem de m, na ultima palavra, ficam 0.
DG_EXPORT void dg_bool_bits(u64* s, u64 thr, i64 m, u64* out) {
  u64 s0=s[0],s1=s[1],s2=s[2],s3=s[3];
  i64 words = (m + 63) >> 6;
  auto next = [&]() { u64 x=rotl(s0+s3,23)+s0, t=s1<<17; s2^=s0; s3^=s1; s1^=s2; s0^=s3; s2^=t; s3=rotl(s3,45); return x; };
  for (i64 w = 0; w < words; w++) {
    u64 word;
    if (thr == 0x80000000ull) word = next();
    else if (thr == 0) word = 0;
    else if (thr >= 0x100000000ull) word = ~0ull;
    else {
      word = 0;
      for (int b = 0; b < 32; b++) {
        u64 x = next();
        word |= (u64)((u64)(u32)x < thr) << (2*b);
        word |= (u64)((u64)(x >> 32) < thr) << (2*b+1);
      }
    }
    out[w] = word;
  }
  i64 rem = m & 63;
  if (rem) out[words-1] &= (1ull << rem) - 1;
  s[0]=s0;s[1]=s1;s[2]=s2;s[3]=s3;
}

// ===================================================================== numericos
#define NEXT_X() u64 x=rotl(s0+s3,23)+s0, t_=s1<<17; s2^=s0; s3^=s1; s1^=s2; s0^=s3; s2^=t_; s3=rotl(s3,45)
#define LOAD_S u64 s0=s[0],s1=s[1],s2=s[2],s3=s[3]
#define SAVE_S s[0]=s0;s[1]=s1;s[2]=s2;s[3]=s3

// inteiro uniforme em [lo, lo+span) (span >= 1). span < 2^32: multiplicacao 32x32 (viés < 2^-32 relativo, ok para mock);
// senão multiplicação 64x64->128.
DG_EXPORT void dg_rand_i64(u64* s, i64 lo, u64 span, i64 m, i64* out) {
  LOAD_S;
  if (span <= 0x100000000ull) {
    for (i64 r = 0; r < m; r++) { NEXT_X(); out[r] = lo + (i64)(((x >> 32) * span) >> 32); }
  } else {
    for (i64 r = 0; r < m; r++) { NEXT_X(); out[r] = lo + (i64)mulhi64(x, span); }
  }
  SAVE_S;
}
DG_EXPORT void dg_rand_i32(u64* s, int lo, u32 span, i64 m, int* out) {
  LOAD_S;
  for (i64 r = 0; r < m; r++) { NEXT_X(); out[r] = lo + (int)(((x >> 32) * (u64)span) >> 32); }
  SAVE_S;
}
// double uniforme em [lo, hi)
DG_EXPORT void dg_rand_f64(u64* s, double lo, double hi, i64 m, double* out) {
  LOAD_S; const double sc = (hi - lo) * (1.0 / 9007199254740992.0);
  for (i64 r = 0; r < m; r++) { NEXT_X(); out[r] = lo + (double)(x >> 11) * sc; }
  SAVE_S;
}
DG_EXPORT void dg_rand_f32(u64* s, float lo, float hi, i64 m, float* out) {
  LOAD_S; const float sc = (hi - lo) * (1.0f / 16777216.0f);
  for (i64 r = 0; r < m; r++) { NEXT_X(); out[r] = lo + (float)(x >> 40) * sc; }
  SAVE_S;
}
// ===================================================================== normal e lognormal
// Determinismo entre sistemas: só + - * / e sqrt (que o IEEE 754 exige com arredondamento correto) e log/exp próprios.
#include "detmath.hpp"   // det_log, det_exp, inv_norm: os mesmos bits em qualquer sistema

// ----------------------------------------------------------------- AVX2 escolhido na hora (só x86-64, GCC/Clang)
// Os wheels são para x86-64-v2 (SSE4.2: 2 doubles por instrução). Os laços sem desvio de normal/lognormal ganham uma
// segunda cópia compilada para AVX2 (4 por instrução), usada se a CPU e o sistema tiverem AVX2. Sem FMA (o alvo é só
// "avx2" e o CMake usa -ffp-contract=off): cada linha faz as mesmas operações IEEE na mesma ordem, então os bits são os
// mesmos nas duas cópias (os testes conferem, com dg_simd).
#if (defined(__x86_64__) || defined(_M_X64)) && (defined(__GNUC__) || defined(__clang__))
#define DG_AVX2_DISPATCH 1
#include <cpuid.h>
static bool cpu_has_avx2() {
  unsigned a = 0, b = 0, c = 0, d = 0;
  if (!__get_cpuid(1, &a, &b, &c, &d)) return false;
  if (!(c & (1u << 27)) || !(c & (1u << 28))) return false;   // OSXSAVE e AVX
  unsigned lo = 0, hi = 0;
  __asm__ volatile("xgetbv" : "=a"(lo), "=d"(hi) : "c"(0));    // o sistema salva os registradores YMM?
  (void)hi;
  if ((lo & 6u) != 6u) return false;
  if (__get_cpuid_max(0, nullptr) < 7) return false;
  __cpuid_count(7, 0, a, b, c, d);
  return (b & (1u << 5)) != 0;                                  // AVX2
}
#define DG_AVX2 __attribute__((target("avx2")))
#else
static bool cpu_has_avx2() { return false; }
#endif
static int g_avx2 = 0;
void init_simd() { g_avx2 = cpu_has_avx2() ? 1 : 0; }
// level < 0: só consulta; 0: desliga o AVX2; 1: liga (se a CPU tiver). Devolve o estado em vigor.
DG_EXPORT int dg_simd(int level) {
  if (level >= 0) g_avx2 = (level > 0 && cpu_has_avx2()) ? 1 : 0;
  return g_avx2;
}

// os laços sem desvio (região central da inversa da normal; exp): o mesmo corpo nas duas cópias
static const double NA0=-3.969683028665376e+01,NA1=2.209460984245205e+02,NA2=-2.759285104469687e+02,NA3=1.383577518672690e+02,NA4=-3.066479806614716e+01,NA5=2.506628277459239e+00;
static const double NB0=-5.447609879822406e+01,NB1=1.615858368580409e+02,NB2=-1.556989798598866e+02,NB3=6.680131188771972e+01,NB4=-1.328068155288572e+01;
#define DG_NORMAL_CENTRAL_BODY                                                                       \
  for (i64 r = 0; r < m; r++) {                                                                      \
    double q = out[r] - 0.5, rr = q * q;                                                             \
    out[r] = mu + sigma * ((((((NA0*rr+NA1)*rr+NA2)*rr+NA3)*rr+NA4)*rr+NA5)*q /                       \
                           (((((NB0*rr+NB1)*rr+NB2)*rr+NB3)*rr+NB4)*rr+1.0));                        \
  }
#define DG_EXP_BODY for (i64 r = 0; r < m; r++) out[r] = det_exp(out[r]);
// caudas da inversa (as mesmas contas de inv_norm para p < 0,02425 ou p > 0,97575), sobre as linhas já separadas
static const double NC0=-7.784894002430293e-03,NC1=-3.223964580411365e-01,NC2=-2.400758277161838e+00,NC3=-2.549732539343734e+00,NC4=4.374664141464968e+00,NC5=2.938163982698783e+00;
static const double ND0=7.784695709041462e-03,ND1=3.224671290700398e-01,ND2=2.445134137142996e+00,ND3=3.754408661907416e+00;
#define DG_TAILS_BODY                                                                                \
  for (size_t i = 0; i < nt; i++) {                                                                  \
    double p = tp[i];                                                                                \
    double q = std::sqrt(-2.0 * det_log(p < 0.5 ? p : 1.0 - p));                                     \
    double v = (((((NC0*q+NC1)*q+NC2)*q+NC3)*q+NC4)*q+NC5) / ((((ND0*q+ND1)*q+ND2)*q+ND3)*q+1.0);     \
    tp[i] = mu + sigma * (p < 0.5 ? v : -v);                                                         \
  }
static void tails_base(double* tp, size_t nt, double mu, double sigma) { DG_TAILS_BODY }
static void normal_central_base(double* out, i64 m, double mu, double sigma) { DG_NORMAL_CENTRAL_BODY }
static void exp_inplace_base(double* out, i64 m) { DG_EXP_BODY }
#ifdef DG_AVX2_DISPATCH
DG_AVX2 static void normal_central_avx2(double* out, i64 m, double mu, double sigma) { DG_NORMAL_CENTRAL_BODY }
DG_AVX2 static void exp_inplace_avx2(double* out, i64 m) { DG_EXP_BODY }
DG_AVX2 static void tails_avx2(double* tp, size_t nt, double mu, double sigma) { DG_TAILS_BODY }
#endif
static void tails_eval(double* tp, size_t nt, double mu, double sigma) {
#ifdef DG_AVX2_DISPATCH
  if (g_avx2) { tails_avx2(tp, nt, mu, sigma); return; }
#endif
  tails_base(tp, nt, mu, sigma);
}
static void normal_central(double* out, i64 m, double mu, double sigma) {
#ifdef DG_AVX2_DISPATCH
  if (g_avx2) { normal_central_avx2(out, m, mu, sigma); return; }
#endif
  normal_central_base(out, m, mu, sigma);
}
static void exp_inplace(double* out, i64 m) {
#ifdef DG_AVX2_DISPATCH
  if (g_avx2) { exp_inplace_avx2(out, m); return; }
#endif
  exp_inplace_base(out, m);
}

// normal(mu, sigma); se lognormal != 0, exp(normal)
// Em passadas, para o compilador vetorizar a parte cara: 1) sorteia p de todas as linhas e anota as das caudas (~5%);
// 2) a região central da inversa (dois polinômios e uma divisão) em todas, sem desvio; 3) refaz as caudas. Cada linha
// faz exatamente as mesmas contas de inv_norm(p), na mesma ordem: os mesmos bits do laço linha a linha.
DG_EXPORT void dg_rand_normal(u64* s, double mu, double sigma, int lognormal, i64 m, double* out) {
  std::vector<u32> tails((size_t)(m > 0 ? m : 0) / 8 + 64);
  size_t nt = 0;
  LOAD_S;
  for (i64 r = 0; r < m; r++) {
    NEXT_X(); double p = ((double)(x >> 11) + 0.5) * (1.0 / 9007199254740992.0);
    out[r] = p;
    if (nt == tails.size()) tails.resize(2 * nt);
    tails[nt] = (u32)r; nt += (size_t)((p < 0.02425) | (p > 1.0 - 0.02425));
  }
  SAVE_S;
  std::vector<double> tp(nt);
  for (size_t i = 0; i < nt; i++) tp[i] = out[tails[i]];
  normal_central(out, m, mu, sigma);
  tails_eval(tp.data(), nt, mu, sigma);
  for (size_t i = 0; i < nt; i++) out[tails[i]] = tp[i];
  if (lognormal) exp_inplace(out, m);
}

// correlated: mean + a*z + b*Normal(0,1) (e exp, se lognormal), z = (x - center) / scale (0 sem escala), com o mesmo
// sorteio de dg_rand_normal e o exp deterministico (sem a biblioteca do sistema: os mesmos bits em qualquer maquina)
DG_EXPORT void dg_correlated(u64* s, const double* x_in, double center, double scale, double a, double b, double mean,
                             int lognormal, i64 m, double* out) {
  LOAD_S;
  for (i64 r = 0; r < m; r++) {
    NEXT_X(); double p = ((double)(x >> 11) + 0.5) * (1.0 / 9007199254740992.0);
    double z = scale > 0.0 ? (x_in[r] - center) / scale : 0.0;
    double y = b * inv_norm(p);
    y += a * z;
    out[r] = y + mean;
  }
  SAVE_S;
  if (lognormal) exp_inplace(out, m);
}

// birthdate: dia sorteado uniforme em [lower[a], upper[a]] (dias desde 1970) para a idade a de cada linha. O sorteio
// e o de dg_rand_f64(0, 1): o mesmo resultado do calculo em numpy que veio antes, so que numa passada.
DG_EXPORT void dg_birthdate(u64* s, const i64* ages, const i64* lower, const i64* upper, i64 m, i32* out) {
  LOAD_S; const double sc = 1.0 * (1.0 / 9007199254740992.0);
  for (i64 r = 0; r < m; r++) {
    NEXT_X(); double u = 0.0 + (double)(x >> 11) * sc;
    i64 age = ages[r], lo = lower[age], span = upper[age] - lo + 1;
    out[r] = (i32)(lo + (i64)(u * (double)span));
  }
  SAVE_S;
}

// exp deterministico, para o Python (parametros derivados, ex.: media da lognormal) sem o exp do sistema
DG_EXPORT double dg_det_exp(double x) { return det_exp(x); }

// indices ponderados (alias) como uint32 -- para valores numericos com distribuicao arbitraria (ex.: idade)
DG_EXPORT void dg_alias_idx(u32 k, const u64* tab, u64* s, i64 m, u32* out) {
  LOAD_S;
  for (i64 r = 0; r < m; r++) {
    NEXT_X();
    u32 i = (u32)(((x >> 32) * (u64)k) >> 32); u64 e = tab[i];
    u32 al = (u32)(e >> 32), mask = 0u - (u32)((u32)x < (u32)e); out[r] = al ^ ((i ^ al) & mask);
  }
  SAVE_S;
}
