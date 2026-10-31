"""Valores e distribuições de cada gerador."""

from __future__ import annotations

import datetime as dt
from collections import Counter

import numpy as np
import pytest

import nini_datagen as dg
from nini_datagen.locales import get_locale

N = 200_000


def chisquare_ok(counts, expected) -> bool:
    stats = pytest.importorskip("scipy.stats")
    counts = np.asarray(counts, dtype=float)
    expected = np.asarray(expected, dtype=float)
    expected = expected / expected.sum() * counts.sum()
    return stats.chisquare(counts, expected).pvalue > 1e-4


def ks_ok(sample, cdf) -> bool:
    stats = pytest.importorskip("scipy.stats")
    return stats.kstest(sample, cdf).pvalue > 1e-4


# ------------------------------------------------------------------ números
@pytest.mark.parametrize(("low", "high"), [(0, 0), (1, 6), (-5, 5), (-(2**31), 2**31 - 1), (0, 2**32)])
def test_integer_range_inclusive(low, high):
    s = dg.integer(N, seed=1, low=low, high=high).to_numpy()
    assert s.min() >= low
    assert s.max() <= high
    if high - low < 100:
        assert set(s.tolist()) == set(range(low, high + 1))


def test_integer_uniformity():
    s = dg.integer(N, seed=2, low=1, high=6).to_numpy()
    assert chisquare_ok(np.bincount(s)[1:], [1] * 6)


def test_integer_dtypes():
    assert str(dg.integer(5, seed=1, high=2**31).dtype) == str(dg.integer(5, seed=1, dtype="int64").dtype)
    big = dg.integer(1000, seed=1, low=-(2**62), high=2**62).to_numpy()
    assert big.dtype == np.int64
    assert big.min() < -(2**60)
    assert big.max() > 2**60


@pytest.mark.parametrize("dtype", ["float32", "float64"])
def test_uniform(dtype):
    s = dg.uniform(N, seed=3, low=-2.0, high=6.0, dtype=dtype).to_numpy()
    assert s.min() >= -2.0
    assert s.max() < 6.0
    assert ks_ok((s.astype(np.float64) + 2.0) / 8.0, "uniform")


def test_normal_and_lognormal():
    s = dg.normal(N, seed=4, mean=10.0, std=3.0).to_numpy()
    assert ks_ok((s - 10.0) / 3.0, "norm")
    lg = dg.lognormal(N, seed=5, mean=1.0, sigma=0.5).to_numpy()
    assert lg.min() > 0
    assert ks_ok((np.log(lg) - 1.0) / 0.5, "norm")


@pytest.mark.parametrize("p", [0.0, 0.01, 0.5, 0.9, 1.0])
def test_boolean(p):
    s = dg.boolean(N, seed=6, p=p).to_numpy()
    assert abs(s.mean() - p) < 0.005


# ------------------------------------------------------------------ datas
def test_date_range_inclusive_and_uniform():
    s = dg.date(N, seed=7, start="2024-02-27", end="2024-03-02").to_list()
    c = Counter(s)
    days = [dt.date(2024, 2, 27) + dt.timedelta(days=i) for i in range(5)]  # 2024 é bissexto: 29/02 entra
    assert set(c) == set(days)
    assert chisquare_ok([c[d] for d in days], [1] * 5)


def test_date_single_day():
    assert set(dg.date(100, seed=1, start="2000-01-01", end="2000-01-01").to_list()) == {dt.date(2000, 1, 1)}


@pytest.mark.parametrize("unit", ["ms", "us", "ns"])
def test_datetime_range(unit):
    start, end = dt.datetime(2020, 1, 1), dt.datetime(2020, 1, 1, 0, 0, 10)
    s = dg.datetime(50_000, seed=8, start=start, end=end, unit=unit).to_list()
    assert min(s) >= start
    assert max(s) < end
    assert max(s) - min(s) > dt.timedelta(seconds=9.9)


# ------------------------------------------------------------------ escolha
def test_choice_weights():
    s = dg.choice(N, ["a", "b", "c", "zero"], seed=9, weights=[5, 3, 2, 0]).to_list()
    c = Counter(s)
    assert c["zero"] == 0
    assert chisquare_ok([c["a"], c["b"], c["c"]], [5, 3, 2])


def test_choice_uniform_and_types():
    c = Counter(dg.choice(N, ["x", "y", "z"], seed=10).to_list())
    assert chisquare_ok(list(c.values()), [1, 1, 1])
    assert set(dg.choice(1000, [7, 8], seed=1).to_list()) == {7, 8}
    assert set(dg.choice(1000, [0.5, 1.5], seed=1).to_list()) == {0.5, 1.5}
    b = dg.choice(N, [True, False], seed=1, weights=[1, 3]).to_numpy()
    assert abs(b.mean() - 0.25) < 0.005
    assert dg.choice(5, ["só"], seed=1).to_list() == ["só"] * 5


def test_choice_long_and_unicode_strings():
    vals = ["", "curto", "exatamente12", "treze letras!", "São João da Boa Vista — SP", "ç" * 40]
    out = set(dg.choice(5000, vals, seed=12).to_list())
    assert out == set(vals)


def test_choice_many_values():
    vals = [f"opção {i}" for i in range(50_000)]
    s = dg.choice(N, vals, seed=13).to_list()
    assert set(s) <= set(vals)
    assert len(set(s)) > 45_000


# ------------------------------------------------------------------ pessoa
def test_sex_proportion_and_labels():
    s = dg.sex(N, seed=14).to_list()
    assert set(s) == {"F", "M"}
    assert abs(s.count("F") / N - get_locale().p_female) < 0.005
    lab = dg.sex(N, seed=14, labels=("Feminino", "Masculino"), p_female=0.2).to_list()
    assert abs(lab.count("Feminino") / N - 0.2) < 0.005


