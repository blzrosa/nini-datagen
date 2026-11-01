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

// ===================================================================== enderecos do CNEFE (fase 5)
// Cada linha sorteia um trecho (CEP x logradouro) com peso = numero de enderecos; as colunas de texto copiam a view
// (16 bytes) do nome no vocabulario e o CEP sai do UInt32 ja formatado na view (8 ou 9 caracteres, inline).
#include "detmath.hpp"

static inline void cep_view(u32 c, int formatted, u32* v) {
  u32 p = c / 1000u, suf = c - p * 1000u;                 // 5 primeiros digitos e os 3 ultimos
  u32 hi = T4[p / 10u], lo = T4[(p % 10u) * 1000u + suf];  // "0131" e "0100"
  if (!formatted) { v[0] = 8; v[1] = hi; v[2] = lo; v[3] = 0; }
  else {                                                  // "01310-100": insere o hifen depois do 5o digito
    v[0] = 9; v[1] = hi;
    v[2] = (lo & 0xFFu) | ((u32)'-' << 8) | (((lo >> 8) & 0xFFu) << 16) | (((lo >> 16) & 0xFFu) << 24);
    v[3] = (lo >> 24) & 0xFFu;
  }
}

// Sorteio de trechos com prefetch. Na base completa (4 milhoes de trechos) a tabela alias (32 MB) e os dados dos
// trechos nao cabem no cache: cada linha esperaria a memoria duas vezes, uma depois da outra. Em lotes de PICK_BATCH
// linhas: 1) sorteia e pede ao processador a entrada da tabela alias de todas (prefetch); 2) resolve o alias e pede o
// trecho; 3) usa o trecho. As esperas de linhas diferentes se sobrepoem. Mesmo consumo do gerador que dg_alias_idx
// (um numero por linha, na mesma ordem): o resultado e identico ao do sorteio linha a linha.
#define PICK_BATCH 64
#if defined(__GNUC__) || defined(__clang__)
#define DG_PREFETCH(p) __builtin_prefetch((const void*)(p))
#elif defined(_MSC_VER)
#include <intrin.h>
#if defined(_M_X64) || defined(_M_IX86)
#define DG_PREFETCH(p) _mm_prefetch((const char*)(p), _MM_HINT_T0)
#else
#define DG_PREFETCH(p) __prefetch((const void*)(p))
#endif
#else
#define DG_PREFETCH(p) ((void)0)
#endif

// CEP direto: sorteia o trecho (alias sobre os pesos) e formata o CEP dele
DG_EXPORT void dg_cep_pick(u64* st, u32 k, const u64* tab, const u32* ceps, int formatted, i64 m, u32* V) {
  init_cpf();
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  u64 xs[PICK_BATCH]; u32 js[PICK_BATCH];
  for (i64 r0 = 0; r0 < m; r0 += PICK_BATCH) {
    int b = (int)(m - r0 < PICK_BATCH ? m - r0 : PICK_BATCH);
    for (int q = 0; q < b; q++) {
      u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45);
      xs[q] = x; DG_PREFETCH(tab + (u32)(((x >> 32) * (u64)k) >> 32));
    }
    for (int q = 0; q < b; q++) { js[q] = alias_pick(k, tab, xs[q]); DG_PREFETCH(ceps + js[q]); }
    for (int q = 0; q < b; q++) cep_view(ceps[js[q]], formatted, V + 4 * (r0 + q));
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
}

