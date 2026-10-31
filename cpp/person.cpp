// person.cpp -- escolha em dicionário, nomes por sexo, telefone, email/username
// Parte do nini-datagen (kernels C++ com ABI em C; veja datagen.h).
#include "common.hpp"

// ---------------------------------------------------------------------------------------------------------
// Escolha uniforme em dicionário: V[r] = dv[idx_r] (copia a view de 16 bytes pronta do dicionário).
// `dv`: k x 4 uint32 (views Arrow do dicionário; textos > 12 bytes apontam para o buffer de dados do dicionário,
// que o Python repassa ao array de saída). idx = (x32 * k) >> 32, 2 índices por uint64 do xoshiro256++.
// O viés desse mapeamento é < k / 2^32 (para k = 1e5, ~2e-5), irrelevante para dados sintéticos.
// ---------------------------------------------------------------------------------------------------------
DG_EXPORT void dg_choice_views(const u32* dv, u32 k, u64* s, i64 m, u32* V) {
  u64 s0 = s[0], s1 = s[1], s2 = s[2], s3 = s[3];
  auto next = [&]() -> u64 {
    u64 r = rotl(s0 + s3, 23) + s0, t = s1 << 17;
    s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45);
    return r;
  };
  i64 r = 0;
  for (; r + 1 < m; r += 2) {
    u64 x = next();
    u32 i0 = (u32)(((x & 0xFFFFFFFFULL) * (u64)k) >> 32), i1 = (u32)(((x >> 32) * (u64)k) >> 32);
    memcpy(V + 4 * r, dv + 4 * (size_t)i0, 16);
    memcpy(V + 4 * (r + 1), dv + 4 * (size_t)i1, 16);
  }
  if (r < m) {
    u64 x = next();
    memcpy(V + 4 * r, dv + 4 * (size_t)(u32)(((x & 0xFFFFFFFFULL) * (u64)k) >> 32), 16);
  }
  s[0] = s0; s[1] = s1; s[2] = s2; s[3] = s3;
}

// ---------------------------------------------------------------------------------------------------------
// Escolha ponderada pelo método alias (Walker/Vose): O(1) por linha, uma chamada do RNG (64 bits) por linha.
//   i = (x_alto32 * k) >> 32;  sel = (x_baixo32 < thr[i]) ? i : alias[i];  V[r] = dv[sel]   (sem desvio, veja abaixo)
// `thr[i]` = probabilidade de ficar com a coluna i, em escala 2^32 (entradas com probabilidade 1 têm alias[i] = i,
// então não há viés). O erro de quantização é <= 2^-33 por entrada.
// ---------------------------------------------------------------------------------------------------------
DG_EXPORT void dg_choice_alias_views(const u32* dv, u32 k, const u64* tab, u64* s, i64 m, u32* V) {
  // tab[i] = thr[i] | (alias[i] << 32): uma única leitura por linha; escolha sem desvio (o `?:` com dados
  // aleatórios geraria ~50% de previsões erradas do desvio).
  u64 s0 = s[0], s1 = s[1], s2 = s[2], s3 = s[3];
  for (i64 r = 0; r < m; r++) {
    u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17;
    s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45);
    u32 i = (u32)(((x >> 32) * (u64)k) >> 32);
    u64 e = tab[i];
    u32 al = (u32)(e >> 32), mask = 0u - (u32)((u32)x < (u32)e);
    u32 sel = al ^ ((i ^ al) & mask);
    memcpy(V + 4 * r, dv + 4 * (size_t)sel, 16);
  }
  s[0] = s0; s[1] = s1; s[2] = s2; s[3] = s3;
}

