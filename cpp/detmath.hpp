// detmath.hpp -- log, exp e inversa da normal deterministicos (os mesmos bits em qualquer sistema e compilador).
// Parte do nini-datagen. Usado pelos numeros (normal, lognormal) e pelo numero da casa no endereco.
#pragma once
#include "common.hpp"
#include <cmath>

// Nada de std::log/std::exp: cada biblioteca matemática (glibc, MSVC, macOS) pode errar o último bit de um jeito
// diferente, e a mesma semente daria números diferentes em cada sistema. O CMake também desliga a fusão de
// multiplicação e soma (-ffp-contract=off), que arredondaria diferente no ARM e em CPUs com FMA.
static inline double bits_to_double(u64 b) { double d; memcpy(&d, &b, 8); return d; }
static inline u64 double_to_bits(double d) { u64 b; memcpy(&b, &d, 8); return b; }

// log(x) para x > 0 normal (não subnormal), erro < 1e-15 relativo. x = 2^e * m com m em [sqrt(1/2), sqrt(2));
// log(m) = 2 atanh(f), f = (m - 1) / (m + 1), |f| <= 0,1716: série até f^21 (resto < 1e-18).
static inline double det_log(double x) {
  const u64 bits = double_to_bits(x);
  // expoente como double sem conversão de inteiro (que o SSE/AVX2 não têm vetorizada para 64 bits): 2^52 + campo,
  // menos 2^52 + 1023, dá exatamente o mesmo valor de (double)(campo - 1023)
  double e = bits_to_double(((bits >> 52) & 0x7FF) | 0x4330000000000000ull) - 4503599627371519.0;
  double m = bits_to_double((bits & 0x000FFFFFFFFFFFFFull) | 0x3FF0000000000000ull);  // mantissa em [1, 2)
  const bool big = m > 1.4142135623730951;   // escolha sem desvio (vetoriza): as mesmas contas do if de antes
  m = big ? m * 0.5 : m;
  e = big ? e + 1.0 : e;
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
