// text.cpp -- texto por palavras e por gramática (modelos com slots)
// Parte do nini-datagen (kernels C++ com ABI em C; veja datagen.h).
#include "common.hpp"

// ===================================================================== texto livre e URL
// Palavras: wch[k*32] (ate 24 bytes UTF-8) + wln[k]; escolha por alias (wtab).
// text_views: cada linha tem S frases (smin..smax) de W palavras (wmin..wmax); a 1a letra de cada frase vai a maiuscula
// (se ASCII) e cada frase termina em '.'. Os textos ficam encadeados em D (V[r] aponta para o trecho); `max_row` e o
// limite de bytes por linha que o chamador garante que cabe (D tem m*max_row + 64 bytes).
DG_EXPORT void dg_text_views(u64* st, u32 k, const u8* wch, const u8* wln, const u64* wtab, u32 wmin, u32 wmax, u32 smin, u32 smax,
                       i64 m, u32* V, u8* D) {
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  auto next = [&]() -> u64 { u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45); return x; };
  u32 off = 0;
  for (i64 r = 0; r < m; r++) {
    u64 x = next();
    u32 S = smin + (u32)(((x >> 32) * (u64)(smax - smin + 1)) >> 32);
    u32 Wr = (u32)x;
    u8* start = D + off; u8* o = start;
    for (u32 s = 0; s < S; s++) {
      u32 W = wmin + (u32)(((u64)Wr * (u64)(wmax - wmin + 1)) >> 32); Wr = Wr * 2654435761u + 0x9E3779B9u;
      u8* sent = o;
      for (u32 w = 0; w < W; w++) {
        u64 y = next(); u32 i = (u32)(((y >> 32) * (u64)k) >> 32); u64 e = wtab[i];
        u32 al = (u32)(e >> 32), mk = 0u - (u32)((u32)y < (u32)e); u32 sel = al ^ ((i ^ al) & mk);
        memcpy(o, wch + 32 * (size_t)sel, 24); o += wln[sel]; *o++ = ' ';
      }
      if (*sent >= 'a' && *sent <= 'z') *sent = (u8)(*sent - 32);
      else if (sent[0] == 0xC3 && sent[1] >= 0xA0 && sent[1] <= 0xBE && sent[1] != 0xB7) sent[1] = (u8)(sent[1] - 0x20);   // á é ô ... -> Á É Ô
      o[-1] = '.'; *o++ = ' ';
    }
    o--;   // sem o espaco final
    u32 n = (u32)(o - start);
    u32* v = V + 4 * r; v[0] = n;
    if (n <= 12) { u8 t[12] = {0}; memcpy(t, start, n); memcpy(&v[1], t, 12); }
    else { memcpy(&v[1], start, 4); v[2] = 0; v[3] = off; }
    off += n;
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
}

// ===================================================================== texto por gramatica (modelos com slots)
// Gramatica sem ciclos: simbolos -> opcoes (ponderadas por alias) -> sequencias de tokens. Token = literal (indice no pool)
// ou referencia a outro simbolo (bit 31 ligado). O simbolo 0 e a frase. Cada linha tem S frases (smin..smax), separadas
// por espaco; a 1a letra de cada frase vai a maiuscula (ASCII ou vogal acentuada em UTF-8). Com row_root, o tema (opcao do
// simbolo 0) e fixo por linha.
//   sym_off[s]..sym_off[s+1]  opcoes do simbolo s (tab: alias thr|alias<<32 local ao simbolo)
//   opt_off[o]..opt_off[o+1]  tokens da opcao o
//   lit_off[l], lit_len[l]    literal l no pool (o pool tem 16 bytes de folga: as copias sao em blocos de 16)
// D precisa de m * max_row + 64 bytes, onde max_row (calculado no Python) e o maior texto possivel de uma linha.
static const u32 TPL_REF = 0x80000000u;
DG_EXPORT void dg_template_views(u64* st, const u32* sym_off, const u64* tab, const u32* opt_off, const u32* tok,
                           const u32* lit_off, const u16* lit_len, const u8* pool, u32 smin, u32 smax, int row_root,
                           i64 m, u32* V, u8* D) {
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  auto next = [&]() -> u64 { u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45); return x; };
  auto pick = [&](u32 s) -> u32 {   // opcao (indice global) do simbolo s
    u32 base = sym_off[s], k = sym_off[s + 1] - base;
    return base + alias_pick(k, tab + base, next());
  };
  u32 stk_o[64], stk_t[64];         // pilha: opcao em expansao e proximo token
  u32 off = 0;
  for (i64 r = 0; r < m; r++) {
    u32 S = smin + (u32)(((next() >> 32) * (u64)(smax - smin + 1)) >> 32);
    // row_root: a opcao do simbolo 0 e sorteada UMA vez por linha e deve ser uma referencia unica a outro simbolo (ex.: o
    // tema); as frases da linha saem todas desse simbolo (paragrafo coerente, sem misturar temas).
    u32 root = 0;
    if (row_root) { u32 o0 = pick(0); root = tok[opt_off[o0]] & ~TPL_REF; }
    u8* start = D + off; u8* o = start;
    for (u32 sn = 0; sn < S; sn++) {
      if (sn) *o++ = ' ';
      u8* sent = o;
      int sp = 0; u32 op = pick(root); stk_o[0] = op; stk_t[0] = opt_off[op];
      while (sp >= 0) {
        u32 oi = stk_o[sp];
        if (stk_t[sp] == opt_off[oi + 1]) { sp--; continue; }
        u32 t = tok[stk_t[sp]++];
        if (t & TPL_REF) { if (sp < 63) { u32 c = pick(t & ~TPL_REF); ++sp; stk_o[sp] = c; stk_t[sp] = opt_off[c]; } }
        else { const u8* src = pool + lit_off[t]; u32 L = lit_len[t]; for (u32 k = 0; k < L; k += 16) memcpy(o + k, src + k, 16); o += L; }
      }
      if (*sent >= 'a' && *sent <= 'z') *sent = (u8)(*sent - 32);
      else if (sent[0] == 0xC3 && sent[1] >= 0xA0 && sent[1] <= 0xBE && sent[1] != 0xB7) sent[1] = (u8)(sent[1] - 0x20);
    }
    u32 n = (u32)(o - start);
    u32* v = V + 4 * r; v[0] = n;
    if (n <= 12) { u8 t[12] = {0}; memcpy(t, start, n); memcpy(&v[1], t, 12); }
    else { memcpy(&v[1], start, 4); v[2] = 0; v[3] = off; }
    off += n;
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
}