// Escolha ponderada em DOIS dicionarios de uma vez, conforme a mascara isf[r] (1 = primeiro, 0 = segundo): dv = views do
// primeiro dicionario (kf) seguidas das do segundo (km); tab = tabelas alias na mesma ordem. Uma passada so, sem separar
// as linhas por grupo nem reordenar depois (usado em first_name(sex=...)).
DG_EXPORT void dg_choice_alias_views_by(const u32* dv, u32 kf, u32 km, const u64* tab, const u8* isf, u64* s, i64 m, u32* V) {
  u64 s0 = s[0], s1 = s[1], s2 = s[2], s3 = s[3];
  for (i64 r = 0; r < m; r++) {
    u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17;
    s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45);
    // sem desvio: com sexos misturados, o `?:` erraria a previsão em metade das linhas (custava ~5 ns/linha)
    u32 msk = 0u - (u32)(isf[r] != 0), k = km ^ ((kf ^ km) & msk), base = kf & ~msk;
    u32 i = (u32)(((x >> 32) * (u64)k) >> 32);
    u64 e = tab[(size_t)base + i];
    u32 al = (u32)(e >> 32), mask = 0u - (u32)((u32)x < (u32)e);
    u32 sel = al ^ ((i ^ al) & mask);
    memcpy(V + 4 * r, dv + 4 * ((size_t)base + sel), 16);
  }
  s[0] = s0; s[1] = s1; s[2] = s2; s[3] = s3;
}

// ===================================================================== telefone e CEP
// Telefone brasileiro: celular (DD) 9XXXX-XXXX (11 digitos) ou fixo (DD) NXXX-XXXX, N em 2..5 (10 digitos).
//   style 0: so digitos ("11987654321", ate 11 caracteres: view inline, sem buffer de dados)
//   style 1: mascara "(11) 98765-4321" / "(11) 2345-6789"   (stride 16 em D)
//   style 2: E.164 "+5511987654321"                          (stride 16 em D)
// ddd_tab: alias (thr | alias<<32) sobre k DDDs; ddd_chars[k]: 2 caracteres ASCII de cada DDD (u16).
// mobile_thr: P(celular) em escala 2^32 (0..2^32).
// Truque sem desvios: o fixo "NXXX-XXXX" e o numero de 8 digitos Q em [2e7, 6e7) (o primeiro digito sai 2..5 sozinho),
// e o celular e '9' + 8 digitos. Os dois usam as mesmas tabelas de 4 digitos; so muda um prefixo de 0 ou 1 caractere (pl).
DG_EXPORT void dg_phone_views(u64* st, u32 k, const u64* ddd_tab, const u16* ddd_chars, u64 mobile_thr, int style, i64 m, u32* V, u8* D, const u32* ddd_row) {
  init_cpf();
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  auto next = [&]() -> u64 { u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45); return x; };
  for (i64 r = 0; r < m; r++) {
    u64 x1 = next(), x2 = next();
    u32 i = (u32)(((x2 >> 32) * (u64)k) >> 32); u64 e = ddd_tab[i];
    u32 al = (u32)(e >> 32), mk = 0u - (u32)((u32)x2 < (u32)e); u32 sel = al ^ ((i ^ al) & mk);
    u16 dd = ddd_chars[ddd_row ? ddd_row[r] : sel];   // ddd_row: DDD já escolhido por linha (ex.: coerente com a UF)
    u32 pl = (u32)((u64)(u32)(x1 >> 32) < mobile_thr);                      // 1 = celular
    u32 lo = (u32)x1;
    u32 qm = (u32)(((u64)lo * 100000000ull) >> 32);                          // celular: 8 digitos quaisquer
    u32 ql = 20000000u + (u32)(((u64)lo * 40000000ull) >> 32);               // fixo: 8 digitos comecando em 2..5
    u32 Q = pl ? qm : ql;                                                    // (cmov)
    u32 hi4 = Q / 10000u, lo4 = Q - hi4 * 10000u;
    u32 A = T4[hi4], B = T4[lo4];
    u8 o[32]; memset(o, 0, sizeof o);
    int n;
    if (style == 0) {
      o[0] = (u8)dd; o[1] = (u8)(dd >> 8); o[2] = '9';
      memcpy(o + 2 + pl, &A, 4); memcpy(o + 6 + pl, &B, 4); n = 10 + pl;
    } else if (style == 1) {
      o[0] = '('; o[1] = (u8)dd; o[2] = (u8)(dd >> 8); o[3] = ')'; o[4] = ' '; o[5] = '9';
      memcpy(o + 5 + pl, &A, 4); o[9 + pl] = '-'; memcpy(o + 10 + pl, &B, 4); n = 14 + pl;
    } else {
      o[0] = '+'; o[1] = '5'; o[2] = '5'; o[3] = (u8)dd; o[4] = (u8)(dd >> 8); o[5] = '9';
      memcpy(o + 5 + pl, &A, 4); memcpy(o + 9 + pl, &B, 4); n = 13 + pl;
    }
    u32* v = V + 4 * r;
    if (style == 0) { v[0] = (u32)n; memcpy(&v[1], o, 12); }
    else { memcpy(D + (size_t)r * 16, o, 16); v[0] = (u32)n; memcpy(&v[1], o, 4); v[2] = 0; v[3] = (u32)r * 16u; }
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
}


