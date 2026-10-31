"""Validade da saída de cada kernel, lida de volta só com numpy (sem Polars).

Os testes de cada gerador público (fase 3) vão cobrir as opções; aqui o foco é o contrato do C++: views bem formadas,
dígitos verificadores, faixas, proporções e determinismo para o mesmo estado.
"""

from __future__ import annotations

import ipaddress
import re

import numpy as np
import pytest

from nini_datagen.core.rng import seed_state
from nini_datagen.core.views import decode, empty_views, used_bytes

from .conftest import as_str

M = 20_000
NO_TP = 0xFFFFFFFF
KNOWN_NORMAL_DIGESTS = ["756a820481c19bfb", "20d70a42aa04940c"]  # normal, lognormal (veja test_normal_known_bits)


def _dv_cpf(d: list[int]) -> tuple[int, int]:
    s1 = sum(x * w for x, w in zip(d[:9], range(10, 1, -1), strict=True))
    v1 = 0 if s1 % 11 < 2 else 11 - s1 % 11
    s2 = sum(x * w for x, w in zip([*d[:9], v1], range(11, 1, -1), strict=True))
    v2 = 0 if s2 % 11 < 2 else 11 - s2 % 11
    return v1, v2


def _dv_cnpj(vals: list[int]) -> tuple[int, int]:
    def one(xs: list[int]) -> int:
        w = [(i % 8) + 2 for i in range(len(xs))][::-1]
        r = sum(x * k for x, k in zip(xs, w, strict=True)) % 11
        return 0 if r < 2 else 11 - r

    v1 = one(vals[:12])
    return v1, one([*vals[:12], v1])


@pytest.mark.parametrize("formatted", [0, 1])
def test_cpf_random(lib, state, P, formatted):
    V, D = empty_views(M), np.zeros((M, 4), np.uint32)
    lib.dg_cpf_random(P(state), M, formatted, P(V), P(D))
    rows = as_str(decode(V, D))
    pat = r"\d{3}\.\d{3}\.\d{3}-\d{2}" if formatted else r"\d{11}"
    for s in rows:
        assert re.fullmatch(pat, s), s
        d = [int(c) for c in s if c.isdigit()]
        assert tuple(d[9:]) == _dv_cpf(d), s
    assert len(set(rows)) > M * 0.99


@pytest.mark.parametrize("alpha", [10, 36])
@pytest.mark.parametrize("formatted", [0, 1])
def test_cnpj_random(lib, state, P, alpha, formatted):
    V, D = empty_views(M), np.zeros(M * 64 + 64, np.uint8)
    lib.dg_cnpj_gen(P(state), alpha, NO_TP, 1, formatted, 0, 0, 0, M, P(V), P(D))
    rows = as_str(decode(V, D))
    body = "[0-9]" if alpha == 10 else "[0-9A-Z]"
    pat = rf"{body}{{2}}\.{body}{{3}}\.{body}{{3}}/{body}{{4}}-\d{{2}}" if formatted else rf"{body}{{12}}\d{{2}}"
    for s in rows:
        assert re.fullmatch(pat, s), s
        vals = [ord(c) - 48 for c in s if c.isalnum()]
        assert tuple(vals[12:]) == _dv_cnpj(vals), s
    if alpha == 36:
        assert any(re.search("[A-Z]", s) for s in rows)


def test_cnpj_unique_mode(lib, state, P):
    V, D = empty_views(M), np.zeros(M * 64 + 64, np.uint8)
    lib.dg_cnpj_gen(P(state), 10, NO_TP, 1, 0, 1, 123, 977, M, P(V), P(D))
    rows = decode(V, D)
    assert len(set(rows)) == M
    # a mesma chave a partir da linha 123 + 10 dá as mesmas linhas deslocadas (só depende da linha global)
    V2, D2 = empty_views(M - 10), np.zeros(M * 64 + 64, np.uint8)
    lib.dg_cnpj_gen(P(state), 10, NO_TP, 1, 0, 1, 133, 977, M - 10, P(V2), P(D2))
    assert decode(V2, D2) == rows[10:]


