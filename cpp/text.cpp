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
// Gramatica sem ciclos: simbolos -> opcoes (ponderadas por alias) -> sequencias de tokens. Token = literal (indice no
// pool), referencia a outro simbolo (bit 31) ou referencia a um simbolo FOLHA (bit 30): simbolo em que toda opcao e um
// literal so ({d}, {pessoa}, {canal}...). A folha nao passa pela pilha: sorteia a opcao e copia o literal na hora (o
// grosso das referencias de uma frase, ex. os 10 digitos de um protocolo). O simbolo 0 e a frase. Cada linha tem S frases
// (smin..smax), separadas por espaco; a 1a letra de cada frase vai a maiuscula (ASCII ou vogal acentuada em UTF-8). Com
// row_root, o tema (opcao do simbolo 0) e fixo por linha.
//   sym_off[s]..sym_off[s+1]  opcoes do simbolo s (tab: alias thr|alias<<32 local ao simbolo)
//   opt_off[o]..opt_off[o+1]  tokens da opcao o, terminando no token de fim (numa folha: 1 literal + fim)
//   lit[l]                    literal l no pool: deslocamento | comprimento << 32 (uma leitura so)
//   leaf_lit[o]               numa folha, o literal da opcao o ja resolvido (mesmo formato): a folha vira
//                             simbolo -> alias -> leaf_lit -> pool, sem passar por opt_off e tok (cadeia de leituras
//                             dependentes mais curta). O pool tem 32 bytes de folga: as copias sao em blocos de 32/16.
// Capacidade: D tem cap bytes + 64 de folga; antes de cada linha, se off + max_row > cap, para e devolve quantas linhas
// escreveu (o Python abre outro buffer e chama de novo com o mesmo estado, que e atualizado no lugar: o resultado nao
// depende de onde o buffer foi cortado). max_row = maior texto possivel de uma linha (calculado no Python).
static const u32 TPL_SYM = 0x3FFFFFFFu;   // simbolo do token; tipo = t >> 30: 0 literal, 1 folha, 2 ref, 3 fim
DG_EXPORT i64 dg_template_views(u64* st, const u32* sym_off, const u64* tab, const u32* opt_off, const u32* tok,
                           const u64* lit, const u64* leaf_lit, const u8* pool, u32 smin, u32 smax, int row_root,
                           i64 max_row, i64 cap, i64 m, u32* V, u8* D) {
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  auto next = [&]() -> u64 { u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45); return x; };
  auto pick = [&](u32 s) -> u32 {   // opcao (indice global) do simbolo s
    u32 base = sym_off[s], k = sym_off[s + 1] - base;
    return base + alias_pick(k, tab + base, next());
  };
  const u32* stk[64];               // pilha: proximo token de cada opcao em expansao
  // gera uma frase de `root` a partir de o; devolve o fim. O tipo do token (2 bits altos) e decodificado de uma vez
  // (literal, folha, referencia ou fim da opcao): um desvio de 4 vias em vez de tres decisoes encadeadas, que eram a
  // maior fonte de desvios mal previstos.
  auto sentence = [&](u32 root, u8* o) -> u8* {
    u8* sent = o;
    const u32* p = tok + opt_off[pick(root)];
    int sp = 0;
    for (;;) {
      u32 t = *p++;
      u32 kind = t >> 30;
      if (kind == 3) { if (sp == 0) break; p = stk[--sp]; continue; }
      if (kind == 2) { if (sp < 64) { stk[sp++] = p; p = tok + opt_off[pick(t & TPL_SYM)]; } continue; }
      u64 e = kind ? leaf_lit[pick(t & TPL_SYM)] : lit[t];
      const u8* src = pool + (u32)e; u32 L = (u32)(e >> 32);
      memcpy(o, src, 32);                                   // quase todo literal tem <= 32 bytes: sem laco
      for (u32 k = 32; k < L; k += 16) memcpy(o + k, src + k, 16);   // (desvio raro, bem previsto)
      o += L;
    }
    // maiuscula na 1a letra, sem desvio: ASCII a-z, ou vogal acentuada em UTF-8 (0xC3 0xA0..0xBE, menos 0xB7)
    u32 c0 = sent[0], c1 = sent[1];
    u32 ascii = (c0 - 'a') < 26u, utf = (c0 == 0xC3) & ((c1 - 0xA0u) <= 0x1Eu) & (c1 != 0xB7);
    sent[0] = (u8)(c0 - 32u * ascii); sent[1] = (u8)(c1 - 0x20u * utf);
    return o;
  };
  u64 off = 0;
  i64 r = 0;
  for (; r < m; r++) {
    if ((i64)off + max_row > cap) break;
    u32 S = smin + (u32)(((next() >> 32) * (u64)(smax - smin + 1)) >> 32);
    // row_root: a opcao do simbolo 0 e sorteada UMA vez por linha e deve ser uma referencia unica a outro simbolo (ex.: o
    // tema); as frases da linha saem todas desse simbolo (paragrafo coerente, sem misturar temas).
    u32 root = 0;
    if (row_root) { u32 o0 = pick(0); root = tok[opt_off[o0]] & TPL_SYM; }
    u8* start = D + off; u8* o = start;
    u8* prev = nullptr; u32 prev_len = 0;
    for (u32 sn = 0; sn < S; sn++) {
      if (sn) *o++ = ' ';
      u8* sent = o;
      o = sentence(root, sent);
      // frase igual a anterior do mesmo paragrafo: sorteia de novo (ate 16 vezes: gramatica com uma frase so nao trava)
      for (int tries = 0; tries < 16 && prev && (u32)(o - sent) == prev_len && memcmp(sent, prev, prev_len) == 0; tries++)
        o = sentence(root, sent);
      prev = sent; prev_len = (u32)(o - sent);
    }
    u32 n = (u32)(o - start);
    u32* v = V + 4 * r; v[0] = n;
    if (n <= 12) { u8 t[12] = {0}; memcpy(t, start, n); memcpy(&v[1], t, 12); }
    else { memcpy(&v[1], start, 4); v[2] = 0; v[3] = (u32)off; }
    off += n;
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
  return r;
}