// ===================================================================== username e email
// Compoe o username a partir de um primeiro nome e um sobrenome ja normalizados (ASCII minusculo, ate 24 caracteres)
// e, opcionalmente, "@dominio". Sem desvios: cada estilo e uma linha de 4 bytes {troca, so_inicial, separador, digitos}.
//   troca: sobrenome antes do nome; so_inicial: nome vira so a 1a letra; separador: '.', '_' ou 0; digitos: 0, 2 ou 4 (ano).
// Os textos ficam encadeados num unico buffer D; o email e o username de uma linha compartilham o mesmo trecho
// (V = email; V2 = username, opcional), sem copiar nada. Strings com ate 12 bytes vao inline.
// Tabelas de nomes: chars[k*32] (24 caracteres uteis) + lens[k]. idxF/idxL (opcionais) devolvem os indices sorteados.
DG_EXPORT void dg_email_views(u64* st, u32 kf, const u8* fch, const u8* fln, u32 kl, const u8* lch, const u8* lln,
                        const u32* sty_thr, const u8* sty_tab, int with_domain, u32 kd, const u64* dtab, const u8* dch,
                        const u8* dln, i64 m, u32* V, u32* V2, u8* D, u32* idxF, u32* idxL) {
  init_cpf();
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  auto next = [&]() -> u64 { u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45); return x; };
  auto put = [&](u32* v, const u8* p, u32 n, u32 off) {
    u64 w0, w1; memcpy(&w0, p, 8); memcpy(&w1, p + 8, 8);
    u64 m0 = n >= 8 ? ~0ull : ((1ull << (8 * n)) - 1);
    u64 m1 = n <= 8 ? 0ull : ((1ull << (8 * (n - 8 > 7 ? 7 : n - 8))) - 1);
    bool inl = n <= 12;
    v[0] = n;
    v[1] = inl ? (u32)(w0 & m0) : (u32)w0;
    v[2] = inl ? (u32)((w0 & m0) >> 32) : 0u;
    v[3] = inl ? (u32)(w1 & m1) : off;
  };
  u32 off = 0;
  for (i64 r = 0; r < m; r++) {
    u64 x1 = next(), x2 = next();
    u32 fi = (u32)(((x1 >> 32) * (u64)kf) >> 32), li = (u32)(((x1 & 0xFFFFFFFFull) * (u64)kl) >> 32);
    u32 lo = (u32)x2, hi = (u32)(x2 >> 32);
    u32 sidx = 0; for (int j = 0; j < 7; j++) sidx += (lo >= sty_thr[j]);
    const u8* S = sty_tab + 4 * sidx;
    u32 swap = S[0], init = S[1], sep = S[2], dig = S[3];
    u32 la = fln[fi], lb = lln[li]; if (init && la > 1) la = 1;
    const u8* pa = fch + 32 * (size_t)fi; const u8* pb = lch + 32 * (size_t)li;
    const u8* p1 = swap ? pb : pa; const u8* p2 = swap ? pa : pb; u32 l1 = swap ? lb : la, l2 = swap ? la : lb;
    u8* start = D + off; u8* o = start;
    memcpy(o, p1, 24); o += l1;
    *o = (u8)sep; o += (sep != 0);
    memcpy(o, p2, 24); o += l2;
    u32 year = 1950u + (u32)(((u64)hi * 60ull) >> 32), n2 = (u32)(((u64)hi * 100ull) >> 32);
    u32 dv = dig == 4 ? T4[year] : (T4[n2] >> 16);
    memcpy(o, &dv, 4); o += dig;
    u32 n1 = (u32)(o - start);
    if (V2) put(V2 + 4 * r, start, n1, off);
    if (with_domain) {
      u64 x3 = next(); u32 i = (u32)(((x3 >> 32) * (u64)kd) >> 32); u64 e = dtab[i];
      u32 al = (u32)(e >> 32), mk = 0u - (u32)((u32)x3 < (u32)e); u32 sel = al ^ ((i ^ al) & mk);
      *o++ = '@'; memcpy(o, dch + 32 * (size_t)sel, 24); o += dln[sel];
    }
    u32 n = (u32)(o - start);
    put(V + 4 * r, start, n, off);
    off += n;
    if (idxF) idxF[r] = fi;
    if (idxL) idxL[r] = li;
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
}
// V[r] = dv[idx[r]] (copia as views do dicionario pelos indices dados)
DG_EXPORT void dg_gather_views(const u32* dv, const u32* idx, i64 m, u32* V) {
  for (i64 r = 0; r < m; r++) memcpy(V + 4 * r, dv + 4 * (size_t)idx[r], 16);
}

