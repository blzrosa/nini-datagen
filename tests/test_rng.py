from __future__ import annotations

import numpy as np
import pytest

from nini_datagen.core.rng import block_states, new_seed, seed_state, stream_key

MASK = (1 << 64) - 1
JUMP = (0x180EC6D33CFD0ABA, 0xD5A61266F0C9392C, 0xA9582618E03FC9AA, 0x39ABDC4529B1661C)


def _rotl(x: int, k: int) -> int:
    return ((x << k) | (x >> (64 - k))) & MASK


def _next(s: list[int]) -> int:
    """xoshiro256++ de referência (Vigna), em Python puro."""
    out = (_rotl((s[0] + s[3]) & MASK, 23) + s[0]) & MASK
    t = (s[1] << 17) & MASK
    s[2] ^= s[0]
    s[3] ^= s[1]
    s[1] ^= s[2]
    s[0] ^= s[3]
    s[2] ^= t
    s[3] = _rotl(s[3], 45)
    return out


def _jump(s: list[int]) -> None:
    acc = [0, 0, 0, 0]
    for j in JUMP:
        for b in range(64):
            if j >> b & 1:
                acc = [a ^ x for a, x in zip(acc, s, strict=True)]
            _next(s)
    s[:] = acc


def test_stream_key_is_stable():
    # valores fixos: se mudarem, todos os dados gerados mudam (quebra a garantia da v0.2.0)
    assert stream_key("cpf") == stream_key("cpf")
    assert stream_key("cpf") != stream_key("cnpj")
    assert 0 <= stream_key("x") < 2**64
    with pytest.raises(ValueError, match="vazio"):
        stream_key("")


def test_seed_state_deterministic_and_distinct():
    a = seed_state(42, "cpf")
    assert a.dtype == np.uint64
    assert a.shape == (4,)
    assert np.array_equal(a, seed_state(42, "cpf"))
    assert not np.array_equal(a, seed_state(43, "cpf"))
    assert not np.array_equal(a, seed_state(42, "cnpj"))
    assert a.any()


def test_seed_validation():
    with pytest.raises(ValueError, match=">= 0"):
        seed_state(-1, "x")
    with pytest.raises(TypeError):
        seed_state(1.5, "x")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        seed_state(True, "x")
    assert np.array_equal(seed_state(np.int64(7), "x"), seed_state(7, "x"))
    seed_state(2**200, "x")  # sementes grandes são aceitas


def test_new_seed_is_random():
    assert new_seed() != new_seed()
    assert new_seed() >= 0


def test_block_states_match_reference_jump():
    base = [int(x) for x in seed_state(9, "ref")]
    got = block_states(9, "ref", 3)
    s = base[:]
    for i in range(3):
        assert [int(x) for x in got[i]] == s
        _jump(s)


def test_block_states_prefix_and_offset():
    full = block_states(1, "s", 10)
    assert np.array_equal(block_states(1, "s", 4), full[:4])
    assert np.array_equal(block_states(1, "s", 3, first=5), full[5:8])
    assert block_states(1, "s", 0).shape == (0, 4)
    assert len({tuple(r) for r in full.tolist()}) == 10
    with pytest.raises(ValueError, match=">= 0"):
        block_states(1, "s", -1)


def test_kernel_consumes_state_like_reference(lib, P):
    """O kernel de inteiros usa o mesmo xoshiro256++ da referência: mulhi64(x, span) da 1a saída."""
    st = seed_state(3, "k")
    ref = [int(x) for x in st]
    out = np.empty(5, np.int64)
    lib.dg_rand_i64(P(st), 0, 2**63, 5, P(out))
    want = [(_next(ref) * 2**63) >> 64 for _ in range(5)]
    assert out.tolist() == want
    assert [int(x) for x in st] == ref  # estado devolvido atualizado
