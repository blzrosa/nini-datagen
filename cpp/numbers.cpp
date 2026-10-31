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
// Nada de std::log/std::exp: cada biblioteca matemática (glibc, MSVC, macOS) pode errar o último bit de um jeito
// diferente, e a mesma semente daria números diferentes em cada sistema. O CMake também desliga a fusão de
// multiplicação e soma (-ffp-contract=off), que arredondaria diferente no ARM e em CPUs com FMA.
static inline double bits_to_double(u64 b) { double d; memcpy(&d, &b, 8); return d; }
static inline u64 double_to_bits(double d) { u64 b; memcpy(&b, &d, 8); return b; }

// log(x) para x > 0 normal (não subnormal), erro < 1e-15 relativo. x = 2^e * m com m em [sqrt(1/2), sqrt(2));
// log(m) = 2 atanh(f), f = (m - 1) / (m + 1), |f| <= 0,1716: série até f^21 (resto < 1e-18).
static inline double det_log(double x) {
  const u64 bits = double_to_bits(x);
  double e = (double)((i64)((bits >> 52) & 0x7FF) - 1023);
  double m = bits_to_double((bits & 0x000FFFFFFFFFFFFFull) | 0x3FF0000000000000ull);  // mantissa em [1, 2)
  if (m > 1.4142135623730951) { m = m * 0.5; e = e + 1.0; }
  const double f = (m - 1.0) / (m + 1.0), f2 = f * f;
  double p = 1.0 / 21.0;
  p = p * f2 + 1.0 / 19.0; p = p * f2 + 1.0 / 17.0; p = p * f2 + 1.0 / 15.0; p = p * f2 + 1.0 / 13.0;
  p = p * f2 + 1.0 / 11.0; p = p * f2 + 1.0 / 9.0;  p = p * f2 + 1.0 / 7.0;  p = p * f2 + 1.0 / 5.0;
  p = p * f2 + 1.0 / 3.0;  p = p * f2 + 1.0;
  const double ln2_hi = 6.93147180369123816490e-01, ln2_lo = 1.90821492927058770002e-10;  // ln 2 = hi + lo
  return e * ln2_hi + (2.0 * f * p + e * ln2_lo);
}

// exp(x) (reduz o argumento a 2^k * e^r, polinômio grau 11): erro relativo ~1e-13, sem desvios.
static inline double det_exp(double x) {
  x = x > 700.0 ? 700.0 : x;
  x = x < -700.0 ? -700.0 : x;
  const double kf = std::floor(x * 1.4426950408889634 + 0.5);
  const double r = x - kf * 0.6931471805599453;
  double p = 1.0 / 39916800.0;
  p = p * r + 1.0 / 3628800.0; p = p * r + 1.0 / 362880.0; p = p * r + 1.0 / 40320.0; p = p * r + 1.0 / 5040.0;
  p = p * r + 1.0 / 720.0; p = p * r + 1.0 / 120.0; p = p * r + 1.0 / 24.0; p = p * r + 1.0 / 6.0;
  p = p * r + 0.5; p = p * r + 1.0; p = p * r + 1.0;
  // 2^kf sem converter double -> int64 (que o SSE/AVX2 não têm vetorizado, e o laço deixaria de vetorizar): os bits
  // baixos de kf + 2^52 + 1023 são exatamente kf + 1023
  return p * bits_to_double(double_to_bits(kf + 4503599627371519.0) << 52);
}

// inversa da normal padrão (Acklam, erro relativo < 1.2e-9); a cauda (sqrt + log) só em ~5% das linhas
static inline double inv_norm(double p) {
  static const double a0=-3.969683028665376e+01,a1=2.209460984245205e+02,a2=-2.759285104469687e+02,a3=1.383577518672690e+02,a4=-3.066479806614716e+01,a5=2.506628277459239e+00;
  static const double b0=-5.447609879822406e+01,b1=1.615858368580409e+02,b2=-1.556989798598866e+02,b3=6.680131188771972e+01,b4=-1.328068155288572e+01;
  static const double c0=-7.784894002430293e-03,c1=-3.223964580411365e-01,c2=-2.400758277161838e+00,c3=-2.549732539343734e+00,c4=4.374664141464968e+00,c5=2.938163982698783e+00;
  static const double d0=7.784695709041462e-03,d1=3.224671290700398e-01,d2=2.445134137142996e+00,d3=3.754408661907416e+00;
  if (p < 0.02425 || p > 1.0 - 0.02425) {
    double q = std::sqrt(-2.0 * det_log(p < 0.5 ? p : 1.0 - p));
    double v = (((((c0*q+c1)*q+c2)*q+c3)*q+c4)*q+c5) / ((((d0*q+d1)*q+d2)*q+d3)*q+1.0);
    return p < 0.5 ? v : -v;
  }
  double q = p - 0.5, r = q * q;
  return (((((a0*r+a1)*r+a2)*r+a3)*r+a4)*r+a5)*q / (((((b0*r+b1)*r+b2)*r+b3)*r+b4)*r+1.0);
}

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