// Como dg_choice_alias_views_by, mas devolve o índice escolhido (no vocabulário concatenado: o primeiro grupo em
// [0, kf), o segundo em [kf, kf + km)) em vez de copiar a view. Consome o gerador exatamente igual.
DG_EXPORT void dg_alias_idx_by(u32 kf, u32 km, const u64* tab, const u8* isf, u64* s, i64 m, u32* out) {
  u64 s0 = s[0], s1 = s[1], s2 = s[2], s3 = s[3];
  for (i64 r = 0; r < m; r++) {
    u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17;
    s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45);
    // sem desvio: com sexos misturados, o `?:` erraria a previsão em metade das linhas (custava ~5 ns/linha)
    u32 msk = 0u - (u32)(isf[r] != 0), k = km ^ ((kf ^ km) & msk), base = kf & ~msk;
    u32 i = (u32)(((x >> 32) * (u64)k) >> 32);
    u64 e = tab[(size_t)base + i];
    u32 al = (u32)(e >> 32), mask = 0u - (u32)((u32)x < (u32)e);
    out[r] = base + (al ^ ((i ^ al) & mask));
  }
  s[0] = s0; s[1] = s1; s[2] = s2; s[3] = s3;
}

// ===================================================================== junção de textos
// Junta k partes de texto linha a linha, com `sep` entre elas; parte vazia (len 0) é pulada, sem separador. Usado pelo
// nome completo (e, depois, pelo endereço). Cada parte p é um vocabulário (views dv[p], texto datas[p]) e um índice
// por linha (idx[p]): a linha r usa a palavra dv[p][idx[p][r]].
//
// Cópia em pedaços fixos de 16 bytes (sem chamar memcpy de tamanho variável, que custava mais que o resto): por isso
// o chamador garante 16 bytes de folga depois do texto de cada vocabulário, uma view a mais no fim de cada um (a
// leitura de um texto curto, que mora dentro da view, passa para a seguinte) e 16 bytes de folga no buffer de saída.
static inline const u8* view_bytes(const u32* v, const u8* data) {
  return v[0] <= 12 ? (const u8*)(v + 1) : data + v[3];
}
static inline void copy16(u8* dst, const u8* src, u32 len) {
  for (u32 i = 0; i < len; i += 16) memcpy(dst + i, src + i, 16);
}

