// network.cpp -- UUID v4, IPv4 (público/privado), URL
// Parte do nini-datagen (kernels C++ com ABI em C; veja datagen.h).
#include "common.hpp"

// ===================================================================== UUID v4 e IPv4 (versoes rapidas)
// uuid_views: D tem m*36 + 64 bytes; a linha r fica em D[36*r..], sempre > 12 bytes => view {36, prefixo, 0, 36*r}.
// Escritas diretas em u32 (sem buffer temporario, sem loop com desvio para os hifens).
DG_EXPORT void dg_uuid_views(u64* st, i64 m, u32* V, u8* D) {
  init_h2();
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  auto next = [&]() -> u64 { u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45); return x; };
  auto hx = [&](u32 a, u32 b) -> u32 { return (u32)H2[a] | ((u32)H2[b] << 16); };
  for (i64 r = 0; r < m; r++) {
    u64 a = next(), b = next();
    u32 b0 = (u32)a & 255, b1 = (u32)(a >> 8) & 255, b2 = (u32)(a >> 16) & 255, b3 = (u32)(a >> 24) & 255;
    u32 b4 = (u32)(a >> 32) & 255, b5 = (u32)(a >> 40) & 255, b6 = (((u32)(a >> 48) & 255) & 0x0F) | 0x40, b7 = (u32)(a >> 56);
    u32 b8 = (((u32)b & 255) & 0x3F) | 0x80, b9 = (u32)(b >> 8) & 255, b10 = (u32)(b >> 16) & 255, b11 = (u32)(b >> 24) & 255;
    u32 b12 = (u32)(b >> 32) & 255, b13 = (u32)(b >> 40) & 255, b14 = (u32)(b >> 48) & 255, b15 = (u32)(b >> 56);
    u8* o = D + 36 * (size_t)r;
    u32 w0 = hx(b0, b1), w1 = hx(b2, b3), w2 = hx(b4, b5), w3 = hx(b6, b7), w4 = hx(b8, b9), w5 = hx(b10, b11), w6 = hx(b12, b13), w7 = hx(b14, b15);
    memcpy(o, &w0, 4); memcpy(o + 4, &w1, 4); o[8] = '-'; memcpy(o + 9, &w2, 4); o[13] = '-'; memcpy(o + 14, &w3, 4); o[18] = '-';
    memcpy(o + 19, &w4, 4); o[23] = '-'; memcpy(o + 24, &w5, 4); memcpy(o + 28, &w6, 4); memcpy(o + 32, &w7, 4);
    u32* v = V + 4 * (size_t)r; v[0] = 36; v[1] = w0; v[2] = 0; v[3] = (u32)(36 * r);
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
}

// ipv4_views: D tem m*16 + 64 bytes; a linha r e escrita em D[16*r..] (16 bytes) e a view e INLINE (n <= 12) ou aponta
// para ali (n > 12), sem desvio (mascaras). Tabela: cada octeto 0..255 -> "ddd." (digitos + ponto) e comprimento.
static u32 IPE[256]; static u8 IPL[256]; static bool ip_ready = false;
void init_ip() {
  if (ip_ready) return;
  for (int v = 0; v < 256; v++) {
    char t[5] = {0, 0, 0, 0, 0}; int p = 0;
    if (v >= 100) t[p++] = (char)('0' + v / 100);
    if (v >= 10) t[p++] = (char)('0' + (v / 10) % 10);
    t[p++] = (char)('0' + v % 10); t[p++] = '.';
    memcpy(&IPE[v], t, 4); IPL[v] = (u8)p;
  }
  ip_ready = true;
}
template <bool PRIV>
static void ipv4_run(u64* st, i64 m, u32* V, u8* D) {
  init_ip();
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  auto next = [&]() -> u64 { u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45); return x; };
  for (i64 r = 0; r < m; r++) {
    u64 x = next();
    u32 b0, b1 = (u32)(x >> 8) & 255u, b2 = (u32)(x >> 16) & 255u, b3 = (u32)(x >> 24) & 255u;
    if (!PRIV) {   // publico: 1..223 sem 10 e 127 e sem as faixas reservadas (ip_bad1/ip_bad2)
      u32 a = 1 + (u32)((((x >> 32) & 0xFFFFFFFFull) * 222ull) >> 32);
      a += (a == 10) | (a == 127);
      b0 = a; b1 = ip_bad1(a, b1) ? ((b1 + 64) & 255u) : b1;
      b2 = ip_bad2(a, b1, b2) ? b2 + 1 : b2;
    } else {
      u32 c = (u32)(((x >> 32) * 3ull) >> 32);
      b0 = c == 0 ? 10u : (c == 1 ? 172u : 192u);
      b1 = c == 0 ? b1 : (c == 1 ? 16u + (b1 & 15u) : 168u);
    }
    // monta os até 16 bytes do texto: cada octeto vira "ddd." (4 bytes, zeros depois do ponto); escrever os 4 bytes
    // seguintes por cima dá o mesmo resultado que o OR em 128 bits do MVP, sem depender de __int128 (MSVC não tem)
    u32 l0 = IPL[b0], l1 = IPL[b1], l2 = IPL[b2], l3 = IPL[b3];
    u8 tb[20] = {0};
    memcpy(tb, &IPE[b0], 4); memcpy(tb + l0, &IPE[b1], 4); memcpy(tb + l0 + l1, &IPE[b2], 4); memcpy(tb + l0 + l1 + l2, &IPE[b3], 4);
    u64 lo, hi; memcpy(&lo, tb, 8); memcpy(&hi, tb + 8, 8);
    u32 n = l0 + l1 + l2 + l3 - 1;   // sem o ponto final
    u8* row = D + 16 * (size_t)r; memcpy(row, &lo, 8); memcpy(row + 8, &hi, 8);
    u32 w[3] = {(u32)lo, (u32)(lo >> 32), (u32)hi};
    u32 big = n > 12 ? 1u : 0u, bm = 0u - big;
    u32 m0 = 0xFFFFFFFFu, m1 = n >= 8 ? 0xFFFFFFFFu : (n <= 4 ? 0u : (u32)((1ull << (8 * (n - 4))) - 1ull)), m2 = n >= 12 ? 0xFFFFFFFFu : (n <= 8 ? 0u : (u32)((1ull << (8 * (n - 8))) - 1ull));
    u32* v = V + 4 * (size_t)r; v[0] = n; v[1] = w[0] & m0;
    v[2] = (w[1] & m1) & ~bm; v[3] = (((u32)(16 * r)) & bm) | ((w[2] & m2) & ~bm);
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
}
DG_EXPORT void dg_ipv4_views(u64* st, int priv, i64 m, u32* V, u8* D) { if (priv) ipv4_run<true>(st, m, V, D); else ipv4_run<false>(st, m, V, D); }