def test_cpf_perm_is_a_permutation(lib, P):
    """Num espaço pequeno dá para conferir a bijeção inteira: perm de [0, 10^9) restrita aos primeiros milhões é
    injetiva, e começar no meio dá as mesmas linhas."""
    m = 1 << 20
    V, D = empty_views(m), np.zeros(m * 16 + 64, np.uint8)
    lib.dg_cpf_perm(42, 0, m, 0, P(V), P(D))
    rows = decode(V, D)
    assert len(set(rows)) == m
    V2, D2 = empty_views(1000), np.zeros(1000 * 16 + 64, np.uint8)
    lib.dg_cpf_perm(42, 5000, 1000, 0, P(V2), P(D2))
    assert decode(V2, D2) == rows[5000:6000]


def test_pis(lib, state, P):
    V, D = empty_views(M), np.zeros(M * 64 + 64, np.uint8)
    lib.dg_id_views(P(state), 0, 0, M, P(V), P(D), 64)
    for s in as_str(decode(V, D)):
        d = [int(c) for c in s]
        r = 11 - sum(x * w for x, w in zip(d[:10], [3, 2, 9, 8, 7, 6, 5, 4, 3, 2], strict=True)) % 11
        assert len(d) == 11
        assert d[10] == (0 if r >= 10 else r), s


def test_uuid4(lib, state, P):
    V, D = empty_views(M), np.zeros(M * 64 + 64, np.uint8)
    lib.dg_uuid_views(P(state), M, P(V), P(D))
    rows = as_str(decode(V, D))
    for s in rows:
        assert re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", s), s
    assert len(set(rows)) == M


@pytest.mark.parametrize("private", [0, 1])
def test_ipv4(lib, state, P, private):
    V, D = empty_views(M), np.zeros(M * 64 + 64, np.uint8)
    lib.dg_ipv4_views(P(state), private, M, P(V), P(D))
    for s in as_str(decode(V, D)):
        ip = ipaddress.IPv4Address(s)  # também rejeita zeros à esquerda
        assert str(ip) == s
        if private:
            assert ip.is_private, s
        else:
            assert ip.is_global, s


@pytest.mark.parametrize(("lo", "span"), [(0, 1), (0, 100), (-5, 2**40), (-(2**62), 2**63 + 12345)])
def test_rand_i64_range(lib, state, P, lo, span):
    out = np.empty(M, np.int64)
    lib.dg_rand_i64(P(state), lo, span, M, P(out))
    assert out.min() >= lo
    assert int(out.max()) < lo + span
    if span == 100:
        assert out.min() == 0
        assert out.max() == 99


def test_rand_i32_range(lib, state, P):
    out = np.empty(M, np.int32)
    lib.dg_rand_i32(P(state), -3, 7, M, P(out))
    assert set(out.tolist()) == set(range(-3, 4))


@pytest.mark.parametrize(("dtype", "fn"), [(np.float64, "dg_rand_f64"), (np.float32, "dg_rand_f32")])
def test_rand_float_range(lib, state, P, dtype, fn):
    out = np.empty(M, dtype)
    getattr(lib, fn)(P(state), -1.0, 2.0, M, P(out))
    assert out.min() >= -1.0
    assert out.max() < 2.0
    assert abs(out.mean() - 0.5) < 0.05


def test_normal_and_lognormal(lib, state, P):
    out = np.empty(200_000, np.float64)
    lib.dg_rand_normal(P(state), 1.0, 0.5, 0, len(out), P(out))
    assert abs(out.mean() - 1.0) < 0.01
    assert abs(out.std() - 0.5) < 0.01
    lib.dg_rand_normal(P(state), 0.0, 0.25, 1, len(out), P(out))
    assert out.min() > 0
    assert abs(np.log(out).std() - 0.25) < 0.01