// Bytes que dg_join_views vai escrever no buffer de texto (só as linhas com mais de 12 bytes vão para lá).
DG_EXPORT i64 dg_join_size(i64 m, int k, const u32* const* dv, const u32* const* idx, u32 seplen) {
  i64 total = 0;
  for (i64 r = 0; r < m; r++) {
    u32 len = 0, parts = 0;
    for (int p = 0; p < k; p++) {
      u32 l = dv[p][4 * (size_t)idx[p][r]];
      len += l; parts += l != 0;
    }
    if (parts > 1) len += seplen * (parts - 1);
    if (len > 12) total += len;
  }
  return total;
}

// Escreve as views (V, m x 4) e o texto das linhas longas em D (tamanho de dg_join_size + 16 de folga), com índice de
// buffer `buf` (cada bloco de linhas tem o seu buffer).
DG_EXPORT void dg_join_views(i64 m, int k, const u32* const* dv, const u8* const* datas, const u32* const* idx,
                             const u8* sep, u32 seplen, u32 buf, u32* V, u8* D) {
  u64 off = 0;
  u8 small[48];
  for (i64 r = 0; r < m; r++) {
    u32 len = 0, parts = 0;
    for (int p = 0; p < k; p++) {
      u32 l = dv[p][4 * (size_t)idx[p][r]];
      len += l; parts += l != 0;
    }
    if (parts > 1) len += seplen * (parts - 1);
    u8* dst = len <= 12 ? small : D + off;
    u32 w = 0;
    bool first = true;
    for (int p = 0; p < k; p++) {
      const u32* pv = dv[p] + 4 * (size_t)idx[p][r];
      u32 l = pv[0];
      if (!l) continue;
      if (!first) { copy16(dst + w, sep, seplen); w += seplen; }  // sep também com 16 bytes de folga
      copy16(dst + w, view_bytes(pv, datas[p]), l);
      w += l;
      first = false;
    }
    u32* v = V + 4 * r;
    v[0] = len;
    if (len <= 12) {
      memset(small + len, 0, 12 - len);  // o Arrow pede zeros depois do texto curto
      memcpy(v + 1, small, 12);
    } else {
      memcpy(v + 1, dst, 4);
      v[2] = buf;
      v[3] = (u32)off;
      off += len;
    }
  }
}

// ===================================================================== coluna de sexo -> máscara
// Lê a coluna de sexo direto das views do Arrow (sem passar pelo Python): out[r] = 1 se o texto começa com F/f, 0 se
// começa com M/m, 2 se é nulo, vazio ou começa com outra coisa. O primeiro byte está sempre no byte 4 da view (texto
// curto inline ou prefixo do texto longo). `valid`: bits de validade do Arrow (nullptr = sem nulos), a partir do bit
// `bit_offset`. Devolve quantas linhas ficaram com 2 (desconhecidas).
DG_EXPORT i64 dg_sex_mask(const u32* V, const u8* valid, i64 bit_offset, i64 m, u8* out) {
  i64 unknown = 0;
  for (i64 r = 0; r < m; r++) {
    const u32* v = V + 4 * r;
    u8 c = (u8)(v[1] & 0xFF) | 0x20;  // minúscula (só importa para F/M)
    bool ok = v[0] != 0;
    if (valid) {
      i64 b = bit_offset + r;
      ok = ok && ((valid[b >> 3] >> (b & 7)) & 1);
    }
    u8 res = !ok ? 2 : c == 'f' ? 1 : c == 'm' ? 0 : 2;
    out[r] = res;
    unknown += res == 2;
  }
  return unknown;
}
