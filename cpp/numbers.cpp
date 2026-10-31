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

// normal(mu, sigma); se lognormal != 0, exp(normal)
DG_EXPORT void dg_rand_normal(u64* s, double mu, double sigma, int lognormal, i64 m, double* out) {
  LOAD_S;
  for (i64 r = 0; r < m; r++) {
    NEXT_X(); double p = ((double)(x >> 11) + 0.5) * (1.0 / 9007199254740992.0);
    out[r] = mu + sigma * inv_norm(p);
  }
  SAVE_S;
  if (lognormal) for (i64 r = 0; r < m; r++) out[r] = det_exp(out[r]);
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
  if (lognormal) for (i64 r = 0; r < m; r++) out[r] = det_exp(out[r]);
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
