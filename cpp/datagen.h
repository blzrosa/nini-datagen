// datagen.h -- ABI em C do nini-datagen, chamada pelo Python via ctypes (src/nini_datagen/_native.py).
// GERADO por tools/gen_bindings.py a partir dos .cpp: não edite à mão. As funções que sorteiam recebem
// o estado do xoshiro256++ (uint64_t[4], atualizado no lugar) e escrevem em buffers alocados pelo chamador.
// Mudou a assinatura de alguma função? Aumente ABI_VERSION em tools/gen_bindings.py e regenere.
#pragma once
#include <stdint.h>

#define DG_ABI_VERSION 3

// DG_API: exportada ao compilar a biblioteca (DG_BUILDING), importada ao usá-la de outro código C/C++
#if defined(_WIN32)
#  if defined(DG_BUILDING)
#    define DG_API __declspec(dllexport)
#  else
#    define DG_API __declspec(dllimport)
#  endif
#else
#  define DG_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* address.cpp */
DG_API void dg_cep_views(uint64_t* st, uint32_t k, const uint32_t* prefixes, int style, int64_t m, uint32_t* V);
DG_API void dg_cep_views_uf(uint64_t* st, const uint32_t* uf_idx, const uint32_t* off, const uint32_t* cnt, const uint32_t* prefixes, int style, int64_t m, uint32_t* V);
DG_API void dg_empresa_views(uint64_t* st, uint32_t ks, const uint8_t* sch, const uint8_t* sln, const uint64_t* stab, uint32_t kb, const uint8_t* bch, const uint8_t* bln, const uint64_t* btab, uint32_t kr, const uint8_t* rch, const uint8_t* rln, const uint64_t* rtab, uint32_t kt, const uint8_t* tch, const uint8_t* tln, const uint64_t* ttab, int64_t m, uint32_t* V, uint8_t* D);
DG_API void dg_veiculo_idx(uint64_t* st, uint32_t nb, const uint64_t* btab, const uint32_t* moff, const uint32_t* mcnt, const uint64_t* mtabs, uint32_t ky, const uint64_t* ytab, int64_t m, uint32_t* bo, uint32_t* mo, uint32_t* yo);

/* documents.cpp */
DG_API void dg_cpf_from_base(const uint32_t* base, int64_t m, int formatted, uint32_t* V, uint32_t* D);
DG_API void dg_cpf_affine(uint32_t a, uint32_t start, int64_t m, int formatted, uint32_t* V, uint32_t* D);
DG_API void dg_cpf_random(uint64_t* s, int64_t m, int formatted, uint32_t* V, uint32_t* D);
DG_API void dg_cnpj_gen(uint64_t* s, int alpha, uint32_t tp4, uint32_t tp5, int formatted, int unique, uint64_t x0, uint64_t a, int64_t m, uint32_t* V, uint8_t* D);
DG_API void dg_id_views(uint64_t* st, int kind, int style, int64_t m, uint32_t* V, uint8_t* D, int stride);

/* network.cpp */
DG_API void dg_uuid_views(uint64_t* st, int64_t m, uint32_t* V, uint8_t* D);
DG_API void dg_ipv4_views(uint64_t* st, int priv, int64_t m, uint32_t* V, uint8_t* D);
DG_API void dg_url_views(uint64_t* st, uint32_t k, const uint8_t* wch, const uint8_t* wln, const uint64_t* wtab, uint32_t kt, const uint8_t* tch, const uint8_t* tln, const uint64_t* ttab, int64_t m, uint32_t* V, uint8_t* D);

/* numbers.cpp */
DG_API void dg_alias_build(const double* w, uint32_t k, uint64_t* tab);
DG_API void dg_bool_bits(uint64_t* s, uint64_t thr, int64_t m, uint64_t* out);
DG_API void dg_rand_i64(uint64_t* s, int64_t lo, uint64_t span, int64_t m, int64_t* out);
DG_API void dg_rand_i32(uint64_t* s, int lo, uint32_t span, int64_t m, int* out);
DG_API void dg_rand_f64(uint64_t* s, double lo, double hi, int64_t m, double* out);
DG_API void dg_rand_f32(uint64_t* s, float lo, float hi, int64_t m, float* out);
DG_API void dg_rand_normal(uint64_t* s, double mu, double sigma, int lognormal, int64_t m, double* out);
DG_API void dg_alias_idx(uint32_t k, const uint64_t* tab, uint64_t* s, int64_t m, uint32_t* out);

/* person.cpp */
DG_API void dg_choice_views(const uint32_t* dv, uint32_t k, uint64_t* s, int64_t m, uint32_t* V);
DG_API void dg_choice_alias_views(const uint32_t* dv, uint32_t k, const uint64_t* tab, uint64_t* s, int64_t m, uint32_t* V);
DG_API void dg_choice_alias_views_by(const uint32_t* dv, uint32_t kf, uint32_t km, const uint64_t* tab, const uint8_t* isf, uint64_t* s, int64_t m, uint32_t* V);
DG_API void dg_phone_views(uint64_t* st, uint32_t k, const uint64_t* ddd_tab, const uint16_t* ddd_chars, uint64_t mobile_thr, int style, int64_t m, uint32_t* V, uint8_t* D, const uint32_t* ddd_row);
DG_API void dg_email_views(uint64_t* st, uint32_t kf, const uint8_t* fch, const uint8_t* fln, uint32_t kl, const uint8_t* lch, const uint8_t* lln, const uint32_t* sty_thr, const uint8_t* sty_tab, int with_domain, uint32_t kd, const uint64_t* dtab, const uint8_t* dch, const uint8_t* dln, int64_t m, uint32_t* V, uint32_t* V2, uint8_t* D, uint32_t* idxF, uint32_t* idxL);
DG_API void dg_gather_views(const uint32_t* dv, const uint32_t* idx, int64_t m, uint32_t* V);
DG_API void dg_alias_idx_by(uint32_t kf, uint32_t km, const uint64_t* tab, const uint8_t* isf, uint64_t* s, int64_t m, uint32_t* out);
DG_API int64_t dg_join_size(int64_t m, int k, const uint32_t* const* dv, const uint32_t* const* idx, uint32_t seplen);
DG_API void dg_join_views(int64_t m, int k, const uint32_t* const* dv, const uint8_t* const* datas, const uint32_t* const* idx, const uint8_t* sep, uint32_t seplen, uint32_t buf, uint32_t* V, uint8_t* D);
DG_API int64_t dg_sex_mask(const uint32_t* V, const uint8_t* valid, int64_t bit_offset, int64_t m, uint8_t* out);

/* rng.cpp */
DG_API void dg_xoshiro_streams(const uint64_t* seed, int64_t first, int64_t count, uint64_t* out);

/* tables.cpp */
DG_API int dg_init();
DG_API int dg_abi_version();

/* text.cpp */
DG_API void dg_text_views(uint64_t* st, uint32_t k, const uint8_t* wch, const uint8_t* wln, const uint64_t* wtab, uint32_t wmin, uint32_t wmax, uint32_t smin, uint32_t smax, int64_t m, uint32_t* V, uint8_t* D);
DG_API void dg_template_views(uint64_t* st, const uint32_t* sym_off, const uint64_t* tab, const uint32_t* opt_off, const uint32_t* tok, const uint32_t* lit_off, const uint16_t* lit_len, const uint8_t* pool, uint32_t smin, uint32_t smax, int row_root, int64_t m, uint32_t* V, uint8_t* D);

#ifdef __cplusplus
}
#endif