// Endereco, numa passada por lote de PICK_BATCH linhas: sorteia o trecho (prefetch da tabela alias), le o registro
// dele (prefetch; REC_U32 inteiros: cep, rua, bairro, cidade, UF, numero minimo, numero maximo, livre), pede os nomes
// da rua e do bairro (prefetch nos vocabularios, que na base completa tambem nao cabem no cache) e escreve as views de
// rua, bairro, cidade, UF e CEP. Para os passos seguintes (numero, DDD) sai `small`, ROW_U32 inteiros por linha:
// numero minimo, numero maximo e UF. Mesmo consumo do gerador que dg_alias_idx: resultado identico.
#define REC_U32 8
#define ROW_U32 4
DG_EXPORT void dg_address_core(u64* st, u32 k, const u64* tab, const u32* rec, const u32* dv_street,
                               const u32* dv_district, const u32* dv_city, const u32* dv_state, i64 m, u32* idx,
                               u32* small, u32* Vs, u32* Vd, u32* Vc, u32* Vu, u32* Vcep) {
  init_cpf();
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  u64 xs[PICK_BATCH];
  for (i64 r0 = 0; r0 < m; r0 += PICK_BATCH) {
    int b = (int)(m - r0 < PICK_BATCH ? m - r0 : PICK_BATCH);
    for (int q = 0; q < b; q++) {
      u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45);
      xs[q] = x; DG_PREFETCH(tab + (u32)(((x >> 32) * (u64)k) >> 32));
    }
    for (int q = 0; q < b; q++) {
      u32 j = alias_pick(k, tab, xs[q]); idx[r0 + q] = j; DG_PREFETCH(rec + (size_t)REC_U32 * j);
    }
    for (int q = 0; q < b; q++) {
      const u32* e = rec + (size_t)REC_U32 * idx[r0 + q];
      DG_PREFETCH(dv_street + 4 * (size_t)e[1]); DG_PREFETCH(dv_district + 4 * (size_t)e[2]);
    }
    for (int q = 0; q < b; q++) {
      i64 r = r0 + q;
      const u32* e = rec + (size_t)REC_U32 * idx[r];
      memcpy(Vs + 4 * r, dv_street + 4 * (size_t)e[1], 16);
      memcpy(Vd + 4 * r, dv_district + 4 * (size_t)e[2], 16);
      memcpy(Vc + 4 * r, dv_city + 4 * (size_t)e[3], 16);
      memcpy(Vu + 4 * r, dv_state + 4 * (size_t)e[4], 16);
      cep_view(e[0], 1, Vcep + 4 * r);
      u32* w = small + (size_t)ROW_U32 * r; w[0] = e[5]; w[1] = e[6]; w[2] = e[4]; w[3] = 0;
    }
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
}

// Numero da casa. Com a faixa real do trecho (lo..hi, lo > 0): log-uniforme entre lo e hi, para numeros baixos sairem
// mais (um unico endereco rural "27201" nao puxa a rua inteira para 5 digitos). Sem faixa (lo nulo, ou lo[i] <= 0):
// lognormal(4,2; 1,1) cortada em 1..9999. Um numero do gerador por linha; log/exp deterministicos (detmath.hpp).
// det_log dos inteiros 1..HOUSE_LOGS-1 (faixas de número dos trechos), calculado uma vez: os dois det_log por linha
// custavam mais que o resto do endereço. Mesmos bits do det_log direto (é a mesma função).
#define HOUSE_LOGS 65536
static double HOUSE_LOG[HOUSE_LOGS];
static bool house_logs_ready = false;
void init_house_logs() {
  if (house_logs_ready) return;
  HOUSE_LOG[0] = 0.0;
  for (u32 v = 1; v < HOUSE_LOGS; v++) HOUSE_LOG[v] = det_log((double)v);
  house_logs_ready = true;
}
static inline double house_log(u32 v) { return v < HOUSE_LOGS ? HOUSE_LOG[v] : det_log((double)v); }

DG_EXPORT void dg_house_number(u64* st, const u32* small, i64 m, i32* out) {
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  for (i64 r = 0; r < m; r++) {
    u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45);
    double u = (double)(x >> 11) * (1.0 / 9007199254740992.0);   // [0, 1)
    const u32* row = small + (size_t)ROW_U32 * r;
    i32 a = (i32)row[0], b = (i32)row[1];                         // faixa do trecho (0 quando a base nao tem)
    i32 v;
    if (a > 0 && b >= a) {
      double la = house_log((u32)a), lb = house_log((u32)b + 1u);
      double y = std::floor(det_exp(la + u * (lb - la)));
      v = y > (double)b ? b : (y < (double)a ? a : (i32)y);
    } else {
      double p = u < 1e-300 ? 1e-300 : u;
      double y = std::floor(det_exp(4.2 + 1.1 * inv_norm(p)));
      v = y < 1.0 ? 1 : (y > 9999.0 ? 9999 : (i32)y);
    }
    out[r] = v;
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
}