def test_age_default_pyramid():
    s = dg.age(N, seed=15).to_numpy()
    assert s.min() >= 0
    assert s.max() <= 100
    w = get_locale().age_weights(0, 100)
    assert chisquare_ok(np.bincount(s, minlength=101), w)


def test_age_custom_weights_and_offset():
    s = dg.age(N, seed=16, low=20, high=22, weights=[1, 0, 3]).to_numpy()
    c = Counter(s.tolist())
    assert set(c) == {20, 22}
    assert chisquare_ok([c[20], c[22]], [1, 3])


def _first_names():
    d = get_locale().first_names()
    return d, dict(zip(d.names, range(len(d.names)), strict=True))


def test_first_name_frequencies():
    d, pos = _first_names()
    c = Counter(dg.first_name(N, seed=17).to_list())
    top = sorted(c, key=c.get, reverse=True)[:5]  # type: ignore[arg-type]
    assert top[0] == "Maria"
    expected = d.total[[pos[x] for x in top]]
    assert chisquare_ok([c[x] for x in top], expected)


@pytest.mark.parametrize("sex", ["F", "M"])
def test_first_name_fixed_sex(sex):
    d, pos = _first_names()
    col = d.female if sex == "F" else d.male
    names = dg.first_name(20_000, seed=18, sex=sex).to_list()
    assert all(col[pos[x]] > 0 for x in names)
    assert Counter(names).most_common(1)[0][0] == ("Maria" if sex == "F" else "José")


def test_first_name_follows_sex_column():
    d, pos = _first_names()
    g = dg.DataGen(seed=19)
    sx = g.sex(50_000)
    names = g.first_name(50_000, sex=sx).to_list()
    for s, x in zip(sx.to_list(), names, strict=True):
        col = d.female if s == "F" else d.male
        assert col[pos[x]] > 0, (s, x)


def test_first_name_sex_column_variants():
    g = dg.DataGen(seed=20)
    sx = ["Feminino", "masculino", None, "?", "F", "M"] * 1000
    names = g.first_name(len(sx), sex=sx).to_list()
    d, pos = _first_names()
    for s, x in zip(sx, names, strict=True):
        if s in ("Feminino", "F"):
            assert d.female[pos[x]] > 0
        elif s in ("masculino", "M"):
            assert d.male[pos[x]] > 0
    # desconhecidos são sorteados de forma reproduzível
    assert g.first_name(len(sx), sex=sx).to_list() == names
    with pytest.raises(ValueError, match="valores"):
        g.first_name(10, sex=["F"] * 9)


def test_last_name_frequencies():
    c = Counter(dg.last_name(N, seed=21).to_list())
    assert c.most_common(1)[0][0] == "Silva"
    d = get_locale().last_names()
    assert set(c) <= set(d.names)


def _split_full(full: str, compound_possible: bool) -> tuple[list[str], str]:
    """(prenomes, sobrenomes) — prenomes não têm espaço; sobrenomes podem ter ("de Jesus")."""
    p = full.split(" ")
    k = 2 if compound_possible else 1
    return p[:k], " ".join(p[k:])


def test_full_name_defaults():
    c = dg.FullNameConfig()
    assert c.compound == 0.25
    assert c.two_surnames == 0.9


def test_full_name_surnames():
    last = set(get_locale().last_names().names)
    s = dg.full_name(20_000, seed=22, compound=0.0, two_surnames=0.6).to_list()
    two = 0
    for full in s:
        assert full == full.strip()
        assert "  " not in full
        _, rest = _split_full(full, False)
        if rest not in last:
            two += 1
            assert len(rest.split(" ")) >= 2
    assert 0.55 < two / len(s) < 0.6  # um pouco abaixo de 0,6: sobrenome repetido vira um só
    one = dg.full_name(2000, seed=22, compound=0.0, two_surnames=0.0).to_list()
    assert all(_split_full(x, False)[1] in last for x in one)


def test_full_name_compound_given_names():
    d, pos = _first_names()
    last = set(get_locale().last_names().names)
    prefixes = get_locale().compound_prefixes()
    g = dg.DataGen(seed=24)
    sx = g.sex(20_000)
    s = g.full_name(20_000, sex=sx, compound=1.0, two_surnames=0.0).to_list()
    for full, sex in zip(s, sx.to_list(), strict=True):
        given, rest = _split_full(full, True)
        col = d.female if sex == "F" else d.male
        if rest in last and all(x in pos for x in given):  # dois prenomes (o segundo some se repete o primeiro)
            assert given[0] != given[1], full
            assert all(col[pos[x]] > 0 for x in given), (sex, full)
            assert given[0] in prefixes[0 if sex == "F" else 1], full
    zero = g.full_name(5000, compound=0.0, two_surnames=0.0).to_list()
    assert all(_split_full(x, False)[1] in last for x in zero)
    frac = g.full_name(20_000, compound=0.3, two_surnames=0.0).to_list()
    k = sum(_split_full(x, False)[1] not in last for x in frac) / len(frac)
    assert 0.27 < k < 0.31


def test_full_name_without_sex_keeps_given_names_coherent():
    d, pos = _first_names()
    for full in dg.full_name(5000, seed=25, compound=1.0, two_surnames=0.0).to_list():
        given = full.split(" ")[:2]
        fem = all(d.female[pos[x]] > 0 for x in given if x in pos)
        mas = all(d.male[pos[x]] > 0 for x in given if x in pos)
        assert fem or mas, full


def test_full_name_by_sex():
    d, pos = _first_names()
    for x in dg.full_name(5000, seed=23, sex="F").to_list():
        assert d.female[pos[x.split(" ")[0]]] > 0
