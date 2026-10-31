from __future__ import annotations

import numpy as np
import pytest

from nini_datagen.core.views import INLINE_MAX, decode, empty_views, trim, used_bytes


def make_views(strings: list[bytes]) -> tuple[np.ndarray, np.ndarray]:
    """Monta views do Arrow em Python (referência independente do C++)."""
    V = np.zeros((len(strings), 4), np.uint32)
    raw = V.view(np.uint8).reshape(-1, 16)
    data = bytearray()
    for i, s in enumerate(strings):
        V[i, 0] = len(s)
        if len(s) <= INLINE_MAX:
            raw[i, 4 : 4 + len(s)] = np.frombuffer(s, np.uint8) if s else []
        else:
            raw[i, 4:8] = np.frombuffer(s[:4], np.uint8)
            V[i, 2], V[i, 3] = 0, len(data)
            data += s
    return V, np.frombuffer(bytes(data) + b"\0" * 64, np.uint8).copy()


STRINGS = [b"", b"a", b"exatamente12", b"treze letras!", "São Paulo — 01310-100".encode(), b"x" * 100]


def test_decode_roundtrip():
    V, D = make_views(STRINGS)
    assert decode(V, D) == STRINGS


def test_decode_detects_bad_prefix():
    V, D = make_views([b"uma string longa"])
    V[0, 1] ^= 1
    with pytest.raises(ValueError, match="prefixo"):
        decode(V, D)


def test_used_bytes():
    V, _ = make_views(STRINGS)
    assert used_bytes(V) == sum(len(s) for s in STRINGS if len(s) > INLINE_MAX)
    assert used_bytes(make_views([b"curta"])[0]) == 0
    assert used_bytes(empty_views(0)) == 0


def test_trim_copies_only_when_worth_it():
    big = np.zeros(1_000_000, np.uint8)
    t = trim(big, 1000)
    assert len(t) == 1000
    assert t.base is None  # cópia: não segura o buffer grande
    small = np.zeros(70_000, np.uint8)
    t2 = trim(small, 60_000)
    assert len(t2) == 60_000
    assert t2.base is small  # fatia: copiar não compensaria
    with pytest.raises(ValueError, match="maior"):
        trim(small, 70_001)