// Escolha uniforme dentro do grupo da linha: out[r] = flat[off[g] + uniforme(cnt[g])], g = small[r * ROW_U32 + field]
// (ex.: DDD entre os da UF do trecho sorteado)
DG_EXPORT void dg_pick_in_group(u64* st, const u32* small, int field, const u32* off, const u32* cnt, const u32* flat,
                                i64 m, u32* out) {
  u64 s0 = st[0], s1 = st[1], s2 = st[2], s3 = st[3];
  for (i64 r = 0; r < m; r++) {
    u64 x = rotl(s0 + s3, 23) + s0, t = s1 << 17; s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 45);
    u32 g = small[(size_t)ROW_U32 * r + field];
    out[r] = flat[off[g] + (u32)(((x >> 32) * (u64)cnt[g]) >> 32)];
  }
  st[0] = s0; st[1] = s1; st[2] = s2; st[3] = s3;
}

// Inteiro >= 0 como texto (inline: ate 10 digitos), para montar o endereco completo
DG_EXPORT void dg_int_views(const i32* x, i64 m, u32* V) {
  for (i64 r = 0; r < m; r++) {
    u32 v = x[r] < 0 ? 0u : (u32)x[r];
    u8 tmp[12]; int n = 0;
    do { tmp[n++] = (u8)('0' + v % 10u); v /= 10u; } while (v);
    u8 o[12] = {0};
    for (int i = 0; i < n; i++) o[i] = tmp[n - 1 - i];
    u32* w = V + 4 * r; w[0] = (u32)n; memcpy(&w[1], o, 12);
  }
}

// Concatena k colunas de views com separadores: entre a parte p-1 e a p vai seps[sep_off[p-1] .. sep_off[p]) (sep_off
// tem k entradas, sep_off[0] = 0; sep_off[k-1] = bytes de separador por linha). Cada parte p tem as
// views V[p] e os buffers de texto bufs[p][...] (indexados pelo indice de buffer da view). Escreve em sequencia em D;
// views longas apontam para o buffer 0 (o Python corrige o indice). dg_concat_size da o tamanho exato do texto; D
// precisa de 16 bytes de folga depois dele, e seps de 8 depois do ultimo separador (copias de tamanho fixo).
DG_EXPORT i64 dg_concat_size(i64 m, int k, const u32* const* V, const u32* sep_off) {
  i64 total = 0;
  for (int p = 0; p < k; p++) for (i64 r = 0; r < m; r++) total += V[p][4 * r];
  return total + m * (i64)sep_off[k - 1];
}
DG_EXPORT void dg_concat_views(i64 m, int k, const u32* const* V, const u8* const* const* bufs, const u8* seps,
                               const u32* sep_off, u32* out, u8* D) {
  u64 off = 0;
  for (i64 r = 0; r < m; r++) {
    u8* start = D + off; u8* o = start;
    for (int p = 0; p < k; p++) {
      // copias de tamanho fixo (D tem folga): o separador (ate 8 bytes; seps tem 8 de folga no fim) e o texto inline
      // (os 12 bytes da propria view); so o texto longo usa memcpy de tamanho variavel
      if (p) { u32 a = sep_off[p - 1], b = sep_off[p]; memcpy(o, seps + a, 8); o += b - a; }
      const u32* v = V[p] + 4 * r;
      u32 n = v[0];
      if (n <= 12) memcpy(o, v + 1, 12);
      else memcpy(o, bufs[p][v[2]] + v[3], n);
      o += n;
    }
    u32 n = (u32)(o - start);
    u32* v = out + 4 * r; v[0] = n;
    if (n <= 12) { u8 t[12] = {0}; memcpy(t, start, n); memcpy(&v[1], t, 12); }
    else { memcpy(&v[1], start, 4); v[2] = 0; v[3] = (u32)off; }
    off += n;
  }
}
