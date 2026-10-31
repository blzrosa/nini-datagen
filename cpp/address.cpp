// address.cpp -- CEP (por faixas e por UF), razão social, veículo
// Parte do nini-datagen (kernels C++ com ABI em C; veja datagen.h).
#include "common.hpp"

// CEP: prefixo de 5 digitos sorteado entre `k` prefixos validos (ex.: faixas de uma UF) + sufixo 000..999.
//   style 0: "01310100" (8 chars, inline)   style 1: "01310-100" (9 chars, inline)
DG_EXPORT void dg_cep_views(u64* st, u32 k, const u32* prefixes, int style, i64 m, u32* V) {
  init_cpf();
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  for (i64 r = 0; r < m; r++) {
    u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45);
    u32 p = prefixes[(u32)(((x >> 32) * (u64)k) >> 32)];          // 5 digitos
    u32 suf = (u32)(((x & 0xFFFFFFFFull) * 1000ull) >> 32);        // 3 digitos
    u32 hi = T4[p / 10], lo = T4[(p % 10) * 1000 + suf];            // "0131" | "0100" (p%10 + suf -> 4 digitos)
    u32* v = V + 4 * r; v[1] = v[2] = v[3] = 0;
    if (style == 0) { v[0] = 8; v[1] = hi; v[2] = lo; }
    else { v[0] = 9; v[1] = hi; v[2] = (lo & 0xFF) | ((u32)'-' << 8) | (((lo >> 8) & 0xFF) << 16) | (((lo >> 16) & 0xFF) << 24); v[3] = (lo >> 24) & 0xFF; }
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
}

// CEP coerente com a UF de cada linha: uf_idx[r] indexa as tabelas off/cnt dos prefixos validos daquela UF.
DG_EXPORT void dg_cep_views_uf(u64* st, const u32* uf_idx, const u32* off, const u32* cnt, const u32* prefixes, int style, i64 m, u32* V) {
  init_cpf();
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  for (i64 r = 0; r < m; r++) {
    u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45);
    u32 u = uf_idx[r];
    u32 p = prefixes[off[u] + (u32)(((x >> 32) * (u64)cnt[u]) >> 32)];
    u32 suf = (u32)(((x & 0xFFFFFFFFull) * 1000ull) >> 32);
    u32 hi = T4[p / 10], lo = T4[(p % 10) * 1000 + suf];
    u32* v = V + 4 * r; v[1] = v[2] = v[3] = 0;
    if (style == 0) { v[0] = 8; v[1] = hi; v[2] = lo; }
    else { v[0] = 9; v[1] = hi; v[2] = (lo & 0xFF) | ((u32)'-' << 8) | (((lo >> 8) & 0xFF) << 16) | (((lo >> 16) & 0xFF) << 24); v[3] = (lo >> 24) & 0xFF; }
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
}

// ===================================================================== empresa e veiculo
// empresa_views: razao social. padrao 0 (60%): "Sobrenome Ramo Tipo"; 1 (20%): "Sobrenome & Sobrenome Ramo Tipo";
// 2 (20%): "Marca Marca Ramo Tipo". Listas de ate 31 bytes UTF-8 (entradas de 32 bytes). D tem m*128 + 64 bytes.
DG_EXPORT void dg_empresa_views(u64* st, u32 ks, const u8* sch, const u8* sln, const u64* stab, u32 kb, const u8* bch, const u8* bln,
                          const u64* btab, u32 kr, const u8* rch, const u8* rln, const u64* rtab, u32 kt, const u8* tch,
                          const u8* tln, const u64* ttab, i64 m, u32* V, u8* D) {
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  auto next = [&]() -> u64 { u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45); return x; };
  u32 off = 0;
  for (i64 r = 0; r < m; r++) {
    u64 x = next();
    u32 q = (u32)(((x >> 32) & 0xFFFFu) * 100u >> 16);   // 0..99
    u32 pat = q < 60 ? 0u : (q < 80 ? 1u : 2u);
    u8* start = D + off; u8* o = start;
    auto put = [&](const u8* ch, const u8* ln, u32 i) { memcpy(o, ch + 32 * (size_t)i, 32); o += ln[i]; };
    if (pat == 2) { u32 a = alias_pick(kb, btab, next()); put(bch, bln, a); *o++ = ' '; u32 b = alias_pick(kb, btab, next()); put(bch, bln, b); }
    else { u32 a = alias_pick(ks, stab, next()); put(sch, sln, a);
           if (pat == 1) { *o++ = ' '; *o++ = '&'; *o++ = ' '; u32 b = alias_pick(ks, stab, next()); put(sch, sln, b); } }
    *o++ = ' '; put(rch, rln, alias_pick(kr, rtab, next()));
    *o++ = ' '; put(tch, tln, alias_pick(kt, ttab, next()));
    u32 n = (u32)(o - start);
    u32* v = V + 4 * r; v[0] = n;
    if (n <= 12) { u8 t[12] = {0}; memcpy(t, start, n); memcpy(&v[1], t, 12); }
    else { memcpy(&v[1], start, 4); v[2] = 0; v[3] = off; }
    off += n;
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
}
// veiculo_idx: marca (alias), modelo da marca (alias por marca, indice GLOBAL = moff[b] + local) e ano (alias; indice).
// mtabs concatena as tabelas alias dos modelos de cada marca (mesmos offsets de moff).
DG_EXPORT void dg_veiculo_idx(u64* st, u32 nb, const u64* btab, const u32* moff, const u32* mcnt, const u64* mtabs, u32 ky, const u64* ytab,
                        i64 m, u32* bo, u32* mo, u32* yo) {
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  auto next = [&]() -> u64 { u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45); return x; };
  for (i64 r = 0; r < m; r++) {
    u32 b = alias_pick(nb, btab, next());
    u32 loc = alias_pick(mcnt[b], mtabs + moff[b], next());
    bo[r] = b; mo[r] = moff[b] + loc; yo[r] = alias_pick(ky, ytab, next());
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
}
