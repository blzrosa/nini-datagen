"""Contrato comum de todos os geradores: tipo, tamanho, determinismo, estabilidade por prefixo, nulos."""

from __future__ import annotations

import pytest

import nini_datagen as dg
from nini_datagen.core.blocks import BLOCK_ROWS

from .helpers import CASES, DTYPES, N_MULTI, case, same

ALL = sorted(CASES)


@pytest.mark.parametrize("name", ALL)
def test_dtype_length_and_name(name):
    kind, kw = case(name)
    s = dg.DataGen(seed=1).generate(kind, 1000, **kw)
    assert len(s) == 1000
    assert s.dtype == DTYPES[name]
    assert s.name == kind
    assert s.null_count() == 0
    assert dg.DataGen(seed=1).generate(kind, 10, name="minha_coluna", **kw).name == "minha_coluna"


@pytest.mark.parametrize("name", ALL)
def test_empty(name):
    kind, kw = case(name)
    s = dg.generate(kind, 0, seed=1, **kw)
    assert len(s) == 0
    assert s.dtype == DTYPES[name]


@pytest.mark.parametrize("name", ALL)
def test_same_seed_same_data_any_threads(name):
    kind, kw = case(name)
    ref = dg.DataGen(seed=7, threads=1).generate(kind, N_MULTI, **kw)
    for threads in (2, 8):
        assert same(dg.DataGen(seed=7, threads=threads).generate(kind, N_MULTI, **kw), ref), threads
    assert same(dg.generate(kind, N_MULTI, seed=7, **kw), ref)  # função solta = DataGen


@pytest.mark.parametrize("name", ALL)
def test_prefix_stability(name):
    """n pequeno dá exatamente o começo de n grande (inclusive cruzando a borda de um bloco)."""
    kind, kw = case(name)
    g = dg.DataGen(seed=3)
    big = g.generate(kind, N_MULTI, **kw).to_list()
    for n in (1, 17, BLOCK_ROWS, BLOCK_ROWS + 5):
        assert g.generate(kind, n, **kw).to_list() == big[:n], n


@pytest.mark.parametrize("name", ALL)
def test_seed_and_name_change_the_stream(name):
    kind, kw = case(name)
    a = dg.generate(kind, 2000, seed=1, **kw).to_list()
    assert dg.generate(kind, 2000, seed=2, **kw).to_list() != a
    assert dg.generate(kind, 2000, seed=1, name="outra", **kw).to_list() != a


@pytest.mark.parametrize("name", ALL)
def test_null_fraction(name):
    kind, kw = case(name)
    g = dg.DataGen(seed=11)
    plain = g.generate(kind, N_MULTI, **kw).to_list()
    with_nulls = g.generate(kind, N_MULTI, null_fraction=0.25, **kw)
    vals = with_nulls.to_list()
    frac = with_nulls.null_count() / N_MULTI
    assert abs(frac - 0.25) < 0.01
    # os nulos têm fluxo próprio: as linhas preenchidas mantêm os valores de sem nulos
    assert all(v is None or v == p for v, p in zip(vals, plain, strict=True))
    assert g.generate(kind, 500, null_fraction=1.0, **kw).null_count() == 500


def test_random_seed_when_omitted():
    a, b = dg.integer(1000), dg.integer(1000)
    assert a.to_list() != b.to_list()
    g = dg.DataGen()
    assert g.integer(100).to_list() == g.integer(100).to_list()  # mesma semente no mesmo DataGen
    assert dg.DataGen(seed=g.seed).integer(100).to_list() == g.integer(100).to_list()


def test_datagen_validation_and_repr():
    with pytest.raises(ValueError, match=">= 0"):
        dg.DataGen(seed=-1)
    with pytest.raises(ValueError, match="n deve ser"):
        dg.DataGen(seed=1).integer(-1)
    with pytest.raises(ValueError, match="n deve ser"):
        dg.DataGen(seed=1).integer(1.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="locale"):
        dg.DataGen(locale="xx_XX")
    assert "seed=5" in repr(dg.DataGen(seed=5))
    assert dg.DataGen(seed=5, threads=3).threads == 3
    assert dg.DataGen(seed=5).locale.code == "pt_BR"


def test_config_object_and_kwargs_are_equivalent():
    g = dg.DataGen(seed=4)
    a = g.integer(500, dg.IntegerConfig(low=1, high=6))
    assert same(a, g.integer(500, low=1, high=6))
    assert same(a, g.integer(500, {"low": 1, "high": 6}))
    assert same(a, g.integer(500, dg.IntegerConfig(low=1, high=2), high=6))