@pytest.mark.parametrize("p", [0.0, 0.3, 0.5, 1.0])
def test_bool_bits(lib, state, P, p):
    n = 200_000
    bits = np.zeros((n + 63) // 64, np.uint64)
    lib.dg_bool_bits(P(state), int(p * 2**32), n, P(bits))
    frac = np.unpackbits(bits.view(np.uint8), bitorder="little")[:n].mean()
    assert abs(frac - p) < 0.01


def test_alias_frequencies(lib, state, P):
    stats = pytest.importorskip("scipy.stats")
    w = np.array([5.0, 1.0, 0.0, 3.0, 0.5, 10.0])
    tab = np.zeros(len(w), np.uint64)
    lib.dg_alias_build(P(w), len(w), P(tab))
    n = 300_000
    idx = np.empty(n, np.uint32)
    lib.dg_alias_idx(len(w), P(tab), P(state), n, P(idx))
    counts = np.bincount(idx, minlength=len(w))
    assert counts[2] == 0  # peso zero nunca sai
    keep = w > 0
    expected = w[keep] / w.sum() * n
    assert stats.chisquare(counts[keep], expected).pvalue > 1e-4


def test_choice_views_gather(lib, state, P):
    words = [b"ana", b"bruno", b"carolina!!", b"x"]
    dv = np.zeros((len(words), 4), np.uint32)
    raw = dv.view(np.uint8).reshape(-1, 16)
    for i, w in enumerate(words):
        dv[i, 0] = len(w)
        raw[i, 4 : 4 + len(w)] = np.frombuffer(w, np.uint8)
    V = empty_views(M)
    lib.dg_choice_views(P(dv), len(words), P(state), M, P(V))
    assert set(decode(V)) == set(words)
    idx = np.array([3, 0, 1], np.uint32)
    G = empty_views(3)
    lib.dg_gather_views(P(dv), P(idx), 3, P(G))
    assert decode(G) == [b"x", b"ana", b"bruno"]


def test_same_state_same_output(lib, P):
    outs = []
    for _ in range(2):
        st = seed_state(77, "det")
        V, D = empty_views(M), np.zeros(M * 64 + 64, np.uint8)
        lib.dg_uuid_views(P(st), M, P(V), P(D))
        outs.append((V.copy(), D[: used_bytes(V)].copy(), st.copy()))
    assert all(np.array_equal(a, b) for a, b in zip(outs[0], outs[1], strict=True))


def test_normal_matches_reference_quantiles(lib, P):
    """normal = Φ⁻¹(p) com p tirado do xoshiro; confere contra o scipy (inclusive a cauda, onde entra o log próprio)."""
    stats = pytest.importorskip("scipy.stats")
    from .test_rng import _next  # noqa: PLC0415

    st = seed_state(5, "normal-ref")
    ref = [int(x) for x in st]
    n = 20_000
    out = np.empty(n)
    lib.dg_rand_normal(P(st), 0.0, 1.0, 0, n, P(out))
    p = np.array([((_next(ref) >> 11) + 0.5) / 2**53 for _ in range(n)])
    expected = stats.norm.ppf(p)
    assert np.allclose(out, expected, rtol=2e-9, atol=1e-12)
    tail = (p < 0.02425) | (p > 1 - 0.02425)
    assert tail.sum() > 500  # a cauda foi exercitada
    st2 = seed_state(5, "normal-ref")
    logn = np.empty(n)
    lib.dg_rand_normal(P(st2), 0.0, 1.0, 1, n, P(logn))
    assert np.allclose(logn, np.exp(out), rtol=1e-12)


def test_normal_known_bits(lib, P):
    """Resumo dos bits de 20 mil saídas: o mesmo em todo sistema e compilador (sem std::log/exp, sem FMA). Se mudar, a
    mesma semente passou a dar outro resultado (quebra a reprodutibilidade da v0.2.0)."""
    import hashlib  # noqa: PLC0415

    digests = []
    for lognormal in (0, 1):
        st = np.array([1, 2, 3, 4], np.uint64) * np.uint64(0x9E3779B97F4A7C15)
        out = np.empty(20_000)
        lib.dg_rand_normal(P(st), 0.0, 1.0, lognormal, len(out), P(out))
        digests.append(hashlib.blake2b(out.tobytes(), digest_size=8).hexdigest())
    assert digests == KNOWN_NORMAL_DIGESTS


def test_alias_idx_by_matches_views_by(lib, P):
    """O índice por grupo consome o gerador igual à escolha de views por grupo (o full_name depende disso)."""
    from nini_datagen.core.tables import Vocabulary, alias_table  # noqa: PLC0415

    words = [f"palavra{i}" for i in range(7)] + ["uma palavra bem comprida"] * 1 + [f"outra{i}" for i in range(5)]
    vocab = Vocabulary.from_strings(words)
    kf, km = 8, 5
    tab = np.concatenate([alias_table(np.arange(1, kf + 1)), alias_table(np.arange(km, 0, -1))])
    isf = (np.random.default_rng(1).random(M) < 0.5).astype(np.uint8)
    s1, s2 = seed_state(9, "by"), seed_state(9, "by")
    V, idx = empty_views(M), np.empty(M, np.uint32)
    lib.dg_choice_alias_views_by(P(vocab.views), kf, km, P(tab), P(isf), P(s1), M, P(V))
    lib.dg_alias_idx_by(kf, km, P(tab), P(isf), P(s2), M, P(idx))
    assert np.array_equal(s1, s2)
    assert decode(V, vocab.data) == [words[i].encode() for i in idx]
    assert ((idx < kf) == isf.astype(bool)).all()


def test_join_views(lib, P):
    from nini_datagen.core.tables import Vocabulary  # noqa: PLC0415

    rng = np.random.default_rng(3)
    a = Vocabulary.from_strings(["Ana", "Maria", "Conceição", "Maximiliano Augusto"])
    b = Vocabulary.from_strings(["Silva", "de Jesus", "Bitencourt", "X" * 40])
    m = 5000
    ia = rng.integers(0, len(a) + 1, m).astype(np.uint32)  # len(vocab) = parte vazia
    ib = rng.integers(0, len(b) + 1, m).astype(np.uint32)
    ia[:3], ib[:3] = len(a), len(b)  # linhas totalmente vazias
    pad = np.zeros(16, np.uint8)
    dvs = [np.vstack([v.views, np.zeros((1, 4), np.uint32)]) for v in (a, b)]
    texts = [np.concatenate([v.data if v.data is not None else pad[:0], pad]) for v in (a, b)]
    dv_ptrs = np.array([P(d) for d in dvs], np.uint64)
    data_ptrs = np.array([P(t) for t in texts], np.uint64)
    idx_ptrs = np.array([P(ia), P(ib)], np.uint64)
    sep = np.frombuffer(b" - " + bytes(16), np.uint8).copy()
    size = lib.dg_join_size(m, 2, P(dv_ptrs), P(idx_ptrs), 3)
    buf, V = np.full(size + 16, 255, np.uint8), empty_views(m)
    lib.dg_join_views(m, 2, P(dv_ptrs), P(data_ptrs), P(idx_ptrs), P(sep), 3, 0, P(V), P(buf))
    got = decode(V, buf[:size])
    wa, wb = [*a.strings, ""], [*b.strings, ""]
    want = [" - ".join(x for x in (wa[i], wb[j]) if x).encode() for i, j in zip(ia, ib, strict=True)]
    assert got == want
    assert used_bytes(V) == size
    raw = V.view(np.uint8).reshape(-1, 16)
    for r in range(m):  # o Arrow pede zeros depois de um texto curto
        n = int(V[r, 0])
        if n <= 12:
            assert not raw[r, 4 + n :].any()