// url: https://[www.]palavra[-palavra].tld[/seg[/seg[/seg]]][?pagina=N]
//  palavras ASCII sorteadas uniformemente (wch/wln: 32 bytes por palavra), TLDs com peso (tch/tln/ttab, alias).
//  Números por linha: x (formato), y (2 palavras do domínio), z (TLD), e só se preciso u (2 trechos) e w (3º trecho e
//  página); cada palavra usa 32 bits (índice = (32 bits * k) >> 32). Probabilidades fixas razoáveis.
DG_EXPORT void dg_url_views(u64* st, u32 k, const u8* wch, const u8* wln, u32 kt, const u8* tch, const u8* tln,
                      const u64* ttab, i64 m, u32* V, u8* D) {
  init_cpf();
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  auto next = [&]() -> u64 { u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45); return x; };
  auto word = [&](u32 h) -> u32 { return (u32)(((u64)h * k) >> 32); };
  u32 off = 0;
  for (i64 r = 0; r < m; r++) {
    u64 x = next(), y = next(), z = next();
    u32 lo = (u32)x, hi = (u32)(x >> 32);
    bool www = (lo >> 24) < 154u;              // ~60% com www.
    bool two = ((lo >> 8) & 255u) < 31u;        // ~12% de domínio com dois termos ("minha-loja")
    u32 segs = (hi < 0x40000000u) ? 0 : (hi < 0xA0000000u) ? 1 : (hi < 0xE0000000u) ? 2 : 3;
    bool query = ((lo >> 16) & 255u) < 51u;    // ~20% com ?pagina=
    u8* start = D + off; u8* o = start;
    memcpy(o, "https://www.", 12); o += www ? 12 : 8;
    u32 w1 = word((u32)y); memcpy(o, wch + 32 * (size_t)w1, 24); o += wln[w1];
    u32 w2 = word((u32)(y >> 32)); *o = '-'; memcpy(o + 1, wch + 32 * (size_t)w2, 24); o += two ? 1 + wln[w2] : 0;
    *o++ = '.'; u32 t = alias_pick(kt, ttab, z); memcpy(o, tch + 32 * (size_t)t, 24); o += tln[t];
    if (segs | (u32)query) {
      u64 u = next(), w = next();
      u32 sw[3] = {word((u32)u), word((u32)(u >> 32)), word((u32)w)};
      for (u32 sg = 0; sg < segs; sg++) { *o++ = '/'; memcpy(o, wch + 32 * (size_t)sw[sg], 24); o += wln[sw[sg]]; }
      if (query) {
        if (segs == 0) *o++ = '/';
        memcpy(o, "?pagina=", 8); o += 8;
        u32 pg = 1 + (u32)(((w >> 32) * 99ull) >> 32);   // 1..99
        u32 dd = T4[pg] >> (pg < 10 ? 24 : 16); memcpy(o, &dd, 4); o += pg < 10 ? 1 : 2;
      }
    }
    u32 n = (u32)(o - start);
    u32* v = V + 4 * r; v[0] = n; memcpy(&v[1], start, 4); v[2] = 0; v[3] = off;   // sempre > 12 bytes
    off += n;
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
}
