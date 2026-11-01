"""Tipos dos argumentos de cada função da biblioteca C++ (GERADO por tools/gen_bindings.py; não edite)."""
from __future__ import annotations

from ctypes import c_double, c_float, c_int, c_int64, c_uint8, c_uint16, c_uint32, c_uint64, c_void_p

ABI_VERSION = 12

# nome: (tipo de retorno, [tipos dos argumentos])
SIGNATURES = {
    "dg_cep_views": (None, [c_void_p, c_uint32, c_void_p, c_int, c_int64, c_void_p]),
    "dg_cep_views_uf": (None, [c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_int, c_int64, c_void_p]),
    "dg_empresa_views": (None, [c_void_p, c_uint32, c_void_p, c_void_p, c_void_p, c_uint32, c_void_p, c_void_p, c_void_p, c_uint32, c_void_p, c_void_p, c_void_p, c_uint32, c_void_p, c_void_p, c_void_p, c_int64, c_void_p, c_void_p]),
    "dg_veiculo_idx": (None, [c_void_p, c_uint32, c_void_p, c_void_p, c_void_p, c_void_p, c_uint32, c_void_p, c_int64, c_void_p, c_void_p, c_void_p]),
    "dg_cep_pick": (None, [c_void_p, c_uint32, c_void_p, c_void_p, c_int, c_int64, c_void_p]),
    "dg_address_core": (None, [c_void_p, c_uint32, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_int64, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p]),
    "dg_house_number": (None, [c_void_p, c_void_p, c_int64, c_void_p]),
    "dg_pick_in_group": (None, [c_void_p, c_void_p, c_int, c_void_p, c_void_p, c_void_p, c_int64, c_void_p]),
    "dg_int_views": (None, [c_void_p, c_int64, c_void_p]),
    "dg_concat_size": (c_int64, [c_int64, c_int, c_void_p, c_void_p]),
    "dg_concat_views": (None, [c_int64, c_int, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p]),
    "dg_cpf_from_base": (None, [c_void_p, c_int64, c_int, c_void_p, c_void_p]),
    "dg_cpf_perm": (None, [c_uint64, c_uint64, c_int64, c_int, c_void_p, c_void_p]),
    "dg_cpf_random": (None, [c_void_p, c_int64, c_int, c_void_p, c_void_p]),
    "dg_cnpj_gen": (None, [c_void_p, c_int, c_uint32, c_uint32, c_int, c_int, c_uint64, c_uint64, c_int64, c_void_p, c_void_p]),
    "dg_id_views": (None, [c_void_p, c_int, c_int, c_int64, c_void_p, c_void_p, c_int]),
    "dg_pool_alloc": (c_int64, [c_int64]),
    "dg_pool_free": (None, [c_int64]),
    "dg_pool_limit": (c_int64, [c_int64]),
    "dg_pool_trim": (None, []),
    "dg_pool_stats": (None, [c_void_p]),
    "dg_uuid_views": (None, [c_void_p, c_int64, c_void_p, c_void_p]),
    "dg_ipv4_views": (None, [c_void_p, c_int, c_int64, c_void_p, c_void_p]),
    "dg_url_views": (None, [c_void_p, c_uint32, c_void_p, c_void_p, c_uint32, c_void_p, c_void_p, c_void_p, c_int64, c_void_p, c_void_p]),
    "dg_alias_build": (None, [c_void_p, c_uint32, c_void_p]),
    "dg_bool_bits": (None, [c_void_p, c_uint64, c_int64, c_void_p]),
    "dg_rand_i64": (None, [c_void_p, c_int64, c_uint64, c_int64, c_void_p]),
    "dg_rand_i32": (None, [c_void_p, c_int, c_uint32, c_int64, c_void_p]),
    "dg_rand_f64": (None, [c_void_p, c_double, c_double, c_int64, c_void_p]),
    "dg_rand_f32": (None, [c_void_p, c_float, c_float, c_int64, c_void_p]),
    "dg_simd": (c_int, [c_int]),
    "dg_rand_normal": (None, [c_void_p, c_double, c_double, c_int, c_int64, c_void_p]),
    "dg_correlated": (None, [c_void_p, c_void_p, c_double, c_double, c_double, c_double, c_double, c_int, c_int64, c_void_p]),
    "dg_birthdate": (None, [c_void_p, c_void_p, c_void_p, c_void_p, c_int64, c_void_p]),
    "dg_det_exp": (c_double, [c_double]),
    "dg_alias_idx": (None, [c_uint32, c_void_p, c_void_p, c_int64, c_void_p]),
    "dg_choice_views": (None, [c_void_p, c_uint32, c_void_p, c_int64, c_void_p]),
    "dg_choice_alias_views": (None, [c_void_p, c_uint32, c_void_p, c_void_p, c_int64, c_void_p]),
    "dg_choice_alias_views_by": (None, [c_void_p, c_uint32, c_uint32, c_void_p, c_void_p, c_void_p, c_int64, c_void_p]),
    "dg_phone_views": (None, [c_void_p, c_uint32, c_void_p, c_void_p, c_uint64, c_int, c_int64, c_void_p, c_void_p, c_void_p]),
    "dg_email_views": (None, [c_void_p, c_uint32, c_void_p, c_void_p, c_uint32, c_void_p, c_void_p, c_void_p, c_void_p, c_int, c_uint32, c_void_p, c_void_p, c_void_p, c_int64, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p]),
    "dg_gather_views": (None, [c_void_p, c_void_p, c_int64, c_void_p]),
    "dg_alias_idx_by": (None, [c_uint32, c_uint32, c_void_p, c_void_p, c_void_p, c_int64, c_void_p]),
    "dg_join_size": (c_int64, [c_int64, c_int, c_void_p, c_void_p, c_uint32]),
    "dg_join_views": (None, [c_int64, c_int, c_void_p, c_void_p, c_void_p, c_void_p, c_uint32, c_uint32, c_void_p, c_void_p]),
    "dg_sex_mask": (c_int64, [c_void_p, c_void_p, c_int64, c_int64, c_void_p]),
    "dg_xoshiro_streams": (None, [c_void_p, c_int64, c_int64, c_void_p]),
    "dg_views_used": (c_int64, [c_void_p, c_int64, c_int]),
    "dg_init": (c_int, []),
    "dg_abi_version": (c_int, []),
    "dg_text_views": (None, [c_void_p, c_uint32, c_void_p, c_void_p, c_void_p, c_uint32, c_uint32, c_uint32, c_uint32, c_int64, c_void_p, c_void_p]),
    "dg_template_views": (c_int64, [c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_void_p, c_uint32, c_uint32, c_int, c_int64, c_int64, c_int64, c_void_p, c_void_p]),
}

__all__ = ['ABI_VERSION', 'SIGNATURES', 'c_double', 'c_float', 'c_int', 'c_int64', 'c_uint8', 'c_uint16', 'c_uint32', 'c_uint64', 'c_void_p']
